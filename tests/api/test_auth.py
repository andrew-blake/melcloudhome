"""Tests for MELCloud Home authentication.

Tests the OAuth 2.0 PKCE authentication flow, token management,
and session handling. All tests use mocked HTTP (not VCR).
"""

import contextlib
import time
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from custom_components.melcloudhome.api.auth import MELCloudHomeAuth
from custom_components.melcloudhome.api.exceptions import (
    AuthenticationError,
    ServiceUnavailableError,
)


@pytest_asyncio.fixture
async def auth(request_pacer) -> AsyncIterator[MELCloudHomeAuth]:
    """Provide a fresh (unauthenticated) auth instance."""
    auth_instance = MELCloudHomeAuth(request_pacer=request_pacer)
    yield auth_instance
    with contextlib.suppress(Exception):
        await auth_instance.close()


class TestOAuthPKCE:
    """Test OAuth PKCE code generation."""

    def test_pkce_verifier_length(self) -> None:
        """PKCE verifier should be a base64url string of sufficient length."""
        verifier, _challenge = MELCloudHomeAuth._generate_pkce()
        assert 43 <= len(verifier) <= 128
        assert all(
            c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
            for c in verifier
        )

    def test_pkce_challenge_matches_verifier(self) -> None:
        """PKCE challenge should be S256 hash of verifier."""
        import base64
        import hashlib

        verifier, challenge = MELCloudHomeAuth._generate_pkce()
        expected = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        assert challenge == expected

    def test_pkce_generates_unique_values(self) -> None:
        """Each call should generate unique verifier/challenge pairs."""
        v1, c1 = MELCloudHomeAuth._generate_pkce()
        v2, c2 = MELCloudHomeAuth._generate_pkce()
        assert v1 != v2
        assert c1 != c2


class TestTokenManagement:
    """Test token expiry and storage."""

    @pytest.mark.asyncio
    async def test_is_token_expired_when_no_token(self, request_pacer) -> None:
        """No token means expired."""
        auth = MELCloudHomeAuth(request_pacer=request_pacer)
        try:
            assert auth.is_token_expired is True
        finally:
            await auth.close()

    @pytest.mark.asyncio
    async def test_is_token_expired_with_valid_token(self, request_pacer) -> None:
        """Valid token with future expiry should not be expired."""
        auth = MELCloudHomeAuth(request_pacer=request_pacer)
        try:
            auth.restore_tokens("fake-token", "fake-refresh", time.time() + 3600)
            assert auth.is_token_expired is False
        finally:
            await auth.close()

    @pytest.mark.asyncio
    async def test_is_token_expired_with_buffer(self, request_pacer) -> None:
        """Token expiring within 60s buffer should be considered expired."""
        auth = MELCloudHomeAuth(request_pacer=request_pacer)
        try:
            auth.restore_tokens("fake-token", "fake-refresh", time.time() + 30)
            assert auth.is_token_expired is True
        finally:
            await auth.close()

    @pytest.mark.asyncio
    async def test_restore_and_snapshot_roundtrip(self, request_pacer) -> None:
        """Restore/snapshot should roundtrip correctly."""
        auth = MELCloudHomeAuth(request_pacer=request_pacer)
        try:
            expiry = time.time() + 3600
            auth.restore_tokens("access-123", "refresh-456", expiry)
            snapshot = auth.get_token_snapshot()
            assert snapshot == {
                "access_token": "access-123",
                "refresh_token": "refresh-456",
                "token_expiry": expiry,
            }
            assert auth.is_authenticated is True
        finally:
            await auth.close()

    @pytest.mark.asyncio
    async def test_access_token_property(self, request_pacer) -> None:
        """access_token property should return stored token."""
        auth = MELCloudHomeAuth(request_pacer=request_pacer)
        try:
            assert auth.access_token is None
            auth.restore_tokens("my-token", "my-refresh", time.time() + 3600)
            assert auth.access_token == "my-token"
        finally:
            await auth.close()

    @pytest.mark.asyncio
    async def test_refresh_token_property(self, request_pacer) -> None:
        """refresh_token property should return stored token."""
        auth = MELCloudHomeAuth(request_pacer=request_pacer)
        try:
            assert auth.refresh_token is None
            auth.restore_tokens("my-token", "my-refresh", time.time() + 3600)
            assert auth.refresh_token == "my-refresh"
        finally:
            await auth.close()


