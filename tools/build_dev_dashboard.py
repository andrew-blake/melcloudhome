#!/usr/bin/env python3
"""Generate the dev testing dashboard from the live entity registry.

One view per ATW unit, plus a single view comparing the ATA units' fan speeds.

`make dev-reset` restores `dev-config-template/.storage/`, so a dashboard only
survives a reset if it lives there. A static snapshot cannot: entity IDs carry
the building name as a prefix (`<building>_melcloudhome_<id>_<measure>`), and
for real devices that name is personal data which must not reach the repo.

So the design is committed as this generator rather than as its output. It reads
whatever ATW units the registry holds and emits cards for them, which also means
it keeps working when a device share lapses or a building is renamed.

    # write the live dashboard for every unit found
    python3 tools/build_dev_dashboard.py

    # refresh the committed template with the mock units only
    python3 tools/build_dev_dashboard.py --mock-only \
        --out dev-config-template/.storage/lovelace.melcloudhome_testing

Restart HA afterwards (`make dev-restart`) - lovelace configs are read at
startup.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

DEV_STORAGE = Path("dev-config/.storage")
DASHBOARD = "lovelace.melcloudhome_testing"

# The mock server's two building names (tools/mock_melcloud_server.py, "My Home"
# and "Shared Building"), which are synthetic and safe to commit. Keep this list
# matching the mock, and add nothing else to it: every other building name comes
# from a real MELCloud account, and one of them is a street address. An
# unrecognised building is treated as real and excluded by --mock-only, so the
# failure mode of a stale list is a missing view rather than a leak.
MOCK_BUILDINGS = ("my_home", "shared_building")

# Every water-temperature series the vendor defines. Listed in full for every
# unit whether or not the entity still exists: #266 stopped creating the ones
# for absent hardware, so on most units the suffixed four are orphaned registry
# entries. Graphing them anyway is deliberate - where a series stops is the
# discontinuity worth comparing against the MELCloud Home app's own charts.
WATER_TEMPS = (
    "flow_temperature",
    "return_temperature",
    "flow_temperature_zone_1",
    "return_temperature_zone_1",
    "flow_temperature_zone_2",
    "return_temperature_zone_2",
    "flow_temperature_boiler",
    "return_temperature_boiler",
)

ENTITY_RE = re.compile(r"^[a-z_]+\.(.+_melcloudhome_[0-9a-f]{4}_[0-9a-f]{4})_")


def find_atw_units(storage: Path) -> list[tuple[str, bool]]:
    """Return (entity_id_prefix, has_zone2) for each ATW unit in the registry.

    An ATW unit is identified by its water heater; zone 2 by a second climate
    entity. Both are capability-gated at creation (#266), so the registry is
    the honest source for what a unit actually has.
    """
    registry = json.loads((storage / "core.entity_registry").read_text())
    prefixes: set[str] = set()
    entity_ids: set[str] = set()
    for entry in registry["data"]["entities"]:
        entity_id = entry["entity_id"]
        entity_ids.add(entity_id)
        match = ENTITY_RE.match(entity_id)
        if match:
            prefixes.add(match.group(1))

    units = []
    for prefix in sorted(prefixes):
        if f"water_heater.{prefix}_tank" not in entity_ids:
            continue  # ATA unit
        units.append((prefix, f"climate.{prefix}_zone_2" in entity_ids))
    return units


def find_ata_units(storage: Path) -> list[str]:
    """Return the entity_id prefix of each ATA unit in the registry.

    An ATA unit is the inverse of find_atw_units' test: a climate entity with
    no water heater beside it. Reading the registry rather than assuming keeps
    this correct when a shared unit disappears.
    """
    registry = json.loads((storage / "core.entity_registry").read_text())
    entity_ids = {entry["entity_id"] for entry in registry["data"]["entities"]}
    prefixes = {
        match.group(1)
        for entity_id in entity_ids
        if (match := ENTITY_RE.match(entity_id))
    }
    return sorted(
        prefix
        for prefix in prefixes
        if f"climate.{prefix}_climate" in entity_ids
        and f"water_heater.{prefix}_tank" not in entity_ids
    )


def build_ata_fan_view(prefixes: list[str], names: dict[str, str]) -> dict[str, Any]:
    """One view comparing every ATA unit's actual fan speed against its mode.

    The sensor is a device_class=ENUM, so it has no long-term statistics and a
    statistics-graph cannot show it: history-graph renders the states as a
    timeline instead, which is the only way to see Auto modulating. The mock
    server does not emit ActualFanSpeed, so mock units read `unknown` here and
    only the real-API entry's units show a series.
    """
    fans = [f"sensor.{prefix}_actual_fan_speed" for prefix in prefixes]
    climates = [f"climate.{prefix}_climate" for prefix in prefixes]
    return {
        "type": "sections",
        "max_columns": 4,
        "title": "ATA fan speed",
        "path": "ata-fan",
        "sections": [
            {
                "type": "grid",
                # Full width: these are wide time series read side by side, and
                # the default two-column grid squeezes them unreadably.
                "column_span": 4,
                "cards": [
                    _heading("Actual fan speed"),
                    {
                        "type": "history-graph",
                        "hours_to_show": 24,
                        "title": "Actual fan speed (24h) - never Auto, Off means powered down",
                        "entities": fans,
                        "grid_options": {"columns": "full", "rows": "auto"},
                    },
                    _heading("Requested mode, for correlation"),
                    {
                        # fan_mode is a climate attribute, which history-graph
                        # cannot plot, so this shows hvac state only. Comparing
                        # requested against actual needs a template sensor.
                        "type": "history-graph",
                        "hours_to_show": 24,
                        "title": "Power and HVAC mode (24h)",
                        "entities": climates,
                        "grid_options": {"columns": "full"},
                    },
                    _heading("Changes as text"),
                    {
                        "type": "logbook",
                        "hours_to_show": 24,
                        "target": {"entity_id": fans},
                        "grid_options": {"columns": "full"},
                    },
                    {
                        "type": "markdown",
                        "title": "Current",
                        "content": "| unit | requested | actual |\n|---|---|---|\n"
                        + "\n".join(
                            f"| {label(prefix, names)} "
                            f"| {{{{ state_attr('climate.{prefix}_climate', 'fan_mode') }}}} "
                            f"| {{{{ states('sensor.{prefix}_actual_fan_speed') }}}} |"
                            for prefix in prefixes
                        ),
                        "grid_options": {"columns": "full"},
                    },
                ],
            }
        ],
    }


def device_names(storage: Path) -> dict[str, str]:
    """Map entity-id prefix -> the device's display name, read at runtime.

    Device names are personal data for real units, so they are looked up from
    the local registry rather than written into this file.

    Joined entity -> device_id -> device rather than matched on the entity id's
    `<uuid first 4>_<uuid last 4>` short form, because that short form is NOT
    unique: the mock unit `bf8d5678-...-456789ab5119` and the real
    `bf8d1e84-...-25b87a945119` both render `bf8d_5119`, and matching on it gave
    the mock unit the real device's name. The entity registry's device_id is
    exact.
    """
    devices = json.loads((storage / "core.device_registry").read_text())
    by_id = {
        device["id"]: (device.get("name_by_user") or device.get("name") or "")
        for device in devices["data"]["devices"]
    }
    entities = json.loads((storage / "core.entity_registry").read_text())
    names: dict[str, str] = {}
    for entry in entities["data"]["entities"]:
        match = ENTITY_RE.match(entry["entity_id"])
        name = by_id.get(entry.get("device_id") or "")
        if match and name:
            names[match.group(1)] = name
    return names


def label(prefix: str, names: dict[str, str]) -> str:
    """A human view title, preferring the device's own name."""
    kind = "mock" if prefix.startswith(MOCK_BUILDINGS) else "real"
    name = names.get(prefix)
    if name:
        return f"{name} ({kind})"
    building, _, short = prefix.partition("_melcloudhome_")
    return f"{building.replace('_', ' ').title()} {short} ({kind})"


def _heading(text: str) -> dict[str, Any]:
    return {"type": "heading", "heading": text, "heading_style": "title"}


def _stats(
    entities: list[str],
    *,
    title: str,
    period: str = "5minute",
    stat_types: list[str] | None = None,
    days: int = 7,
) -> dict[str, Any]:
    return {
        "type": "statistics-graph",
        "chart_type": "line",
        "period": period,
        "entities": entities,
        "stat_types": stat_types or ["mean"],
        "days_to_show": days,
        "title": title,
        "grid_options": {"columns": "full"},
    }


def _provenance(prefix: str) -> dict[str, Any]:
    """A table of each water temperature's value and its last_reading.

    A statistics graph cannot show an attribute, and last_reading is what
    separates a genuinely steady circuit from a feed that stopped (ADR-022).
    """
    rows = []
    for measure in WATER_TEMPS:
        entity = f"sensor.{prefix}_{measure}"
        rows.append(
            f"| {measure.replace('_', ' ')} "
            f"| {{{{ states('{entity}') }}}} "
            f"| {{{{ state_attr('{entity}', 'last_reading') or '-' }}}} |"
        )
    return {
        "type": "markdown",
        "title": "Reading provenance",
        "content": "| measure | value | last_reading |\n|---|---|---|\n"
        + "\n".join(rows),
        "grid_options": {"columns": "full"},
    }


def build_view(prefix: str, has_zone2: bool, names: dict[str, str]) -> dict[str, Any]:
    name = label(prefix, names)
    water = [f"sensor.{prefix}_{m}" for m in WATER_TEMPS]

    live: list[dict[str, Any]] = [_heading(f"{name} - live")]
    live.append({"type": "tile", "entity": f"climate.{prefix}_zone_1"})
    if has_zone2:
        live.append({"type": "tile", "entity": f"climate.{prefix}_zone_2"})
    live += [
        {"type": "tile", "entity": f"water_heater.{prefix}_tank"},
        {"type": "tile", "entity": f"switch.{prefix}_system_power"},
        {"type": "tile", "entity": f"sensor.{prefix}_operation_status"},
        {"type": "tile", "entity": f"binary_sensor.{prefix}_forced_dhw_active"},
        {"type": "tile", "entity": f"sensor.{prefix}_outdoor_temperature"},
        {"type": "tile", "entity": f"sensor.{prefix}_tank_temperature"},
    ]

    temps = [
        _heading("Water temperatures"),
        _stats(
            water,
            title="All water temperatures (7d mean) - includes series no longer reported",
        ),
        {
            # Raw states, because statistics hide the distinction this change
            # introduced: a missing reading is a gap here, not a flat line.
            "type": "history-graph",
            "hours_to_show": 24,
            "title": "Raw states (24h) - gaps are unknown, not a steady value",
            "entities": water,
            "grid_options": {"columns": "full"},
        },
        _provenance(prefix),
    ]

    energy = [
        _heading("Energy and diagnostics"),
        _stats(
            [
                f"sensor.{prefix}_energy_consumed",
                f"sensor.{prefix}_energy_produced",
            ],
            title="Energy (7d)",
            period="hour",
            stat_types=["sum"],
        ),
        _stats(
            [f"sensor.{prefix}_coefficient_of_performance"],
            title="COP (7d)",
            stat_types=["mean", "min", "max"],
        ),
        _stats(
            [f"sensor.{prefix}_wifi_signal"],
            title="WiFi signal (7d)",
            period="hour",
        ),
    ]

    return {
        "type": "sections",
        "max_columns": 4,
        "title": name,
        "sections": [
            {"type": "grid", "cards": live},
            {"type": "grid", "cards": temps},
            {"type": "grid", "cards": energy},
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--storage",
        type=Path,
        default=DEV_STORAGE,
        help="HA .storage directory to read the registry from",
    )
    parser.add_argument(
        "--out",
        type=Path,
        help=f"output file (default: <storage>/{DASHBOARD})",
    )
    parser.add_argument(
        "--mock-only",
        action="store_true",
        help="emit only mock-server units, so the output is safe to commit",
    )
    args = parser.parse_args()

    units = find_atw_units(args.storage)
    ata = find_ata_units(args.storage)
    names = device_names(args.storage)
    if args.mock_only:
        units = [u for u in units if u[0].startswith(MOCK_BUILDINGS)]
        ata = [p for p in ata if p.startswith(MOCK_BUILDINGS)]
    if not units and not ata:
        print("No units found - is the integration configured?")
        return 1

    out = args.out or args.storage / DASHBOARD
    envelope: dict[str, Any] = {
        "version": 1,
        "minor_version": 1,
        "key": DASHBOARD,
        "data": {
            "config": {
                "views": [build_view(p, z, names) for p, z in units]
                + ([build_ata_fan_view(ata, names)] if ata else []),
            }
        },
    }
    if out.exists():
        # Keep whatever version/minor_version HA is writing today
        existing = json.loads(out.read_text())
        existing["data"]["config"] = envelope["data"]["config"]
        envelope = existing

    out.write_text(json.dumps(envelope, indent=1) + "\n")
    total = len(units) + (1 if ata else 0)
    print(f"Wrote {out} with {total} view(s):")
    for prefix, has_zone2 in units:
        print(f"  {label(prefix, names)}{' [zone 2]' if has_zone2 else ''}")
    if ata:
        print(f"  ATA fan speed [{len(ata)} unit(s)]")
    print("Restart HA to pick it up: make dev-restart")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
