"""Tests for MELCloud Home ATW sensor entities.

Tests cover sensor entity creation, state updates, and ATW-specific sensors.
Follows HA best practices: test observable behavior through hass.states, not internals.

Reference: docs/testing-best-practices.md
Run with: make test-integration
"""

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant

from .conftest import (
    TEST_ATW_UNIT_ID,
    TEST_SENSOR_COP,
    TEST_SENSOR_ENERGY_CONSUMED,
    TEST_SENSOR_ENERGY_PRODUCED,
    create_mock_atw_building,
    create_mock_atw_energy_response,
    create_mock_atw_unit,
    create_mock_atw_user_context,
    setup_atw_integration_custom,
)

MOCK_STORE_PATH = "custom_components.melcloudhome.energy_tracker_base.Store"


@pytest.mark.asyncio
async def test_atw_zone_1_temperature_sensor_created(hass: HomeAssistant) -> None:
    """Test ATW Zone 1 temperature sensor is created."""
    mock_unit = create_mock_atw_unit(room_temperature_zone1=20.5)
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )
    await setup_atw_integration_custom(hass, mock_context)

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
    await setup_atw_integration_custom(hass, mock_context)

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
    await setup_atw_integration_custom(hass, mock_context)

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
    await setup_atw_integration_custom(hass, mock_context)

    state = hass.states.get("sensor.melcloudhome_0efc_9abc_operation_status")
    # Raw API value, not mapped
    assert state.state == "Heating"


@pytest.mark.asyncio
async def test_atw_sensor_unknown_when_temp_none(hass: HomeAssistant) -> None:
    """Test ATW sensors read unknown when temperature is None."""
    mock_unit = create_mock_atw_unit(
        room_temperature_zone1=None, tank_water_temperature=None
    )
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )
    await setup_atw_integration_custom(hass, mock_context)

    zone_temp = hass.states.get("sensor.melcloudhome_0efc_9abc_zone_1_temperature")
    tank_temp = hass.states.get("sensor.melcloudhome_0efc_9abc_tank_temperature")

    assert zone_temp.state == "unknown"
    assert tank_temp.state == "unknown"


@pytest.mark.asyncio
async def test_atw_sensors_unavailable_when_device_in_error(
    hass: HomeAssistant,
) -> None:
    """Test ATW sensors unavailable when device in error."""
    mock_unit = create_mock_atw_unit(is_in_error=True)
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )
    await setup_atw_integration_custom(hass, mock_context)

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
    mock_unit = create_mock_atw_unit(has_energy_meter=True)
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )

    mock_consumed = create_mock_atw_energy_response(10000.0, "intervalEnergyConsumed")
    mock_produced = create_mock_atw_energy_response(40000.0, "intervalEnergyProduced")

    def configure(client: Any) -> None:
        client.atw = AsyncMock()
        client.atw.get_energy_consumed = AsyncMock(return_value=mock_consumed)
        client.atw.get_energy_produced = AsyncMock(return_value=mock_produced)

    with patch(MOCK_STORE_PATH) as mock_store_class:
        mock_store = mock_store_class.return_value
        mock_store.async_load = AsyncMock(return_value=None)
        mock_store.async_save = AsyncMock()

        await setup_atw_integration_custom(
            hass, mock_context, configure_client=configure
        )

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
        # COP is unknown on first init (consumed = 0)
        assert cop.state == "unknown"


@pytest.mark.asyncio
async def test_atw_energy_sensors_not_created_without_capability(
    hass: HomeAssistant,
) -> None:
    """Test energy sensors are NOT created when device lacks energy capability."""
    mock_unit = create_mock_atw_unit(has_energy_meter=False)
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )
    await setup_atw_integration_custom(hass, mock_context)

    assert hass.states.get(TEST_SENSOR_ENERGY_CONSUMED) is None
    assert hass.states.get(TEST_SENSOR_ENERGY_PRODUCED) is None
    assert hass.states.get(TEST_SENSOR_COP) is None


@pytest.mark.asyncio
async def test_atw_energy_sensors_unknown_when_values_none(
    hass: HomeAssistant,
) -> None:
    """Test energy sensors read unknown when energy values are None."""
    mock_unit = create_mock_atw_unit(
        has_energy_meter=True,
        energy_consumed=None,
        energy_produced=None,
        cop=None,
    )
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )
    await setup_atw_integration_custom(hass, mock_context)

    consumed = hass.states.get(TEST_SENSOR_ENERGY_CONSUMED)
    produced = hass.states.get(TEST_SENSOR_ENERGY_PRODUCED)
    cop = hass.states.get(TEST_SENSOR_COP)

    assert consumed is not None
    assert produced is not None
    assert cop is not None

    assert consumed.state == "unknown"
    assert produced.state == "unknown"
    assert cop.state == "unknown"


