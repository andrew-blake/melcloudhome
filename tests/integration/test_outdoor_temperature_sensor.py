"""Integration tests for outdoor temperature sensor."""

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.melcloudhome.api.models import Building, UserContext
from custom_components.melcloudhome.api.models_ata import (
    AirToAirCapabilities,
    AirToAirUnit,
)
from custom_components.melcloudhome.const import DOMAIN

# Mock at API boundary
MOCK_CLIENT_PATH = "custom_components.melcloudhome.MELCloudHomeClient"

# Test device UUIDs (match mock server IDs)
LIVING_ROOM_ID = "0efc1234-5678-9abc-def0-123456787db"  # Has outdoor sensor
BEDROOM_ID = "5b3e4321-8765-cba9-fed0-abcdef987a9b"  # No outdoor sensor
STUDY_ID = "a1b2c3d4-e5f6-7890-abcd-ef0123456789"  # Has outdoor sensor (2nd unit)
TEST_BUILDING_ID = "building-test-id"


def create_mock_unit(
    unit_id: str,
    name: str,
    has_outdoor_sensor: bool = False,
) -> AirToAirUnit:
    """Create a mock AirToAirUnit for testing."""
    unit = AirToAirUnit(
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
        is_in_error=False,
        rssi=-50,
        capabilities=AirToAirCapabilities(),
    )
    # Set outdoor temp fields based on whether device has sensor
    if has_outdoor_sensor:
        unit.has_outdoor_temp_sensor = True
        unit.outdoor_temperature = 12.0
    return unit


def create_mock_building(units: list[AirToAirUnit]) -> Building:
    """Create a mock Building for testing."""
    return Building(id=TEST_BUILDING_ID, name="Test Building", air_to_air_units=units)


def create_mock_user_context(buildings: list[Building]) -> UserContext:
    """Create a mock UserContext for testing."""
    return UserContext(buildings=buildings)


@pytest.fixture
async def setup_integration_with_outdoor_temp(hass: HomeAssistant) -> MockConfigEntry:
    """Set up integration with two devices - one with outdoor sensor, one without."""
    # Create two test devices
    living_room = create_mock_unit(
        LIVING_ROOM_ID, "Living Room AC", has_outdoor_sensor=True
    )
    bedroom = create_mock_unit(BEDROOM_ID, "Bedroom AC", has_outdoor_sensor=False)

    mock_context = create_mock_user_context(
        [create_mock_building([living_room, bedroom])]
    )

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        # Mock get_outdoor_temperature to return 12.0 for Living Room, None for Bedroom
        async def mock_get_outdoor_temp(unit_id: str) -> float | None:
            if unit_id == LIVING_ROOM_ID:
                return 12.0
            return None

        mock_client.get_outdoor_temperature = AsyncMock(
            side_effect=mock_get_outdoor_temp
        )

        # Mock ATA control client
        mock_client.ata = MagicMock()
        mock_client.ata.set_power = AsyncMock()
        mock_client.ata.set_temperature = AsyncMock()

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        return entry


async def test_outdoor_temperature_sensor_created_when_device_has_sensor(
    hass: HomeAssistant, setup_integration_with_outdoor_temp
):
    """Test outdoor temp sensor created for device with outdoor sensor."""
    # Living Room AC (0efc..7db) has outdoor sensor in mock
    entity_id = "sensor.melcloudhome_0efc_87db_outdoor_temperature"

    state = hass.states.get(entity_id)

    assert state is not None
    assert state.state == "12.0"  # Value from mock
    assert state.attributes["unit_of_measurement"] == "°C"
    assert state.attributes["device_class"] == "temperature"
    assert state.attributes["state_class"] == "measurement"


async def test_outdoor_temperature_sensor_not_created_when_no_sensor(
    hass: HomeAssistant, setup_integration_with_outdoor_temp
):
    """Test outdoor temp sensor NOT created for device without outdoor sensor."""
    # Bedroom AC (5b3e..7a9b) does not have outdoor sensor in mock
    entity_id = "sensor.melcloudhome_5b3e_7a9b_outdoor_temperature"

    state = hass.states.get(entity_id)

    assert state is None  # Entity should not exist


