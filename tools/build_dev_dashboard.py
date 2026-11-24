#!/usr/bin/env python3
"""Generate the dev testing dashboard from the live entity registry.

One view per ATW unit, plus a single view comparing the ATA units' fan speeds.

`make dev-reset` restores `dev-config-template/.storage/`, so a dashboard only
survives a reset if it lives there. A static snapshot of a real install cannot:
entity IDs belong to Home Assistant and the user, built from device names and
areas, and for real devices those names are personal data which must not reach
the repo.

So the design is committed as this generator rather than as its output. It
groups entities by device from the registries and finds each one by its unique
ID, never by entity ID text, so it works whatever the IDs look like and keeps
working when a device share lapses or a building is renamed.

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
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEV_STORAGE = Path("dev-config/.storage")
DASHBOARD = "lovelace.melcloudhome_testing"
DOMAIN = "melcloudhome"

# Every water-temperature series the vendor defines. Graphed for every unit
# whose registry holds the entity, live or not: #266 stopped creating the ones
# for absent hardware, so on most units the suffixed four are orphaned registry
# entries. Graphing them anyway is deliberate - where a series stops is the
# discontinuity worth comparing against the MELCloud Home app's own charts.
# A series never registered for a unit has no entity ID to graph.
# Unique-ID suffixes (the sensor description keys).
WATER_TEMPS = (
    "flow_temperature",
    "return_temperature",
    "flow_temperature_zone1",
    "return_temperature_zone1",
    "flow_temperature_zone2",
    "return_temperature_zone2",
    "flow_temperature_boiler",
    "return_temperature_boiler",
)


@dataclass
class Unit:
    """One MELCloud unit's device, and its entities keyed by unique-ID suffix.

    A unique ID is the unit UUID plus `_<key>` (the ATA climate is the bare
    UUID, so its suffix is ""). `mock` comes from the config entry: the mock
    server's entry is created with debug_mode on.
    """

    name: str
    mock: bool
    entities: dict[str, str]

    def eid(self, suffix: str) -> str:
        return self.entities.get(suffix, f"sensor.missing{suffix}")

    @property
    def is_atw(self) -> bool:
        return "_tank" in self.entities

    @property
    def label(self) -> str:
        return f"{self.name} ({'mock' if self.mock else 'real'})"


def _load(storage: Path, name: str) -> Any:
    return json.loads((storage / name).read_text())["data"]


def find_units(storage: Path) -> list[Unit]:
    """Every unit device in the registry, mock or real, sorted by name.

    Device names are personal data for real units, so they are read here at
    runtime rather than written into this file. The account's service device
    (identifier = its config entry ID) isn't a unit and is skipped.
    """
    mock_entries = {
        entry["entry_id"]
        for entry in _load(storage, "core.config_entries")["entries"]
        if entry["domain"] == DOMAIN and entry["data"].get("debug_mode")
    }
    units: dict[str, tuple[str, Unit]] = {}
    for device in _load(storage, "core.device_registry")["devices"]:
        entry_ids = device.get("config_entries") or [device.get("config_entry_id")]
        for identifier in device["identifiers"]:  # not always pairs
            domain, unit_id = identifier[0], identifier[-1]
            if domain == DOMAIN and unit_id not in entry_ids:
                name = device.get("name_by_user") or device.get("name") or unit_id
                mock = any(e in mock_entries for e in entry_ids)
                units[device["id"]] = (unit_id, Unit(name, mock, {}))
    for entity in _load(storage, "core.entity_registry")["entities"]:
        if entity["platform"] == DOMAIN and entity.get("device_id") in units:
            unit_id, unit = units[entity["device_id"]]
            unit.entities[entity["unique_id"].removeprefix(unit_id)] = entity[
                "entity_id"
            ]
    return sorted((u for _, u in units.values()), key=lambda u: u.name)


def build_ata_fan_view(units: list[Unit]) -> dict[str, Any]:
    """One view comparing every ATA unit's actual fan speed against its mode.

    The sensor is a device_class=ENUM, so it has no long-term statistics and a
    statistics-graph cannot show it: history-graph renders the states as a
    timeline instead, which is the only way to see Auto modulating.

    Mock units carry a series too, derived rather than modulating, so a mock row
    reading `unknown` is a fault rather than a gap in the mock.
    """
    fans = [u.eid("_actual_fan_speed") for u in units]
    climates = [u.eid("") for u in units]
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
                    _heading("Changes as text, fan and mode interleaved"),
                    {
                        "type": "logbook",
                        "hours_to_show": 24,
                        "target": {"entity_id": fans + climates},
                        "grid_options": {"columns": "full"},
                    },
                    {
                        "type": "markdown",
                        "title": "Current",
                        # ATA units have no power switch entity: power is the
                        # climate entity's state, off versus a mode, and it is
                        # what explains an actual speed of off.
                        "content": "| unit | power / mode | requested | actual |"
                        "\n|---|---|---|---|\n"
                        + "\n".join(
                            f"| {u.label} "
                            f"| {{{{ states('{u.eid('')}') }}}} "
                            f"| {{{{ state_attr('{u.eid('')}', 'fan_mode') }}}} "
                            f"| {{{{ states('{u.eid('_actual_fan_speed')}') }}}} |"
                            for u in units
                        ),
                        "grid_options": {"columns": "full"},
                    },
                ],
            }
        ],
    }


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


def _provenance(unit: Unit) -> dict[str, Any]:
    """A table of each water temperature's value and its last_reading.

    A statistics graph cannot show an attribute, and last_reading is what
    separates a genuinely steady circuit from a feed that stopped (ADR-022).
    """
    rows = []
    for measure in WATER_TEMPS:
        entity = unit.eid(f"_{measure}")
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


def build_view(unit: Unit) -> dict[str, Any]:
    name = unit.label
    water = [unit.eid(f"_{m}") for m in WATER_TEMPS if f"_{m}" in unit.entities]

    live: list[dict[str, Any]] = [_heading(f"{name} - live")]
    zones = [z for z in ("_zone_1", "_zone_2") if z in unit.entities]
    live += [{"type": "tile", "entity": unit.eid(z)} for z in zones]
    live += [
        {"type": "tile", "entity": unit.eid(suffix)}
        for suffix in (
            "_tank",
            "_system_power",
            "_operation_status",
            "_forced_dhw_active",
            "_outdoor_temperature",
            "_tank_temperature",
        )
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
        _provenance(unit),
    ]

    energy = [
        _heading("Energy and diagnostics"),
        _stats(
            [unit.eid("_energy_consumed"), unit.eid("_energy_produced")],
            title="Energy (7d)",
            period="hour",
            stat_types=["sum"],
        ),
        _stats(
            [unit.eid("_cop")],
            title="COP (7d)",
            stat_types=["mean", "min", "max"],
        ),
        _stats(
            [unit.eid("_wifi_signal")],
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
        help="emit only mock-server units (debug_mode entry), safe to commit",
    )
    args = parser.parse_args()

    found = [u for u in find_units(args.storage) if u.mock or not args.mock_only]
    units = [u for u in found if u.is_atw]
    ata = [u for u in found if not u.is_atw]
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
                "views": [build_view(u) for u in units]
                + ([build_ata_fan_view(ata)] if ata else []),
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
    for unit in units:
        print(f"  {unit.label}{' [zone 2]' if '_zone_2' in unit.entities else ''}")
    if ata:
        print(f"  ATA fan speed [{len(ata)} unit(s)]")
    print("Restart HA to pick it up: make dev-restart")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