class TestAuthenticationState:
    """Test authentication state management."""

    @pytest.mark.asyncio
    async def test_initial_state_not_authenticated(
        self, auth: MELCloudHomeAuth
    ) -> None:
        """New auth instance should not be authenticated."""
        assert not auth.is_authenticated

    @pytest.mark.asyncio
    async def test_is_authenticated_requires_valid_token(self, request_pacer) -> None:
        """is_authenticated should be False with expired tokens."""
        auth = MELCloudHomeAuth(request_pacer=request_pacer)
        try:
            # Set authenticated but with expired token
            auth._authenticated = True
            auth._access_token = "expired"
            auth._token_expiry = time.time() - 100
            assert auth.is_authenticated is False
        finally:
            await auth.close()


class TestMockLogin:
    """Test mock server login flow."""

    @pytest.mark.asyncio
    async def test_login_mock_populates_tokens(self, request_pacer) -> None:
        """_login_mock should populate token fields from response."""
        auth = MELCloudHomeAuth(debug_mode=True, request_pacer=request_pacer)

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_in": 3600,
                "token_type": "Bearer",
            }
        )
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_response)

        try:
            with patch.object(auth, "_ensure_session", return_value=mock_session):
                result = await auth.login("test@example.com", "password")

            assert result is True
            assert auth.is_authenticated is True
            assert auth.access_token == "mock-access-token"
            assert auth.refresh_token == "mock-refresh-token"
            assert auth._token_expiry > time.time()
        finally:
            await auth.close()

    @pytest.mark.asyncio
    async def test_login_mock_rejects_bad_credentials(self, request_pacer) -> None:
        """_login_mock should raise on 401."""
        auth = MELCloudHomeAuth(debug_mode=True, request_pacer=request_pacer)

        mock_response = MagicMock()
        mock_response.status = 401
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_response)

        try:
            with (
                patch.object(auth, "_ensure_session", return_value=mock_session),
                pytest.raises(AuthenticationError, match="Invalid credentials"),
            ):
                await auth.login("test@example.com", "WRONG_PASSWORD")
        finally:
            await auth.close()


class TestTokenRefresh:
    """Test token refresh flow."""

    @pytest.mark.asyncio
    async def test_refresh_success(self, request_pacer) -> None:
        """Successful refresh should update tokens."""
        auth = MELCloudHomeAuth(request_pacer=request_pacer)
        auth.restore_tokens("old-access", "old-refresh", time.time() + 3600)

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "access_token": "new-access",
                "refresh_token": "new-refresh",
                "expires_in": 3600,
            }
        )
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_response)

        try:
            with patch.object(auth, "_ensure_session", return_value=mock_session):
                result = await auth.refresh_access_token()

            assert result is True
            assert auth.access_token == "new-access"
            assert auth.refresh_token == "new-refresh"
            assert auth.is_authenticated is True
        finally:
            await auth.close()

    @pytest.mark.asyncio
    async def test_refresh_rejected(self, request_pacer) -> None:
        """Rejected refresh should clear auth state and raise."""
        auth = MELCloudHomeAuth(request_pacer=request_pacer)
        auth.restore_tokens("old-access", "old-refresh", time.time() + 3600)

        mock_response = MagicMock()
        mock_response.status = 400
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_response)

        try:
            with (
                patch.object(auth, "_ensure_session", return_value=mock_session),
                pytest.raises(AuthenticationError, match="Refresh token rejected"),
            ):
                await auth.refresh_access_token()

            assert auth.access_token is None
            assert auth.refresh_token is None
            assert auth.is_authenticated is False
        finally:
            await auth.close()

    @pytest.mark.asyncio
    async def test_refresh_without_token_raises(self, request_pacer) -> None:
        """Refresh without stored refresh token should raise."""
        auth = MELCloudHomeAuth(request_pacer=request_pacer)
        try:
            with pytest.raises(AuthenticationError, match="No refresh token"):
                await auth.refresh_access_token()
        finally:
            await auth.close()


