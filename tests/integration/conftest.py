"""Fixtures for Home Assistant integration tests.

These fixtures require pytest-homeassistant-custom-component.
"""

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.melcloudhome.api.models import Building, UserContext
    from custom_components.melcloudhome.api.models_atw import AirToWaterUnit

# Import fixtures from pytest-homeassistant-custom-component
pytest_plugins = ["pytest_homeassistant_custom_component"]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations in all tests."""
    yield


# Mock path for MELCloudHomeClient in config_flow
MOCK_CLIENT_CONFIG_FLOW = (
    "custom_components.melcloudhome.config_flow.MELCloudHomeClient"
)


@pytest.fixture
def mock_melcloud_client():
    """Mock MELCloudHomeClient for config_flow tests."""
    with patch(MOCK_CLIENT_CONFIG_FLOW) as mock_client:
        client = mock_client.return_value
        client.login = AsyncMock()
        client.close = AsyncMock()
        yield client


@pytest.fixture
def mock_setup_entry():
    """Mock async_setup_entry to skip actual setup during config flow tests."""
    from custom_components.melcloudhome.const import DOMAIN

    with patch(
        f"custom_components.{DOMAIN}.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


# Mock path for MELCloudHomeClient in main integration
MOCK_CLIENT_PATH = "custom_components.melcloudhome.MELCloudHomeClient"

# Test device UUID - generates entity_id: water_heater.melcloudhome_0efc_9abc_tank
TEST_ATW_UNIT_ID = "0efc1234-5678-9abc-def0-123456789abc"
TEST_ATW_BUILDING_ID = "building-test-id"

# Test entity IDs (calculated from TEST_ATW_UNIT_ID)
# Unit ID 0efc1234-5678-9abc... → first 4 chars: 0efc, last 4 chars: 9abc
TEST_CLIMATE_ZONE1_ENTITY_ID = "climate.melcloudhome_0efc_9abc_zone_1"
TEST_WATER_HEATER_ENTITY_ID = "water_heater.melcloudhome_0efc_9abc_tank"
TEST_SWITCH_SYSTEM_POWER = "switch.melcloudhome_0efc_9abc_system_power"
TEST_SENSOR_ZONE1_TEMP = "sensor.melcloudhome_0efc_9abc_zone_1_temperature"
TEST_SENSOR_TANK_TEMP = "sensor.melcloudhome_0efc_9abc_tank_temperature"
TEST_SENSOR_ENERGY_CONSUMED = "sensor.melcloudhome_0efc_9abc_energy_consumed"
TEST_SENSOR_ENERGY_PRODUCED = "sensor.melcloudhome_0efc_9abc_energy_produced"
TEST_SENSOR_COP = "sensor.melcloudhome_0efc_9abc_cop"
TEST_BINARY_SENSOR_ERROR = "binary_sensor.melcloudhome_0efc_9abc_error_state"
TEST_BINARY_SENSOR_CONNECTION = "binary_sensor.melcloudhome_0efc_9abc_connection_state"


def create_mock_atw_unit(
    unit_id: str = TEST_ATW_UNIT_ID,
    name: str = "Test ATW Unit",
    power: bool = True,
    tank_water_temperature: float | None = 48.5,
    set_tank_water_temperature: float | None = 50.0,
    forced_hot_water_mode: bool = False,
    room_temperature_zone1: float | None = 20.0,
    set_temperature_zone1: float | None = 21.0,
    operation_mode_zone1: str = "HeatRoomTemperature",
    operation_status: str = "Stop",
    is_in_error: bool = False,
    error_code: str | None = None,
    ftc_model: int = 6,
    rssi: int | None = -50,
    has_zone2: bool = False,
    in_standby_mode: bool = False,
    has_energy_meter: bool = False,
    has_cooling_mode: bool = False,
    energy_consumed: float | None = None,
    energy_produced: float | None = None,
    cop: float | None = None,
) -> "AirToWaterUnit":
    """Create a mock AirToWaterUnit for testing.

    Uses real model class with realistic data. All parameters can be customized
    to test different scenarios (error states, forced DHW, energy monitoring, etc.).
    """
    from custom_components.melcloudhome.api.models_atw import (
        AirToWaterCapabilities,
        AirToWaterUnit,
    )

    return AirToWaterUnit(
        id=unit_id,
        name=name,
        power=power,
        in_standby_mode=in_standby_mode,
        tank_water_temperature=tank_water_temperature,
        set_tank_water_temperature=set_tank_water_temperature,
        forced_hot_water_mode=forced_hot_water_mode,
        room_temperature_zone1=room_temperature_zone1,
        set_temperature_zone1=set_temperature_zone1,
        operation_mode_zone1=operation_mode_zone1,
        operation_status=operation_status,
        has_zone2=has_zone2,
        is_in_error=is_in_error,
        error_code=error_code,
        rssi=rssi,
        ftc_model=ftc_model,
        energy_consumed=energy_consumed,
        energy_produced=energy_produced,
        cop=cop,
        capabilities=AirToWaterCapabilities(
            has_zone2=has_zone2,
            has_estimated_energy_consumption=has_energy_meter,
            has_estimated_energy_production=has_energy_meter,
            has_cooling_mode=has_cooling_mode,
        ),
    )


def create_mock_atw_building(
    building_id: str = TEST_ATW_BUILDING_ID,
    name: str = "Test Building",
    units: list | None = None,
) -> "Building":
    """Create a mock Building with ATW units for testing."""
    from custom_components.melcloudhome.api.models import Building

    if units is None:
        units = [create_mock_atw_unit()]
    return Building(id=building_id, name=name, air_to_water_units=units)


def create_mock_atw_user_context(buildings: list | None = None) -> "UserContext":
    """Create a mock UserContext with ATW buildings for testing."""
    from custom_components.melcloudhome.api.models import UserContext

    if buildings is None:
        buildings = [create_mock_atw_building()]
    return UserContext(buildings=buildings)


def create_mock_atw_energy_response(wh_value: float, measure_type: str) -> dict:
    """Create a mock ATW energy API response.

    Args:
        wh_value: Energy value in watt-hours
        measure_type: Measure type (intervalEnergyConsumed or intervalEnergyProduced)

    Returns:
        Mock API response matching MELCloud ATW format
    """
    return {
        "measureData": [
            {
                "type": measure_type,
                "values": [{"time": "2026-01-18T10:00:00Z", "value": wh_value}],
            }
        ]
    }


@pytest.fixture
async def setup_atw_integration(hass: "HomeAssistant") -> "MockConfigEntry":
    """Set up the integration with mocked ATW API client.

    Follows HA best practices:
    - Mocks at API boundary (MELCloudHomeClient)
    - Sets up through core interface (hass.config_entries.async_setup)
    - Returns config entry for test use
    - Mock persists across coordinator refresh cycles

    Use this fixture in ATW tests to ensure mock data persists correctly.
    For custom mock data, use setup_atw_integration_custom() factory.
    """
    from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.melcloudhome.const import DOMAIN

    mock_context = create_mock_atw_user_context()

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        # Mock ATW control client (composition pattern)
        mock_client.atw = MagicMock()
        mock_client.atw.set_power_atw = AsyncMock()
        mock_client.atw.set_temperature_zone1 = AsyncMock()
        mock_client.atw.set_mode_zone1 = AsyncMock()
        mock_client.atw.set_dhw_temperature = AsyncMock()
        mock_client.atw.set_forced_hot_water = AsyncMock()

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        return entry
