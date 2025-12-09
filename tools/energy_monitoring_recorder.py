#!/usr/bin/env python3
"""Energy API monitoring recorder.

Records full API responses at regular intervals to characterize API behavior:
- How quickly data becomes available
- How values change over time within a hour
- When hours transition from partial to complete

Usage:
    # Start new recording session
    python energy_monitoring_recorder.py

    # Resume existing session (appends to log file)
    python energy_monitoring_recorder.py --resume

    # Custom interval (default 10 minutes)
    python energy_monitoring_recorder.py --interval 5

    # Custom duration (default 2 hours = 120 minutes)
    python energy_monitoring_recorder.py --duration 180

    # Focus on specific unit
    python energy_monitoring_recorder.py --unit-id 0efce33f-5847-4042-88eb-aaf3ff6a76db

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

# Add parent directory to path to import the API client
sys.path.insert(0, str(Path(__file__).parent.parent))

from custom_components.melcloudhome.api.client import MELCloudHomeClient


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
            log_file: Path to JSON log file
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

        # Load existing data if resuming
        self.entries: list[dict[str, Any]] = []
        if resume and log_file.exists():
            try:
                with open(log_file) as f:
                    self.entries = json.load(f)
                print(f"📂 Resuming from existing log with {len(self.entries)} entries")
            except json.JSONDecodeError as e:
                print(f"⚠️  Warning: Could not parse existing log: {e}")
                print("   Starting fresh recording")
                self.entries = []

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
            units = []
            for building in context.buildings:
                for unit in building.air_to_air_units:
                    if unit.capabilities.has_energy_consumed_meter and (
                        not self.unit_filter or unit.id == self.unit_filter
                    ):
                        units.append(
                            {
                                "id": unit.id,
                                "name": unit.name,
                                "building": building.name,
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
                    f"   • {unit_info['name']} ({unit_info['building']}) - {unit_info['id']}"
                )

            # Recording loop
            while datetime.now(UTC) < end_time:
                poll_count += 1
                poll_time = datetime.now(UTC)

                print(f"\n🔍 Poll #{poll_count} at {poll_time.strftime('%H:%M:%S')}")

                # Fetch energy data for each unit
                to_time = poll_time
                from_time = poll_time - timedelta(hours=6)  # Get last 6 hours

                for unit_info in units:
                    try:
                        print(f"   {unit_info['name']:20s} ... ", end="", flush=True)

                        data = await client.get_energy_data(
                            unit_info["id"], from_time, to_time, "Hour"
                        )

                        # Record entry
                        entry = {
                            "poll_time": poll_time.isoformat(),
                            "poll_number": poll_count,
                            "unit_id": unit_info["id"],
                            "unit_name": unit_info["name"],
                            "building": unit_info["building"],
                            "from_time": from_time.isoformat(),
                            "to_time": to_time.isoformat(),
                            "api_response": data,
                        }

                        self.entries.append(entry)

                        # Summarize response
                        if data and data.get("measureData"):
                            values = data["measureData"][0].get("values", [])
                            if values:
                                latest = values[-1]
                                print(
                                    f"✓ {len(values)} hour(s), latest: {latest['time'][:16]} = {latest['value']} Wh"
                                )
                            else:
                                print("✓ No values")
                        else:
                            print("✓ No data (304 or empty)")

                    except Exception as e:
                        print(f"❌ Error: {e}")
                        entry = {
                            "poll_time": poll_time.isoformat(),
                            "poll_number": poll_count,
                            "unit_id": unit_info["id"],
                            "unit_name": unit_info["name"],
                            "building": unit_info["building"],
                            "error": str(e),
                        }
                        self.entries.append(entry)

                # Save after each poll
                self._save_log()

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
            print(f"  Total entries: {len(self.entries)}")
            print(f"  Log file: {self.log_file}")
            print("=" * 80)

        finally:
            await client.close()

    def _save_log(self) -> None:
        """Save entries to log file."""
        try:
            with open(self.log_file, "w") as f:
                json.dump(self.entries, f, indent=2)
        except Exception as e:
            print(f"⚠️  Warning: Failed to save log: {e}")


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
        default=Path("energy_recording.json"),
        help="Output JSON log file (default: energy_recording.json)",
    )

    args = parser.parse_args()

    # Get credentials from environment
    email = os.getenv("MELCLOUD_USER")
    password = os.getenv("MELCLOUD_PASSWORD")

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
