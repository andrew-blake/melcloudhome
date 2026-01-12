"""Tests for multi-building support with VCR.

These tests verify that the integration correctly handles accounts with:
- Multiple buildings (owned buildings)
- Guest buildings (shared buildings)
- Mixed device types (ATA and ATW) across buildings
"""

import pytest

from custom_components.melcloudhome.api.client import MELCloudHomeClient


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_guest_buildings_only(
    authenticated_client: MELCloudHomeClient,
) -> None:
    """Test account with only guest buildings (no owned buildings).

    This test uses a real account with access ONLY to shared buildings (guestBuildings).
    It verifies that:
    1. Devices in guest buildings are properly discovered
    2. The is_guest flag is set correctly (all should be True for this account)
    3. Both ATA and ATW devices from guest buildings are accessible
    """
    context = await authenticated_client.get_user_context()

    # Should have at least one building
    assert len(context.buildings) > 0, "Should have at least one building"

    # This account only has guest buildings, all should have is_guest=True
    guest_buildings = [b for b in context.buildings if b.is_guest]
    assert len(guest_buildings) > 0, "Should have at least one guest building"
    assert len(guest_buildings) == len(
        context.buildings
    ), "All buildings should be guest buildings for this test account"

    # Verify is_guest flag is set correctly (all True for this account)
    for building in context.buildings:
        assert building.is_guest is True, "All buildings should be guest buildings"

    # Should have both ATA and ATW devices
    ata_units = context.get_all_air_to_air_units()
    atw_units = context.get_all_air_to_water_units()

    assert len(ata_units) > 0, "Should have ATA devices"
    assert len(atw_units) > 0, "Should have ATW devices"

    # Verify devices from guest buildings are accessible
    guest_device_count = 0
    for building in guest_buildings:
        guest_device_count += len(building.air_to_air_units)
        guest_device_count += len(building.air_to_water_units)

    assert guest_device_count > 0, "Guest buildings should contain devices"

    # Verify ATA device attributes
    for ata_unit in ata_units:
        assert ata_unit.id is not None
        assert ata_unit.name is not None
        assert isinstance(ata_unit.power, bool)

    # Verify ATW device attributes
    for atw_unit in atw_units:
        assert atw_unit.id is not None
        assert atw_unit.name is not None
        # ATW-specific attributes
        assert hasattr(atw_unit, "set_temperature_zone1")
        assert hasattr(atw_unit, "tank_water_temperature")


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_get_atw_device_from_guest_building(
    authenticated_client: MELCloudHomeClient,
) -> None:
    """Test accessing ATW device from guest building.

    Verifies that ATW devices in shared buildings can be accessed and controlled.
    """
    context = await authenticated_client.get_user_context()

    # Get all ATW devices
    atw_units = context.get_all_air_to_water_units()
    assert len(atw_units) > 0, "Should have at least one ATW device"

    # Get first ATW device
    atw_device = atw_units[0]

    # Verify it can be retrieved by ID
    retrieved = context.get_air_to_water_unit_by_id(atw_device.id)
    assert retrieved is not None
    assert retrieved.id == atw_device.id
    assert retrieved.name == atw_device.name

    # Verify ATW-specific state
    assert atw_device.set_temperature_zone1 is not None
    assert atw_device.tank_water_temperature is not None
    assert atw_device.power is not None