async def test_outdoor_temperature_updates_on_coordinator_refresh(
    hass: HomeAssistant, setup_integration_with_outdoor_temp
):
    """Test outdoor temperature value updates when coordinator refreshes."""
    entity_id = "sensor.melcloudhome_0efc_87db_outdoor_temperature"

    # Initial state
    state_before = hass.states.get(entity_id)
    assert state_before is not None
    assert state_before.state == "12.0"

    # Trigger coordinator refresh by calling the coordinator directly
    from custom_components.melcloudhome.const import DOMAIN

    coordinator = hass.data[DOMAIN][setup_integration_with_outdoor_temp.entry_id][
        "coordinator"
    ]
    await coordinator.async_request_refresh()
    await hass.async_block_till_done()

    # Value should still be 12.0 (mock returns constant)
    state_after = hass.states.get(entity_id)
    assert state_after.state == "12.0"


async def test_outdoor_temperature_unavailable_when_api_fails(
    hass: HomeAssistant,
):
    """Test outdoor temp sensor shows unavailable when API fails."""
    # Create device with outdoor sensor
    living_room = create_mock_unit(
        LIVING_ROOM_ID, "Living Room AC", has_outdoor_sensor=False
    )  # Start as False - discovery will try to enable it
    mock_context = create_mock_user_context([create_mock_building([living_room])])

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        # Mock get_outdoor_temperature to raise exception
        mock_client.get_outdoor_temperature = AsyncMock(
            side_effect=Exception("API error")
        )

        mock_client.ata = MagicMock()
        mock_client.ata.set_power = AsyncMock()

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Entity should not be created because API call failed during discovery
        entity_id = "sensor.melcloudhome_0efc_87db_outdoor_temperature"
        state = hass.states.get(entity_id)
        assert state is None  # Not created due to discovery failure


async def test_outdoor_temperature_all_units_polled_on_refresh(
    hass: HomeAssistant,
):
    """Test that ALL units with outdoor sensors get polled, not just the first.

    Regression test: a shared polling timer was consumed by the first unit
    in the loop, starving all subsequent units from ever updating.
    """
    # Create two units that BOTH have outdoor sensors
    living_room = create_mock_unit(
        LIVING_ROOM_ID, "Living Room AC", has_outdoor_sensor=True
    )
    study = create_mock_unit(STUDY_ID, "Study AC", has_outdoor_sensor=True)

    mock_context = create_mock_user_context(
        [create_mock_building([living_room, study])]
    )

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        # Return different temperatures per unit to verify both are polled
        async def mock_get_outdoor_temp(unit_id: str) -> float | None:
            if unit_id == LIVING_ROOM_ID:
                return 8.0
            if unit_id == STUDY_ID:
                return 3.0
            return None

        mock_client.get_outdoor_temperature = AsyncMock(
            side_effect=mock_get_outdoor_temp
        )

        mock_client.ata = MagicMock()
        mock_client.ata.set_power = AsyncMock()
        mock_client.ata.set_temperature = AsyncMock()

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Both sensors should exist with their respective values
        living_room_entity = "sensor.melcloudhome_0efc_87db_outdoor_temperature"
        # STUDY_ID clean: a1b2c3d4e5f678901234ef0123456789 -> first4=a1b2 last4=6789
        study_entity = "sensor.melcloudhome_a1b2_6789_outdoor_temperature"

        state_lr = hass.states.get(living_room_entity)
        state_study = hass.states.get(study_entity)

        assert state_lr is not None, "Living Room outdoor temp sensor not created"
        assert state_study is not None, "Study outdoor temp sensor not created"
        assert state_lr.state == "8.0"
        assert state_study.state == "3.0"

        # Now change the mock to return updated temps and trigger a refresh
        # after the polling interval has elapsed
        async def mock_get_outdoor_temp_updated(unit_id: str) -> float | None:
            if unit_id == LIVING_ROOM_ID:
                return 10.0
            if unit_id == STUDY_ID:
                return 1.0
            return None

        mock_client.get_outdoor_temperature = AsyncMock(
            side_effect=mock_get_outdoor_temp_updated
        )

        # Force polling interval to elapse by resetting per-unit timestamps
        coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        coordinator._last_outdoor_temp_poll.clear()

        await coordinator.async_request_refresh()
        await hass.async_block_till_done()

        # BOTH units should have updated values
        state_lr = hass.states.get(living_room_entity)
        state_study = hass.states.get(study_entity)

        assert (
            state_lr.state == "10.0"
        ), f"Living Room stuck at {state_lr.state}, expected 10.0"
        assert (
            state_study.state == "1.0"
        ), f"Study stuck at {state_study.state}, expected 1.0"
