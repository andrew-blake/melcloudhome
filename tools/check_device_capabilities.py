#!/usr/bin/env python3
"""Check device capabilities for energy monitoring."""

import asyncio
import os
import sys

sys.path.insert(0, "custom_components/melcloudhome")

from api.client import MELCloudHomeClient


async def check_capabilities():
    """Check energy capabilities for both devices."""
    email = os.getenv("MELCLOUD_USER")
    password = os.getenv("MELCLOUD_PASSWORD")

    if not email or not password:
        print("❌ Missing MELCLOUD_USER or MELCLOUD_PASSWORD")
        return

    client = MELCloudHomeClient()
    try:
        await client.login(email, password)
        context = await client.get_user_context()

        print("🔍 Checking device capabilities:\n")

        for building in context.buildings:
            for unit in building.air_to_air_units:
                print(f"📍 {building.name}: {unit.name}")
                print(f"   ID: {unit.id}")
                print(f"   Power: {unit.power}")
                print(
                    f"   Has Energy Meter: {unit.capabilities.has_energy_consumed_meter}"
                )
                print()

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(check_capabilities())
