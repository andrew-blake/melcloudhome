#!/usr/bin/env python3
"""Scan Home Assistant's Long-Term Statistics for corrupt energy jumps.

Background: the MELCloud cloud API has occasionally returned a corrupt
hourly energy value of ~6,553,600 Wh (~6553.6 kWh) for one hour, consistent
with a 16-bit counter wrap (65536 * 100 Wh). Before this was caught by a
sanity check in the integration (see GitHub issue #161), a value like that
could get written straight into a total_increasing energy sensor's history,
permanently distorting the Energy Dashboard for that day.

Upgrading the integration stops new occurrences and self-heals its own
internal running total, but Home Assistant's Long-Term Statistics (what the
Energy Dashboard's history graph actually reads) are recorded separately by
HA core and are NOT touched by the integration. Any spike already baked into
your statistics history needs a one-time manual fix via Developer Tools ->
Statistics -> (find the entity) -> Adjust a statistic.

This script only finds the bad points for you - it never writes anything.
It works against any recorder backend (SQLite/MySQL/Postgres) because it
goes through Home Assistant's WebSocket API, the same one the frontend's
History and Energy Dashboard pages use, authenticated with a normal
long-lived access token - no database credentials needed.

Prerequisites:
    A Home Assistant long-lived access token (Profile -> Security ->
    Long-Lived Access Tokens -> Create Token).

Usage:
    export HA_URL=https://homeassistant.local:8123
    export HA_TOKEN=your_long_lived_token_here
    uv run tools/find_corrupt_energy_readings.py
    uv run tools/find_corrupt_energy_readings.py --days 1095 --threshold-kwh 50
    uv run tools/find_corrupt_energy_readings.py --entity sensor.melcloudhome_0efc_76db_energy
    uv run tools/find_corrupt_energy_readings.py --insecure --csv bad_points.csv

Note: uses recorder/list_statistic_ids and recorder/statistics_during_period,
the same internal WebSocket commands the frontend uses. These aren't part of
HA's stable public API and could change shape between versions; this script
fails loudly rather than guessing if a response doesn't look as expected.
"""

from __future__ import annotations

import argparse
import asyncio
import csv as csv_module
import os
import sys
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from pathlib import Path
from typing import Any

import aiohttp

DEFAULT_THRESHOLD_KWH = 100.0
# Signature of the known root cause (65536 * 100 Wh). Deltas within this
# tolerance of the signature are called out specifically as high-confidence
# matches for the counter-wrap bug, rather than some other kind of outlier.
KNOWN_SIGNATURE_KWH = 6553.6
KNOWN_SIGNATURE_TOLERANCE_KWH = 5.0
# A jump spanning a multi-hour gap can be legitimate accumulation, but only
# up to a physically sane rate - no single residential ATA/ATW unit sustains
# continuous draw/output anywhere near this, even generously accounting for
# large multi-split systems. Above this, a gap doesn't excuse the jump.
MAX_PLAUSIBLE_CONTINUOUS_KW = 30.0


class HaWebSocketClient:
    """Minimal client for the subset of the HA WebSocket API this script needs."""

    def __init__(self, session: aiohttp.ClientSession, ws_url: str, token: str) -> None:
        self._session = session
        self._ws_url = ws_url
        self._token = token
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._next_id = 1

    async def connect(self) -> None:
        ws = await self._session.ws_connect(self._ws_url)
        self._ws = ws

        hello = await ws.receive_json()
        if hello.get("type") != "auth_required":
            raise RuntimeError(f"Unexpected handshake message: {hello}")

        await ws.send_json({"type": "auth", "access_token": self._token})
        auth_result = await ws.receive_json()
        if auth_result.get("type") != "auth_ok":
            raise RuntimeError(
                f"Authentication failed: {auth_result.get('message', auth_result)}"
            )

    async def command(self, payload: dict[str, Any]) -> Any:
        if self._ws is None:
            raise RuntimeError("call connect() first")
        message_id = self._next_id
        self._next_id += 1
        await self._ws.send_json({"id": message_id, **payload})

        while True:
            response = await self._ws.receive_json()
            if response.get("id") != message_id:
                continue
            if not response.get("success", False):
                error = response.get("error", {})
                raise RuntimeError(
                    f"{payload.get('type')} failed: "
                    f"{error.get('code', '?')}: {error.get('message', response)}"
                )
            return response.get("result", {})

    async def close(self) -> None:
        if self._ws is not None:
            await self._ws.close()


