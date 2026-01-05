"""Tests for MELCloud Home switch entity.

Tests cover switch entity behavior through Home Assistant core interfaces only.
Follows HA best practices: test observable behavior, not implementation details.

Reference: docs/testing-best-practices.md
Run with: make test-ha
"""

from unittest.mock import AsyncMock, PropertyMock, patch

import pytest
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    CONF_EMAIL,
    CONF_PASSWORD,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.melcloudhome.const import DOMAIN

# Import shared test helpers from conftest
from .conftest import (
    MOCK_CLIENT_PATH,
    TEST_ATW_UNIT_ID,
    TEST_SWITCH_SYSTEM_POWER,
    create_mock_atw_building,
    create_mock_atw_unit,
    create_mock_atw_user_context,
)


@pytest.mark.asyncio
async def test_switch_entity_created_with_correct_attributes(
    hass: HomeAssistant,
    setup_atw_integration: MockConfigEntry,
) -> None:
    """Test switch entity is created with correct attributes."""
    # Check entity exists
    state = hass.states.get(TEST_SWITCH_SYSTEM_POWER)
    assert state is not None
    assert state.state == STATE_ON  # Mock unit has power=True by default
    assert "System Power" in state.attributes[ATTR_FRIENDLY_NAME]


@pytest.mark.asyncio
async def test_turn_on_powers_atw_system(hass: HomeAssistant) -> None:
    """Test turning on switch powers entire ATW system."""
    mock_unit = create_mock_atw_unit(power=False)
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        mock_client.set_power_atw = AsyncMock()
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Check initial state - powered off
        state = hass.states.get(TEST_SWITCH_SYSTEM_POWER)
        assert state is not None
        assert state.state == STATE_OFF

        # Call turn_on service
        await hass.services.async_call(
            SWITCH_DOMAIN,
            "turn_on",
            {"entity_id": TEST_SWITCH_SYSTEM_POWER},
            blocking=True,
        )

        # Verify API was called correctly
        await hass.async_block_till_done()
        mock_client.set_power_atw.assert_called_once_with(TEST_ATW_UNIT_ID, True)


@pytest.mark.asyncio
async def test_turn_off_powers_off_atw_system(hass: HomeAssistant) -> None:
    """Test turning off switch powers off entire ATW system."""
    mock_unit = create_mock_atw_unit(power=True)
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        mock_client.set_power_atw = AsyncMock()
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Check initial state - powered on
        state = hass.states.get(TEST_SWITCH_SYSTEM_POWER)
        assert state is not None
        assert state.state == STATE_ON

        # Call turn_off service
        await hass.services.async_call(
            SWITCH_DOMAIN,
            "turn_off",
            {"entity_id": TEST_SWITCH_SYSTEM_POWER},
            blocking=True,
        )

        # Verify API was called correctly
        await hass.async_block_till_done()
        mock_client.set_power_atw.assert_called_once_with(TEST_ATW_UNIT_ID, False)


@pytest.mark.asyncio
async def test_switch_state_reflects_system_power(hass: HomeAssistant) -> None:
    """Test switch state reflects actual system power state."""
    mock_unit_off = create_mock_atw_unit(power=False)
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit_off])]
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

        # Check state reflects power off
        state = hass.states.get(TEST_SWITCH_SYSTEM_POWER)
        assert state is not None
        assert state.state == STATE_OFF


@pytest.mark.asyncio
async def test_switch_unavailable_when_device_in_error(hass: HomeAssistant) -> None:
    """Test switch becomes unavailable when device is in error state."""
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

        # Check switch is unavailable
        state = hass.states.get(TEST_SWITCH_SYSTEM_POWER)
        assert state is not None
        assert state.state == "unavailable"