@pytest.mark.asyncio
async def test_atw_cop_calculation_correct(hass: HomeAssistant) -> None:
    """Test COP sensor calculates correctly from consumed and produced energy.

    On first init, energy values start at 0.0, so COP is unknown (divide by zero).
    This test verifies the COP sensor is created and reads unknown when consumed=0.
    """
    mock_unit = create_mock_atw_unit(has_energy_meter=True)
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )

    mock_consumed = create_mock_atw_energy_response(1000.0, "intervalEnergyConsumed")
    mock_produced = create_mock_atw_energy_response(4000.0, "intervalEnergyProduced")

    def configure(client: Any) -> None:
        client.atw = AsyncMock()
        client.atw.get_energy_consumed = AsyncMock(return_value=mock_consumed)
        client.atw.get_energy_produced = AsyncMock(return_value=mock_produced)

    with patch(MOCK_STORE_PATH) as mock_store_class:
        mock_store = mock_store_class.return_value
        mock_store.async_load = AsyncMock(return_value=None)
        mock_store.async_save = AsyncMock()

        await setup_atw_integration_custom(
            hass, mock_context, configure_client=configure
        )

        consumed = hass.states.get(TEST_SENSOR_ENERGY_CONSUMED)
        produced = hass.states.get(TEST_SENSOR_ENERGY_PRODUCED)
        cop = hass.states.get(TEST_SENSOR_COP)

        assert consumed is not None
        assert produced is not None
        assert cop is not None

        # First init: values start at 0.0
        assert float(consumed.state) == 0.0
        assert float(produced.state) == 0.0
        # COP unknown when consumed = 0 (divide by zero)
        assert cop.state == "unknown"


@pytest.mark.asyncio
async def test_atw_energy_sensors_have_correct_device_class(
    hass: HomeAssistant,
) -> None:
    """Test energy sensors have correct device classes for Energy Dashboard."""
    mock_unit = create_mock_atw_unit(has_energy_meter=True)
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )

    mock_consumed = create_mock_atw_energy_response(10000.0, "intervalEnergyConsumed")
    mock_produced = create_mock_atw_energy_response(40000.0, "intervalEnergyProduced")

    def configure(client: Any) -> None:
        client.atw = AsyncMock()
        client.atw.get_energy_consumed = AsyncMock(return_value=mock_consumed)
        client.atw.get_energy_produced = AsyncMock(return_value=mock_produced)

    with patch(MOCK_STORE_PATH) as mock_store_class:
        mock_store = mock_store_class.return_value
        mock_store.async_load = AsyncMock(return_value=None)
        mock_store.async_save = AsyncMock()

        await setup_atw_integration_custom(
            hass, mock_context, configure_client=configure
        )

        consumed = hass.states.get(TEST_SENSOR_ENERGY_CONSUMED)
        produced = hass.states.get(TEST_SENSOR_ENERGY_PRODUCED)
        cop = hass.states.get(TEST_SENSOR_COP)

        assert consumed.attributes.get("device_class") == "energy"
        assert produced.attributes.get("device_class") == "energy"

        # COP is dimensionless, no device class
        assert cop.attributes.get("device_class") is None

        assert consumed.attributes.get("state_class") == "total_increasing"
        assert produced.attributes.get("state_class") == "total_increasing"

        # COP should have MEASUREMENT state class
        assert cop.attributes.get("state_class") == "measurement"

        assert consumed.attributes.get("unit_of_measurement") == "kWh"
        assert produced.attributes.get("unit_of_measurement") == "kWh"
        assert cop.attributes.get("unit_of_measurement") is None


