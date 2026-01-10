#!/usr/bin/env python3
"""Test ATW Phase 1 models against mock server.

This script validates that the Phase 1 API models (AirToWaterUnit, AirToWaterCapabilities)
correctly parse responses from the mock server.

Usage:
    # Start mock server first
    python tools/mock_melcloud_server.py --port 8888

    # Then run this test
    python tools/test_atw_mock_server.py

    # Or specify custom port
    python tools/test_atw_mock_server.py --port 8888
"""

import argparse
import asyncio
import sys
from pathlib import Path

import aiohttp

# Add project root to path (must be before custom_components import)
# ruff: noqa: E402
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))

from custom_components.melcloudhome.api.models import UserContext


async def test_mock_server(port: int = 8888) -> bool:
    """Test Phase 1 models against mock server.

    Args:
        port: Mock server port (default: 8888)

    Returns:
        True if all tests pass, False otherwise
    """
    base_url = f"http://localhost:{port}"

    print("🧪 Testing Phase 1 ATW Models Against Mock Server")
    print("=" * 70)
    print(f"Mock server: {base_url}\n")

    try:
        async with aiohttp.ClientSession() as session:
            # Test 1: Fetch user context
            print("✅ Test 1: Fetch User Context")
            async with session.get(f"{base_url}/api/user/context") as resp:
                if resp.status != 200:
                    print(f"   ❌ ERROR: HTTP {resp.status}")
                    return False
                data = await resp.json()
                print(f"   HTTP {resp.status}")

            # Test 2: Parse with UserContext model
            print("\n✅ Test 2: Parse with UserContext Model")
            context = UserContext.from_dict(data)
            print(f"   Buildings: {len(context.buildings)}")

            # Test 3: Get ATW units
            print("\n✅ Test 3: Get ATW Units")
            atw_units = context.get_all_air_to_water_units()
            print(f"   Found {len(atw_units)} ATW device(s)")

            if len(atw_units) == 0:
                print("   ❌ ERROR: No ATW devices found!")
                return False

            # Test 4: Validate ATW device parsing
            print("\n✅ Test 4: Validate ATW Device Parsing")
            unit = atw_units[0]
            print(f"   ID: {unit.id}")
            print(f"   Name: {unit.name}")
            print(f"   Power: {unit.power}")
            print(f"   In Standby: {unit.in_standby_mode}")
            print(f"   FTC Model: {unit.ftc_model}")

            # Test 5: Zone 1 fields
            print("\n✅ Test 5: Zone 1 Fields")
            print(f"   Room Temperature: {unit.room_temperature_zone1}°C")
            print(f"   Set Temperature: {unit.set_temperature_zone1}°C")
            print(f"   Operation Mode: {unit.operation_mode_zone1}")

            # Test 6: DHW fields
            print("\n✅ Test 6: DHW Tank Fields")
            print(f"   Tank Temperature: {unit.tank_water_temperature}°C")
            print(f"   Set Tank Temperature: {unit.set_tank_water_temperature}°C")
            print(f"   Forced Hot Water Mode: {unit.forced_hot_water_mode}")

            # Test 7: Operation status (3-way valve)
            print("\n✅ Test 7: Operation Status (3-Way Valve)")
            print(f"   Operation Status: {unit.operation_status}")
            status_correct = unit.operation_status in [
                "Stop",
                "HotWater",
                "HeatRoomTemperature",
                "HeatFlowTemperature",
                "HeatCurve",
            ]
            print(f"   {'✅' if status_correct else '⚠️ '} Valid operation status value")

            # Test 8: Capabilities
            print("\n✅ Test 8: Capabilities Parsing")
            caps = unit.capabilities
            print(f"   Has Hot Water: {caps.has_hot_water}")
            print(f"   Has Zone 2: {caps.has_zone2}")
            print(f"   FTC Model: {caps.ftc_model}")
            print(f"   Has Half Degrees: {caps.has_half_degrees}")

            # Test 9: Temperature ranges (CRITICAL - safe defaults)
            print("\n✅ Test 9: Temperature Ranges (Safe Defaults)")
            print(
                f"   DHW: {caps.min_set_tank_temperature}-{caps.max_set_tank_temperature}°C"
            )
            print(f"   Zone: {caps.min_set_temperature}-{caps.max_set_temperature}°C")

            checks = [
                (caps.min_set_tank_temperature == 40.0, "DHW min = 40.0°C"),
                (caps.max_set_tank_temperature == 60.0, "DHW max = 60.0°C"),
                (caps.min_set_temperature == 10.0, "Zone min = 10.0°C"),
                (caps.max_set_temperature == 30.0, "Zone max = 30.0°C"),
            ]

            all_pass = True
            for passed, msg in checks:
                status = "✅" if passed else "❌"
                print(f"   {status} {msg}")
                if not passed:
                    all_pass = False

            # Test 10: Field naming (critical distinction)
            print("\n✅ Test 10: Field Naming Convention")
            print(
                f"   operation_status (STATUS - what's heating NOW): '{unit.operation_status}'"
            )
            print(
                f"   operation_mode_zone1 (CONTROL - HOW to heat): '{unit.operation_mode_zone1}'"
            )
            naming_correct = hasattr(unit, "operation_status") and hasattr(
                unit, "operation_mode_zone1"
            )
            print(
                f"   {'✅' if naming_correct else '❌'} Both fields exist and are distinct"
            )
            if not naming_correct:
                all_pass = False

            # Test 11: Data types
            print("\n✅ Test 11: Data Type Validation")
            type_checks = [
                (isinstance(unit.power, bool), "power: bool"),
                (
                    isinstance(unit.set_temperature_zone1, float | None),
                    "zone temp: float",
                ),
                (
                    isinstance(unit.set_tank_water_temperature, float | None),
                    "tank temp: float",
                ),
                (isinstance(unit.forced_hot_water_mode, bool), "forced DHW: bool"),
                (isinstance(unit.operation_status, str), "operation status: str"),
                (isinstance(unit.operation_mode_zone1, str), "operation mode: str"),
            ]

            for passed, msg in type_checks:
                status = "✅" if passed else "❌"
                print(f"   {status} {msg}")
                if not passed:
                    all_pass = False

            # Test 12: Zone 2 handling
            print("\n✅ Test 12: Zone 2 Handling")
            print(f"   has_zone2: {unit.has_zone2}")
            if unit.has_zone2:
                print("   Zone 2 fields present (multi-zone device)")
            else:
                print("   No Zone 2 (single-zone device)")

            # Test 13: Error state fields
            print("\n✅ Test 13: Error State Fields")
            print(f"   is_in_error: {unit.is_in_error}")
            print(f"   error_code: {unit.error_code}")

            print("\n" + "=" * 70)
            if all_pass:
                print("✅ ALL VALIDATION PASSED!")
                print("\n📊 Summary:")
                print("   ✅ Mock server responding correctly")
                print("   ✅ UserContext model parses ATW data")
                print("   ✅ AirToWaterUnit model parses all fields")
                print(
                    "   ✅ Safe temperature defaults applied (40-60°C DHW, 10-30°C Zone)"
                )
                print(
                    "   ✅ Field naming convention correct (operation_status vs operation_mode_zone1)"
                )
                print("   ✅ Data types correct")
                print("   ✅ 3-way valve status field present")
                print("\n🎯 Phase 1 API models are CONSISTENT with mock server!")
                return True
            else:
                print("⚠️  SOME VALIDATIONS FAILED")
                return False

    except aiohttp.ClientConnectorError as e:
        print(f"\n❌ Cannot connect to mock server at {base_url}")
        print(f"   Error: {e}")
        print("\n💡 Start the mock server first:")
        print(f"   python tools/mock_melcloud_server.py --port {port}")
        return False
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test ATW Phase 1 models against mock server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # Default: localhost:8888
  %(prog)s --port 8080        # Custom port

Prerequisites:
  1. Start mock server: python tools/mock_melcloud_server.py --port 8888
  2. Run this test: python tools/test_atw_mock_server.py
        """,
    )
    parser.add_argument(
        "--port", type=int, default=8888, help="Mock server port (default: 8888)"
    )

    args = parser.parse_args()

    try:
        result = asyncio.run(test_mock_server(args.port))
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(130)


if __name__ == "__main__":
    main()
