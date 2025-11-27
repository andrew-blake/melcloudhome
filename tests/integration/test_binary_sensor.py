"""Tests for MELCloud Home binary sensor entities.

Tests cover binary sensor entity creation, connection/error state reporting.
Follows HA best practices: test observable behavior through hass.states, not internals.

Reference: docs/testing-best-practices.md
Run with: make test-ha
"""

from unittest.mock import AsyncMock, PropertyMock, patch

import pytest
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.melcloudhome.api.models import (
    AirToAirUnit,
    Building,
    DeviceCapabilities,
    UserContext,
)
from custom_components.melcloudhome.const import DOMAIN

# Mock at API boundary (NOT coordinator or sensor classes)
MOCK_CLIENT_PATH = "custom_components.melcloudhome.MELCloudHomeClient"

# Test device identifiers
TEST_UNIT_ID = "0efc1234-5678-9abc-def0-123456789abc"
TEST_BUILDING_ID = "building-test-id"


def create_mock_unit(
    unit_id: str = TEST_UNIT_ID,
    name: str = "Test Unit",
    is_in_error: bool = False,
) -> AirToAirUnit:
    """Create a mock AirToAirUnit for binary sensor testing."""
    capabilities = DeviceCapabilities(has_energy_consumed_meter=False)

    return AirToAirUnit(
        id=unit_id,
        name=name,
        power=True,
        operation_mode="Heat",
        set_temperature=21.0,
        room_temperature=20.0,
        set_fan_speed="Auto",
        vane_vertical_direction="Auto",
        vane_horizontal_direction="Auto",
        in_standby_mode=False,
        is_in_error=is_in_error,
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
    """Create a mock Building for binary sensor testing."""
    if units is None:
        units = [create_mock_unit()]
    return Building(id=building_id, name=name, air_to_air_units=units)


def create_mock_user_context(buildings: list[Building] | None = None) -> UserContext:
    """Create a mock UserContext for binary sensor testing."""
    if buildings is None:
        buildings = [create_mock_building()]
    return UserContext(buildings=buildings)


@pytest.mark.asyncio
async def test_binary_sensor_entity_creation(hass: HomeAssistant) -> None:
    """Test that binary sensor entities are created for each unit."""
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

        # Verify binary sensors created (entity ID from UUID: 0efc1234-...9abc)
        error_sensor_id = "binary_sensor.melcloudhome_0efc_9abc_error_state"
        connection_sensor_id = "binary_sensor.melcloudhome_0efc_9abc_connection_state"

        # Check error state sensor exists
        error_state = hass.states.get(error_sensor_id)
        assert error_state is not None
        assert error_state.attributes["device_class"] == "problem"

        # Check connection state sensor exists
        connection_state = hass.states.get(connection_sensor_id)
        assert connection_state is not None
        assert connection_state.attributes["device_class"] == "connectivity"


@pytest.mark.asyncio
async def test_error_state_sensor_reflects_unit_status(hass: HomeAssistant) -> None:
    """Test that error state sensor reflects unit error status."""
    # Create unit with error
    unit_with_error = create_mock_unit(is_in_error=True)
    building = create_mock_building(units=[unit_with_error])
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

        # Check error state sensor shows error (ON = problem)
        error_sensor_id = "binary_sensor.melcloudhome_0efc_9abc_error_state"
        error_state = hass.states.get(error_sensor_id)
        assert error_state is not None
        assert error_state.state == STATE_ON  # ON = problem exists

        # Now create unit without error and update
        unit_no_error = create_mock_unit(is_in_error=False)
        building_updated = create_mock_building(units=[unit_no_error])
        mock_context_updated = create_mock_user_context(buildings=[building_updated])
        mock_client.get_user_context = AsyncMock(return_value=mock_context_updated)

        # Trigger coordinator refresh
        await hass.services.async_call(
            DOMAIN,
            "force_refresh",
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

        # Check error state sensor now shows no error (OFF = no problem)
        error_state = hass.states.get(error_sensor_id)
        assert error_state.state == STATE_OFF  # OFF = no problem


@pytest.mark.asyncio
async def test_connection_state_sensor_reflects_coordinator_status(
    hass: HomeAssistant,
) -> None:
    """Test that connection state sensor reflects coordinator update success."""
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

        # Check connection state sensor shows connected (ON = connected)
        connection_sensor_id = "binary_sensor.melcloudhome_0efc_9abc_connection_state"
        connection_state = hass.states.get(connection_sensor_id)
        assert connection_state is not None
        assert connection_state.state == STATE_ON  # ON = connected

        # Simulate coordinator update failure
        from custom_components.melcloudhome.api.exceptions import ApiError

        mock_client.get_user_context = AsyncMock(
            side_effect=ApiError("Connection failed")
        )

        # Trigger coordinator refresh (will fail)
        await hass.services.async_call(
            DOMAIN,
            "force_refresh",
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

        # Check connection state sensor now shows disconnected (OFF = disconnected)
        connection_state = hass.states.get(connection_sensor_id)
        assert connection_state.state == STATE_OFF  # OFF = disconnected


@pytest.mark.asyncio
async def test_error_sensor_unavailable_when_coordinator_fails(
    hass: HomeAssistant,
) -> None:
    """Test that error state sensor becomes unavailable when coordinator fails."""
    mock_context = create_mock_user_context()

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        # Setup mock client - initially working
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

        # Error sensor should be available initially
        error_sensor_id = "binary_sensor.melcloudhome_0efc_9abc_error_state"
        error_state = hass.states.get(error_sensor_id)
        assert error_state is not None
        assert error_state.state != "unavailable"

        # Simulate coordinator failure
        from custom_components.melcloudhome.api.exceptions import ApiError

        mock_client.get_user_context = AsyncMock(
            side_effect=ApiError("Connection failed")
        )

        # Trigger coordinator refresh (will fail)
        await hass.services.async_call(
            DOMAIN,
            "force_refresh",
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

        # Error sensor should become unavailable
        error_state = hass.states.get(error_sensor_id)
        assert error_state.state == "unavailable"


@pytest.mark.asyncio
async def test_connection_sensor_always_available(hass: HomeAssistant) -> None:
    """Test that connection state sensor is always available, even when coordinator fails."""
    mock_context = create_mock_user_context()

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        # Setup mock client that will fail
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

        # Simulate coordinator failure
        from custom_components.melcloudhome.api.exceptions import ApiError

        mock_client.get_user_context = AsyncMock(
            side_effect=ApiError("Connection failed")
        )

        # Trigger coordinator refresh (will fail)
        await hass.services.async_call(
            DOMAIN,
            "force_refresh",
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

        # Connection sensor should still be available (not "unavailable")
        # It should be OFF (indicating connection failure), but not unavailable
        connection_sensor_id = "binary_sensor.melcloudhome_0efc_9abc_connection_state"
        connection_state = hass.states.get(connection_sensor_id)
        assert connection_state is not None
        assert connection_state.state == STATE_OFF  # Shows disconnection
        # Not checking != "unavailable" because that's implicit in state == STATE_OFF
