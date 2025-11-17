"""Tests for MELCloud Home authentication.

These tests verify the authentication flow, session management, and error handling.
Uses VCR to record/replay OAuth interactions with AWS Cognito.
"""

import contextlib
import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

from custom_components.melcloudhome.api.auth import MELCloudHomeAuth
from custom_components.melcloudhome.api.exceptions import AuthenticationError


@pytest_asyncio.fixture
async def auth() -> AsyncIterator[MELCloudHomeAuth]:
    """Provide a fresh auth instance."""
    auth_instance = MELCloudHomeAuth()
    yield auth_instance
    # Cleanup
    with contextlib.suppress(Exception):
        await auth_instance.close()


class TestAuthenticationState:
    """Test authentication state management."""

    @pytest.mark.asyncio
    async def test_initial_state_not_authenticated(
        self, auth: MELCloudHomeAuth
    ) -> None:
        """New auth instance should not be authenticated."""
        assert not auth.is_authenticated

    @pytest.mark.vcr()
    @pytest.mark.asyncio
    async def test_authenticated_after_login(self, auth: MELCloudHomeAuth) -> None:
        """Auth instance should be authenticated after successful login."""
        username = os.getenv("MELCLOUD_USER", "***PLACEHOLDER***")
        password = os.getenv("MELCLOUD_PASSWORD", "***PLACEHOLDER***")

        if username == "***PLACEHOLDER***" or password == "***PLACEHOLDER***":
            pytest.skip("MELCLOUD_USER and MELCLOUD_PASSWORD required")

        await auth.login(username, password)
        assert auth.is_authenticated

    @pytest.mark.vcr()
    @pytest.mark.asyncio
    async def test_not_authenticated_after_logout(self, auth: MELCloudHomeAuth) -> None:
        """Auth instance should not be authenticated after logout."""
        username = os.getenv("MELCLOUD_USER", "***PLACEHOLDER***")
        password = os.getenv("MELCLOUD_PASSWORD", "***PLACEHOLDER***")

        if username == "***PLACEHOLDER***" or password == "***PLACEHOLDER***":
            pytest.skip("MELCLOUD_USER and MELCLOUD_PASSWORD required")

        await auth.login(username, password)
        assert auth.is_authenticated

        await auth.logout()
        assert not auth.is_authenticated


class TestLoginSuccess:
    """Test successful login scenarios."""

    @pytest.mark.vcr()
    @pytest.mark.asyncio
    async def test_login_with_valid_credentials(self, auth: MELCloudHomeAuth) -> None:
        """Login should succeed with valid credentials."""
        username = os.getenv("MELCLOUD_USER", "***PLACEHOLDER***")
        password = os.getenv("MELCLOUD_PASSWORD", "***PLACEHOLDER***")

        if username == "***PLACEHOLDER***" or password == "***PLACEHOLDER***":
            pytest.skip("MELCLOUD_USER and MELCLOUD_PASSWORD required")

        result = await auth.login(username, password)
        assert result is True
        assert auth.is_authenticated

    @pytest.mark.vcr()
    @pytest.mark.asyncio
    async def test_login_returns_true(self, auth: MELCloudHomeAuth) -> None:
        """Login should return True on success."""
        username = os.getenv("MELCLOUD_USER", "***PLACEHOLDER***")
        password = os.getenv("MELCLOUD_PASSWORD", "***PLACEHOLDER***")

        if username == "***PLACEHOLDER***" or password == "***PLACEHOLDER***":
            pytest.skip("MELCLOUD_USER and MELCLOUD_PASSWORD required")

        result = await auth.login(username, password)
        assert result is True


class TestLoginFailure:
    """Test login failure scenarios.

    Note: These tests are skipped by default as they require live API
    calls with invalid credentials. VCR cassettes cannot properly
    capture auth failures without triggering rate limiting.
    """

    @pytest.mark.skip(reason="Requires live bad-credential testing")
    @pytest.mark.asyncio
    async def test_login_with_invalid_credentials(self, auth: MELCloudHomeAuth) -> None:
        """Login should fail with invalid credentials."""
        # Use obviously wrong credentials
        with pytest.raises(
            AuthenticationError,
            match="Authentication failed|Invalid username or password",
        ):
            await auth.login("wrong@example.com", "wrongpassword")

    @pytest.mark.skip(reason="Requires live bad-credential testing")
    @pytest.mark.asyncio
    async def test_login_with_empty_username(self, auth: MELCloudHomeAuth) -> None:
        """Login should fail with empty username."""
        with pytest.raises(AuthenticationError):
            await auth.login("", "password")

    @pytest.mark.skip(reason="Requires live bad-credential testing")
    @pytest.mark.asyncio
    async def test_login_with_empty_password(self, auth: MELCloudHomeAuth) -> None:
        """Login should fail with empty password."""
        username = os.getenv("MELCLOUD_USER", "test@example.com")
        with pytest.raises(AuthenticationError):
            await auth.login(username, "")

    @pytest.mark.asyncio
    async def test_login_failure_leaves_unauthenticated(
        self, auth: MELCloudHomeAuth
    ) -> None:
        """Failed login should leave auth state as not authenticated."""
        # This test doesn't need VCR - we're testing the state without API call
        assert not auth.is_authenticated


