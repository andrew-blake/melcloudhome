#!/usr/bin/env python3
"""
Long-running recorder for outdoor-temperature integrity investigations
(issues #152, #171 and the trendsummary synthetic-point bug). Every
--interval-minutes, polls:

  - trendsummary (period=Hourly, last --lookback-hours) for each ATA unit
  - trendsummary (period=Daily, same window) for each ATA unit
  - /context once, to read the first ATW unit's native OutdoorTemperature
    field (a control group: this field doesn't go through the trendsummary
    report endpoint at all, so if it ALSO shows query-time-echoed values, the
    echo behaviour is backend-wide rather than specific to trendsummary)
  - HA's currently-reported outdoor_temperature (state + last_reading
    attribute) and climate hvac_action/hvac_mode for each ATA unit, so the
    integration's view can be compared against what's actually available live.

Every returned datapoint (not just the latest) is appended to its CSV, tagged
with the poll time, so later analysis can check whether values for a given
upstream timestamp ever get revised in a later poll (real delayed backfill)
or stay fixed forever (pure query-time echo).

ATA units are discovered from /context; HA entity IDs are derived from the
unit UUIDs via the integration's entity-ID convention (docs/entities.md).

Usage:
    source .env && uv run tools/outdoor_temp_recorder.py --insecure
    uv run tools/outdoor_temp_recorder.py --insecure --interval-minutes 5 --duration-hours 24

Environment: MELCLOUD_USER, MELCLOUD_PASSWORD, HA_URL, HA_TOKEN (or HA_API_KEY).

Output CSVs (default diagnostics/outdoor-temp-recorder/, gitignored):
    {unit}_hourly.csv, {unit}_daily.csv, atw_control.csv, ha_state.csv
"""

import argparse
import asyncio
import csv
import json
import os
import re
import ssl
import sys
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "custom_components" / "melcloudhome"))
from api.client import MELCloudHomeClient  # noqa: E402
from api.const_shared import API_REPORT_TRENDSUMMARY  # noqa: E402


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def entity_suffix(unit_id: str) -> str:
    """UUID -> entity ID fragment per the integration's convention (docs/entities.md)."""
    parts = unit_id.split("-")
    return f"{parts[0][:4]}_{parts[-1][-4:]}"


def ha_ctx(insecure):
    ctx = ssl.create_default_context()
    if insecure:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


