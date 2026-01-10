#!/usr/bin/env python3
"""Dump full MELCloud Home state to console."""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add parent directory to path to import the integration
sys.path.insert(0, str(Path(__file__).parent.parent))

from custom_components.melcloudhome.api.client import MELCloudHomeClient


async def main():
    """Main function to dump state."""
    # Get credentials from environment
    email = os.getenv("MELCLOUD_USER")
    password = os.getenv("MELCLOUD_PASSWORD")

    if not email or not password:
        print("Error: MELCLOUD_USER and MELCLOUD_PASSWORD must be set")
        print(
            "Usage: MELCLOUD_USER=user@example.com MELCLOUD_PASSWORD=password python dump_state.py"
        )
        sys.exit(1)

    print("=" * 80)
    print("MELCloud Home State Dump")
    print("=" * 80)
    print(f"Email: {email}\n")

    # Create client and authenticate
    client = MELCloudHomeClient()

    try:
        print("Authenticating...")
        await client.login(email, password)
        print("✓ Authentication successful\n")

        # Get user context
        print("Fetching user context...")
        context = await client.get_user_context()
        print("✓ User context retrieved\n")

        # Print building and unit information
        print("=" * 80)
        print("BUILDINGS AND UNITS")
        print("=" * 80)

        for building in context.buildings:
            print(f"\n🏠 Building: {building.name}")
            print(f"   ID: {building.id}")
            print(f"   Units: {len(building.air_to_air_units)}")

            for unit in building.air_to_air_units:
                print(f"\n   📱 Unit: {unit.name}")
                print(f"      ID: {unit.id}")
                print(f"      Power: {unit.power}")
                print(f"      Operation Mode: {unit.operation_mode}")
                print(f"      Room Temperature: {unit.room_temperature}°C")
                print(f"      Set Temperature: {unit.set_temperature}°C")
                print(f"      Fan Speed: {unit.set_fan_speed}")
                print(f"      Vane Vertical: {unit.vane_vertical_direction}")
                print(f"      Vane Horizontal: {unit.vane_horizontal_direction}")
                print(f"      In Standby: {unit.in_standby_mode}")
                print(f"      In Error: {unit.is_in_error}")

                if unit.capabilities:
                    print("\n      Capabilities:")
                    print(
                        f"         Fan Speeds: {unit.capabilities.number_of_fan_speeds}"
                    )
                    print(f"         Has Swing: {unit.capabilities.has_swing}")
                    print(
                        f"         Has Air Direction: {unit.capabilities.has_air_direction}"
                    )
                    print(
                        f"         Temp Range (Heat): {unit.capabilities.min_temp_heat}°C - {unit.capabilities.max_temp_heat}°C"
                    )
                    print(
                        f"         Temp Range (Cool): {unit.capabilities.min_temp_cool_dry}°C - {unit.capabilities.max_temp_cool_dry}°C"
                    )

        # Print raw JSON for detailed inspection
        print("\n" + "=" * 80)
        print("RAW JSON DATA")
        print("=" * 80)

        # Convert to dict for JSON serialization
        raw_data = {
            "buildings": [
                {
                    "id": building.id,
                    "name": building.name,
                    "units": [
                        {
                            "id": unit.id,
                            "name": unit.name,
                            "power": unit.power,
                            "operation_mode": unit.operation_mode,
                            "set_temperature": unit.set_temperature,
                            "room_temperature": unit.room_temperature,
                            "set_fan_speed": unit.set_fan_speed,
                            "vane_vertical_direction": unit.vane_vertical_direction,
                            "vane_horizontal_direction": unit.vane_horizontal_direction,
                            "in_standby_mode": unit.in_standby_mode,
                            "is_in_error": unit.is_in_error,
                        }
                        for unit in building.air_to_air_units
                    ],
                }
                for building in context.buildings
            ]
        }

        print(json.dumps(raw_data, indent=2))

    except Exception as e:
        print(f"\n✗ Error: {type(e).__name__}: {e}")
        sys.exit(1)
    finally:
        await client.close()

    print("\n" + "=" * 80)
    print("State dump complete!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
