#!/usr/bin/env python3
"""Debug script to fetch and analyze actual energy API responses.

This script logs into MELCloud Home and fetches energy data to understand
the actual format and values returned by the API.
"""

import asyncio
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Add parent directory to path to import the API client
sys.path.insert(0, str(Path(__file__).parent.parent))

from custom_components.melcloudhome.api.client import MELCloudHomeClient


async def main():
    """Fetch and analyze energy data from MELCloud Home API."""
    # Get credentials from environment
    email = os.getenv("MELCLOUD_USER")
    password = os.getenv("MELCLOUD_PASSWORD")

    if not email or not password:
        print("ERROR: MELCLOUD_USER and MELCLOUD_PASSWORD must be set in environment")
        print("Run: source .env")
        return

    print(f"Logging in as: {email}")
    print("=" * 80)

    client = MELCloudHomeClient()
    try:
        # Login
        await client.login(email, password)
        print("✓ Login successful\n")

        # Get user context to find devices
        context = await client.get_user_context()
        print(f"Found {len(context.buildings)} building(s)")

        for building in context.buildings:
            print(f"\nBuilding: {building.name}")
            print(f"  Units: {len(building.air_to_air_units)}")

            for unit in building.air_to_air_units:
                print(f"\n  Unit: {unit.name}")
                print(f"    ID: {unit.id}")
                print(
                    f"    Has Energy Meter: {unit.capabilities.has_energy_consumed_meter}"
                )

                if not unit.capabilities.has_energy_consumed_meter:
                    print("    ⚠ No energy meter capability, skipping")
                    continue

                # Fetch energy data for last 6 hours
                to_time = datetime.now(UTC)
                from_time = to_time - timedelta(hours=6)

                print("\n    Fetching energy data:")
                print(f"      From: {from_time.strftime('%Y-%m-%d %H:%M')} UTC")
                print(f"      To:   {to_time.strftime('%Y-%m-%d %H:%M')} UTC")
                print("      Interval: Hour")

                data = await client.get_energy_data(unit.id, from_time, to_time, "Hour")

                if not data:
                    print("    ⚠ No data returned (304 or empty)")
                    continue

                print("\n    Raw API Response:")
                print(f"    {json.dumps(data, indent=6)}")

                # Analyze the values
                if data.get("measureData"):
                    measure_data = data["measureData"][0]
                    values = measure_data.get("values", [])

                    if values:
                        print("\n    Energy Values Analysis:")
                        print("    " + "-" * 70)
                        print(
                            f"    {'Hour':<25} {'Value (Wh)':<15} {'kWh':<10} {'Delta from prev'}"
                        )
                        print("    " + "-" * 70)

                        prev_wh = None
                        for value_entry in values:
                            timestamp = value_entry["time"]
                            wh_value = float(value_entry["value"])
                            kwh_value = wh_value / 1000.0

                            delta_str = ""
                            if prev_wh is not None:
                                delta_wh = wh_value - prev_wh
                                delta_kwh = delta_wh / 1000.0
                                delta_str = f"+{delta_kwh:.3f} kWh"
                                if delta_wh < 0:
                                    delta_str = f"{delta_kwh:.3f} kWh (NEGATIVE!)"

                            print(
                                f"    {timestamp[:19]:<25} {wh_value:>12.1f}   {kwh_value:>8.3f}   {delta_str}"
                            )
                            prev_wh = wh_value

                        print("    " + "-" * 70)

                        # Analysis
                        print("\n    Interpretation:")
                        if len(values) >= 2:
                            first_val = float(values[0]["value"])
                            last_val = float(values[-1]["value"])
                            total_increase = last_val - first_val

                            print(
                                f"      First value: {first_val:.1f} Wh ({first_val/1000:.3f} kWh)"
                            )
                            print(
                                f"      Last value:  {last_val:.1f} Wh ({last_val/1000:.3f} kWh)"
                            )
                            print(
                                f"      Total increase: {total_increase:.1f} Wh ({total_increase/1000:.3f} kWh)"
                            )

                            if total_increase > 0:
                                print(
                                    "\n      ✓ Values appear to be CUMULATIVE (increasing over time)"
                                )
                                print(
                                    "        Each value includes previous hours in the period."
                                )
                            elif all(
                                float(values[i]["value"]) > 0
                                for i in range(len(values))
                            ):
                                print(
                                    "\n      ? Values appear to be PER-HOUR (not increasing)"
                                )
                                print(
                                    "        Each value represents consumption during that hour only."
                                )

                    else:
                        print("    ⚠ No values in response")

        print("\n" + "=" * 80)
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