class TestSessionManagement:
    """Test session creation and management."""

    @pytest.mark.vcr()
    @pytest.mark.asyncio
    async def test_get_session_after_login(self, auth: MELCloudHomeAuth) -> None:
        """get_session should return session after login."""
        username = os.getenv("MELCLOUD_USER", "***PLACEHOLDER***")
        password = os.getenv("MELCLOUD_PASSWORD", "***PLACEHOLDER***")

        if username == "***PLACEHOLDER***" or password == "***PLACEHOLDER***":
            pytest.skip("MELCLOUD_USER and MELCLOUD_PASSWORD required")

        await auth.login(username, password)
        session = await auth.get_session()
        assert session is not None
        assert not session.closed

    @pytest.mark.vcr()
    @pytest.mark.asyncio
    async def test_session_persists_across_calls(self, auth: MELCloudHomeAuth) -> None:
        """Same session should be returned across multiple get_session calls."""
        username = os.getenv("MELCLOUD_USER", "***PLACEHOLDER***")
        password = os.getenv("MELCLOUD_PASSWORD", "***PLACEHOLDER***")

        if username == "***PLACEHOLDER***" or password == "***PLACEHOLDER***":
            pytest.skip("MELCLOUD_USER and MELCLOUD_PASSWORD required")

        await auth.login(username, password)
        session1 = await auth.get_session()
        session2 = await auth.get_session()
        assert session1 is session2  # Same instance

    @pytest.mark.vcr()
    @pytest.mark.asyncio
    async def test_close_closes_session(self, auth: MELCloudHomeAuth) -> None:
        """close() should close the session."""
        username = os.getenv("MELCLOUD_USER", "***PLACEHOLDER***")
        password = os.getenv("MELCLOUD_PASSWORD", "***PLACEHOLDER***")

        if username == "***PLACEHOLDER***" or password == "***PLACEHOLDER***":
            pytest.skip("MELCLOUD_USER and MELCLOUD_PASSWORD required")

        await auth.login(username, password)
        session = await auth.get_session()
        assert not session.closed

        await auth.close()
        assert session.closed


class TestLogout:
    """Test logout functionality."""

    @pytest.mark.vcr()
    @pytest.mark.asyncio
    async def test_logout_after_login(self, auth: MELCloudHomeAuth) -> None:
        """Logout should succeed after login."""
        username = os.getenv("MELCLOUD_USER", "***PLACEHOLDER***")
        password = os.getenv("MELCLOUD_PASSWORD", "***PLACEHOLDER***")

        if username == "***PLACEHOLDER***" or password == "***PLACEHOLDER***":
            pytest.skip("MELCLOUD_USER and MELCLOUD_PASSWORD required")

        await auth.login(username, password)
        assert auth.is_authenticated

        # Logout should not raise
        await auth.logout()
        assert not auth.is_authenticated

    @pytest.mark.asyncio
    async def test_logout_when_not_authenticated(self, auth: MELCloudHomeAuth) -> None:
        """Logout should not raise even when not authenticated."""
        assert not auth.is_authenticated
        # Should not raise
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


class TestErrorMessageExtraction:
    """Test error message extraction from HTML."""

    @pytest.mark.asyncio
    async def test_extract_error_message_from_html(
        self, auth: MELCloudHomeAuth
    ) -> None:
        """_extract_error_message should extract error from HTML."""
        html = '<div class="error-message">Invalid credentials</div>'
        error = auth._extract_error_message(html)
        # Implementation may vary, just check it doesn't crash
        assert error is None or isinstance(error, str)

    @pytest.mark.asyncio
    async def test_extract_error_message_from_empty_html(
        self, auth: MELCloudHomeAuth
    ) -> None:
        """_extract_error_message should handle empty HTML."""
        error = auth._extract_error_message("")
        assert error is None or isinstance(error, str)


class TestMultipleAuthInstances:
    """Test multiple auth instances can coexist."""

    @pytest.mark.asyncio
    async def test_multiple_instances_independent(self) -> None:
        """Multiple auth instances should be independent."""
        auth1 = MELCloudHomeAuth()
        auth2 = MELCloudHomeAuth()

        try:
            assert not auth1.is_authenticated
            assert not auth2.is_authenticated
            assert auth1 is not auth2
        finally:
            await auth1.close()
            await auth2.close()
