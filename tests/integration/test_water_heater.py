"""Tests for MELCloud Home water heater entity.

Tests cover water heater entity behavior through Home Assistant core interfaces only.
Follows HA best practices: test observable behavior, not implementation details.

Reference: docs/testing-best-practices.md
Run with: make test-integration
"""

from unittest.mock import AsyncMock

import pytest
from homeassistant.components.water_heater import (
    ATTR_OPERATION_MODE,
    STATE_ECO,
    STATE_HIGH_DEMAND,
)
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant

from .conftest import (
    TEST_ATW_UNIT_ID,
    TEST_WATER_HEATER_ENTITY_ID,
    create_mock_atw_building,
    create_mock_atw_unit,
    create_mock_atw_user_context,
    setup_atw_integration_custom,
)


@pytest.mark.asyncio
async def test_water_heater_entity_created_with_correct_attributes(
    hass: HomeAssistant,
    setup_atw_integration,
) -> None:
    """Test water heater entity is created with correct attributes."""
    state = hass.states.get("water_heater.melcloudhome_0efc_9abc_tank")
    assert state is not None
    assert state.state == STATE_ECO
    assert state.attributes[ATTR_TEMPERATURE] == 50.0
    assert state.attributes["current_temperature"] == 48.5
    assert state.attributes[ATTR_OPERATION_MODE] == STATE_ECO


@pytest.mark.asyncio
async def test_set_temperature_updates_dhw_temp(hass: HomeAssistant) -> None:
    """Test setting DHW temperature via service."""
    mock_context = create_mock_atw_user_context()
    _, mock_client = await setup_atw_integration_custom(hass, mock_context)
    mock_client.atw.set_dhw_temperature = AsyncMock()

    await hass.services.async_call(
        "water_heater",
        "set_temperature",
        {"entity_id": TEST_WATER_HEATER_ENTITY_ID, "temperature": 55},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_client.atw.set_dhw_temperature.assert_called_once_with(TEST_ATW_UNIT_ID, 55)


@pytest.mark.asyncio
async def test_set_operation_mode_eco_to_performance(hass: HomeAssistant) -> None:
    """Test changing operation mode from eco to performance."""
    mock_unit = create_mock_atw_unit(forced_hot_water_mode=False)
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )
    _, mock_client = await setup_atw_integration_custom(hass, mock_context)
    mock_client.atw.set_forced_hot_water = AsyncMock()

    state = hass.states.get(TEST_WATER_HEATER_ENTITY_ID)
    assert state.attributes[ATTR_OPERATION_MODE] == STATE_ECO

    await hass.services.async_call(
        "water_heater",
        "set_operation_mode",
        {"entity_id": TEST_WATER_HEATER_ENTITY_ID, "operation_mode": STATE_HIGH_DEMAND},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_client.atw.set_forced_hot_water.assert_called_once_with(TEST_ATW_UNIT_ID, True)


@pytest.mark.asyncio
async def test_set_operation_mode_performance_to_eco(hass: HomeAssistant) -> None:
    """Test changing operation mode from performance to eco."""
    mock_unit = create_mock_atw_unit(forced_hot_water_mode=True)
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )
    _, mock_client = await setup_atw_integration_custom(hass, mock_context)
    mock_client.atw.set_forced_hot_water = AsyncMock()

    state = hass.states.get(TEST_WATER_HEATER_ENTITY_ID)
    assert state.attributes[ATTR_OPERATION_MODE] == STATE_HIGH_DEMAND

    await hass.services.async_call(
        "water_heater",
        "set_operation_mode",
        {"entity_id": TEST_WATER_HEATER_ENTITY_ID, "operation_mode": STATE_ECO},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_client.atw.set_forced_hot_water.assert_called_once_with(
        TEST_ATW_UNIT_ID, False
    )


@pytest.mark.asyncio
async def test_current_operation_reflects_forced_dhw_mode(hass: HomeAssistant) -> None:
    """Test current_operation reflects forced_hot_water_mode."""
    mock_context = create_mock_atw_user_context(
        [
            create_mock_atw_building(
                units=[create_mock_atw_unit(forced_hot_water_mode=False)]
            )
        ]
    )
    await setup_atw_integration_custom(hass, mock_context)

    state = hass.states.get("water_heater.melcloudhome_0efc_9abc_tank")
    assert state.attributes[ATTR_OPERATION_MODE] == STATE_ECO


@pytest.mark.asyncio
async def test_availability_false_when_device_in_error(hass: HomeAssistant) -> None:
    """Test water heater unavailable when device in error."""
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[create_mock_atw_unit(is_in_error=True)])]
    )
    await setup_atw_integration_custom(hass, mock_context)

    assert (
        hass.states.get("water_heater.melcloudhome_0efc_9abc_tank").state
        == "unavailable"
    )


@pytest.mark.asyncio
async def test_extra_state_attributes_include_operation_status(
    hass: HomeAssistant,
) -> None:
    """Test extra state attributes include operation_status."""
    mock_context = create_mock_atw_user_context(
        [
            create_mock_atw_building(
                units=[create_mock_atw_unit(operation_status="HotWater")]
            )
        ]
    )
    await setup_atw_integration_custom(hass, mock_context)

    state = hass.states.get("water_heater.melcloudhome_0efc_9abc_tank")
    assert state.attributes["operation_status"] == "HotWater"
    assert "forced_dhw_active" in state.attributes
    assert "zone_heating_suspended" in state.attributes


@pytest.mark.asyncio
async def test_water_heater_with_performance_mode(hass: HomeAssistant) -> None:
    """Test water heater reflects performance mode correctly."""
    mock_context = create_mock_atw_user_context(
        [
            create_mock_atw_building(
                units=[create_mock_atw_unit(forced_hot_water_mode=True)]
            )
        ]
    )
    await setup_atw_integration_custom(hass, mock_context)

    assert (
        hass.states.get("water_heater.melcloudhome_0efc_9abc_tank").attributes[
            ATTR_OPERATION_MODE
        ]
        == STATE_HIGH_DEMAND
    )


@pytest.mark.asyncio
async def test_water_heater_device_info_matches_climate(hass: HomeAssistant) -> None:
    """Test water heater and climate entities share same device."""
    mock_context = create_mock_atw_user_context()
    await setup_atw_integration_custom(hass, mock_context)

    assert hass.states.get("water_heater.melcloudhome_0efc_9abc_tank") is not None
    assert hass.states.get("climate.melcloudhome_0efc_9abc_zone_1") is not None


@pytest.mark.asyncio
async def test_water_heater_temperature_in_range(hass: HomeAssistant) -> None:
    """Test water heater temperature within valid range (40-60°C)."""
    mock_unit = create_mock_atw_unit(
        tank_water_temperature=45.0, set_tank_water_temperature=50.0
    )
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )
    await setup_atw_integration_custom(hass, mock_context)

    state = hass.states.get("water_heater.melcloudhome_0efc_9abc_tank")
    assert state.attributes["current_temperature"] == 45.0
    assert state.attributes[ATTR_TEMPERATURE] == 50.0
    assert 40 <= state.attributes[ATTR_TEMPERATURE] <= 60


@pytest.mark.asyncio
async def test_water_heater_entity_naming_includes_tank(hass: HomeAssistant) -> None:
    """Test water heater entity ID includes 'tank' suffix."""
    mock_context = create_mock_atw_user_context()
    await setup_atw_integration_custom(hass, mock_context)

    state = hass.states.get("water_heater.melcloudhome_0efc_9abc_tank")
    assert state is not None
    assert "_tank" in state.entity_id