class TestPARRequest:
    """Test PAR (Pushed Authorization Request) step."""

    @pytest.mark.asyncio
    async def test_par_failure_raises(self, request_pacer) -> None:
        """PAR returning non-201 should raise AuthenticationError."""
        auth = MELCloudHomeAuth(request_pacer=request_pacer)

        mock_response = MagicMock()
        mock_response.status = 400
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_response)

        try:
            with (
                patch.object(auth, "_ensure_session", return_value=mock_session),
                pytest.raises(AuthenticationError, match="PAR request failed"),
            ):
                await auth.login("test@example.com", "password")
        finally:
            await auth.close()

    @pytest.mark.asyncio
    async def test_par_5xx_raises_service_unavailable(self, request_pacer) -> None:
        """PAR returning 5xx should raise ServiceUnavailableError."""
        auth = MELCloudHomeAuth(request_pacer=request_pacer)

        mock_response = MagicMock()
        mock_response.status = 503
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_response)

        try:
            with (
                patch.object(auth, "_ensure_session", return_value=mock_session),
                pytest.raises(ServiceUnavailableError),
            ):
                await auth.login("test@example.com", "password")
        finally:
            await auth.close()


class TestSessionManagement:
    """Test session creation and management."""

    @pytest.mark.asyncio
    async def test_get_session_when_not_authenticated(
        self, auth: MELCloudHomeAuth
    ) -> None:
        """get_session should raise when not authenticated."""
        with pytest.raises(AuthenticationError, match="Not authenticated"):
            await auth.get_session()

    @pytest.mark.asyncio
    async def test_close_closes_session(self, request_pacer) -> None:
        """close() should close the session."""
        auth = MELCloudHomeAuth(request_pacer=request_pacer)
        auth.restore_tokens("token", "refresh", time.time() + 3600)

        session = await auth.get_session()
        assert not session.closed

        await auth.close()
        assert session.closed


class TestLogout:
    """Test logout functionality."""

    @pytest.mark.asyncio
    async def test_logout_clears_tokens(self, request_pacer) -> None:
        """Logout should clear all token state."""
        auth = MELCloudHomeAuth(request_pacer=request_pacer)
        auth.restore_tokens("token", "refresh", time.time() + 3600)
        assert auth.is_authenticated is True

        await auth.logout()
        assert auth.is_authenticated is False
        assert auth.access_token is None
        assert auth.refresh_token is None

    @pytest.mark.asyncio
    async def test_logout_when_not_authenticated(self, auth: MELCloudHomeAuth) -> None:
        """Logout should not raise even when not authenticated."""
        assert not auth.is_authenticated
        await auth.logout()
        assert not auth.is_authenticated


class TestCSRFTokenExtraction:
    """Test CSRF token extraction from HTML."""

    @pytest.mark.asyncio
    async def test_extract_csrf_token_from_html(self, auth: MELCloudHomeAuth) -> None:
        """_extract_csrf_token should extract token from HTML."""
        html = """
        <html>
        <input type="hidden" name="_csrf" value="test-csrf-token-12345">
        </html>
        """
        token = auth._extract_csrf_token(html)
        assert token == "test-csrf-token-12345"

    @pytest.mark.asyncio
    async def test_extract_csrf_token_returns_none_when_missing(
        self, auth: MELCloudHomeAuth
    ) -> None:
        """_extract_csrf_token should return None when token not found."""
        html = "<html><body>No token here</body></html>"
        token = auth._extract_csrf_token(html)
        assert token is None

    @pytest.mark.asyncio
    async def test_extract_csrf_token_from_empty_html(
        self, auth: MELCloudHomeAuth
    ) -> None:
        """_extract_csrf_token should handle empty HTML."""
        token = auth._extract_csrf_token("")
        assert token is None


class TestMultipleAuthInstances:
    """Test multiple auth instances can coexist."""

    @pytest.mark.asyncio
    async def test_multiple_instances_independent(self, request_pacer) -> None:
        """Multiple auth instances should be independent."""
        from tests.conftest import NoOpRequestPacer

        auth1 = MELCloudHomeAuth(request_pacer=NoOpRequestPacer())
        auth2 = MELCloudHomeAuth(request_pacer=NoOpRequestPacer())

        try:
            assert not auth1.is_authenticated
            assert not auth2.is_authenticated
            assert auth1 is not auth2
        finally:
            await auth1.close()
            await auth2.close()
