"""Tests for MELCloudHomeClient with RequestPacer integration."""

import pytest


@pytest.mark.asyncio
async def test_client_uses_request_pacer():
    """Verify MELCloudHomeClient uses RequestPacer for _api_request."""
    from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

    from custom_components.melcloudhome.api.auth import MELCloudHomeAuth
    from custom_components.melcloudhome.api.client import MELCloudHomeClient

    with patch(
        "custom_components.melcloudhome.api.client.RequestPacer"
    ) as mock_pacer_class:
        # Create mock pacer instance
        mock_pacer = MagicMock()
        mock_pacer.__aenter__ = AsyncMock(return_value=mock_pacer)
        mock_pacer.__aexit__ = AsyncMock(return_value=False)
        mock_pacer_class.return_value = mock_pacer

        # Create client
        client = MELCloudHomeClient()

        # Verify pacer was created
        mock_pacer_class.assert_called_once()

        # Mock authentication property using patch.object
        with patch.object(
            MELCloudHomeAuth, "is_authenticated", new_callable=PropertyMock
        ) as mock_is_auth:
            mock_is_auth.return_value = True

            # Create properly configured mocks
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"data": "test"})
            mock_response.content_length = 100
            mock_response.content_type = "application/json"

            mock_request_cm = MagicMock()
            mock_request_cm.__aenter__ = AsyncMock(return_value=mock_response)
            mock_request_cm.__aexit__ = AsyncMock(return_value=False)

            mock_session = MagicMock()
            mock_session.request = MagicMock(return_value=mock_request_cm)

            with patch.object(
                client._auth, "get_session", new=AsyncMock(return_value=mock_session)
            ):
                # Make API request
                await client._api_request("GET", "/test")

        # Verify pacer context manager was used
        mock_pacer.__aenter__.assert_called_once()
        mock_pacer.__aexit__.assert_called_once()
