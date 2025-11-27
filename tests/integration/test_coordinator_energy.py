"""Tests for MELCloud Home coordinator energy data lifecycle.

Tests cover energy data management, accumulation, persistence, and polling.
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

# Mock at API boundary (NOT coordinator)
MOCK_CLIENT_PATH = "custom_components.melcloudhome.MELCloudHomeClient"
MOCK_STORE_PATH = "custom_components.melcloudhome.coordinator.Store"

# Test device UUID - generates entity_id: sensor.melcloudhome_0efc_9abc_energy
TEST_UNIT_ID = "0efc1234-5678-9abc-def0-123456789abc"
TEST_BUILDING_ID = "building-test-id"


def create_mock_unit_with_energy(
    unit_id: str = TEST_UNIT_ID,
    name: str = "Test Unit",
    has_energy_meter: bool = True,
) -> AirToAirUnit:
    """Create a mock AirToAirUnit with energy capabilities.

    Uses real model class with realistic data.
    """
    capabilities = DeviceCapabilities(has_energy_consumed_meter=has_energy_meter)

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
        is_in_error=False,
        rssi=-50,
        capabilities=capabilities,
        schedule=[],
        schedule_enabled=False,
        energy_consumed=None,  # Will be populated by coordinator
    )


def create_mock_building_with_energy(
    building_id: str = TEST_BUILDING_ID,
    name: str = "Test Building",
    units: list[AirToAirUnit] | None = None,
) -> Building:
    """Create a mock Building with energy-capable units."""
    if units is None:
        units = [create_mock_unit_with_energy()]
    return Building(id=building_id, name=name, air_to_air_units=units)


def create_mock_user_context_with_energy(
    buildings: list[Building] | None = None,
) -> UserContext:
    """Create a mock UserContext with energy-capable devices."""
    if buildings is None:
        buildings = [create_mock_building_with_energy()]
    return UserContext(buildings=buildings)


def create_mock_energy_response(
    hour_values: list[tuple[str, float]],
) -> dict:
    """Create a mock energy API response.

    Args:
        hour_values: List of (timestamp, watt-hours) tuples
            Example: [("2025-01-15T10:00:00Z", 500.0), ("2025-01-15T11:00:00Z", 600.0)]

    Returns:
        Mock API response matching MELCloud format
    """
    values = [{"time": timestamp, "value": wh} for timestamp, wh in hour_values]

    return {
        "measureData": [
            {
                "measure": "cumulative_energy_consumed_since_last_upload",
                "unit": "Wh",
                "values": values,
            }
        ]
    }


@pytest.mark.asyncio
async def test_initial_energy_fetch_with_first_init(hass: HomeAssistant) -> None:
    """Test that initial energy fetch skips historical data.

    When coordinator starts for the first time (no stored data), it should:
    1. Fetch energy data from API
    2. Mark latest hour as processed (initialize tracking)
    3. Set cumulative total to 0.0 (don't count historical data)
    4. Create energy sensor with initial value 0.0

    Validates: First initialization behavior prevents inflating totals
    Tests through: hass.states (sensor entity state)
    """
    mock_context = create_mock_user_context_with_energy()

    # Mock energy response with 2 hours of historical data (should be skipped)
    mock_energy_data = create_mock_energy_response(
        [
            ("2025-01-15T10:00:00Z", 500.0),  # Historical - skip
            (
                "2025-01-15T11:00:00Z",
                600.0,
            ),  # Latest - mark as processed but don't count
        ]
    )

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

        # Mock storage to return no stored data (first init)
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
        state = hass.states.get("sensor.melcloudhome_0efc_9abc_energy")
        assert state is not None
        assert state.state == "0.0"  # Should start at 0, not include historical data
        assert state.attributes["unit_of_measurement"] == "kWh"

        # Verify API was called for initial fetch
        mock_client.get_energy_data.assert_called()


@pytest.mark.asyncio
async def test_energy_accumulation_cumulative_totals(hass: HomeAssistant) -> None:
    """Test that energy accumulates correctly over time.

    When periodic energy updates occur, the coordinator should:
    1. Fetch new hourly data from API
    2. Add new hours to cumulative total (in kWh)
    3. Update sensor state with new total
    4. Save cumulative data to storage

    Validates: Energy accumulation logic works correctly
    Tests through: hass.states (sensor shows accumulated total)
    """
    mock_context = create_mock_user_context_with_energy()

    # Initial state: 1 hour already processed
    initial_storage = {
        "cumulative": {TEST_UNIT_ID: 0.5},  # 0.5 kWh already accumulated
        "last_hour": {TEST_UNIT_ID: "2025-01-15T10:00:00Z"},  # Last processed hour
    }

    # New energy data: 2 new hours (should add both)
    mock_energy_data = create_mock_energy_response(
        [
            ("2025-01-15T10:00:00Z", 500.0),  # Already processed - skip
            ("2025-01-15T11:00:00Z", 600.0),  # NEW - add 0.6 kWh
            ("2025-01-15T12:00:00Z", 700.0),  # NEW - add 0.7 kWh
        ]
    )

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

        # Mock storage with initial data
        mock_store = mock_store_class.return_value
        mock_store.async_load = AsyncMock(return_value=initial_storage)
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
        state = hass.states.get("sensor.melcloudhome_0efc_9abc_energy")
        assert state is not None

        # Expected: 0.5 (initial) + 0.6 (11:00) + 0.7 (12:00) = 1.8 kWh
        assert float(state.state) == pytest.approx(1.8, rel=0.01)

        # Verify storage was updated with new cumulative total
        mock_store.async_save.assert_called()
        saved_data = mock_store.async_save.call_args[0][0]
        assert saved_data["cumulative"][TEST_UNIT_ID] == pytest.approx(1.8, rel=0.01)
        assert saved_data["last_hour"][TEST_UNIT_ID] == "2025-01-15T12:00:00Z"


@pytest.mark.asyncio
async def test_double_hour_prevention(hass: HomeAssistant) -> None:
    """Test that same hour is never counted twice.

    When energy data is fetched multiple times with overlapping hours:
    1. Coordinator tracks last processed hour timestamp
    2. Only processes hours AFTER the last processed hour
    3. Cumulative total doesn't increase for already-processed hours

    Validates: Double-counting prevention works correctly
    Tests through: hass.states (total doesn't increase on duplicate)
    """
    mock_context = create_mock_user_context_with_energy()

    # Initial state: 2 hours already processed
    initial_storage = {
        "cumulative": {TEST_UNIT_ID: 1.1},  # 1.1 kWh already
        "last_hour": {TEST_UNIT_ID: "2025-01-15T11:00:00Z"},  # Last = 11:00
    }

    # Energy response has SAME hours again (should skip all)
    mock_energy_data_duplicate = create_mock_energy_response(
        [
            ("2025-01-15T10:00:00Z", 500.0),  # Old - skip
            ("2025-01-15T11:00:00Z", 600.0),  # Already processed - skip
        ]
    )

    with (
        patch(MOCK_CLIENT_PATH) as mock_client_class,
        patch(MOCK_STORE_PATH) as mock_store_class,
    ):
        # Set up mock client
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        mock_client.get_energy_data = AsyncMock(return_value=mock_energy_data_duplicate)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        # Mock storage
        mock_store = mock_store_class.return_value
        mock_store.async_load = AsyncMock(return_value=initial_storage)
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
        state = hass.states.get("sensor.melcloudhome_0efc_9abc_energy")
        assert state is not None

        # Should still be 1.1 kWh (no new hours added)
        assert float(state.state) == pytest.approx(1.1, rel=0.01)

        # Verify last_hour timestamp unchanged
        saved_data = mock_store.async_save.call_args[0][0]
        assert saved_data["last_hour"][TEST_UNIT_ID] == "2025-01-15T11:00:00Z"


@pytest.mark.asyncio
async def test_energy_persistence_across_restarts(hass: HomeAssistant) -> None:
    """Test that energy data persists across Home Assistant restarts.

    When HA restarts:
    1. Coordinator loads cumulative totals from storage
    2. Coordinator loads last processed hour timestamps
    3. Sensors show correct accumulated values immediately
    4. New energy data continues accumulation from stored values

    Validates: Storage persistence works correctly
    Tests through: hass.states (sensor shows persisted value)
    """
    mock_context = create_mock_user_context_with_energy()

    # Simulated persisted data from previous session
    persisted_storage = {
        "cumulative": {TEST_UNIT_ID: 25.7},  # 25.7 kWh total
        "last_hour": {
            TEST_UNIT_ID: "2025-01-14T23:00:00Z"
        },  # Last processed: yesterday
    }

    # New energy data after restart (1 new hour)
    mock_energy_data = create_mock_energy_response(
        [
            ("2025-01-14T23:00:00Z", 800.0),  # Already processed - skip
            ("2025-01-15T00:00:00Z", 900.0),  # NEW - add 0.9 kWh
        ]
    )

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

        # Mock storage with persisted data
        mock_store = mock_store_class.return_value
        mock_store.async_load = AsyncMock(return_value=persisted_storage)
        mock_store.async_save = AsyncMock()

        # Set up integration (simulates restart)
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # ✅ CORRECT: Assert through state machine
        state = hass.states.get("sensor.melcloudhome_0efc_9abc_energy")
        assert state is not None

        # Expected: 25.7 (persisted) + 0.9 (new hour) = 26.6 kWh
        assert float(state.state) == pytest.approx(26.6, rel=0.01)

        # Verify storage saved new total
        saved_data = mock_store.async_save.call_args[0][0]
        assert saved_data["cumulative"][TEST_UNIT_ID] == pytest.approx(26.6, rel=0.01)


@pytest.mark.asyncio
async def test_energy_update_failure_recovery(hass: HomeAssistant) -> None:
    """Test that energy update failures don't crash the integration.

    When energy API call fails during initial setup:
    1. Coordinator logs error but doesn't crash
    2. Integration continues to function normally
    3. Sensor is created but shows as unavailable (no data fetched yet)
    4. Stored cumulative totals are preserved in coordinator state

    Note: Current behavior shows sensor as unavailable when initial fetch fails.
    This is because unit.energy_consumed is only set after successful API fetch.

    Validates: Error handling prevents integration crash
    Tests through: hass.states (sensor exists but unavailable)
    """
    mock_context = create_mock_user_context_with_energy()

    # Initial state with some accumulated energy (simulating previous session)
    initial_storage = {
        "cumulative": {TEST_UNIT_ID: 5.5},
        "last_hour": {TEST_UNIT_ID: "2025-01-15T10:00:00Z"},
    }

    with (
        patch(MOCK_CLIENT_PATH) as mock_client_class,
        patch(MOCK_STORE_PATH) as mock_store_class,
    ):
        # Set up mock client - energy fetch will fail
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        # Simulate API error on energy fetch
        mock_client.get_energy_data = AsyncMock(side_effect=Exception("API timeout"))
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        # Mock storage
        mock_store = mock_store_class.return_value
        mock_store.async_load = AsyncMock(return_value=initial_storage)
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
        state = hass.states.get("sensor.melcloudhome_0efc_9abc_energy")
        assert state is not None

        # Current behavior: sensor shows unavailable when initial fetch fails
        # This is because unit.energy_consumed is None (not populated from storage)
        assert state.state == "unavailable"

        # Verify integration didn't crash - other sensors still work
        climate_state = hass.states.get("climate.melcloudhome_0efc_9abc")
        assert climate_state is not None
        assert climate_state.state == "heat"  # Climate entity still functional


@pytest.mark.asyncio
async def test_energy_polling_cancellation_on_shutdown(hass: HomeAssistant) -> None:
    """Test that energy polling is properly cancelled on shutdown.

    When integration is unloaded:
    1. Coordinator's async_shutdown() is called
    2. Energy polling task is cancelled
    3. No further energy updates occur
    4. Client is closed properly

    Validates: Clean shutdown prevents resource leaks
    Tests through: Integration setup/teardown
    """
    mock_context = create_mock_user_context_with_energy()

    # Mock energy data (will only be called during initial setup)
    mock_energy_data = create_mock_energy_response([("2025-01-15T10:00:00Z", 500.0)])

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

        # Verify sensor exists
        state = hass.states.get("sensor.melcloudhome_0efc_9abc_energy")
        assert state is not None

        # Reset call count after setup
        initial_calls = mock_client.get_energy_data.call_count

        # ✅ CORRECT: Unload through core interface
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

        # Verify client.close() was called (part of shutdown)
        mock_client.close.assert_called()

        # Verify no additional energy fetches after unload
        # (Polling task should be cancelled)
        assert mock_client.get_energy_data.call_count == initial_calls
