"""Tests for MELCloud Home ATW sensor entities.

Tests cover sensor entity creation, state updates, and ATW-specific sensors.
Follows HA best practices: test observable behavior through hass.states, not internals.

Reference: docs/testing-best-practices.md
Run with: make test-integration
"""

from unittest.mock import AsyncMock, PropertyMock, patch

import pytest
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.melcloudhome.const import DOMAIN

from .conftest import (
    TEST_SENSOR_COP,
    TEST_SENSOR_ENERGY_CONSUMED,
    TEST_SENSOR_ENERGY_PRODUCED,
    create_mock_atw_building,
    create_mock_atw_energy_response,
    create_mock_atw_unit,
    create_mock_atw_user_context,
)

# Mock at API boundary (NOT coordinator or sensor classes)
MOCK_CLIENT_PATH = "custom_components.melcloudhome.MELCloudHomeClient"
MOCK_STORE_PATH = "custom_components.melcloudhome.energy_tracker_base.Store"


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
    mock_unit = create_mock_atw_unit(operation_status="Heating")
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
        assert state.state == "Heating"


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


# =============================================================================
# Energy Sensor Tests
# =============================================================================


@pytest.mark.asyncio
async def test_atw_energy_sensors_created_when_capability_present(
    hass: HomeAssistant,
) -> None:
    """Test energy sensors are created when device has energy meter capability."""
    mock_unit = create_mock_atw_unit(
        has_energy_meter=True,
    )
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )

    # Mock energy responses (in watt-hours)
    mock_consumed = create_mock_atw_energy_response(
        10000.0, "intervalEnergyConsumed"
    )  # 10 kWh
    mock_produced = create_mock_atw_energy_response(
        40000.0, "intervalEnergyProduced"
    )  # 40 kWh

    with (
        patch(MOCK_CLIENT_PATH) as mock_client_class,
        patch(MOCK_STORE_PATH) as mock_store_class,
    ):
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        # Mock ATW energy API methods
        mock_client.atw = AsyncMock()
        mock_client.atw.get_energy_consumed = AsyncMock(return_value=mock_consumed)
        mock_client.atw.get_energy_produced = AsyncMock(return_value=mock_produced)

        # Mock storage (both ATA and ATW trackers use the same Store class)
        mock_store = mock_store_class.return_value
        mock_store.async_load = AsyncMock(return_value=None)
        mock_store.async_save = AsyncMock()

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Check all 3 energy sensors exist
        consumed = hass.states.get(TEST_SENSOR_ENERGY_CONSUMED)
        produced = hass.states.get(TEST_SENSOR_ENERGY_PRODUCED)
        cop = hass.states.get(TEST_SENSOR_COP)

        assert consumed is not None
        assert produced is not None
        assert cop is not None

        # Check values (first init starts at 0.0 for consumed/produced)
        # COP = 0.0 / 0.0 = None (can't divide by zero)
        assert float(consumed.state) == 0.0
        assert float(produced.state) == 0.0
        # COP is unavailable on first init (consumed = 0)
        assert cop.state == "unavailable"


