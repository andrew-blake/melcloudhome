"""Tests for MELCloud Home diagnostics.

Tests cover diagnostics data structure, credential redaction, and data collection.
Follows HA best practices: test observable behavior through diagnostics API.

Reference: docs/testing-best-practices.md
Run with: make test-ha
"""

from unittest.mock import AsyncMock, PropertyMock, patch

import pytest
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.melcloudhome.api.models import (
    AirToAirUnit,
    Building,
    DeviceCapabilities,
    UserContext,
)
from custom_components.melcloudhome.const import DOMAIN
from custom_components.melcloudhome.diagnostics import (
    async_get_config_entry_diagnostics,
)

# Mock at API boundary (NOT coordinator or diagnostics internals)
MOCK_CLIENT_PATH = "custom_components.melcloudhome.MELCloudHomeClient"

# Test device identifiers
TEST_UNIT_ID = "0efc1234-5678-9abc-def0-123456789abc"
TEST_BUILDING_ID = "building-test-id"


def create_mock_unit(
    unit_id: str = TEST_UNIT_ID,
    name: str = "Test Unit",
    power: bool = True,
    operation_mode: str = "Heat",
    set_temperature: float = 21.0,
    room_temperature: float = 20.0,
    has_energy_meter: bool = False,
) -> AirToAirUnit:
    """Create a mock AirToAirUnit for diagnostics testing."""
    capabilities = DeviceCapabilities(has_energy_consumed_meter=has_energy_meter)

    return AirToAirUnit(
        id=unit_id,
        name=name,
        power=power,
        operation_mode=operation_mode,
        set_temperature=set_temperature,
        room_temperature=room_temperature,
        set_fan_speed="Auto",
        vane_vertical_direction="Auto",
        vane_horizontal_direction="Auto",
        in_standby_mode=False,
        is_in_error=False,
        rssi=-50,
        capabilities=capabilities,
        schedule=[],
        schedule_enabled=False,
        energy_consumed=None,
    )


def create_mock_building(
    building_id: str = TEST_BUILDING_ID,
    name: str = "Test Building",
    units: list[AirToAirUnit] | None = None,
) -> Building:
    """Create a mock Building for diagnostics testing."""
    if units is None:
        units = [create_mock_unit()]
    return Building(id=building_id, name=name, air_to_air_units=units)


def create_mock_user_context(buildings: list[Building] | None = None) -> UserContext:
    """Create a mock UserContext for diagnostics testing."""
    if buildings is None:
        buildings = [create_mock_building()]
    return UserContext(buildings=buildings)


@pytest.mark.asyncio
async def test_diagnostics_basic_structure(hass: HomeAssistant) -> None:
    """Test diagnostics returns correct basic structure with redacted credentials."""
    mock_context = create_mock_user_context()

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        # Setup mock client
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        # Create and setup config entry
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "secret_password",
            },
            unique_id="test@example.com",
            title="MELCloud Home",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Get diagnostics data
        diagnostics = await async_get_config_entry_diagnostics(hass, entry)

        # Verify basic structure
        assert "entry" in diagnostics
        assert "coordinator" in diagnostics
        assert "entities" in diagnostics
        assert "user_context" in diagnostics

        # Verify entry data
        assert diagnostics["entry"]["title"] == "MELCloud Home"
        assert diagnostics["entry"]["version"] == 1

        # Verify credentials are redacted
        assert diagnostics["entry"]["data"][CONF_EMAIL] == "**REDACTED**"
        assert diagnostics["entry"]["data"][CONF_PASSWORD] == "**REDACTED**"

        # Verify coordinator data
        assert diagnostics["coordinator"]["last_update_success"] is True
        assert diagnostics["coordinator"]["update_interval"] == 60.0


@pytest.mark.asyncio
async def test_diagnostics_includes_entity_states(hass: HomeAssistant) -> None:
    """Test diagnostics includes entity states for climate and sensors."""
    mock_context = create_mock_user_context()

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        # Setup mock client
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        # Create and setup config entry
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Get diagnostics data
        diagnostics = await async_get_config_entry_diagnostics(hass, entry)

        # Verify entities section exists and has data
        assert "entities" in diagnostics
        entities = diagnostics["entities"]

        # Should have climate entity (entity ID derived from UUID: 0efc1234-...9abc)
        climate_entity_id = "climate.melcloudhome_0efc_9abc_climate"
        assert climate_entity_id in entities
        assert entities[climate_entity_id]["state"] == "heat"
        assert "attributes" in entities[climate_entity_id]

        # Should have sensor entities
        temp_sensor_id = "sensor.melcloudhome_0efc_9abc_room_temperature"
        assert temp_sensor_id in entities
        assert entities[temp_sensor_id]["state"] == "20.0"


@pytest.mark.asyncio
async def test_diagnostics_includes_user_context_data(hass: HomeAssistant) -> None:
    """Test diagnostics includes detailed user context with buildings and units."""
    # Create mock data with multiple units
    unit1 = create_mock_unit(
        unit_id="unit-1",
        name="Living Room",
        power=True,
        operation_mode="Heat",
        set_temperature=22.0,
        room_temperature=20.5,
        has_energy_meter=True,
    )
    unit2 = create_mock_unit(
        unit_id="unit-2",
        name="Bedroom",
        power=False,
        operation_mode="Cool",
        set_temperature=19.0,
        room_temperature=21.0,
        has_energy_meter=False,
    )

    building = create_mock_building(
        building_id="building-1",
        name="Home",
        units=[unit1, unit2],
    )
    mock_context = create_mock_user_context(buildings=[building])

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        # Setup mock client
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        # Create and setup config entry
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Get diagnostics data
        diagnostics = await async_get_config_entry_diagnostics(hass, entry)

        # Verify user_context structure
        assert "user_context" in diagnostics
        user_context = diagnostics["user_context"]

        # Verify buildings
        assert "buildings" in user_context
        assert len(user_context["buildings"]) == 1

        building_data = user_context["buildings"][0]
        assert building_data["id"] == "building-1"
        assert building_data["name"] == "Home"
        assert building_data["unit_count"] == 2

        # Verify units
        units = building_data["units"]
        assert len(units) == 2

        # Check unit 1
        assert units[0]["id"] == "unit-1"
        assert units[0]["name"] == "Living Room"
        assert units[0]["power"] is True
        assert units[0]["operation_mode"] == "Heat"
        assert units[0]["set_temperature"] == 22.0
        assert units[0]["room_temperature"] == 20.5
        assert units[0]["has_energy_consumed_meter"] is True

        # Check unit 2
        assert units[1]["id"] == "unit-2"
        assert units[1]["name"] == "Bedroom"
        assert units[1]["power"] is False
        assert units[1]["operation_mode"] == "Cool"
        assert units[1]["set_temperature"] == 19.0
        assert units[1]["room_temperature"] == 21.0
        assert units[1]["has_energy_consumed_meter"] is False
