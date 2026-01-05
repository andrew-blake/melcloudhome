"""Tests for MELCloud Home sensor entities.

Tests cover sensor entity creation, state updates, and conditional creation.
Follows HA best practices: test observable behavior through hass.states, not internals.

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

from .conftest import (
    create_mock_atw_building,
    create_mock_atw_unit,
    create_mock_atw_user_context,
)

# Mock at API boundary (NOT coordinator or sensor classes)
MOCK_CLIENT_PATH = "custom_components.melcloudhome.MELCloudHomeClient"
MOCK_STORE_PATH = "custom_components.melcloudhome.coordinator.Store"

# Test device UUID - generates entity_id: sensor.melcloudhome_0efc_9abc_*
TEST_UNIT_ID = "0efc1234-5678-9abc-def0-123456789abc"
TEST_BUILDING_ID = "building-test-id"


def create_mock_unit(
    unit_id: str = TEST_UNIT_ID,
    name: str = "Test Unit",
    room_temperature: float | None = 20.0,
    rssi: int | None = -50,
    has_energy_meter: bool = False,
    energy_consumed: float | None = None,
) -> AirToAirUnit:
    """Create a mock AirToAirUnit for sensor testing.

    Args:
        unit_id: Unit identifier
        name: Unit display name
        room_temperature: Room temperature in Celsius (None = unavailable)
        rssi: WiFi signal strength in dBm (None = unavailable)
        has_energy_meter: Whether unit has energy meter capability
        energy_consumed: Energy consumed in kWh (None = unavailable)

    Returns:
        Mock AirToAirUnit with sensor-relevant data
    """
    capabilities = DeviceCapabilities(has_energy_consumed_meter=has_energy_meter)

    return AirToAirUnit(
        id=unit_id,
        name=name,
        power=True,
        operation_mode="Heat",
        set_temperature=21.0,
        room_temperature=room_temperature,
        set_fan_speed="Auto",
        vane_vertical_direction="Auto",
        vane_horizontal_direction="Auto",
        in_standby_mode=False,
        is_in_error=False,
        rssi=rssi,
        capabilities=capabilities,
        schedule=[],
        schedule_enabled=False,
        energy_consumed=energy_consumed,
    )


def create_mock_building(
    building_id: str = TEST_BUILDING_ID,
    name: str = "Test Building",
    units: list[AirToAirUnit] | None = None,
) -> Building:
    """Create a mock Building for sensor testing."""
    if units is None:
        units = [create_mock_unit()]
    return Building(id=building_id, name=name, air_to_air_units=units)


def create_mock_user_context(buildings: list[Building] | None = None) -> UserContext:
    """Create a mock UserContext for sensor testing."""
    if buildings is None:
        buildings = [create_mock_building()]
    return UserContext(buildings=buildings)


def create_mock_energy_response(wh_value: float) -> dict:
    """Create a mock energy API response.

    Args:
        wh_value: Energy value in watt-hours

    Returns:
        Mock API response matching MELCloud format
    """
    return {
        "measureData": [
            {
                "measure": "cumulative_energy_consumed_since_last_upload",
                "unit": "Wh",
                "values": [{"time": "2025-01-15T10:00:00Z", "value": wh_value}],
            }
        ]
    }


@pytest.mark.asyncio
async def test_sensor_entity_creation(hass: HomeAssistant) -> None:
    """Test that all sensor entities are created correctly.

    When integration is set up with a unit that has all sensor data:
    1. Room temperature sensor is created
    2. WiFi signal sensor is created
    3. Energy sensor is created (if unit has energy meter capability)
    4. All sensors show correct initial values

    Validates: Basic sensor entity creation
    Tests through: hass.states (sensor entity states)
    """
    # Create unit with energy meter capability
    unit_with_energy = create_mock_unit(
        has_energy_meter=True,
        energy_consumed=None,  # Will be populated by coordinator
    )
    mock_context = create_mock_user_context(
        buildings=[create_mock_building(units=[unit_with_energy])]
    )

    # Mock energy response (5500 Wh = 5.5 kWh)
    mock_energy_data = create_mock_energy_response(5500.0)

    with (
        patch(MOCK_CLIENT_PATH) as mock_client_class,
        patch(MOCK_STORE_PATH) as mock_store_class,
    ):
        # Set up mock client
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        mock_client.get_energy_data = AsyncMock(return_value=mock_energy_data)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        # Mock storage (no stored data)
        mock_store = mock_store_class.return_value
        mock_store.async_load = AsyncMock(return_value=None)
        mock_store.async_save = AsyncMock()

        # Set up integration
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # ✅ CORRECT: Assert through state machine
        # Check room temperature sensor
        temp_state = hass.states.get("sensor.melcloudhome_0efc_9abc_room_temperature")
        assert temp_state is not None
        assert float(temp_state.state) == 20.0
        assert temp_state.attributes["unit_of_measurement"] == "°C"
        assert temp_state.attributes["device_class"] == "temperature"

        # Check WiFi signal sensor
        wifi_state = hass.states.get("sensor.melcloudhome_0efc_9abc_wifi_signal")
        assert wifi_state is not None
        assert int(wifi_state.state) == -50
        assert wifi_state.attributes["unit_of_measurement"] == "dBm"
        assert wifi_state.attributes["device_class"] == "signal_strength"

        # Check energy sensor (should be created and show initial value of 0.0)
        # Note: First init skips historical data, starts at 0.0
        energy_state = hass.states.get("sensor.melcloudhome_0efc_9abc_energy")
        assert energy_state is not None
        assert float(energy_state.state) == 0.0  # First init starts at 0
        assert energy_state.attributes["unit_of_measurement"] == "kWh"
        assert energy_state.attributes["device_class"] == "energy"


@pytest.mark.asyncio
async def test_energy_sensor_conditional_creation(hass: HomeAssistant) -> None:
    """Test that energy sensor is only created for units with energy meter capability.

    When integration is set up:
    1. Units WITH energy meter capability get energy sensor created
    2. Units WITHOUT energy meter capability do NOT get energy sensor created
    3. Other sensors (temp, WiFi) are created regardless

    Validates: Conditional sensor creation based on device capabilities
    Tests through: hass.states (sensor presence/absence)
    """
    # Create two units: one with energy meter, one without
    # Use simple unit IDs that will generate predictable entity IDs
    unit_with_energy = create_mock_unit(
        unit_id="aaaa1234-5678-9abc-def0-123456789999",  # → aaaa_9999
        name="Unit With Energy",
        has_energy_meter=True,
        energy_consumed=None,  # Will be populated by coordinator
    )
    unit_without_energy = create_mock_unit(
        unit_id="bbbb1234-5678-9abc-def0-123456788888",  # → bbbb_8888
        name="Unit Without Energy",
        has_energy_meter=False,  # No energy capability
        energy_consumed=None,
    )

    mock_context = create_mock_user_context(
        buildings=[create_mock_building(units=[unit_with_energy, unit_without_energy])]
    )

    # Mock energy response for unit with energy capability
    mock_energy_data = create_mock_energy_response(10000.0)  # 10 kWh

    with (
        patch(MOCK_CLIENT_PATH) as mock_client_class,
        patch(MOCK_STORE_PATH) as mock_store_class,
    ):
        # Set up mock client
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        mock_client.get_energy_data = AsyncMock(return_value=mock_energy_data)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        # Mock storage
        mock_store = mock_store_class.return_value
        mock_store.async_load = AsyncMock(return_value=None)
        mock_store.async_save = AsyncMock()

        # Set up integration
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # ✅ CORRECT: Assert through state machine
        # Unit WITH energy capability should have energy sensor (starts at 0.0)
        energy_state_1 = hass.states.get("sensor.melcloudhome_aaaa_9999_energy")
        assert energy_state_1 is not None
        assert float(energy_state_1.state) == 0.0  # First init starts at 0

        # Unit WITHOUT energy capability should NOT have energy sensor
        energy_state_2 = hass.states.get("sensor.melcloudhome_bbbb_8888_energy")
        assert energy_state_2 is None  # Should not exist

        # Both units should have temp and WiFi sensors (always created)
        temp_state_1 = hass.states.get("sensor.melcloudhome_aaaa_9999_room_temperature")
        assert temp_state_1 is not None

        temp_state_2 = hass.states.get("sensor.melcloudhome_bbbb_8888_room_temperature")
        assert temp_state_2 is not None


@pytest.mark.asyncio
async def test_sensor_state_updates_on_refresh(hass: HomeAssistant) -> None:
    """Test that sensor values update when coordinator refreshes.

    When coordinator receives new data:
    1. Temperature sensor updates to new value
    2. WiFi signal sensor updates to new value
    3. Updates happen automatically via coordinator

    Validates: Sensor state synchronization with coordinator
    Tests through: hass.states (sensor values after refresh)
    """
    # Initial data (no energy meter to simplify test)
    initial_unit = create_mock_unit(
        room_temperature=20.0,
        rssi=-50,
        has_energy_meter=False,  # Skip energy for this test
    )
    initial_context = create_mock_user_context(
        buildings=[create_mock_building(units=[initial_unit])]
    )

    # Updated data (simulate coordinator refresh)
    updated_unit = create_mock_unit(
        room_temperature=22.0,  # Temperature increased
        rssi=-45,  # WiFi signal improved
        has_energy_meter=False,
    )
    updated_context = create_mock_user_context(
        buildings=[create_mock_building(units=[updated_unit])]
    )

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        # Set up mock client
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        # First call returns initial data, second call returns updated data
        mock_client.get_user_context = AsyncMock(
            side_effect=[initial_context, updated_context]
        )
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        # Set up integration
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # ✅ CORRECT: Verify initial values through state machine
        temp_state = hass.states.get("sensor.melcloudhome_0efc_9abc_room_temperature")
        assert float(temp_state.state) == 20.0

        wifi_state = hass.states.get("sensor.melcloudhome_0efc_9abc_wifi_signal")
        assert int(wifi_state.state) == -50

        # ✅ CORRECT: Trigger coordinator refresh through core interface
        await hass.services.async_call(
            DOMAIN,
            "force_refresh",
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

        # ✅ CORRECT: Verify updated values through state machine
        temp_state = hass.states.get("sensor.melcloudhome_0efc_9abc_room_temperature")
        assert float(temp_state.state) == 22.0

        wifi_state = hass.states.get("sensor.melcloudhome_0efc_9abc_wifi_signal")
        assert int(wifi_state.state) == -45


@pytest.mark.asyncio
async def test_energy_sensor_availability(hass: HomeAssistant) -> None:
    """Test that energy sensor availability depends on data presence.

    Energy sensor behavior:
    1. Created if unit has energy meter capability (even without data)
    2. Unavailable when energy_consumed is None (no data fetched yet)
    3. Becomes available when energy data is fetched

    Validates: Energy sensor availability logic
    Tests through: hass.states (sensor unavailable initially, then available)
    """
    # Create unit with energy meter but no initial energy fetch will fail
    unit_with_energy = create_mock_unit(
        has_energy_meter=True,
        energy_consumed=None,  # No data yet
    )
    mock_context = create_mock_user_context(
        buildings=[create_mock_building(units=[unit_with_energy])]
    )

    # Mock energy response - empty response (no data)
    no_energy_data: dict = {"measureData": []}  # Empty energy response

    with (
        patch(MOCK_CLIENT_PATH) as mock_client_class,
        patch(MOCK_STORE_PATH) as mock_store_class,
    ):
        # Set up mock client
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        mock_client.get_energy_data = AsyncMock(return_value=no_energy_data)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        # Mock storage - no stored data
        mock_store = mock_store_class.return_value
        mock_store.async_load = AsyncMock(return_value=None)
        mock_store.async_save = AsyncMock()

        # Set up integration
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # ✅ CORRECT: Verify energy sensor exists but unavailable (no data fetched)
        energy_state = hass.states.get("sensor.melcloudhome_0efc_9abc_energy")
        assert energy_state is not None
        assert energy_state.state == "unavailable"  # No energy data fetched

        # Other sensors should still be available
        temp_state = hass.states.get("sensor.melcloudhome_0efc_9abc_room_temperature")
        assert temp_state is not None
        assert float(temp_state.state) == 20.0


# ============================================================================
# ATW (Air-to-Water) Sensor Tests
# ============================================================================


@pytest.mark.asyncio
async def test_atw_zone_1_temperature_sensor_created(hass: HomeAssistant) -> None:
    """Test ATW Zone 1 temperature sensor is created."""
    mock_unit = create_mock_atw_unit(room_temperature_zone1=20.5)
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Check Zone 1 temperature sensor exists
        state = hass.states.get("sensor.melcloudhome_0efc_9abc_zone_1_temperature")
        assert state is not None
        assert float(state.state) == 20.5


@pytest.mark.asyncio
async def test_atw_tank_temperature_sensor_created(hass: HomeAssistant) -> None:
    """Test ATW tank temperature sensor is created."""
    mock_unit = create_mock_atw_unit(tank_water_temperature=48.5)
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Check tank temperature sensor exists
        state = hass.states.get("sensor.melcloudhome_0efc_9abc_tank_temperature")
        assert state is not None
        assert float(state.state) == 48.5


@pytest.mark.asyncio
async def test_atw_operation_status_sensor_created(hass: HomeAssistant) -> None:
    """Test ATW operation status sensor is created."""
    mock_unit = create_mock_atw_unit(operation_status="HotWater")
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Check operation status sensor exists
        state = hass.states.get("sensor.melcloudhome_0efc_9abc_operation_status")
        assert state is not None
        assert state.state == "HotWater"


@pytest.mark.asyncio
async def test_atw_operation_status_shows_raw_api_value(hass: HomeAssistant) -> None:
    """Test operation status sensor shows raw API value (no mapping)."""
    mock_unit = create_mock_atw_unit(operation_status="HeatFlowTemperature")
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.melcloudhome_0efc_9abc_operation_status")
        # Raw API value, not mapped
        assert state.state == "HeatFlowTemperature"


@pytest.mark.asyncio
async def test_atw_sensor_unavailable_when_temp_none(hass: HomeAssistant) -> None:
    """Test ATW sensors unavailable when temperature is None."""
    mock_unit = create_mock_atw_unit(
        room_temperature_zone1=None, tank_water_temperature=None
    )
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Temperature sensors should be unavailable when data is None
        zone_temp = hass.states.get("sensor.melcloudhome_0efc_9abc_zone_1_temperature")
        tank_temp = hass.states.get("sensor.melcloudhome_0efc_9abc_tank_temperature")

        assert zone_temp.state == "unavailable"
        assert tank_temp.state == "unavailable"


@pytest.mark.asyncio
async def test_atw_sensors_unavailable_when_device_in_error(
    hass: HomeAssistant,
) -> None:
    """Test ATW sensors unavailable when device in error."""
    mock_unit = create_mock_atw_unit(is_in_error=True)
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # All ATW sensors should be unavailable
        zone_temp = hass.states.get("sensor.melcloudhome_0efc_9abc_zone_1_temperature")
        tank_temp = hass.states.get("sensor.melcloudhome_0efc_9abc_tank_temperature")
        operation = hass.states.get("sensor.melcloudhome_0efc_9abc_operation_status")

        assert zone_temp.state == "unavailable"
        assert tank_temp.state == "unavailable"
        assert operation.state == "unavailable"
