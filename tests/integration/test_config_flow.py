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
from custom_components.melcloudhome.const import CONF_DEBUG_MODE, DOMAIN


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
        CONF_DEBUG_MODE: False,
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


@pytest.mark.asyncio
async def test_debug_mode_hidden_by_default(
    hass: HomeAssistant,
    mock_melcloud_client: MagicMock,
) -> None:
    """Test that debug_mode is hidden when advanced options disabled."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user", "show_advanced_options": False},
    )

    # Verify form schema doesn't include debug_mode
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    # Check schema doesn't have CONF_DEBUG_MODE key
    assert not any(CONF_DEBUG_MODE in str(k) for k in result["data_schema"].schema)


@pytest.mark.asyncio
async def test_debug_mode_shown_when_advanced(
    hass: HomeAssistant,
    mock_melcloud_client: MagicMock,
) -> None:
    """Test that debug_mode is shown when advanced options enabled."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user", "show_advanced_options": True},
    )

    # Verify form schema includes debug_mode
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert any(CONF_DEBUG_MODE in str(k) for k in result["data_schema"].schema)


@pytest.mark.asyncio
async def test_debug_mode_defaults_false_when_hidden(
    hass: HomeAssistant,
    mock_melcloud_client: MagicMock,
    mock_setup_entry,
) -> None:
    """Test that debug_mode defaults to False when field hidden."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user", "show_advanced_options": False},
    )

    # Submit without debug_mode field
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password123"},
    )

    # Verify entry created with debug_mode=False
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEBUG_MODE] is False


@pytest.mark.asyncio
async def test_debug_mode_true_when_explicitly_set(
    hass: HomeAssistant,
    mock_melcloud_client: MagicMock,
    mock_setup_entry,
) -> None:
    """Test that debug_mode=True is preserved when explicitly set."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user", "show_advanced_options": True},
    )

    # Submit WITH debug_mode field
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "password123",
            CONF_DEBUG_MODE: True,
        },
    )

    # Verify entry created with debug_mode=True
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEBUG_MODE] is True
    assert result["title"] == "MELCloud Home (Debug)"
