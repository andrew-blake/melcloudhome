"""Tests for coordinator retry logic on session expiry."""

import asyncio
import contextlib
import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError

from custom_components.melcloudhome.api.client import MELCloudHomeClient
from custom_components.melcloudhome.api.exceptions import (
    ApiError,
    AuthenticationError,
    ServiceUnavailableError,
)
from custom_components.melcloudhome.coordinator import MELCloudHomeCoordinator


@pytest.fixture
def mock_client():
    """Create mock MELCloudHomeClient."""
    client = MELCloudHomeClient()
    client.login = AsyncMock()  # type: ignore[method-assign]
    client.close = AsyncMock()  # type: ignore[method-assign]
    return client


@pytest.fixture
def coordinator(hass, mock_client):
    """Create coordinator instance for testing."""
    return MELCloudHomeCoordinator(
        hass, mock_client, "test@example.com", "password", None
    )


@pytest.mark.asyncio
async def test_success_first_attempt(coordinator):
    """Test operation succeeds on first attempt."""
    operation = AsyncMock(return_value="success")
    result = await coordinator._execute_with_retry(operation, "test_op")

    assert result == "success"
    assert operation.call_count == 1


@pytest.mark.asyncio
async def test_session_expired_recovers(coordinator):
    """Test automatic recovery when session expires."""
    operation = AsyncMock(
        side_effect=[
            AuthenticationError("Session expired"),  # First attempt
            AuthenticationError("Session expired"),  # Double-check (still expired)
            "success",  # After re-auth
        ]
    )

    result = await coordinator._execute_with_retry(operation, "test_op")

    assert result == "success"
    assert coordinator.client.login.call_count == 1
    assert operation.call_count == 3  # First attempt + double-check + final retry


@pytest.mark.asyncio
async def test_reauth_fails_raises_config_entry_auth_failed(coordinator):
    """Test that ConfigEntryAuthFailed raised when re-auth fails."""
    operation = AsyncMock(side_effect=AuthenticationError("Session expired"))
    coordinator.client.login.side_effect = AuthenticationError("Invalid credentials")

    with pytest.raises(ConfigEntryAuthFailed, match="Re-authentication failed"):
        await coordinator._execute_with_retry(operation, "test_op")


@pytest.mark.asyncio
async def test_double_check_pattern_prevents_redundant_reauth(coordinator):
    """Test double-check pattern prevents multiple re-auth attempts."""
    operation = AsyncMock(
        side_effect=[
            AuthenticationError("Session expired"),  # First attempt fails
            "success",  # Second attempt (double-check) succeeds
        ]
    )

    result = await coordinator._execute_with_retry(operation, "test_op")

    # Should NOT call login because double-check succeeded
    assert coordinator.client.login.call_count == 0
    assert operation.call_count == 2
    assert result == "success"


@pytest.mark.asyncio
async def test_concurrent_calls_trigger_single_reauth(coordinator):
    """Test concurrent service calls trigger only ONE re-authentication."""
    reauth_count = 0
    session_valid = False  # Shared auth state

    async def mock_login(*args):
        nonlocal reauth_count, session_valid
        reauth_count += 1
        await asyncio.sleep(0.1)  # Simulate re-auth delay
        session_valid = True  # Session now valid
        return True

    async def mock_operation(name: str) -> str:
        """Mock operation that checks shared auth state."""
        if not session_valid:
            raise AuthenticationError("Expired")
        return f"success_{name}"

    coordinator.client.login.side_effect = mock_login

    results = await asyncio.gather(
        coordinator._execute_with_retry(lambda: mock_operation("1"), "op1"),
        coordinator._execute_with_retry(lambda: mock_operation("2"), "op2"),
    )

    assert results == ["success_1", "success_2"]  # type: ignore[comparison-overlap]
    assert reauth_count == 1  # CRITICAL: Only one re-auth


@pytest.mark.asyncio
async def test_final_retry_catches_auth_error(coordinator):
    """Test final retry after re-auth catches AuthenticationError (safety net)."""
    operation = AsyncMock(side_effect=AuthenticationError("Session expired"))

    with pytest.raises(ConfigEntryAuthFailed, match="after re-auth"):
        await coordinator._execute_with_retry(operation, "test_op")