def _to_datetime(value: Any) -> datetime | None:
    """Parse a statistics 'start' field - can be epoch ms (number) or ISO string."""
    if value is None:
        return None
    if isinstance(value, int | float):
        return datetime.fromtimestamp(value / 1000, tz=UTC)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


async def discover_energy_statistic_ids(
    client: HaWebSocketClient, prefix: str | None
) -> list[str]:
    """Find sum-type (cumulative) statistic_ids, optionally filtered by prefix."""
    result = await client.command({"type": "recorder/list_statistic_ids"})
    entries: list[dict[str, Any]] = result if isinstance(result, list) else []
    ids = [
        entry["statistic_id"]
        for entry in entries
        if entry.get("has_sum") and entry.get("statistic_id")
    ]
    if prefix:
        ids = [sid for sid in ids if sid.startswith(prefix)]
    return sorted(ids)


async def fetch_hourly_sums(
    client: HaWebSocketClient, statistic_id: str, start: datetime, end: datetime
) -> list[tuple[datetime, float]]:
    """Fetch (timestamp, sum) pairs for one statistic_id over the given window."""
    result = await client.command(
        {
            "type": "recorder/statistics_during_period",
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
            "statistic_ids": [statistic_id],
            "period": "hour",
            "types": ["sum"],
        }
    )
    rows = result.get(statistic_id, []) if isinstance(result, dict) else []
    points = []
    for row in rows:
        ts = _to_datetime(row.get("start"))
        value = row.get("sum")
        if ts is not None and value is not None:
            points.append((ts, float(value)))
    points.sort(key=lambda p: p[0])
    return points


def find_suspicious_jumps(
    points: list[tuple[datetime, float]], threshold_kwh: float
) -> list[dict]:
    """Flag consecutive points whose sum increased by more than threshold_kwh."""
    flagged = []
    for (prev_ts, prev_sum), (ts, value) in pairwise(points):
        delta = value - prev_sum
        if delta <= threshold_kwh:
            continue
        gap_hours = (ts - prev_ts).total_seconds() / 3600
        implied_kw = delta / gap_hours if gap_hours > 0 else float("inf")
        signature_match = (
            abs(delta - KNOWN_SIGNATURE_KWH) <= KNOWN_SIGNATURE_TOLERANCE_KWH
        )
        flagged.append(
            {
                "timestamp": ts,
                "previous_timestamp": prev_ts,
                "previous_sum": prev_sum,
                "sum": value,
                "delta_kwh": delta,
                "gap_hours": gap_hours,
                "implied_kw": implied_kw,
                "signature_match": signature_match,
            }
        )
    return flagged


def print_report(statistic_id: str, flagged: list[dict]) -> None:
    if not flagged:
        print(f"  OK - no jumps above threshold for {statistic_id}")
        return

    print(f"  {len(flagged)} suspicious jump(s) for {statistic_id}:")
    for item in flagged:
        if item["signature_match"]:
            note = " <- matches known ~6553.6 kWh counter-wrap signature"
        elif item["implied_kw"] > MAX_PLAUSIBLE_CONTINUOUS_KW:
            note = (
                f" <- implausible even accounting for the "
                f"{item['gap_hours']:.1f}h gap (~{item['implied_kw']:.0f} kW "
                "implied continuous average - no residential unit sustains "
                "this)"
            )
        elif item["gap_hours"] > 1.5:
            note = (
                f" <- spans a {item['gap_hours']:.1f}h gap "
                f"(~{item['implied_kw']:.1f} kW implied average - plausible "
                "legitimate accumulation, verify before adjusting)"
            )
        else:
            note = ""
        print(
            f"    {item['previous_timestamp'].isoformat()} -> "
            f"{item['timestamp'].isoformat()}: "
            f"{item['previous_sum']:.3f} -> {item['sum']:.3f} kWh "
            f"(+{item['delta_kwh']:.1f} kWh){note}"
        )


