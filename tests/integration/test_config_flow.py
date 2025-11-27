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

    # Wait for the reload task to complete
    await hass.async_block_till_done()

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


@pytest.mark.asyncio
async def test_initial_user_setup_success(
    hass: HomeAssistant,
    mock_melcloud_client: MagicMock,
    mock_setup_entry,
) -> None:
    """Test successful initial user setup flow."""
    # Start user setup flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Submit credentials
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password123"},
    )

    # Verify entry created
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "MELCloud Home"
    assert result["data"] == {
        CONF_EMAIL: "test@example.com",
        CONF_PASSWORD: "password123",
    }

    # Verify client login was called
    mock_melcloud_client.login.assert_called_once_with(
        "test@example.com", "password123"
    )
    mock_melcloud_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_initial_setup_duplicate_account(
    hass: HomeAssistant,
    mock_melcloud_client: MagicMock,
    mock_setup_entry,
) -> None:
    """Test that duplicate accounts are prevented during initial setup."""
    # Create existing entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
        unique_id="test@example.com",
    )
    entry.add_to_hass(hass)

    # Try to add same account again
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: "test@example.com", CONF_PASSWORD: "different_password"},
    )

    # Verify flow aborted due to duplicate
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.asyncio
async def test_initial_setup_connection_error(
    hass: HomeAssistant,
    mock_melcloud_client: MagicMock,
) -> None:
    """Test initial setup with connection error."""
    from custom_components.melcloudhome.api.exceptions import ApiError

    # Mock connection error
    mock_melcloud_client.login.side_effect = ApiError("Connection failed")

    # Start setup flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password123"},
    )

    # Verify error shown
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert result["step_id"] == "user"
