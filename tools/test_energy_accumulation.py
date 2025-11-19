#!/usr/bin/env python3
"""Test energy accumulation logic."""

import asyncio
import os
import sys
from datetime import UTC, datetime, timedelta

sys.path.insert(0, "custom_components/melcloudhome")

from api.client import MELCloudHomeClient


async def test_accumulation():
    """Test energy accumulation matches coordinator logic."""
    email = os.getenv("MELCLOUD_USER")
    password = os.getenv("MELCLOUD_PASSWORD")

    print("🧪 Testing Energy Accumulation Logic")
    print("=" * 70)

    client = MELCloudHomeClient()
    try:
        await client.login(email, password)
        context = await client.get_user_context()

        for building in context.buildings:
            for unit in building.air_to_air_units:
                # Show ALL units, not just those with energy meters
                print(f"\n📍 {building.name}: {unit.name}")
                print("-" * 70)
                print(f"   Power: {'ON' if unit.power else 'OFF'}")
                print(
                    f"   Has Energy Meter Capability: {unit.capabilities.has_energy_consumed_meter}"
                )

                if not unit.capabilities.has_energy_consumed_meter:
                    print("   ⚠️  No energy meter capability")
                    continue

                # Fetch last 24 hours
                to_time = datetime.now(UTC)
                from_time = to_time - timedelta(hours=24)

                data = await client.get_energy_data(unit.id, from_time, to_time, "Hour")

                if not data or not data.get("measureData"):
                    print("   ⚠️  No energy data from API")
                    print("   Sensor should show: unavailable")
                    continue

                values = data["measureData"][0].get("values", [])
                if not values:
                    print("   ⚠️  Empty values array")
                    print("   Sensor should show: unavailable")
                    continue

                # Simulate coordinator accumulation logic
                cumulative = 0.0
                last_hour = None

                print(f"\n   Hourly Data (last {len(values)} hours):")
                for v in values:
                    hour_time = v["time"]
                    wh = float(v["value"])
                    kwh = wh / 1000.0

                    # Only add NEW hours
                    if last_hour is None or hour_time > last_hour:
                        cumulative += kwh
                        print(
                            f"   {hour_time[:16]}: {kwh:6.3f} kWh → Cumulative: {cumulative:.3f} kWh ✅"
                        )
                        last_hour = hour_time
                    else:
                        print(
                            f"   {hour_time[:16]}: {kwh:6.3f} kWh → SKIP (already counted)"
                        )

                short_id = unit.id.replace("-", "")
                entity_id = f"sensor.melcloud_{short_id[:4]}_{short_id[-4:]}_energy"

                print("\n   📊 Expected Sensor State:")
                print(f"      Entity ID: {entity_id}")
                print(f"      Value: {cumulative:.3f} kWh")
                print("      Increases: ✅ YES (adds new hourly values)")
                print()

        print("=" * 70)
        print("\n✅ VERIFICATION STEPS:")
        print("1. Open HA → Developer Tools → States")
        print("2. Search for energy sensors")
        print("3. Values should match 'Expected Sensor State' above")
        print("4. Wait 30 min and check again - values should increase!")
        print("\nIf Dining Room sensor shows the expected cumulative value,")
        print("the accumulation logic is working correctly!")

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(test_accumulation())