async def run(args: argparse.Namespace) -> int:
    ha_url = os.environ.get("HA_URL")
    token = os.environ.get("HA_TOKEN")
    if not ha_url or not token:
        print("HA_URL and HA_TOKEN must be set (see script docstring)", file=sys.stderr)
        return 1

    ws_url = (
        ha_url.rstrip("/").replace("https://", "wss://").replace("http://", "ws://")
        + "/api/websocket"
    )

    connector = aiohttp.TCPConnector(ssl=False) if args.insecure else None

    end = datetime.now(UTC)
    start = end - timedelta(days=args.days)

    async with aiohttp.ClientSession(connector=connector) as session:
        client = HaWebSocketClient(session, ws_url, token)
        try:
            await client.connect()
        except Exception as err:
            print(f"Failed to connect/authenticate to {ws_url}: {err}", file=sys.stderr)
            return 1

        try:
            if args.entity:
                statistic_ids = args.entity
            else:
                prefix = None if args.all else "sensor.melcloudhome_"
                statistic_ids = await discover_energy_statistic_ids(client, prefix)

            if not statistic_ids:
                print("No matching cumulative (sum-type) statistics found.")
                return 0

            print(
                f"Scanning {len(statistic_ids)} statistic(s) from "
                f"{start.date()} to {end.date()} "
                f"(threshold: +{args.threshold_kwh:.0f} kWh/hour)...\n"
            )

            all_flagged: list[tuple[str, dict]] = []
            for statistic_id in statistic_ids:
                points = await fetch_hourly_sums(client, statistic_id, start, end)
                flagged = find_suspicious_jumps(points, args.threshold_kwh)
                print_report(statistic_id, flagged)
                all_flagged.extend((statistic_id, item) for item in flagged)

            if args.csv:
                csv_path = Path(args.csv)
                csv_path.parent.mkdir(parents=True, exist_ok=True)
                with open(csv_path, "w", newline="") as f:
                    writer = csv_module.writer(f)
                    writer.writerow(
                        [
                            "statistic_id",
                            "previous_timestamp",
                            "timestamp",
                            "gap_hours",
                            "implied_kw",
                            "previous_sum_kwh",
                            "sum_kwh",
                            "delta_kwh",
                            "matches_known_signature",
                            "implausible_even_with_gap",
                        ]
                    )
                    for statistic_id, item in all_flagged:
                        writer.writerow(
                            [
                                statistic_id,
                                item["previous_timestamp"].isoformat(),
                                item["timestamp"].isoformat(),
                                round(item["gap_hours"], 2),
                                round(item["implied_kw"], 2),
                                round(item["previous_sum"], 3),
                                round(item["sum"], 3),
                                round(item["delta_kwh"], 3),
                                item["signature_match"],
                                item["implied_kw"] > MAX_PLAUSIBLE_CONTINUOUS_KW,
                            ]
                        )
                print(f"\nWrote {len(all_flagged)} row(s) to {args.csv}")

            if all_flagged:
                print(
                    "\nThis script is read-only. To fix a flagged point:\n"
                    "  Developer Tools -> Statistics -> search for the entity ->\n"
                    "  click the entity -> 'Adjust a statistic' -> pick the "
                    "timestamp above and correct or zero out the value."
                )
            return 0
        finally:
            await client.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find corrupt (implausibly large) hourly jumps in Home "
        "Assistant Long-Term Statistics for cumulative energy sensors."
    )
    parser.add_argument(
        "--days", type=int, default=730, help="Lookback window in days (default: 730)"
    )
    parser.add_argument(
        "--threshold-kwh",
        type=float,
        default=DEFAULT_THRESHOLD_KWH,
        help=f"Flag single-hour jumps above this many kWh (default: {DEFAULT_THRESHOLD_KWH})",
    )
    parser.add_argument(
        "--entity",
        action="append",
        help="Specific statistic_id to check (repeatable). Default: "
        "auto-discover sensor.melcloudhome_* cumulative sensors.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Scan all cumulative (sum-type) statistics, not just melcloudhome ones.",
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Skip TLS certificate verification (self-signed local certs).",
    )
    parser.add_argument("--csv", help="Optional path to write flagged points as CSV.")
    args = parser.parse_args()

    try:
        exit_code = asyncio.run(run(args))
    except KeyboardInterrupt:
        exit_code = 130
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
