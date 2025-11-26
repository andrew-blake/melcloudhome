"""Tests for coordinator retry logic on session expiry."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError

from custom_components.melcloudhome.api.client import MELCloudHomeClient
from custom_components.melcloudhome.api.exceptions import ApiError, AuthenticationError
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
    return MELCloudHomeCoordinator(hass, mock_client, "test@example.com", "password")


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

    assert list(results) == ["success_1", "success_2"]
    assert reauth_count == 1  # CRITICAL: Only one re-auth


@pytest.mark.asyncio
async def test_final_retry_catches_auth_error(coordinator):
    """Test final retry after re-auth catches AuthenticationError (safety net)."""
    operation = AsyncMock(side_effect=AuthenticationError("Session expired"))

    with pytest.raises(ConfigEntryAuthFailed, match="after re-auth"):
        await coordinator._execute_with_retry(operation, "test_op")


@pytest.mark.asyncio
async def test_api_error_converts_to_home_assistant_error(coordinator):
    """Test that ApiError is converted to HomeAssistantError."""
    operation = AsyncMock(side_effect=ApiError("API failed"))

    with pytest.raises(HomeAssistantError, match="API error: API failed"):
        await coordinator._execute_with_retry(operation, "test_op")


@pytest.mark.asyncio
async def test_wrapper_methods_call_client(coordinator):
    """Test coordinator wrapper methods call client correctly."""
    coordinator.client.set_power = AsyncMock()
    await coordinator.async_set_power("unit123", True)

    coordinator.client.set_power.assert_called_once_with("unit123", True)


@pytest.mark.asyncio
async def test_wrapper_method_handles_session_expiry(coordinator):
    """Test wrapper methods automatically recover from session expiry."""
    coordinator.client.set_power = AsyncMock(
        side_effect=[
            AuthenticationError("Session expired"),  # First attempt
            AuthenticationError("Session expired"),  # Double-check
            None,  # After re-auth
        ]
    )

    await coordinator.async_set_power("unit123", True)

    assert coordinator.client.login.call_count == 1
    assert coordinator.client.set_power.call_count == 3  # First + double-check + retry


@pytest.mark.asyncio
async def test_debounced_refresh_coalesces_calls(coordinator, hass):
    """Test debounced refresh coalesces multiple rapid calls into one."""
    with patch.object(
        coordinator, "async_request_refresh", AsyncMock()
    ) as mock_refresh:
        # Make 5 rapid debounced refresh requests
        await coordinator.async_request_refresh_debounced(delay=0.1)
        await coordinator.async_request_refresh_debounced(delay=0.1)
        await coordinator.async_request_refresh_debounced(delay=0.1)
        await coordinator.async_request_refresh_debounced(delay=0.1)
        await coordinator.async_request_refresh_debounced(delay=0.1)

        # Should not have called refresh yet
        assert mock_refresh.call_count == 0

        # Wait for debounce delay
        await asyncio.sleep(0.15)

        # Should have called refresh exactly once
        assert mock_refresh.call_count == 1


@pytest.mark.asyncio
async def test_deduplication_skips_same_value(coordinator):
    """Test smart deduplication skips API call when value unchanged."""
    from custom_components.melcloudhome.api.models import (
        AirToAirUnit,
        DeviceCapabilities,
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
        capabilities=DeviceCapabilities(),
    )
    coordinator._units = {"unit123": unit}

    coordinator.client.set_power = AsyncMock()

    # Try to set power to True (already True)
    await coordinator.async_set_power("unit123", True)

    # Should NOT call API
    assert coordinator.client.set_power.call_count == 0


@pytest.mark.asyncio
async def test_deduplication_sends_different_value(coordinator):
    """Test smart deduplication sends API call when value changed."""
    from custom_components.melcloudhome.api.models import (
        AirToAirUnit,
        DeviceCapabilities,
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
        capabilities=DeviceCapabilities(),
    )
    coordinator._units = {"unit123": unit}

    coordinator.client.set_power = AsyncMock()

    # Try to set power to True (currently False)
    await coordinator.async_set_power("unit123", True)

    # SHOULD call API
    assert coordinator.client.set_power.call_count == 1
