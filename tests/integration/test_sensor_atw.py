"""Tests for MELCloud Home ATW sensor entities.

Tests cover sensor entity creation, state updates, and ATW-specific sensors.
Follows HA best practices: test observable behavior through hass.states, not internals.

Reference: docs/testing-best-practices.md
Run with: make test-ha
"""

from unittest.mock import AsyncMock, PropertyMock, patch

import pytest
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.melcloudhome.const import DOMAIN

from .conftest import (
    create_mock_atw_building,
    create_mock_atw_unit,
    create_mock_atw_user_context,
)

# Mock at API boundary (NOT coordinator or sensor classes)
MOCK_CLIENT_PATH = "custom_components.melcloudhome.MELCloudHomeClient"


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
