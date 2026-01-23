"""Tests for authentication when session cookies are already valid.

Tests the scenario where the API client thinks the session is expired (got 401)
but the authentication cookies are still valid, causing MELCloud to redirect
directly to /dashboard instead of the Cognito login page.

This was the root cause of the "Unexpected redirect URL" bug reported by beta testers.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from yarl import URL

from custom_components.melcloudhome.api.auth import MELCloudHomeAuth


@pytest.mark.asyncio
async def test_login_when_already_authenticated(request_pacer) -> None:
    """Test login succeeds when redirected to dashboard (cookies still valid).

    Scenario:
    1. Client gets 401 from API (session expired)
    2. Client tries to re-authenticate
    3. But auth cookies are still valid
    4. MELCloud redirects to /dashboard (skip login)
    5. Should recognize this as success, not error
    """
    auth = MELCloudHomeAuth(request_pacer=request_pacer)

    try:
        # Mock the session.get call to simulate redirect to dashboard
        mock_response = MagicMock()
        mock_response.url = URL("https://melcloudhome.com/dashboard")
        mock_response.status = 200
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        with patch.object(
            auth, "_ensure_session", return_value=AsyncMock()
        ) as mock_session:
            mock_session.return_value.get = MagicMock(return_value=mock_response)

            # This should succeed, not raise "Unexpected redirect URL"
            result = await auth.login("test@example.com", "password")

            assert result is True
            assert auth.is_authenticated is True

    finally:
        await auth.close()


@pytest.mark.asyncio
async def test_login_handles_dashboard_redirect_variations(request_pacer) -> None:
    """Test various dashboard redirect URL formats are recognized.

    MELCloud might redirect to:
    - https://melcloudhome.com/dashboard
    - https://www.melcloudhome.com/dashboard
    - https://melcloudhome.com/dashboard?param=value
    """
    test_urls = [
        "https://melcloudhome.com/dashboard",
        "https://www.melcloudhome.com/dashboard",
        "https://melcloudhome.com/dashboard?returnUrl=%2Fdevices",
        "https://app.melcloudhome.com/dashboard",
    ]

    for url in test_urls:
        auth = MELCloudHomeAuth(request_pacer=request_pacer)

        try:
            # Mock the session.get call
            mock_response = MagicMock()
            mock_response.url = URL(url)
            mock_response.status = 200
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)

            with patch.object(
                auth, "_ensure_session", return_value=AsyncMock()
            ) as mock_session:
                mock_session.return_value.get = MagicMock(return_value=mock_response)

                result = await auth.login("test@example.com", "password")

                assert result is True, f"Failed for URL: {url}"
                assert auth.is_authenticated is True

        finally:
            await auth.close()


@pytest.mark.asyncio
async def test_login_still_rejects_invalid_redirects(request_pacer) -> None:
    """Test that truly invalid redirects are still rejected.

    Should still reject redirects to:
    - Different domains (phishing protection)
    - Error pages
    - Unexpected paths
    """
    auth = MELCloudHomeAuth(request_pacer=request_pacer)

    try:
        # Mock redirect to invalid domain
        mock_response = MagicMock()
        mock_response.url = URL("https://evil.com/dashboard")
        mock_response.status = 200
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        with patch.object(
            auth, "_ensure_session", return_value=AsyncMock()
        ) as mock_session:
            mock_session.return_value.get = MagicMock(return_value=mock_response)

            # Should raise AuthenticationError
            from custom_components.melcloudhome.api.exceptions import (
                AuthenticationError,
            )

            with pytest.raises(AuthenticationError, match="Unexpected redirect URL"):
                await auth.login("test@example.com", "password")

    finally:
        await auth.close()
