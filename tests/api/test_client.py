"""Tests for MELCloudHomeClient with RequestPacer integration."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

from custom_components.melcloudhome.api.auth import MELCloudHomeAuth
from custom_components.melcloudhome.api.client import MELCloudHomeClient


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
