#!/usr/bin/env python3
"""Energy API monitoring recorder.

Records full API responses at regular intervals to characterize API behavior:
- How quickly data becomes available
- How values change over time within an hour
- When hours transition from partial to complete

Each poll records, per unit:
- the telemetry energy endpoint over the integration's own request window
  (ATA: consumed; ATW: consumed and produced)
- ATW only: the same telemetry request with "to" at the next hour boundary
- ATW only: /report/v1/combined-energy over the unit's local day, the
  report the MELCloud Home web app draws its energy chart from (issue #333)

Usage:
    # Start new recording session
    python energy_monitoring_recorder.py

    # Resume existing session (appends to the JSON Lines log file)
    python energy_monitoring_recorder.py --resume

    # Custom interval (default 10 minutes)
    python energy_monitoring_recorder.py --interval 5

    # Custom duration (default 2 hours = 120 minutes)
    python energy_monitoring_recorder.py --duration 180

    # Focus on specific unit
    python energy_monitoring_recorder.py --unit-id aaaaaaaa-aaaa-aaaa-aaaa-4c6fd61ac825

    # Inside a Home Assistant image: read credentials from the config entry
    python energy_monitoring_recorder.py --ha-config /config/.storage/core.config_entries

Environment:
    MELCLOUD_USER - MELCloud email
    MELCLOUD_PASSWORD - MELCloud password
"""

import asyncio
import json
import os
import sys
from argparse import ArgumentParser
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

# Add parent directory to path to import the API client
sys.path.insert(0, str(Path(__file__).parent.parent))

from custom_components.melcloudhome.api.client import MELCloudHomeClient
from custom_components.melcloudhome.api.exceptions import AuthenticationError
from custom_components.melcloudhome.const import DATA_LOOKBACK_HOURS_ENERGY

REPORT_TIME_FORMAT = "%Y-%m-%dT%H:%M:%S.0000000Z"


def energy_window(now: datetime) -> tuple[datetime, datetime]:
    """Mirror EnergyTrackerBase._energy_window, which imports Home Assistant."""
    from_time = (now - timedelta(hours=DATA_LOOKBACK_HOURS_ENERGY)).replace(
        minute=0, second=0, microsecond=0
    )
    return from_time, now


