#!/usr/bin/env python3
"""Test energy telemetry endpoint to determine data format."""

import asyncio
import os
import sys
from datetime import datetime, timedelta

# Add custom component to path
sys.path.insert(0, "custom_components/melcloudhome")

from api.client import MELCloudHomeClient


async def test_energy_endpoint():
    """Test the energy telemetry endpoint."""
    # Get credentials from environment
    email = os.getenv("MELCLOUD_USER")
    password = os.getenv("MELCLOUD_PASSWORD")

    if not email or not password:
        print("❌ Missing MELCLOUD_USER or MELCLOUD_PASSWORD environment variables")
        print("   Set these in .env file")
        return

    print(f"🔐 Authenticating as {email}...")

    # Create client and authenticate
    client = MELCloudHomeClient()
    try:
        await client.login(email, password)
        print("✅ Authentication successful")
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        return

    # Get user context to find devices with energy meters
    print("\n📊 Fetching device context...")
    try:
        context = await client.get_user_context()
        print(f"✅ Found {len(context.buildings)} building(s)")

        # Find devices with energy meters
        energy_capable_units = []
        for building in context.buildings:
            for unit in building.air_to_air_units:
                if unit.capabilities.has_energy_consumed_meter:
                    energy_capable_units.append((building.name, unit))
                    print(f"   📍 {building.name}: {unit.name} - HAS ENERGY METER")
                else:
                    print(f"   📍 {building.name}: {unit.name} - no energy meter")

        if not energy_capable_units:
            print("\n❌ No devices with energy meters found")
            return

        # Test energy endpoint for first capable device
        print("\n🔬 Testing energy endpoint...")
        building_name, unit = energy_capable_units[0]
        print(f"   Device: {building_name} - {unit.name}")
        print(f"   Unit ID: {unit.id}")

        # Request last 24 hours of data
        to_time = datetime.utcnow()
        from_time = to_time - timedelta(hours=24)

        print(
            f"   Time range: {from_time.strftime('%Y-%m-%d %H:%M')} to {to_time.strftime('%Y-%m-%d %H:%M')}"
        )

        # Build request URL manually to see what we're calling
        url = f"https://melcloudhome.com/api/telemetry/energy/{unit.id}"
        params = {
            "from": from_time.strftime("%Y-%m-%d %H:%M"),
            "to": to_time.strftime("%Y-%m-%d %H:%M"),
            "interval": "Hour",
            "measure": "cumulative_energy_consumed_since_last_upload",
        }

        print(f"   URL: {url}")
        print(f"   Params: {params}")

        # Make request
        headers = {"x-csrf": "1", "Accept": "application/json"}
        session = await client._auth.get_session()
        async with session.get(url, params=params, headers=headers) as resp:
            print(f"\n📥 Response status: {resp.status}")

            if resp.status == 304:
                print("   INFO: No new data (304 Not Modified)")
                return

            if resp.status == 404:
                print(
                    "   ❌ Endpoint not found (404) - device may not support energy monitoring"
                )
                return

            if resp.status != 200:
                print(f"   ❌ Unexpected status: {resp.status}")
                text = await resp.text()
                print(f"   Response: {text}")
                return

            data = await resp.json()

            print("✅ Energy data received!")
            print("\n📊 Raw response:")
            import json

            print(json.dumps(data, indent=2))

            # Parse the response
            if data.get("measureData"):
                measure_data = data["measureData"][0]
                values = measure_data.get("values", [])

                print(f"\n📈 Found {len(values)} data point(s)")

                if values:
                    print("\n🔍 Analysis:")
                    first_value = float(values[0]["value"])
                    last_value = float(values[-1]["value"])

                    print(f"   First value: {first_value}")
                    print(f"   Last value: {last_value}")
                    print(f"   Change: {last_value - first_value}")

                    # Guess the unit based on magnitude
                    print("\n💡 Unit Analysis:")
                    if last_value < 100:
                        print(f"   Likely in kWh (value: {last_value} kWh)")
                        print("   Typical daily usage: 5-20 kWh for HVAC")
                    else:
                        print(
                            f"   Likely in Wh (value: {last_value} Wh = {last_value/1000:.2f} kWh)"
                        )
                        print("   Will need conversion to kWh for HA")

                    print("\n📝 Sample data points:")
                    for i, point in enumerate(values[:5]):  # Show first 5
                        print(f"   [{i}] {point['time']}: {point['value']}")
                    if len(values) > 5:
                        print(f"   ... ({len(values) - 5} more)")
                else:
                    print("   ⚠️  No values in response")
            else:
                print("   ⚠️  No measureData in response")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(test_energy_endpoint())
