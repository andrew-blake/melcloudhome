"""Tests for MELCloud Home ATW binary sensor entities.

Tests cover ATW-specific binary sensors including forced DHW mode.
Follows HA best practices: test observable behavior through hass.states, not internals.

Reference: docs/testing-best-practices.md
Run with: make test-ha
"""

from unittest.mock import AsyncMock, PropertyMock, patch

import pytest
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, STATE_OFF, STATE_ON
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
async def test_atw_error_state_sensor_created(hass: HomeAssistant) -> None:
    """Test ATW error state binary sensor is created."""
    mock_unit = create_mock_atw_unit(is_in_error=False)
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

        # Check error state sensor exists
        state = hass.states.get("binary_sensor.melcloudhome_0efc_9abc_error_state")
        assert state is not None
        assert state.state == STATE_OFF  # No error


@pytest.mark.asyncio
async def test_atw_connection_state_sensor_created(hass: HomeAssistant) -> None:
    """Test ATW connection state binary sensor is created."""
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

        # Check connection state sensor exists
        state = hass.states.get("binary_sensor.melcloudhome_0efc_9abc_connection_state")
        assert state is not None
        assert state.state == STATE_ON  # Connected


@pytest.mark.asyncio
async def test_atw_forced_dhw_active_sensor_created(hass: HomeAssistant) -> None:
    """Test ATW forced DHW active binary sensor is created (ATW-specific)."""
    mock_unit = create_mock_atw_unit(forced_hot_water_mode=True)
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

        # Check forced DHW active sensor exists
        state = hass.states.get(
            "binary_sensor.melcloudhome_0efc_9abc_forced_dhw_active"
        )
        assert state is not None
        assert state.state == STATE_ON  # Forced DHW is active


@pytest.mark.asyncio
async def test_atw_error_state_on_when_device_in_error(hass: HomeAssistant) -> None:
    """Test error state sensor is ON when device in error."""
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

        state = hass.states.get("binary_sensor.melcloudhome_0efc_9abc_error_state")
        assert state is not None
        assert state.state == STATE_ON  # Device in error


@pytest.mark.asyncio
async def test_atw_forced_dhw_reflects_device_mode(hass: HomeAssistant) -> None:
    """Test forced DHW sensor reflects device forced_hot_water_mode."""
    # Test with forced DHW OFF
    mock_unit = create_mock_atw_unit(forced_hot_water_mode=False)
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

        state = hass.states.get(
            "binary_sensor.melcloudhome_0efc_9abc_forced_dhw_active"
        )
        assert state is not None
        assert state.state == STATE_OFF  # Forced DHW not active


@pytest.mark.asyncio
async def test_atw_connection_always_available(hass: HomeAssistant) -> None:
    """Test ATW connection sensor is always available (reports connection status)."""
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

        # Connection sensor should always be available
        state = hass.states.get("binary_sensor.melcloudhome_0efc_9abc_connection_state")
        assert state is not None
        assert state.state == STATE_ON  # Connected
