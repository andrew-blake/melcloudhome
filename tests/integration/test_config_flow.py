"""Tests for MELCloud Home config flow.

These tests require pytest-homeassistant-custom-component which provides
mock Home Assistant fixtures. They run in Docker or CI.

Run with: make test-ha
"""

from unittest.mock import MagicMock

import aiohttp
import pytest
from homeassistant.config_entries import SOURCE_RECONFIGURE
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.melcloudhome.api.exceptions import AuthenticationError
from custom_components.melcloudhome.const import DOMAIN


@pytest.mark.asyncio
async def test_reconfigure_flow_success(
    hass: HomeAssistant,
    mock_melcloud_client: MagicMock,
    mock_setup_entry,
) -> None:
    """Test successful reconfigure flow."""
    # Setup existing entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "old_password"},
        unique_id="test@example.com",
    )
    entry.add_to_hass(hass)

    # Start reconfigure flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    # Submit new password
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "new_password"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    # Verify entry updated
    assert entry.data[CONF_PASSWORD] == "new_password"
    assert entry.data[CONF_EMAIL] == "test@example.com"  # Email unchanged


@pytest.mark.asyncio
async def test_reconfigure_flow_invalid_auth(
    hass: HomeAssistant,
    mock_melcloud_client: MagicMock,
) -> None:
    """Test reconfigure flow with invalid credentials."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "old_password"},
        unique_id="test@example.com",
    )
    entry.add_to_hass(hass)

    mock_melcloud_client.login.side_effect = AuthenticationError("Invalid credentials")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "wrong_password"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


@pytest.mark.asyncio
async def test_reconfigure_flow_connection_error(
    hass: HomeAssistant,
    mock_melcloud_client: MagicMock,
) -> None:
    """Test reconfigure flow with connection error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "old_password"},
        unique_id="test@example.com",
    )
    entry.add_to_hass(hass)

    mock_melcloud_client.login.side_effect = aiohttp.ClientError("Connection failed")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "new_password"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
