#!/usr/bin/env python3
"""Test script to cycle through vane positions."""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path to import the integration
sys.path.insert(0, str(Path(__file__).parent.parent))

from custom_components.melcloudhome.api.client import MELCloudHomeClient
from custom_components.melcloudhome.api.exceptions import ApiError


async def test_vertical_positions(client: MELCloudHomeClient, unit_id: str) -> None:
    """Test all vertical vane positions."""
    positions = ["Auto", "Swing", "One", "Two", "Three", "Four", "Five"]
    horizontal = "Auto"  # Keep horizontal constant

    print("\n" + "=" * 60)
    print("Testing VERTICAL vane positions")
    print("=" * 60)

    for position in positions:
        print(f"\nTesting vertical position: {position}")
        try:
            await client.ata.set_vanes(
                unit_id, vertical=position, horizontal=horizontal
            )
            print(f"  ✓ SUCCESS: {position}")
            await asyncio.sleep(1)
        except ApiError as e:
            print(f"  ✗ FAILED: {position} - {e}")
        except Exception as e:
            print(f"  ✗ ERROR: {position} - {type(e).__name__}: {e}")


async def test_horizontal_positions(client: MELCloudHomeClient, unit_id: str) -> None:
    """Test all horizontal vane positions."""
    positions = ["Auto", "Swing", "One", "Two", "Three", "Four", "Five"]
    vertical = "Auto"  # Keep vertical constant

    print("\n" + "=" * 60)
    print("Testing HORIZONTAL vane positions")
    print("=" * 60)

    for position in positions:
        print(f"\nTesting horizontal position: {position}")
        try:
            await client.ata.set_vanes(unit_id, vertical=vertical, horizontal=position)
            print(f"  ✓ SUCCESS: {position}")
            await asyncio.sleep(1)
        except ApiError as e:
            print(f"  ✗ FAILED: {position} - {e}")
        except Exception as e:
            print(f"  ✗ ERROR: {position} - {type(e).__name__}: {e}")


async def main() -> None:
    """Main test function."""
    # Get credentials from environment
    email = os.getenv("MELCLOUD_USER")
    password = os.getenv("MELCLOUD_PASSWORD")

    if not email or not password:
        print("Error: MELCLOUD_USER and MELCLOUD_PASSWORD must be set")
        print(
            "Usage: MELCLOUD_USER=user@example.com MELCLOUD_PASSWORD=password python test_vane_positions.py [unit_id]"
        )
        sys.exit(1)

    # Get unit ID from command line or use default
    unit_id = (
        sys.argv[1] if len(sys.argv) > 1 else "0efce33f-5847-4042-88eb-aaf3ff6a76db"
    )

    print("MELCloud Home Vane Position Test")
    print("=" * 60)
    print(f"Unit ID: {unit_id}")
    print(f"Email: {email}")

    # Create client and authenticate
    client = MELCloudHomeClient()

    try:
        print("\nAuthenticating...")
        await client.login(email, password)
        print("  ✓ Authentication successful")

        # Test vertical positions
        await test_vertical_positions(client, unit_id)

        # Test horizontal positions
        await test_horizontal_positions(client, unit_id)

        # Reset to Auto/Auto
        print("\n" + "=" * 60)
        print("Resetting to Auto/Auto")
        print("=" * 60)
        await client.ata.set_vanes(unit_id, vertical="Auto", horizontal="Auto")
        print("  ✓ Reset complete")

    except Exception as e:
        print(f"\n✗ Test failed: {type(e).__name__}: {e}")
        sys.exit(1)
    finally:
        await client.close()

    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
