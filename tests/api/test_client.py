"""Tests for MELCloudHomeClient with RequestPacer integration."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

from custom_components.melcloudhome.api.auth import MELCloudHomeAuth
from custom_components.melcloudhome.api.client import MELCloudHomeClient
from custom_components.melcloudhome.api.exceptions import (
    AuthenticationError,
    ServiceUnavailableError,
)


def create_mock_context_manager(return_value: Any) -> MagicMock:
    """Helper to create a mock async context manager."""
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=return_value)
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    return mock_cm


@pytest.fixture
def mock_pacer():
    """Mock RequestPacer instance."""
    mock = MagicMock()
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=False)
    return mock


@pytest.fixture
def mock_session():
    """Mock aiohttp session with configured response."""
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"data": "test"})
    mock_response.content_length = 100
    mock_response.content_type = "application/json"

    session = MagicMock()
    session.request = MagicMock(return_value=create_mock_context_manager(mock_response))
    return session


@pytest.mark.asyncio
async def test_client_uses_request_pacer(mock_pacer, mock_session, mocker):
    """Verify MELCloudHomeClient uses RequestPacer for _api_request."""
    # Mock RequestPacer class
    mock_pacer_class = mocker.patch(
        "custom_components.melcloudhome.api.client.RequestPacer",
        return_value=mock_pacer,
    )

    # Mock authentication property
    mocker.patch.object(
        MELCloudHomeAuth,
        "is_authenticated",
        new_callable=PropertyMock,
        return_value=True,
    )

    # Create client
    client = MELCloudHomeClient()

    # Verify pacer was created
    mock_pacer_class.assert_called_once()

    # Mock get_session to return our configured session
    mocker.patch.object(
        client._auth, "get_session", new=AsyncMock(return_value=mock_session)
    )

    # Make API request
    await client._api_request("GET", "/test")

    # Verify pacer context manager was used
    mock_pacer.__aenter__.assert_called_once()
    mock_pacer.__aexit__.assert_called_once()


@pytest.mark.asyncio
async def test_api_request_sends_bearer_header(mock_pacer, mocker):
    """API requests should use Bearer auth, not cookies."""
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"data": "test"})
    mock_response.content_length = 100
    mock_response.content_type = "text/plain"

    session = MagicMock()
    session.request = MagicMock(return_value=create_mock_context_manager(mock_response))

    mocker.patch(
        "custom_components.melcloudhome.api.client.RequestPacer",
        return_value=mock_pacer,
    )
    mocker.patch.object(
        MELCloudHomeAuth,
        "is_authenticated",
        new_callable=PropertyMock,
        return_value=True,
    )
    mocker.patch.object(
        MELCloudHomeAuth,
        "access_token",
        new_callable=PropertyMock,
        return_value="test-bearer-token",
    )
    mocker.patch.object(
        MELCloudHomeAuth,
        "is_token_expired",
        new_callable=PropertyMock,
        return_value=False,
    )

    client = MELCloudHomeClient()
    mocker.patch.object(
        client._auth, "get_session", new=AsyncMock(return_value=session)
    )

    await client._api_request("GET", "/context")

    call_args = session.request.call_args
    headers = call_args[1].get("headers", {}) if call_args[1] else {}
    assert headers.get("Authorization") == "Bearer test-bearer-token"
    assert "x-csrf" not in headers


@pytest.mark.asyncio
async def test_api_request_reports_service_unavailable_on_503(mock_pacer, mocker):
    """API request should report service unavailable when server returns 503."""
    mock_response = AsyncMock()
    mock_response.status = 503
    mock_response.content_length = 100
    mock_response.content_type = "text/html"

    session = MagicMock()
    session.request = MagicMock(return_value=create_mock_context_manager(mock_response))

    mocker.patch(
        "custom_components.melcloudhome.api.client.RequestPacer",
        return_value=mock_pacer,
    )
    mocker.patch.object(
        MELCloudHomeAuth,
        "is_authenticated",
        new_callable=PropertyMock,
        return_value=True,
    )

    client = MELCloudHomeClient()
    mocker.patch.object(
        client._auth, "get_session", new=AsyncMock(return_value=session)
    )

    with pytest.raises(ServiceUnavailableError, match="MELCloud service unavailable"):
        await client._api_request("GET", "/api/user/context")


class TestProactiveTokenRefresh:
    """Tests for proactive token refresh in _api_request."""

    @pytest.mark.asyncio
    async def test_refreshes_expired_token_before_request(self, mock_pacer, mocker):
        """When token is expired and refresh token exists, refresh proactively."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"data": "test"})
        mock_response.content_length = 100
        mock_response.content_type = "application/json"

        session = MagicMock()
        session.request = MagicMock(
            return_value=create_mock_context_manager(mock_response)
        )

        mocker.patch(
            "custom_components.melcloudhome.api.client.RequestPacer",
            return_value=mock_pacer,
        )

        client = MELCloudHomeClient()
        # Token is expired but refresh token available
        mocker.patch.object(
            type(client._auth),
            "is_token_expired",
            new_callable=PropertyMock,
            return_value=True,
        )
        mocker.patch.object(
            type(client._auth),
            "refresh_token",
            new_callable=PropertyMock,
            return_value="valid-refresh-token",
        )
        mock_refresh = mocker.patch.object(
            client._auth, "refresh_access_token", new=AsyncMock(return_value=True)
        )
        # After refresh, is_authenticated returns True
        mocker.patch.object(
            type(client._auth),
            "is_authenticated",
            new_callable=PropertyMock,
            return_value=True,
        )
        mocker.patch.object(
            client._auth, "get_session", new=AsyncMock(return_value=session)
        )

        await client._api_request("GET", "/context")

        mock_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_failure_falls_through_to_auth_check(
        self, mock_pacer, mocker
    ):
        """When proactive refresh fails, the is_authenticated check raises."""
        mocker.patch(
            "custom_components.melcloudhome.api.client.RequestPacer",
            return_value=mock_pacer,
        )

        client = MELCloudHomeClient()
        mocker.patch.object(
            type(client._auth),
            "is_token_expired",
            new_callable=PropertyMock,
            return_value=True,
        )
        mocker.patch.object(
            type(client._auth),
            "refresh_token",
            new_callable=PropertyMock,
            return_value="valid-refresh-token",
        )
        mocker.patch.object(
            client._auth,
            "refresh_access_token",
            new=AsyncMock(side_effect=AuthenticationError("Refresh rejected")),
        )
        # After failed refresh, still not authenticated
        mocker.patch.object(
            type(client._auth),
            "is_authenticated",
            new_callable=PropertyMock,
            return_value=False,
        )

        with pytest.raises(AuthenticationError, match="Not authenticated"):
            await client._api_request("GET", "/context")

    @pytest.mark.asyncio
    async def test_no_refresh_when_token_valid(self, mock_pacer, mocker):
        """When token is not expired, no refresh attempt is made."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"data": "test"})
        mock_response.content_length = 100
        mock_response.content_type = "application/json"

        session = MagicMock()
        session.request = MagicMock(
            return_value=create_mock_context_manager(mock_response)
        )

        mocker.patch(
            "custom_components.melcloudhome.api.client.RequestPacer",
            return_value=mock_pacer,
        )

        client = MELCloudHomeClient()
        mocker.patch.object(
            type(client._auth),
            "is_token_expired",
            new_callable=PropertyMock,
            return_value=False,
        )
        mocker.patch.object(
            type(client._auth),
            "is_authenticated",
            new_callable=PropertyMock,
            return_value=True,
        )
        mock_refresh = mocker.patch.object(
            client._auth, "refresh_access_token", new=AsyncMock()
        )
        mocker.patch.object(
            client._auth, "get_session", new=AsyncMock(return_value=session)
        )

        await client._api_request("GET", "/context")

        mock_refresh.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_refresh_without_refresh_token(self, mock_pacer, mocker):
        """When token is expired but no refresh token, skip refresh attempt."""
        mocker.patch(
            "custom_components.melcloudhome.api.client.RequestPacer",
            return_value=mock_pacer,
        )

        client = MELCloudHomeClient()
        mocker.patch.object(
            type(client._auth),
            "is_token_expired",
            new_callable=PropertyMock,
            return_value=True,
        )
        mocker.patch.object(
            type(client._auth),
            "refresh_token",
            new_callable=PropertyMock,
            return_value=None,
        )
        mocker.patch.object(
            type(client._auth),
            "is_authenticated",
            new_callable=PropertyMock,
            return_value=False,
        )
        mock_refresh = mocker.patch.object(
            client._auth, "refresh_access_token", new=AsyncMock()
        )

        with pytest.raises(AuthenticationError, match="Not authenticated"):
            await client._api_request("GET", "/context")

        mock_refresh.assert_not_called()

    @pytest.mark.asyncio
    async def test_refresh_triggers_persistence_callback(self, mock_pacer, mocker):
        """Proactive refresh calls the on_tokens_refreshed callback."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"data": "test"})
        mock_response.content_length = 100
        mock_response.content_type = "application/json"

        session = MagicMock()
        session.request = MagicMock(
            return_value=create_mock_context_manager(mock_response)
        )

        mocker.patch(
            "custom_components.melcloudhome.api.client.RequestPacer",
            return_value=mock_pacer,
        )

        client = MELCloudHomeClient()
        callback = MagicMock()
        client.set_on_tokens_refreshed(callback)

        mocker.patch.object(
            type(client._auth),
            "is_token_expired",
            new_callable=PropertyMock,
            return_value=True,
        )
        mocker.patch.object(
            type(client._auth),
            "refresh_token",
            new_callable=PropertyMock,
            return_value="valid-refresh-token",
        )
        mocker.patch.object(
            client._auth, "refresh_access_token", new=AsyncMock(return_value=True)
        )
        mocker.patch.object(
            type(client._auth),
            "is_authenticated",
            new_callable=PropertyMock,
            return_value=True,
        )
        mocker.patch.object(
            client._auth, "get_session", new=AsyncMock(return_value=session)
        )

        await client._api_request("GET", "/context")

        callback.assert_called_once()
