"""Tests for MELCloud Home integration setup.

These tests require pytest-homeassistant-custom-component which provides
mock Home Assistant fixtures. They run in Docker or CI.

Run with: make test-integration
"""

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.melcloudhome.const import DOMAIN

# Mock where the name is looked up, not where it's defined
# __init__.py IS the melcloudhome module (not __init__ submodule)
MOCK_CLIENT_PATH = "custom_components.melcloudhome.MELCloudHomeClient"


def _create_mock_user_context() -> MagicMock:
    """Create a mock UserContext with empty buildings."""
    context = MagicMock()
    context.buildings = []
    return context


@pytest.mark.asyncio
async def test_force_refresh_service_registered(
    hass: HomeAssistant,
) -> None:
    """Test force refresh service is registered on setup."""
    with patch(MOCK_CLIENT_PATH) as mock_client:
        client = mock_client.return_value
        client.login = AsyncMock()
        client.close = AsyncMock()
        client.get_user_context = AsyncMock(return_value=_create_mock_user_context())
        # is_authenticated is a @property - use PropertyMock
        type(client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Verify service registered
        assert hass.services.has_service(DOMAIN, "force_refresh")


@pytest.mark.asyncio
async def test_force_refresh_service_unregistered_on_last_unload(
    hass: HomeAssistant,
) -> None:
    """Test force refresh service is unregistered when last entry unloaded."""
    with patch(MOCK_CLIENT_PATH) as mock_client:
        client = mock_client.return_value
        client.login = AsyncMock()
        client.close = AsyncMock()
        client.get_user_context = AsyncMock(return_value=_create_mock_user_context())
        # is_authenticated is a @property - use PropertyMock
        type(client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert hass.services.has_service(DOMAIN, "force_refresh")

        # Unload entry
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

        # Verify service unregistered
        assert not hass.services.has_service(DOMAIN, "force_refresh")


def _create_mock_unit(unit_id: str, name: str) -> MagicMock:
    """Create a mock ATA unit."""
    unit = MagicMock()
    unit.id = unit_id
    unit.name = name
    unit.power = True
    unit.operation_mode = "Cooling"
    unit.set_temperature = 22.0
    unit.room_temperature = 21.0
    unit.set_fan_speed = "Auto"
    unit.vane_vertical_direction = "Auto"
    unit.vane_horizontal_direction = "Auto"
    unit.in_standby_mode = False
    unit.is_in_error = False
    unit.rssi = -50
    unit.energy_consumed = None
    # Add capabilities mock
    capabilities = MagicMock()
    capabilities.has_energy_consumed_meter = False
    unit.capabilities = capabilities
    return unit


def _create_mock_atw_unit(unit_id: str, name: str) -> MagicMock:
    """Create a mock ATW unit."""
    unit = MagicMock()
    unit.id = unit_id
    unit.name = name
    unit.power = True
    unit.in_standby_mode = False
    unit.operation_status = "Idle"
    unit.operation_mode_zone1 = "HeatThermostat"
    unit.set_temperature_zone1 = 22.0
    unit.room_temperature_zone1 = 21.0
    unit.has_zone2 = False
    unit.operation_mode_zone2 = None
    unit.set_temperature_zone2 = None
    unit.room_temperature_zone2 = None
    unit.set_tank_water_temperature = 50.0
    unit.tank_water_temperature = 48.0
    unit.forced_hot_water_mode = False
    unit.is_in_error = False
    unit.error_code = None
    unit.rssi = -50
    unit.ftc_model = 3
    # Add capabilities mock
    capabilities = MagicMock()
    unit.capabilities = capabilities
    return unit


def _create_mock_building(
    name: str, ata_units: list, atw_units: list | None = None
) -> MagicMock:
    """Create a mock building with units."""
    building = MagicMock()
    building.id = f"building-{name.lower().replace(' ', '-')}"
    building.name = name
    building.air_to_air_units = ata_units
    building.air_to_water_units = atw_units or []
    return building


def _create_mock_context_with_units(buildings: list) -> MagicMock:
    """Create a mock UserContext with buildings."""
    context = MagicMock()
    context.buildings = buildings
    return context


@pytest.mark.asyncio
async def test_device_name_migration_uuid_pattern(
    hass: HomeAssistant,
) -> None:
    """Test migration updates UUID-pattern device names."""
    from homeassistant.helpers import device_registry as dr

    # Create mock data with one ATA unit (using proper UUID format)
    unit = _create_mock_unit("abc12345-1234-5678-9abc-def123456789", "Dining Room")
    building = _create_mock_building("Test Home", [unit])
    context = _create_mock_context_with_units([building])

    with patch(MOCK_CLIENT_PATH) as mock_client:
        client = mock_client.return_value
        client.login = AsyncMock()
        client.close = AsyncMock()
        client.get_user_context = AsyncMock(return_value=context)
        type(client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)

        # Setup integration
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Get device registry
        device_reg = dr.async_get(hass)
        devices = dr.async_entries_for_config_entry(device_reg, entry.entry_id)

        # Find the device
        device = None
        for dev in devices:
            if (DOMAIN, "abc12345-1234-5678-9abc-def123456789") in dev.identifiers:
                device = dev
                break

        assert device is not None, "Device not found"

        # Verify device name matches UUID pattern (technical name)
        # UUID abc12345-1234-5678-9abc-def123456789 -> abc1...6789
        assert device.name == "melcloudhome_abc1_6789"

        # Verify name_by_user was set to friendly name
        assert device.name_by_user == "Test Home Dining Room"


@pytest.mark.asyncio
async def test_device_name_migration_respects_user_customization(
    hass: HomeAssistant,
) -> None:
    """Test migration skips devices with name_by_user already set."""
    from homeassistant.helpers import device_registry as dr

    # Create mock data (using proper UUID format)
    unit = _create_mock_unit("abc12345-1234-5678-9abc-def123456789", "Dining Room")
    building = _create_mock_building("Test Home", [unit])
    context = _create_mock_context_with_units([building])

    with patch(MOCK_CLIENT_PATH) as mock_client:
        client = mock_client.return_value
        client.login = AsyncMock()
        client.close = AsyncMock()
        client.get_user_context = AsyncMock(return_value=context)
        type(client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)

        # Setup integration (first time - will set name_by_user)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Get device and manually set name_by_user to custom value
        device_reg = dr.async_get(hass)
        devices = dr.async_entries_for_config_entry(device_reg, entry.entry_id)
        device = None
        for dev in devices:
            if (DOMAIN, "abc12345-1234-5678-9abc-def123456789") in dev.identifiers:
                device = dev
                break

        assert device is not None
        assert device.name_by_user == "Test Home Dining Room"

        # User customizes the name
        device_reg.async_update_device(device.id, name_by_user="My Custom Name")
        await hass.async_block_till_done()

        # Reload integration
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Get device again
        device = device_reg.async_get(device.id)

        # Verify custom name was preserved
        assert device.name_by_user == "My Custom Name"


@pytest.mark.asyncio
async def test_device_name_migration_multiple_devices(
    hass: HomeAssistant,
) -> None:
    """Test migration handles multiple ATA and ATW devices correctly."""
    from homeassistant.helpers import device_registry as dr

    # Create mock data with 2 ATA + 1 ATW devices (using proper UUID format)
    ata_unit1 = _create_mock_unit("11111111-1111-1111-1111-111111111111", "Dining Room")
    ata_unit2 = _create_mock_unit("22222222-2222-2222-2222-222222222222", "Living Room")
    atw_unit = _create_mock_atw_unit(
        "33333333-3333-3333-3333-333333333333", "Heat Pump"
    )
    building = _create_mock_building("Test Home", [ata_unit1, ata_unit2], [atw_unit])
    context = _create_mock_context_with_units([building])

    with patch(MOCK_CLIENT_PATH) as mock_client:
        client = mock_client.return_value
        client.login = AsyncMock()
        client.close = AsyncMock()
        client.get_user_context = AsyncMock(return_value=context)
        type(client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)

        # Setup integration
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Get device registry
        device_reg = dr.async_get(hass)
        devices = dr.async_entries_for_config_entry(device_reg, entry.entry_id)

        # Find all devices
        ata_device1 = None
        ata_device2 = None
        atw_device = None
        for dev in devices:
            if (DOMAIN, "11111111-1111-1111-1111-111111111111") in dev.identifiers:
                ata_device1 = dev
            elif (DOMAIN, "22222222-2222-2222-2222-222222222222") in dev.identifiers:
                ata_device2 = dev
            elif (DOMAIN, "33333333-3333-3333-3333-333333333333") in dev.identifiers:
                atw_device = dev

        # Verify all devices found and migrated
        assert ata_device1 is not None
        assert ata_device1.name_by_user == "Test Home Dining Room"

        assert ata_device2 is not None
        assert ata_device2.name_by_user == "Test Home Living Room"

        assert atw_device is not None
        assert atw_device.name_by_user == "Test Home Heat Pump"


@pytest.mark.asyncio
async def test_device_name_migration_idempotent(
    hass: HomeAssistant,
) -> None:
    """Test repeated setup doesn't re-migrate already migrated devices."""
    from homeassistant.helpers import device_registry as dr

    # Create mock data (using proper UUID format)
    unit = _create_mock_unit("abc12345-1234-5678-9abc-def123456789", "Dining Room")
    building = _create_mock_building("Test Home", [unit])
    context = _create_mock_context_with_units([building])

    with patch(MOCK_CLIENT_PATH) as mock_client:
        client = mock_client.return_value
        client.login = AsyncMock()
        client.close = AsyncMock()
        client.get_user_context = AsyncMock(return_value=context)
        type(client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)

        # Setup integration (first time)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Get device
        device_reg = dr.async_get(hass)
        devices = dr.async_entries_for_config_entry(device_reg, entry.entry_id)
        device = None
        for dev in devices:
            if (DOMAIN, "abc12345-1234-5678-9abc-def123456789") in dev.identifiers:
                device = dev
                break

        assert device is not None
        first_name = device.name_by_user
        assert first_name == "Test Home Dining Room"

        # Reload integration (second time)
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Get device again
        device = device_reg.async_get(device.id)

        # Verify name unchanged (migration skipped because name_by_user already set)
        assert device.name_by_user == first_name
