#!/usr/bin/env python3
"""Check current energy sensor status and test API."""

import asyncio
import os
import sys
from datetime import UTC, datetime, timedelta

sys.path.insert(0, "custom_components/melcloudhome")

from api.client import MELCloudHomeClient


async def check_status():
    """Check energy status for both devices."""
    email = os.getenv("MELCLOUD_USER")
    password = os.getenv("MELCLOUD_PASSWORD")

    client = MELCloudHomeClient()
    try:
        await client.login(email, password)
        print("✅ Authenticated\n")

        # Get current device state
        context = await client.get_user_context()

        print("📊 Device Status:")
        print("=" * 60)

        for building in context.buildings:
            for unit in building.air_to_air_units:
                print(f"\n📍 {building.name}: {unit.name}")
                print(f"   ID: {unit.id[:13]}...")
                print(f"   Power: {unit.power}")
                print(
                    f"   Has Energy Meter: {unit.capabilities.has_energy_consumed_meter}"
                )
                print(f"   Energy Consumed (from model): {unit.energy_consumed}")

                if unit.capabilities.has_energy_consumed_meter:
                    # Test energy API
                    to_time = datetime.now(UTC)
                    from_time = to_time - timedelta(hours=1)

                    print("\n   🔬 Testing energy API...")
                    try:
                        data = await client.get_energy_data(
                            unit.id, from_time, to_time, "Hour"
                        )

                        if data:
                            energy = client.parse_energy_response(data)
                            print(f"   ✅ API returned data: {energy} kWh")

                            if data.get("measureData"):
                                values = data["measureData"][0].get("values", [])
                                print(f"   Data points: {len(values)}")
                                if values:
                                    print(
                                        f"   Latest: {values[-1]['time']} = {values[-1]['value']} Wh"
                                    )
                        else:
                            print("   ⚠️  No data (304 or empty)")

                    except Exception as e:
                        print(f"   ❌ Error: {e}")

        print("\n" + "=" * 60)

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(check_status())
