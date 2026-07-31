"""Tests for MELCloud Home switch entity.

Tests cover switch entity behavior through Home Assistant core interfaces only.
Follows HA best practices: test observable behavior, not implementation details.

Reference: docs/testing-best-practices.md
Run with: make test-integration
"""

from unittest.mock import AsyncMock

import pytest
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import ATTR_FRIENDLY_NAME, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from .conftest import (
    TEST_ATW_UNIT_ID,
    TEST_SWITCH_SYSTEM_POWER,
    create_mock_atw_building,
    create_mock_atw_unit,
    create_mock_atw_user_context,
    setup_atw_integration_custom,
)


@pytest.mark.asyncio
async def test_switch_entity_created_with_correct_attributes(
    hass: HomeAssistant,
    setup_atw_integration,
) -> None:
    """Test switch entity is created with correct attributes."""
    state = hass.states.get(TEST_SWITCH_SYSTEM_POWER)
    assert state is not None
    assert state.state == STATE_ON
    assert "System Power" in state.attributes[ATTR_FRIENDLY_NAME]


@pytest.mark.asyncio
async def test_turn_on_powers_atw_system(hass: HomeAssistant) -> None:
    """Test turning on switch powers entire ATW system."""
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[create_mock_atw_unit(power=False)])]
    )
    _, mock_client = await setup_atw_integration_custom(hass, mock_context)
    mock_client.atw.set_power = AsyncMock()

    state = hass.states.get(TEST_SWITCH_SYSTEM_POWER)
    assert state is not None
    assert state.state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN, "turn_on", {"entity_id": TEST_SWITCH_SYSTEM_POWER}, blocking=True
    )
    await hass.async_block_till_done()

    mock_client.atw.set_power.assert_called_once_with(TEST_ATW_UNIT_ID, True)


@pytest.mark.asyncio
async def test_turn_off_powers_off_atw_system(hass: HomeAssistant) -> None:
    """Test turning off switch powers off entire ATW system."""
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[create_mock_atw_unit(power=True)])]
    )
    _, mock_client = await setup_atw_integration_custom(hass, mock_context)
    mock_client.atw.set_power = AsyncMock()

    state = hass.states.get(TEST_SWITCH_SYSTEM_POWER)
    assert state is not None
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {"entity_id": TEST_SWITCH_SYSTEM_POWER},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_client.atw.set_power.assert_called_once_with(TEST_ATW_UNIT_ID, False)


@pytest.mark.asyncio
async def test_switch_state_reflects_system_power(hass: HomeAssistant) -> None:
    """Test switch state reflects actual system power state."""
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[create_mock_atw_unit(power=False)])]
    )
    await setup_atw_integration_custom(hass, mock_context)

    state = hass.states.get(TEST_SWITCH_SYSTEM_POWER)
    assert state is not None
    assert state.state == STATE_OFF


@pytest.mark.asyncio
async def test_switch_unavailable_when_device_in_error(hass: HomeAssistant) -> None:
    """Test switch becomes unavailable when device is in error state."""
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[create_mock_atw_unit(is_in_error=True)])]
    )
    await setup_atw_integration_custom(hass, mock_context)

    state = hass.states.get(TEST_SWITCH_SYSTEM_POWER)
    assert state is not None
    assert state.state == "unavailable"
