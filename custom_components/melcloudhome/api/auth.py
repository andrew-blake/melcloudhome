"""Authentication handling for MELCloud Home API."""

import asyncio
import logging
import re
from typing import Any
from urllib.parse import urlparse

import aiohttp
from aiohttp import TraceConfig, TraceRequestEndParams, TraceRequestStartParams

from .const_shared import (
    AUTH_BASE_URL,
    BASE_URL,
    COGNITO_BASE_URL,
    COGNITO_DOMAIN_SUFFIX,
    MOCK_BASE_URL,
    USER_AGENT,
)
from .exceptions import AuthenticationError

_LOGGER = logging.getLogger(__name__)


class MELCloudHomeAuth:
    """Handle MELCloud Home authentication via AWS Cognito OAuth."""

    def __init__(self, debug_mode: bool = False) -> None:
        """Initialize authenticator.

        Args:
            debug_mode: If True, use simple mock auth instead of Cognito OAuth
        """
        self._session: aiohttp.ClientSession | None = None
        self._authenticated = False
        self._debug_mode = debug_mode
        self._base_url = MOCK_BASE_URL if debug_mode else BASE_URL

        # AWS Cognito OAuth configuration (from discovery docs)
        # Not used in debug mode
        self._cognito_base = COGNITO_BASE_URL
        self._auth_base = AUTH_BASE_URL

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Ensure aiohttp session exists."""
        if self._session is None or self._session.closed:
            # Create session with proper headers for browser impersonation
            # CRITICAL: User-Agent must match Chrome to avoid bot detection
            headers = {
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "sec-ch-ua": '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"macOS"',
            }

            # Cookie jar to maintain session across requests
            # Note: NOT using unsafe=True as it can interfere with __Secure- cookie handling
            jar = aiohttp.CookieJar()

            # Timeout configuration
            timeout = aiohttp.ClientTimeout(total=30)

            # Add request/response tracing for debug logging
            trace_config = self._create_trace_config()

            self._session = aiohttp.ClientSession(
                headers=headers,
                cookie_jar=jar,
                timeout=timeout,
                trace_configs=[trace_config] if trace_config else [],
            )

        return self._session

    def _create_trace_config(self) -> TraceConfig | None:
        """
        Create trace config for request/response logging.

        Only enabled when logger is at DEBUG level.

        Returns:
            TraceConfig if debug enabled, None otherwise
        """
        if not _LOGGER.isEnabledFor(logging.DEBUG):
            return None

        trace_config = TraceConfig()

        async def on_request_start(
            session: aiohttp.ClientSession,
            trace_config_ctx: Any,
            params: TraceRequestStartParams,
        ) -> None:
            """Log request start."""
            _LOGGER.debug(
                "→ Request: %s %s",
                params.method,
                params.url,
            )
            if params.headers:
                # Log headers but redact sensitive ones
                safe_headers = {
                    k: (
                        "***REDACTED***"
                        if k.lower() in ["cookie", "authorization", "x-csrf"]
                        else v
                    )
                    for k, v in params.headers.items()
                }
                _LOGGER.debug("  Headers: %s", safe_headers)

                # Log if Cookie header is present
                if "cookie" in (k.lower() for k in params.headers):
                    cookie_count = len(params.headers.get("Cookie", "").split(";"))
                    _LOGGER.debug("  Sending %d cookie(s) with request", cookie_count)
                else:
                    _LOGGER.debug("  ⚠️ No Cookie header in request!")

        async def on_request_end(
            session: aiohttp.ClientSession,
            trace_config_ctx: Any,
            params: TraceRequestEndParams,
        ) -> None:
            """Log request end."""
            _LOGGER.debug(
                "← Response: %s %s [%d]",
                params.method,
                params.url,
                params.response.status,
            )
            # Log set-cookie headers (redacted) to track session
            if params.response.headers and "set-cookie" in params.response.headers:
                cookies = params.response.headers.getall("set-cookie")
                _LOGGER.debug("  Set-Cookie: %d cookie(s) set", len(cookies))

            # Log current cookies in jar
            if session.cookie_jar:
                melcloud_cookies = [
                    c
                    for c in session.cookie_jar
                    if c["domain"] == "melcloudhome.com"
                    or c["domain"] == ".melcloudhome.com"
                    or c["domain"].endswith(".melcloudhome.com")
                ]
                if melcloud_cookies:
                    _LOGGER.debug(
                        "  Cookie jar has %d melcloudhome.com cookie(s)",
                        len(melcloud_cookies),
                    )

        trace_config.on_request_start.append(on_request_start)
        trace_config.on_request_end.append(on_request_end)

        return trace_config

    async def _login_mock(self, username: str, password: str) -> bool:
        """
        Authenticate with mock server (simple POST /api/login).

        Args:
            username: Email address
            password: Password

        Returns:
            True if authentication successful

        Raises:
            AuthenticationError: If authentication fails
        """
        _LOGGER.debug("🔧 Debug mode: Using simple mock auth flow")

        try:
            session = await self._ensure_session()

            # Simple POST to /api/login (no Cognito)
            async with session.post(
                f"{self._base_url}/api/login",
                json={"email": username, "password": password},
                headers={"Content-Type": "application/json"},
            ) as resp:
                _LOGGER.debug("Mock auth response: %d", resp.status)

                if resp.status == 401:
                    raise AuthenticationError("Invalid credentials (mock server)")

                if resp.status != 200:
                    raise AuthenticationError(
                        f"Mock server returned unexpected status: {resp.status}"
                    )

                # Mock server returns OAuth-like tokens (but we don't validate them)
                data = await resp.json()
                _LOGGER.debug(
                    "Mock auth successful: %s", data.get("token_type", "Bearer")
                )

                self._authenticated = True
                return True

        except aiohttp.ClientError as err:
            _LOGGER.error("Mock auth connection error: %s", err)
            raise AuthenticationError(f"Cannot connect to mock server: {err}") from err

    async def login(self, username: str, password: str) -> bool:
        """
        Authenticate with MELCloud Home via AWS Cognito OAuth.

        Args:
            username: Email address
            password: Password

        Returns:
            True if authentication successful

        Raises:
            AuthenticationError: If authentication fails
        """
        _LOGGER.debug("Starting authentication flow for user: %s", username)

        # Debug mode: Use simple mock auth flow
        if self._debug_mode:
            return await self._login_mock(username, password)

        # Production mode: Use complex Cognito OAuth flow
        try:
            session = await self._ensure_session()

            # Step 1: Initiate login flow
            _LOGGER.debug("Step 1: Initiating login flow")
            async with session.get(
                f"{self._base_url}/bff/login",
                params={"returnUrl": "/dashboard"},
                allow_redirects=True,
            ) as resp:
                # Follow redirects to Cognito login page
                final_url = str(resp.url)
                _LOGGER.debug("Redirected to: %s", final_url)

                parsed = urlparse(final_url)
                if not (
                    parsed.hostname
                    and parsed.hostname.endswith(COGNITO_DOMAIN_SUFFIX)
                    and "/login" in parsed.path
                ):
                    raise AuthenticationError(f"Unexpected redirect URL: {final_url}")

                # Extract CSRF token from login page HTML
                html = await resp.text()
                csrf_token = self._extract_csrf_token(html)
                if not csrf_token:
                    raise AuthenticationError(
                        "Failed to extract CSRF token from login page"
                    )

                _LOGGER.debug("Extracted CSRF token: %s...", csrf_token[:10])

            # Step 2: Submit credentials to Cognito
            _LOGGER.debug("Step 2: Submitting credentials")

            login_data = {
                "_csrf": csrf_token,
                "username": username,
                "password": password,
                "cognitoAsfData": "",  # Can be empty - not strictly required
            }

            # POST to Cognito login endpoint
            async with session.post(
                final_url,  # Use the full URL with query params from step 1
                data=login_data,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Origin": self._cognito_base,
                    "Referer": final_url,
                },
                allow_redirects=True,
            ) as resp:
                # Successful login should redirect back to melcloudhome.com/dashboard
                final_url = str(resp.url)
                _LOGGER.debug("After login redirect: %s", final_url)

                # Check if we ended up on the dashboard (success)
                parsed = urlparse(final_url)
                if (
                    parsed.hostname
                    and (
                        parsed.hostname == "melcloudhome.com"
                        or parsed.hostname.endswith(".melcloudhome.com")
                    )
                    and "/error" not in final_url.lower()
                ):
                    _LOGGER.info("Authentication successful - reached %s", final_url)
                    self._authenticated = True

                    # CRITICAL: Wait for session to fully initialize
                    # The OAuth flow completes but Blazor WASM needs time to initialize
                    # the session before API endpoints will work
                    _LOGGER.debug("Waiting for session initialization (3 seconds)")
                    await asyncio.sleep(3)

                    return True

                # Check for error in URL or response
                if "/error" in final_url.lower() or resp.status >= 400:
                    error_html = await resp.text()
                    error_msg = self._extract_error_message(error_html)
                    raise AuthenticationError(
                        f"Authentication failed: {error_msg or 'Invalid credentials'}"
                    )

                # If we're still on Cognito, credentials were wrong
                parsed = urlparse(final_url)
                if parsed.hostname and parsed.hostname.endswith(COGNITO_DOMAIN_SUFFIX):
                    raise AuthenticationError(
                        "Authentication failed: Invalid username or password"
                    )

                # Unexpected state
                raise AuthenticationError(
                    f"Authentication failed: Unexpected redirect to {final_url}"
                )

        except aiohttp.ClientError as err:
            raise AuthenticationError(
                f"Network error during authentication: {err}"
            ) from err
        except Exception as err:
            if isinstance(err, AuthenticationError):
                raise
            raise AuthenticationError(
                f"Unexpected error during authentication: {err}"
            ) from err

    async def check_session(self) -> bool:
        """
        Check if current session is valid.

        Returns:
            True if session is valid, False otherwise
        """
        if not self._authenticated:
            return False

        try:
            session = await self._ensure_session()

            # Check session by calling main API endpoint
            # MUST include x-csrf: 1 and referer headers for API calls to work
            async with session.get(
                f"{self._base_url}/api/user/context",
                headers={
                    "Accept": "application/json",
                    "x-csrf": "1",
                    "referer": f"{self._base_url}/dashboard",
                },
            ) as resp:
                if resp.status == 200:
                    _LOGGER.debug("Session is valid (API returned 200)")
                    return True

                # 401 = session expired
                if resp.status == 401:
                    _LOGGER.debug("Session expired (401)")
                    self._authenticated = False
                    return False

                # Other errors - assume invalid
                _LOGGER.warning("Unexpected status checking session: %d", resp.status)
                return False

        except Exception as err:
            _LOGGER.error("Error checking session: %s", err)
            return False

    async def get_session(self) -> aiohttp.ClientSession:
        """
        Get authenticated session.

        Returns:
            Authenticated aiohttp ClientSession

        Raises:
            AuthenticationError: If not authenticated
        """
        if not self._authenticated:
            raise AuthenticationError("Not authenticated - call login() first")

        return await self._ensure_session()

    async def logout(self) -> None:
        """Logout and clean up session."""
        if self._session and not self._session.closed:
            try:
                # Call logout endpoint (skip in debug mode - mock server doesn't have this)
                if not self._debug_mode:
                    await self._session.get(f"{self._base_url}/bff/logout")
            except Exception as err:
                _LOGGER.debug("Error during logout: %s", err)
            finally:
                await self._session.close()

        self._session = None
        self._authenticated = False

    async def close(self) -> None:
        """Close session without logout."""
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None
        self._authenticated = False

    def _extract_csrf_token(self, html: str) -> str | None:
        """
        Extract CSRF token from Cognito login page HTML.

        Args:
            html: HTML content of login page

        Returns:
            CSRF token or None if not found
        """
        # Look for hidden input with name="_csrf"
        # Pattern: <input type="hidden" name="_csrf" value="TOKEN" />
        match = re.search(r'<input[^>]+name="_csrf"[^>]+value="([^"]+)"', html)
        if match:
            return match.group(1)

        # Try alternate pattern
        match = re.search(r'<input[^>]+value="([^"]+)"[^>]+name="_csrf"', html)
        if match:
            return match.group(1)

        return None

    def _extract_error_message(self, html: str) -> str | None:
        """
        Extract error message from error page HTML.

        Args:
            html: HTML content of error page

        Returns:
            Error message or None if not found
        """
        # Look for error message in HTML
        # Common patterns in Cognito error pages
        patterns = [
            r'<div[^>]*class="[^"]*error[^"]*"[^>]*>([^<]+)</div>',
            r'<span[^>]*class="[^"]*error[^"]*"[^>]*>([^<]+)</span>',
            r'<p[^>]*class="[^"]*error[^"]*"[^>]*>([^<]+)</p>',
        ]

        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return None

    def _generate_cognito_asf_data(self) -> str:
        """
        Generate cognitoAsfData for AWS Advanced Security Features.

        AWS Cognito uses this for device fingerprinting and bot detection.
        This is a complex JSON structure that includes browser/device info.

        For now, we return an empty/minimal value and rely on proper User-Agent.
        If authentication fails due to missing ASF data, this needs enhancement.

        Returns:
            ASF data string (base64-encoded JSON)
        """
        # TODO: Implement proper ASF data generation if needed
        # For now, return empty string - server may accept without it
        # or we rely on User-Agent being sufficient
        return ""

    @property
    def is_authenticated(self) -> bool:
        """Check if currently authenticated."""
        return self._authenticated