@pytest.mark.asyncio
async def test_atw_energy_sensors_not_created_without_capability(
    hass: HomeAssistant,
) -> None:
    """Test energy sensors are NOT created when device lacks energy capability."""
    mock_unit = create_mock_atw_unit(
        has_energy_meter=False,  # No energy meter
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

        # Energy sensors should NOT exist
        consumed = hass.states.get(TEST_SENSOR_ENERGY_CONSUMED)
        produced = hass.states.get(TEST_SENSOR_ENERGY_PRODUCED)
        cop = hass.states.get(TEST_SENSOR_COP)

        assert consumed is None
        assert produced is None
        assert cop is None


@pytest.mark.asyncio
async def test_atw_energy_sensors_unavailable_when_values_none(
    hass: HomeAssistant,
) -> None:
    """Test energy sensors unavailable when energy values are None."""
    mock_unit = create_mock_atw_unit(
        has_energy_meter=True,  # Has capability
        energy_consumed=None,  # But no data yet
        energy_produced=None,
        cop=None,
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

        # Sensors created but unavailable (no data yet)
        consumed = hass.states.get(TEST_SENSOR_ENERGY_CONSUMED)
        produced = hass.states.get(TEST_SENSOR_ENERGY_PRODUCED)
        cop = hass.states.get(TEST_SENSOR_COP)

        assert consumed is not None
        assert produced is not None
        assert cop is not None

        assert consumed.state == "unavailable"
        assert produced.state == "unavailable"
        assert cop.state == "unavailable"


@pytest.mark.asyncio
async def test_atw_cop_calculation_correct(hass: HomeAssistant) -> None:
    """Test COP sensor calculates correctly from consumed and produced energy.

    On first init, energy values start at 0.0, so COP is unavailable (divide by zero).
    This test verifies the COP sensor is created and becomes unavailable when consumed=0.
    """
    mock_unit = create_mock_atw_unit(
        has_energy_meter=True,
    )
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )

    # Mock energy responses (first init)
    mock_consumed = create_mock_atw_energy_response(1000.0, "intervalEnergyConsumed")
    mock_produced = create_mock_atw_energy_response(4000.0, "intervalEnergyProduced")

    with (
        patch(MOCK_CLIENT_PATH) as mock_client_class,
        patch(MOCK_STORE_PATH) as mock_store_class,
    ):
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        # Mock ATW energy API
        mock_client.atw = AsyncMock()
        mock_client.atw.get_energy_consumed = AsyncMock(return_value=mock_consumed)
        mock_client.atw.get_energy_produced = AsyncMock(return_value=mock_produced)

        # Mock storage (no stored data - first init)
        mock_store = mock_store_class.return_value
        mock_store.async_load = AsyncMock(return_value=None)
        mock_store.async_save = AsyncMock()

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # After first init, consumed and produced start at 0.0
        # COP is unavailable (cannot divide by zero)
        consumed = hass.states.get(TEST_SENSOR_ENERGY_CONSUMED)
        produced = hass.states.get(TEST_SENSOR_ENERGY_PRODUCED)
        cop = hass.states.get(TEST_SENSOR_COP)

        assert consumed is not None
        assert produced is not None
        assert cop is not None

        # First init: values start at 0.0
        assert float(consumed.state) == 0.0
        assert float(produced.state) == 0.0
        # COP unavailable when consumed = 0 (divide by zero)
        assert cop.state == "unavailable"


@pytest.mark.asyncio
async def test_atw_energy_sensors_have_correct_device_class(
    hass: HomeAssistant,
) -> None:
    """Test energy sensors have correct device classes for Energy Dashboard."""
    mock_unit = create_mock_atw_unit(
        has_energy_meter=True,
    )
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )

    # Mock energy responses
    mock_consumed = create_mock_atw_energy_response(10000.0, "intervalEnergyConsumed")
    mock_produced = create_mock_atw_energy_response(40000.0, "intervalEnergyProduced")

    with (
        patch(MOCK_CLIENT_PATH) as mock_client_class,
        patch(MOCK_STORE_PATH) as mock_store_class,
    ):
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        # Mock ATW energy API
        mock_client.atw = AsyncMock()
        mock_client.atw.get_energy_consumed = AsyncMock(return_value=mock_consumed)
        mock_client.atw.get_energy_produced = AsyncMock(return_value=mock_produced)

        # Mock storage (both ATA and ATW trackers use the same Store class)
        mock_store = mock_store_class.return_value
        mock_store.async_load = AsyncMock(return_value=None)
        mock_store.async_save = AsyncMock()

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        consumed = hass.states.get(TEST_SENSOR_ENERGY_CONSUMED)
        produced = hass.states.get(TEST_SENSOR_ENERGY_PRODUCED)
        cop = hass.states.get(TEST_SENSOR_COP)

        # Energy sensors should have energy device class
        assert consumed.attributes.get("device_class") == "energy"
        assert produced.attributes.get("device_class") == "energy"

        # COP is dimensionless, no device class
        assert cop.attributes.get("device_class") is None

        # Energy sensors should have TOTAL_INCREASING state class
        assert consumed.attributes.get("state_class") == "total_increasing"
        assert produced.attributes.get("state_class") == "total_increasing"

        # COP should have MEASUREMENT state class
        assert cop.attributes.get("state_class") == "measurement"

        # Check units
        assert consumed.attributes.get("unit_of_measurement") == "kWh"
        assert produced.attributes.get("unit_of_measurement") == "kWh"
        assert cop.attributes.get("unit_of_measurement") is None


@pytest.mark.asyncio
async def test_atw_rssi_sensor_created(hass: HomeAssistant) -> None:
    """Test ATW WiFi signal (RSSI) sensor is created (starts unavailable until telemetry fetched)."""
    mock_unit = create_mock_atw_unit()
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

        # Check WiFi signal sensor exists with correct attributes
        wifi_state = hass.states.get("sensor.melcloudhome_0efc_9abc_wifi_signal")
        assert wifi_state is not None
        # Sensor starts unavailable (no telemetry fetched yet - that happens on schedule)
        assert wifi_state.state == "unavailable"
        assert wifi_state.attributes["unit_of_measurement"] == "dBm"
        assert wifi_state.attributes["device_class"] == "signal_strength"