@pytest.mark.asyncio
async def test_token_refresh_on_auth_error(coordinator):
    """Test that auth error triggers token refresh before full re-login."""
    coordinator.client.restore_tokens(
        "expired-token", "valid-refresh", time.time() + 3600
    )
    coordinator.client.refresh_access_token = AsyncMock()

    call_count = 0

    async def mock_operation():
        nonlocal call_count
        call_count += 1
        if call_count <= 2:  # Fails on first attempt + double-check
            raise AuthenticationError("Session expired")
        return "success"

    result = await coordinator._execute_with_retry(mock_operation, "test_op")
    assert result == "success"
    coordinator.client.refresh_access_token.assert_awaited_once()
    # login should NOT be called since refresh succeeded
    assert coordinator.client.login.call_count == 0


@pytest.mark.asyncio
async def test_persist_tokens_updates_config_entry(hass, mock_client):
    """Test that _persist_tokens writes token snapshot to config entry."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.melcloudhome.const import DOMAIN

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"email": "test@example.com", "password": "pw", "access_token": None},
    )
    entry.add_to_hass(hass)

    coordinator = MELCloudHomeCoordinator(
        hass, mock_client, "test@example.com", "pw", entry
    )
    mock_client.get_token_snapshot = MagicMock(
        return_value={
            "access_token": "new-token",
            "refresh_token": "new-refresh",
            "token_expiry": 1234567890.0,
        }
    )

    coordinator._persist_tokens()

    assert entry.data["access_token"] == "new-token"
    assert entry.data["refresh_token"] == "new-refresh"
    assert entry.data["token_expiry"] == 1234567890.0


@pytest.mark.asyncio
async def test_service_unavailable_passes_through_retry(coordinator):
    """Test ServiceUnavailableError is not retried or re-authed."""
    operation = AsyncMock(side_effect=ServiceUnavailableError(503))

    with pytest.raises(ServiceUnavailableError):
        await coordinator._execute_with_retry(operation, "test_op")

    # Should NOT attempt re-auth — outage is not an auth problem
    assert coordinator.client.login.call_count == 0
    assert operation.call_count == 1


@pytest.mark.asyncio
async def test_outage_backoff_escalates(coordinator, hass):
    """Test retry_after escalates on consecutive outages."""
    from homeassistant.helpers.update_coordinator import UpdateFailed

    # Ensure client looks unauthenticated so login is attempted
    coordinator.client._auth._authenticated = False
    coordinator.client._auth._access_token = None

    coordinator.client.login = AsyncMock(side_effect=ServiceUnavailableError(503))

    # Collect retry_after values across consecutive failures
    retry_values = []
    for _ in range(5):
        try:
            await coordinator._async_update_data()
        except UpdateFailed as err:
            retry_values.append(err.retry_after)

    assert retry_values == [120, 240, 480, 900, 900]


@pytest.mark.asyncio
async def test_outage_backoff_resets_on_success(coordinator, hass):
    """Test retry count resets after a successful update."""
    from homeassistant.helpers.update_coordinator import UpdateFailed

    from custom_components.melcloudhome.api.models import UserContext

    # Ensure client looks unauthenticated so login is attempted
    coordinator.client._auth._authenticated = False
    coordinator.client._auth._access_token = None

    # Simulate 3 failures to build up the counter
    coordinator.client.login = AsyncMock(side_effect=ServiceUnavailableError(503))
    for _ in range(3):
        with contextlib.suppress(UpdateFailed):
            await coordinator._async_update_data()

    assert coordinator._outage_retry_count == 3

    # Now simulate success — restore tokens so is_authenticated returns True
    coordinator.client.restore_tokens("token", "refresh", time.time() + 3600)
    coordinator.client.login = AsyncMock()
    mock_context = AsyncMock(spec=UserContext)
    mock_context.buildings = []
    coordinator.client.get_user_context = AsyncMock(return_value=mock_context)
    await coordinator._async_update_data()

    assert coordinator._outage_retry_count == 0


@pytest.mark.asyncio
async def test_api_error_converts_to_home_assistant_error(coordinator):
    """Test that ApiError is converted to HomeAssistantError."""
    operation = AsyncMock(side_effect=ApiError("API failed"))

    with pytest.raises(HomeAssistantError, match="API error: API failed"):
        await coordinator._execute_with_retry(operation, "test_op")


@pytest.mark.asyncio
async def test_wrapper_methods_call_client(coordinator):
    """Test coordinator wrapper methods call client correctly."""
    coordinator.client.ata.set_power = AsyncMock()
    await coordinator.async_set_power("unit123", True)

    coordinator.client.ata.set_power.assert_called_once_with("unit123", True)


@pytest.mark.asyncio
async def test_wrapper_method_handles_session_expiry(coordinator):
    """Test wrapper methods automatically recover from session expiry."""
    coordinator.client.ata.set_power = AsyncMock(
        side_effect=[
            AuthenticationError("Session expired"),  # First attempt
            AuthenticationError("Session expired"),  # Double-check
            None,  # After re-auth
        ]
    )

    await coordinator.async_set_power("unit123", True)

    assert coordinator.client.login.call_count == 1
    assert (
        coordinator.client.ata.set_power.call_count == 3
    )  # First + double-check + retry


@pytest.mark.asyncio
async def test_debounced_refresh_coalesces_calls(coordinator, hass):
    """Test debounced refresh coalesces multiple rapid calls into one."""
    # Mock the coordinator's refresh method that control_client will call
    mock_refresh = AsyncMock()
    # Patch the control_client_ata's stored reference to async_request_refresh
    coordinator.control_client_ata._async_request_refresh = mock_refresh

    # Make 5 rapid debounced refresh requests
    await coordinator.async_request_refresh_debounced(delay=0.1)
    await coordinator.async_request_refresh_debounced(delay=0.1)
    await coordinator.async_request_refresh_debounced(delay=0.1)
    await coordinator.async_request_refresh_debounced(delay=0.1)
    await coordinator.async_request_refresh_debounced(delay=0.1)

    # Should not have called refresh yet
    assert mock_refresh.call_count == 0

    # Wait for debounce delay and let hass process the task
    await asyncio.sleep(0.15)
    await hass.async_block_till_done()

    # Should have called refresh exactly once
    assert mock_refresh.call_count == 1


@pytest.mark.asyncio
async def test_deduplication_skips_same_value(coordinator):
    """Test smart deduplication skips API call when value unchanged."""
    from custom_components.melcloudhome.api.models_ata import (
        AirToAirCapabilities,
        AirToAirUnit,
    )

    # Setup coordinator with cached unit data
    unit = AirToAirUnit(
        id="unit123",
        name="Test Unit",
        power=True,
        operation_mode="Heat",
        set_temperature=20.0,
        room_temperature=18.0,
        set_fan_speed="Auto",
        vane_vertical_direction="Auto",
        vane_horizontal_direction="Centre",
        in_standby_mode=False,
        is_in_error=False,
        rssi=-50,
        capabilities=AirToAirCapabilities(),
    )
    coordinator._units = {"unit123": unit}

    coordinator.client.ata.set_power = AsyncMock()

    # Try to set power to True (already True)
    await coordinator.async_set_power("unit123", True)

    # Should NOT call API
    assert coordinator.client.ata.set_power.call_count == 0


@pytest.mark.asyncio
async def test_deduplication_sends_different_value(coordinator):
    """Test smart deduplication sends API call when value changed."""
    from custom_components.melcloudhome.api.models_ata import (
        AirToAirCapabilities,
        AirToAirUnit,
    )

    unit = AirToAirUnit(
        id="unit123",
        name="Test Unit",
        power=False,  # Currently OFF
        operation_mode="Heat",
        set_temperature=20.0,
        room_temperature=18.0,
        set_fan_speed="Auto",
        vane_vertical_direction="Auto",
        vane_horizontal_direction="Centre",
        in_standby_mode=False,
        is_in_error=False,
        rssi=-50,
        capabilities=AirToAirCapabilities(),
    )
    coordinator._units = {"unit123": unit}

    coordinator.client.ata.set_power = AsyncMock()

    # Try to set power to True (currently False)
    await coordinator.async_set_power("unit123", True)

    # SHOULD call API
    assert coordinator.client.ata.set_power.call_count == 1
