"""Tests for MELCloud Home config flow.

These tests require pytest-homeassistant-custom-component which provides
mock Home Assistant fixtures. They run in Docker or CI.

Run with: make test-integration
"""

from unittest.mock import MagicMock

import aiohttp
import pytest
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_RECONFIGURE
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
    # Ensure password wasn't updated
    assert entry.data[CONF_PASSWORD] == "old_password"


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
async def test_user_flow_creates_entry(
    hass: HomeAssistant,
    mock_melcloud_client: MagicMock,
    mock_setup_entry,
) -> None:
    """Test user flow successfully creates config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password123"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "MELCloud Home"
    assert result["data"][CONF_EMAIL] == "test@example.com"
    assert result["data"][CONF_PASSWORD] == "password123"


@pytest.mark.asyncio
async def test_user_flow_invalid_auth(
    hass: HomeAssistant,
    mock_melcloud_client: MagicMock,
) -> None:
    """Test user flow with invalid credentials."""
    mock_melcloud_client.login.side_effect = AuthenticationError("Invalid credentials")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: "test@example.com", CONF_PASSWORD: "wrong_password"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


@pytest.mark.asyncio
async def test_user_flow_connection_error(
    hass: HomeAssistant,
    mock_melcloud_client: MagicMock,
) -> None:
    """Test user flow with connection error."""
    from custom_components.melcloudhome.api.exceptions import ApiError

    mock_melcloud_client.login.side_effect = ApiError("Cannot connect")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password123"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.asyncio
async def test_user_flow_duplicate_account(
    hass: HomeAssistant,
    mock_melcloud_client: MagicMock,
    mock_setup_entry,
) -> None:
    """Test user flow rejects duplicate accounts."""
    # Setup existing entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password123"},
        unique_id="test@example.com",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password123"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.asyncio
async def test_user_flow_unexpected_error(
    hass: HomeAssistant,
    mock_melcloud_client: MagicMock,
) -> None:
    """Test user flow with unexpected error."""
    mock_melcloud_client.login.side_effect = ValueError("Unexpected error")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password123"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


@pytest.mark.asyncio
async def test_debug_mode_defaults_to_false(
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


@pytest.mark.asyncio
async def test_reauth_flow_success(
    hass: HomeAssistant,
    mock_melcloud_client: MagicMock,
    mock_setup_entry,
) -> None:
    """Test successful reauth flow when credentials expire."""
    # Setup existing entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "old_password"},
        unique_id="test@example.com",
    )
    entry.add_to_hass(hass)

    # Start reauth flow (simulating what HA does when ConfigEntryAuthFailed raised)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "entry_id": entry.entry_id,
            "unique_id": entry.unique_id,
        },
        data=entry.data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    # Submit new password
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "new_password"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    # Wait for the reload task to complete
    await hass.async_block_till_done()

    # Verify entry updated
    assert entry.data[CONF_PASSWORD] == "new_password"
    assert entry.data[CONF_EMAIL] == "test@example.com"  # Email unchanged


@pytest.mark.asyncio
async def test_reauth_flow_invalid_auth(
    hass: HomeAssistant,
    mock_melcloud_client: MagicMock,
) -> None:
    """Test reauth flow with invalid credentials."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "old_password"},
        unique_id="test@example.com",
    )
    entry.add_to_hass(hass)

    mock_melcloud_client.login.side_effect = AuthenticationError("Invalid credentials")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "entry_id": entry.entry_id,
            "unique_id": entry.unique_id,
        },
        data=entry.data,
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "wrong_password"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


@pytest.mark.asyncio
async def test_reauth_flow_connection_error(
    hass: HomeAssistant,
    mock_melcloud_client: MagicMock,
) -> None:
    """Test reauth flow with connection error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "old_password"},
        unique_id="test@example.com",
    )
    entry.add_to_hass(hass)

    mock_melcloud_client.login.side_effect = aiohttp.ClientError("Connection failed")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "entry_id": entry.entry_id,
            "unique_id": entry.unique_id,
        },
        data=entry.data,
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "new_password"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


# Session cleanup tests - verify client.close() is always called


@pytest.mark.asyncio
async def test_user_flow_closes_session_on_auth_error(
    hass: HomeAssistant,
    mock_melcloud_client: MagicMock,
) -> None:
    """Test that client session is closed when authentication fails."""
    mock_melcloud_client.login.side_effect = AuthenticationError("Invalid credentials")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: "test@example.com", CONF_PASSWORD: "wrong_password"},
    )

    # Verify close() was called even though login failed
    mock_melcloud_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_user_flow_closes_session_on_connection_error(
    hass: HomeAssistant,
    mock_melcloud_client: MagicMock,
) -> None:
    """Test that client session is closed when connection fails."""
    from custom_components.melcloudhome.api.exceptions import ApiError

    mock_melcloud_client.login.side_effect = ApiError("Cannot connect")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password123"},
    )

    # Verify close() was called even though connection failed
    mock_melcloud_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_user_flow_closes_session_on_unexpected_error(
    hass: HomeAssistant,
    mock_melcloud_client: MagicMock,
) -> None:
    """Test that client session is closed on unexpected errors."""
    mock_melcloud_client.login.side_effect = ValueError("Unexpected error")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password123"},
    )

    # Verify close() was called even though an unexpected error occurred
    mock_melcloud_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_reauth_flow_closes_session_on_auth_error(
    hass: HomeAssistant,
    mock_melcloud_client: MagicMock,
) -> None:
    """Test that client session is closed during reauth when authentication fails."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "old_password"},
        unique_id="test@example.com",
    )
    entry.add_to_hass(hass)

    mock_melcloud_client.login.side_effect = AuthenticationError("Invalid credentials")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "entry_id": entry.entry_id,
            "unique_id": entry.unique_id,
        },
        data=entry.data,
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "wrong_password"},
    )

    # Verify close() was called even though login failed
    mock_melcloud_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_reauth_flow_closes_session_on_connection_error(
    hass: HomeAssistant,
    mock_melcloud_client: MagicMock,
) -> None:
    """Test that client session is closed during reauth when connection fails."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "old_password"},
        unique_id="test@example.com",
    )
    entry.add_to_hass(hass)

    mock_melcloud_client.login.side_effect = aiohttp.ClientError("Connection failed")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "entry_id": entry.entry_id,
            "unique_id": entry.unique_id,
        },
        data=entry.data,
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "new_password"},
    )

    # Verify close() was called even though connection failed
    mock_melcloud_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_reconfigure_flow_closes_session_on_auth_error(
    hass: HomeAssistant,
    mock_melcloud_client: MagicMock,
) -> None:
    """Test that client session is closed during reconfigure when authentication fails."""
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
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "wrong_password"},
    )

    # Verify close() was called even though login failed
    mock_melcloud_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_reconfigure_flow_closes_session_on_connection_error(
    hass: HomeAssistant,
    mock_melcloud_client: MagicMock,
) -> None:
    """Test that client session is closed during reconfigure when connection fails."""
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
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "new_password"},
    )

    # Verify close() was called even though connection failed
    mock_melcloud_client.close.assert_called_once()