def local_day(now: datetime, time_zone: str | None) -> tuple[datetime, datetime]:
    """Return the unit's current local day as UTC bounds, as the web app asks."""
    tz = ZoneInfo(time_zone or "UTC")
    midnight = now.astimezone(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight.astimezone(UTC), (midnight + timedelta(days=1)).astimezone(UTC)


def summarize(endpoint: str, data: Any) -> str:
    """One-line summary of the newest value in a response."""
    if endpoint == "combined-energy":
        points = [
            f"{d['id'].removeprefix('interval_energy_')} "
            f"{d['data'][-1]['x'][11:16]}(local)={d['data'][-1]['y']:.3f}"
            for d in (data or [{}])[0].get("datasets", [])
            if d["id"].startswith("interval_energy_") and d["data"]
        ]
        return "✓ " + ", ".join(points) if points else "✓ No values"
    if data and data.get("measureData"):
        values = data["measureData"][0].get("values", [])
        if values:
            latest = values[-1]
            return f"✓ {len(values)} hour(s), latest: {latest['time'][:16]} = {latest['value']}"
        return "✓ No values"
    return "✓ No data (304 or empty)"


class EnergyRecorder:
    """Records energy API responses over time."""

    def __init__(
        self,
        log_file: Path,
        interval_minutes: int = 10,
        duration_minutes: int = 120,
        unit_filter: str | None = None,
        resume: bool = False,
    ):
        """Initialize recorder.

        Args:
            log_file: Path to JSON Lines log file
            interval_minutes: Minutes between polls
            duration_minutes: Total recording duration in minutes
            unit_filter: Optional unit ID to focus on (records all if None)
            resume: If True, append to existing log file
        """
        self.log_file = log_file
        self.interval = timedelta(minutes=interval_minutes)
        self.duration = timedelta(minutes=duration_minutes)
        self.unit_filter = unit_filter
        self.resume = resume

        # JSON Lines: one entry per line, appended as it is recorded, so a
        # crash can only lose a partial last line, never the whole recording.
        self.entry_count = 0
        if resume and log_file.exists():
            with open(log_file) as f:
                self.entry_count = sum(1 for _ in f)
            print(f"📂 Resuming from existing log with {self.entry_count} entries")
        else:
            log_file.write_text("")

    async def record_session(self, email: str, password: str) -> None:
        """Run recording session.

        Args:
            email: MELCloud email
            password: MELCloud password
        """
        start_time = datetime.now(UTC)
        end_time = start_time + self.duration
        poll_count = 0

        print("=" * 80)
        print("Energy API Monitoring Recorder")
        print("=" * 80)
        print(f"Start time:     {start_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print(f"End time:       {end_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print(f"Poll interval:  {self.interval.total_seconds() / 60:.0f} minutes")
        print(f"Log file:       {self.log_file}")
        if self.unit_filter:
            print(f"Unit filter:    {self.unit_filter}")
        print("=" * 80)

        client = MELCloudHomeClient()
        try:
            # Login
            print(f"\n🔐 Logging in as {email}...")
            await client.login(email, password)
            print("✓ Login successful\n")

            # Get user context to find devices
            context = await client.get_user_context()
            units: list[dict[str, Any]] = []
            for building in context.buildings:
                building_units = [
                    ("ata", u)
                    for u in building.air_to_air_units
                    if u.capabilities.has_energy_consumed_meter
                ] + [("atw", u) for u in building.air_to_water_units]
                for unit_type, unit in building_units:
                    if not self.unit_filter or unit.id == self.unit_filter:
                        units.append(
                            {
                                "id": unit.id,
                                "name": unit.name,
                                "building": building.name,
                                "type": unit_type,
                                "time_zone": unit.time_zone,
                            }
                        )

            if not units:
                print("❌ No energy-capable units found")
                if self.unit_filter:
                    print(f"   Filter: {self.unit_filter}")
                return

            print(f"📊 Monitoring {len(units)} unit(s):")
            for unit_info in units:
                print(
                    f"   • {unit_info['name']} ({unit_info['building']}, "
                    f"{unit_info['type'].upper()}) - {unit_info['id']}"
                )

            # Recording loop
            while datetime.now(UTC) < end_time:
                poll_count += 1
                poll_time = datetime.now(UTC)

                print(f"\n🔍 Poll #{poll_count} at {poll_time.strftime('%H:%M:%S')}")

                for unit_info in units:
                    for endpoint, measure, from_time, to_time in self._requests(
                        unit_info, poll_time
                    ):
                        await self._record(
                            client,
                            email,
                            password,
                            poll_time,
                            poll_count,
                            unit_info,
                            endpoint,
                            measure,
                            from_time,
                            to_time,
                        )

                # Calculate next poll time
                next_poll = poll_time + self.interval
                if next_poll >= end_time:
                    break

                # Wait until next poll
                wait_seconds = (next_poll - datetime.now(UTC)).total_seconds()
                if wait_seconds > 0:
                    print(
                        f"   💤 Waiting {wait_seconds:.0f}s until next poll at {next_poll.strftime('%H:%M:%S')}"
                    )
                    await asyncio.sleep(wait_seconds)

            print("\n" + "=" * 80)
            print("✓ Recording complete")
            print(f"  Total polls: {poll_count}")
            print(f"  Total entries: {self.entry_count}")
            print(f"  Log file: {self.log_file}")
            print("=" * 80)

        finally:
            await client.close()

    @staticmethod
    def _requests(
        unit_info: dict[str, Any], poll_time: datetime
    ) -> list[tuple[str, str, datetime, datetime]]:
        """List the (endpoint, measure, from, to) requests for one unit."""
        from_time, to_time = energy_window(poll_time)
        if unit_info["type"] == "ata":
            return [("telemetry", "consumed", from_time, to_time)]
        # combined-energy is ATW-only: ATA units get HTTP 500 (2026-09-23)
        day_from, day_to = local_day(poll_time, unit_info["time_zone"])
        # Same window but "to" at the next hour boundary, fetched right after
        # its to=now pair: does to=now hold back the in-progress hour? (#333)
        next_hour = poll_time.replace(minute=0, second=0, microsecond=0) + timedelta(
            hours=1
        )
        return [
            ("telemetry", "consumed", from_time, to_time),
            ("telemetry-next-hour", "consumed", from_time, next_hour),
            ("telemetry", "produced", from_time, to_time),
            ("telemetry-next-hour", "produced", from_time, next_hour),
            ("combined-energy", "both", day_from, day_to),
        ]

    async def _fetch(
        self,
        client: MELCloudHomeClient,
        unit_info: dict[str, Any],
        endpoint: str,
        measure: str,
        from_time: datetime,
        to_time: datetime,
    ) -> Any:
        """Issue one request."""
        if endpoint == "combined-energy":
            return await client._api_request(
                "GET",
                "/report/v1/combined-energy",
                params={
                    "unitId": unit_info["id"],
                    "period": "Daily",
                    "from": from_time.strftime(REPORT_TIME_FORMAT),
                    "to": to_time.strftime(REPORT_TIME_FORMAT),
                },
            )
        if unit_info["type"] == "atw":
            fetch = getattr(client.atw, f"get_energy_{measure}")
            return await fetch(unit_info["id"], from_time, to_time, "Hour")
        return await client.get_energy_data(unit_info["id"], from_time, to_time, "Hour")

    async def _record(
        self,
        client: MELCloudHomeClient,
        email: str,
        password: str,
        poll_time: datetime,
        poll_count: int,
        unit_info: dict[str, Any],
        endpoint: str,
        measure: str,
        from_time: datetime,
        to_time: datetime,
    ) -> None:
        """Issue one request and append its entry, re-logging in once on auth loss."""
        entry: dict[str, Any] = {
            "poll_time": poll_time.isoformat(),
            "poll_number": poll_count,
            "unit_id": unit_info["id"],
            "unit_name": unit_info["name"],
            "building": unit_info["building"],
            "unit_type": unit_info["type"],
            "time_zone": unit_info["time_zone"],
            "endpoint": endpoint,
            "measure": measure,
            "from_time": from_time.isoformat(),
            "to_time": to_time.isoformat(),
        }
        label = f"{unit_info['name']} {endpoint} {measure}"
        print(f"   {label:45s} ... ", end="", flush=True)
        try:
            try:
                data = await self._fetch(
                    client, unit_info, endpoint, measure, from_time, to_time
                )
            except AuthenticationError:
                # An unattended soak outlives the session if the proactive
                # token refresh ever fails; without this every later poll errors.
                await client.login(email, password)
                data = await self._fetch(
                    client, unit_info, endpoint, measure, from_time, to_time
                )
            entry["fetched_at"] = datetime.now(UTC).isoformat()
            entry["api_response"] = data
            print(summarize(endpoint, data))
        except Exception as e:
            print(f"❌ Error: {e}")
            entry["error"] = str(e)
        self._append(entry)

    def _append(self, entry: dict[str, Any]) -> None:
        """Append one entry as a JSON line."""
        try:
            with open(self.log_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
            self.entry_count += 1
        except Exception as e:
            print(f"⚠️  Warning: Failed to save entry: {e}")


def ha_credentials(config_entries: Path) -> tuple[str, str]:
    """Read the real (non-mock) melcloudhome entry's login from HA's storage."""
    entries = json.loads(config_entries.read_text())["data"]["entries"]
    entry = next(
        e
        for e in entries
        if e["domain"] == "melcloudhome" and not e["data"].get("debug_mode")
    )
    return entry["data"]["email"], entry["data"]["password"]


def main() -> None:
    """Main entry point."""
    parser = ArgumentParser(description="Record energy API responses over time")
    parser.add_argument(
        "--interval",
        type=int,
        default=10,
        help="Minutes between polls (default: 10)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=120,
        help="Total recording duration in minutes (default: 120 = 2 hours)",
    )
    parser.add_argument(
        "--unit-id",
        help="Focus on specific unit ID (default: record all units)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume existing recording session (append to log file)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("energy_recording.jsonl"),
        help="Output JSON Lines log file (default: energy_recording.jsonl)",
    )
    parser.add_argument(
        "--ha-config",
        type=Path,
        help="Read credentials from this core.config_entries file instead of env",
    )

    args = parser.parse_args()

    if args.ha_config:
        email, password = ha_credentials(args.ha_config)
    else:
        email = os.getenv("MELCLOUD_USER", "")
        password = os.getenv("MELCLOUD_PASSWORD", "")

    if not email or not password:
        print("❌ Error: MELCLOUD_USER and MELCLOUD_PASSWORD must be set")
        print("   Run: source .env")
        sys.exit(1)

    # Create recorder
    recorder = EnergyRecorder(
        log_file=args.output,
        interval_minutes=args.interval,
        duration_minutes=args.duration,
        unit_filter=args.unit_id,
        resume=args.resume,
    )

    # Run recording session
    try:
        asyncio.run(recorder.record_session(email, password))
    except KeyboardInterrupt:
        print("\n\n⚠️  Recording interrupted by user")
        print(f"   Partial data saved to: {args.output}")
        sys.exit(0)


if __name__ == "__main__":
    main()