def ha_state(ha_url, token, entity_id, insecure):
    if not ha_url.startswith(("http://", "https://")):
        raise SystemExit(f"HA_URL must be http(s), got: {ha_url}")
    ctx = ha_ctx(insecure)
    req = urllib.request.Request(  # noqa: S310 - scheme validated above
        f"{ha_url}/api/states/{urllib.parse.quote(entity_id)}",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as r:  # noqa: S310
            return json.loads(r.read())
    except Exception as e:
        return {"state": None, "attributes": {}, "_error": str(e)}


def append_rows(path, fieldnames, rows):
    is_new = not path.exists()
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if is_new:
            w.writeheader()
        w.writerows(rows)


async def query_trendsummary(client, unit_id, period, lookback_hours):
    now = datetime.now(UTC)
    from_time = now - timedelta(hours=lookback_hours)
    params = {
        "unitId": unit_id,
        "period": period,
        "from": from_time.strftime("%Y-%m-%dT%H:%M:%S.0000000"),
        "to": now.strftime("%Y-%m-%dT%H:%M:%S.0000000"),
    }
    response = await client._api_request("GET", API_REPORT_TRENDSUMMARY, params=params)
    report = response[0] if isinstance(response, list) and response else response
    for ds in report.get("datasets", []) if isinstance(report, dict) else []:
        if "OUTDOOR_TEMPERATURE" in ds.get("label", ""):
            return ds.get("data", [])
    return []


def find_atw_control_value(context_raw):
    """Native OutdoorTemperature field on the first ATW unit (no trendsummary)."""
    try:
        for key in ("buildings", "guestBuildings"):
            for b in context_raw.get(key, []):
                for u in b.get("airToWaterUnits", []):
                    for s in u.get("settings", []):
                        if s.get("name") == "OutdoorTemperature":
                            return s.get("value")
    except Exception as e:
        print(f"  [warn] unexpected /context shape: {e}")
    return None


async def poll_once(client, units, out_dir, ha_url, ha_token, insecure, lookback_hours):
    poll_time = datetime.now(UTC).isoformat()

    # ATW control group via raw /context
    try:
        context_raw = await client._api_request("GET", "/context")
        atw_value = find_atw_control_value(context_raw)
    except Exception as e:
        atw_value = None
        print(f"  [warn] /context failed: {e}")
    append_rows(
        out_dir / "atw_control.csv",
        ["poll_time", "value"],
        [{"poll_time": poll_time, "value": atw_value}],
    )
    await asyncio.sleep(1)

    # ATA trendsummary, Hourly + Daily, per unit
    for label, unit_id in units.items():
        for period in ("Hourly", "Daily"):
            try:
                data = await query_trendsummary(client, unit_id, period, lookback_hours)
            except Exception as e:
                print(f"  [warn] {label} {period} failed: {e}")
                data = []
            rows = [
                {"poll_time": poll_time, "point_x": d.get("x"), "point_y": d.get("y")}
                for d in data
            ]
            append_rows(
                out_dir / f"{label}_{period.lower()}.csv",
                ["poll_time", "point_x", "point_y"],
                rows,
            )
            await asyncio.sleep(1)

    # HA's own currently-reported state per unit
    ha_rows = []
    for label, unit_id in units.items():
        suffix = entity_suffix(unit_id)
        sensor = ha_state(
            ha_url,
            ha_token,
            f"sensor.melcloudhome_{suffix}_outdoor_temperature",
            insecure,
        )
        climate = ha_state(ha_url, ha_token, f"climate.melcloudhome_{suffix}", insecure)
        ha_rows.append(
            {
                "poll_time": poll_time,
                "unit": label,
                "ha_outdoor_temp": sensor.get("state"),
                "ha_outdoor_temp_last_changed": sensor.get("last_changed"),
                # poll_time - ha_last_reading = the staleness the integration reports
                "ha_last_reading": sensor.get("attributes", {}).get("last_reading"),
                "hvac_mode": climate.get("state"),
                "hvac_action": climate.get("attributes", {}).get("hvac_action"),
            }
        )
    append_rows(
        out_dir / "ha_state.csv",
        [
            "poll_time",
            "unit",
            "ha_outdoor_temp",
            "ha_outdoor_temp_last_changed",
            "ha_last_reading",
            "hvac_mode",
            "hvac_action",
        ],
        ha_rows,
    )

    return poll_time


async def main():
    parser = argparse.ArgumentParser(
        description="Outdoor temperature integrity recorder"
    )
    parser.add_argument("--interval-minutes", type=float, default=5.0)
    parser.add_argument("--lookback-hours", type=float, default=24.0)
    parser.add_argument(
        "--duration-hours",
        type=float,
        default=None,
        help="Stop after this long (default: run until interrupted)",
    )
    parser.add_argument(
        "--units",
        default=None,
        help="Comma-separated unit-name substrings to record (default: all ATA units)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=REPO_ROOT / "diagnostics" / "outdoor-temp-recorder",
        help="CSV output directory (default: diagnostics/outdoor-temp-recorder/, gitignored)",
    )
    parser.add_argument("--insecure", action="store_true")
    args = parser.parse_args()

    ha_url = os.environ.get("HA_URL", "https://homeassistant.local:8123")
    ha_token = os.environ.get("HA_API_KEY") or os.environ.get("HA_TOKEN")
    if not ha_token:
        raise SystemExit("HA_API_KEY or HA_TOKEN not set")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    client = MELCloudHomeClient()
    await client.login(os.environ["MELCLOUD_USER"], os.environ["MELCLOUD_PASSWORD"])

    context = await client.get_user_context()
    wanted = [w.strip().lower() for w in args.units.split(",")] if args.units else None
    units = {}
    for building in context.buildings:
        for unit in building.air_to_air_units:
            if wanted and not any(w in unit.name.lower() for w in wanted):
                continue
            units[slugify(unit.name)] = unit.id
    if not units:
        raise SystemExit("No ATA units matched")
    print(f"Recording {len(units)} unit(s): {', '.join(units)} -> {args.out_dir}")

    start = datetime.now(UTC)
    deadline = (
        start + timedelta(hours=args.duration_hours)
        if args.duration_hours is not None
        else None
    )
    poll_num = 0

    try:
        while True:
            poll_num += 1
            try:
                poll_time = await poll_once(
                    client,
                    units,
                    args.out_dir,
                    ha_url,
                    ha_token,
                    args.insecure,
                    args.lookback_hours,
                )
                print(f"poll {poll_num} @ {poll_time} -> ok")
            except Exception as e:
                print(f"poll {poll_num} failed: {e}")
                # Re-login in case the session expired
                try:
                    await client.login(
                        os.environ["MELCLOUD_USER"], os.environ["MELCLOUD_PASSWORD"]
                    )
                except Exception as e2:
                    print(f"  re-login also failed: {e2}")

            if deadline and datetime.now(UTC) >= deadline:
                print("Duration reached, stopping.")
                break
            await asyncio.sleep(args.interval_minutes * 60)
    except KeyboardInterrupt:
        print("Interrupted, stopping.")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