@pytest.mark.asyncio
async def test_atw_cop_last_reading_uses_older_measure(hass: HomeAssistant) -> None:
    """Test cop's last_reading is the OLDER of consumed/produced's newest buckets.

    cop is a ratio of the two measures, so it can only be as fresh as its
    staler input (issue #200 plan, Task 8 Step 2): here consumed's newest
    bucket is older than produced's, and last_reading must show the older
    (consumed's) stamp, not produced's fresher one.

    Validates: Task 8 Step 2 - the deliberate choice of the older timestamp
    Tests through: hass.states (cop sensor's last_reading attribute)
    """
    mock_unit = create_mock_atw_unit(has_energy_meter=True)
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )

    persisted_storage = {
        "cumulative": {
            TEST_ATW_UNIT_ID: {"consumed": 10.0, "produced": 40.0},
        },
        "hour_values": {
            TEST_ATW_UNIT_ID: {
                "consumed": {"2026-01-18T08:00:00Z": 5.0},
                "produced": {"2026-01-18T08:00:00Z": 20.0},
            }
        },
    }
    mock_consumed = {
        "measureData": [
            {
                "type": "intervalEnergyConsumed",
                "values": [{"time": "2026-01-18T09:00:00Z", "value": 15.0}],
            }
        ]
    }
    mock_produced = {
        "measureData": [
            {
                "type": "intervalEnergyProduced",
                "values": [{"time": "2026-01-18T11:00:00Z", "value": 20.0}],
            }
        ]
    }

    def configure(client: Any) -> None:
        client.atw = AsyncMock()
        client.atw.get_energy_consumed = AsyncMock(return_value=mock_consumed)
        client.atw.get_energy_produced = AsyncMock(return_value=mock_produced)

    with patch(MOCK_STORE_PATH) as mock_store_class:
        mock_store = mock_store_class.return_value
        mock_store.async_load = AsyncMock(return_value=persisted_storage)
        mock_store.async_save = AsyncMock()

        await setup_atw_integration_custom(
            hass, mock_context, configure_client=configure
        )

        # consumed: 10.0 + (15.0 - 0.0) = 25.0; produced: 40.0 + (20.0 - 0.0) = 60.0
        cop = hass.states.get(TEST_SENSOR_COP)
        assert cop is not None
        assert float(cop.state) == pytest.approx(2.4, rel=0.01)
        assert (
            cop.attributes["last_reading"]
            == datetime.fromisoformat("2026-01-18T09:00:00Z").isoformat()
        )


# Outdoor temperature sensor creation/unknown-state coverage lives in
# tests/integration/test_atw_outdoor_temperature_sensor.py, which mocks the
# actual comfort-graph poll (client.get_atw_outdoor_temperature) - the sole
# source of this value since issue #251. The tests formerly here predated
# that fix and passed only because their unmocked poll silently failed,
# leaving create_mock_atw_unit's directly-set value untouched; they never
# exercised real behaviour.


@pytest.mark.asyncio
async def test_atw_rssi_sensor_created(hass: HomeAssistant) -> None:
    """Test ATW WiFi signal sensor uses RSSI from the current unit context."""
    mock_unit = create_mock_atw_unit()
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )
    await setup_atw_integration_custom(hass, mock_context)

    wifi_state = hass.states.get("sensor.melcloudhome_0efc_9abc_wifi_signal")
    assert wifi_state is not None
    assert wifi_state.state == "-50"
    assert wifi_state.attributes["unit_of_measurement"] == "dBm"
    assert wifi_state.attributes["device_class"] == "signal_strength"


@pytest.mark.asyncio
async def test_telemetry_sensors_created_without_telemetry_data(
    hass: HomeAssistant,
) -> None:
    """Test flow/return sensors exist even when no telemetry has arrived.

    Regression test: creation used to be gated on the measure already being present,
    so a failed telemetry poll at setup dropped the sensor until the next reload.
    """
    # has_zone2/has_boiler so all six measures apply to this device — the zone-1 and
    # boiler pairs are capability-gated (they return a 25 placeholder on hardware that
    # lacks them, see test_sensor_atw_placeholder_gating.py), and this test is about
    # creation not being gated on a *value*.
    unit = create_mock_atw_unit(has_zone2=True, has_boiler=True)
    assert not unit.telemetry, "expected a mock ATW unit to start with no telemetry"
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[unit])]
    )
    await setup_atw_integration_custom(hass, mock_context)

    # entity_id's object-id segment comes from the translated name (see
    # initialize_entity_base() fix for #240), so "zone1" (key) reads as
    # "zone 1" (translated name) -> "zone_1" (slugified) in the entity_id.
    for measure in (
        "flow_temperature",
        "return_temperature",
        "flow_temperature_zone_1",
        "return_temperature_zone_1",
        "flow_temperature_boiler",
        "return_temperature_boiler",
    ):
        entity_id = f"sensor.melcloudhome_0efc_9abc_{measure}"
        state = hass.states.get(entity_id)
        assert state is not None, f"{entity_id} was not created"
        assert state.state == "unknown"
