"""Authentication handling for MELCloud Home API.

Implements OAuth 2.0 Authorization Code + PKCE flow via IdentityServer
and AWS Cognito federated login.
"""

import base64
import hashlib
import logging
import re
import secrets
import time
from typing import Any
from urllib.parse import urlparse

import aiohttp
from aiohttp import TraceConfig, TraceRequestEndParams, TraceRequestStartParams

from .const_shared import (
    AUTH_BASE_URL,
    COGNITO_DOMAIN_SUFFIX,
    MOCK_BASE_URL,
    OAUTH_CLIENT_ID,
    OAUTH_REDIRECT_URI,
    OAUTH_SCOPES,
    USER_AGENT,
)
from .exceptions import AuthenticationError, ServiceUnavailableError

_LOGGER = logging.getLogger(__name__)


class MELCloudHomeAuth:
    """Handle MELCloud Home authentication via OAuth 2.0 PKCE."""

    def __init__(self, debug_mode: bool = False, request_pacer: Any = None) -> None:
        """Initialize authenticator.

        Args:
            debug_mode: If True, use simple mock auth instead of OAuth PKCE
            request_pacer: RequestPacer to prevent rate limiting (required)
        """
        if request_pacer is None:
            raise ValueError("request_pacer is required")

        self._session: aiohttp.ClientSession | None = None
        self._authenticated = False
        self._debug_mode = debug_mode
        self._base_url = MOCK_BASE_URL if debug_mode else ""
        self._request_pacer = request_pacer

        # OAuth configuration — use mock server for token endpoint in debug mode
        self._auth_base = MOCK_BASE_URL if debug_mode else AUTH_BASE_URL

        # OAuth token state
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._token_expiry: float = 0.0  # Unix timestamp

    @staticmethod
    def _generate_pkce() -> tuple[str, str]:
        """Generate PKCE code verifier and challenge (S256)."""
        verifier = (
            base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
        )
        digest = hashlib.sha256(verifier.encode()).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        return verifier, challenge

    @property
    def access_token(self) -> str | None:
        """Get current access token."""
        return self._access_token

    @property
    def refresh_token(self) -> str | None:
        """Get current refresh token."""
        return self._refresh_token

    @property
    def is_token_expired(self) -> bool:
        """Check if access token is expired or about to expire (60s buffer)."""
        if not self._access_token:
            return True
        return time.time() >= (self._token_expiry - 60)

    @property
    def is_authenticated(self) -> bool:
        """Check if currently authenticated with valid tokens."""
        return self._authenticated and not self.is_token_expired

    def restore_tokens(
        self, access_token: str | None, refresh_token: str | None, token_expiry: float
    ) -> None:
        """Restore token state from persisted storage."""
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._token_expiry = token_expiry
        if access_token and refresh_token:
            self._authenticated = True

    def get_token_snapshot(self) -> dict[str, Any]:
        """Return current token state for persistence."""
        return {
            "access_token": self._access_token,
            "refresh_token": self._refresh_token,
            "token_expiry": self._token_expiry,
        }

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Ensure aiohttp session exists."""
        if self._session is None or self._session.closed:
            headers = {
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            }

            # Cookie jar needed for Cognito login step
            jar = aiohttp.CookieJar()
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
        """Create trace config for request/response logging.

        Only enabled when logger is at DEBUG level.
        """
        if not _LOGGER.isEnabledFor(logging.DEBUG):
            return None

        trace_config = TraceConfig()

        async def on_request_start(
            session: aiohttp.ClientSession,
            trace_config_ctx: Any,
            params: TraceRequestStartParams,
        ) -> None:
            _LOGGER.debug("→ Request: %s %s", params.method, params.url)
            if params.headers:
                safe_headers = {
                    k: (
                        "***REDACTED***"
                        if k.lower() in ["cookie", "authorization"]
                        else v
                    )
                    for k, v in params.headers.items()
                }
                _LOGGER.debug("  Headers: %s", safe_headers)

        async def on_request_end(
            session: aiohttp.ClientSession,
            trace_config_ctx: Any,
            params: TraceRequestEndParams,
        ) -> None:
            _LOGGER.debug(
                "← Response: %s %s [%d]",
                params.method,
                params.url,
                params.response.status,
            )

        trace_config.on_request_start.append(on_request_start)
        trace_config.on_request_end.append(on_request_end)

        return trace_config

    async def _login_mock(self, username: str, password: str) -> bool:
        """Authenticate with mock server (simple POST /api/login).

        Populates token fields from mock response so is_authenticated works.
        """
        _LOGGER.debug("Debug mode: Using simple mock auth flow")

        try:
            session = await self._ensure_session()

            async with self._request_pacer:  # noqa: SIM117
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

                    data = await resp.json()
                    self._access_token = data.get("access_token")
                    self._refresh_token = data.get("refresh_token")
                    self._token_expiry = time.time() + data.get("expires_in", 3600)
                    self._authenticated = True
                    return True

        except aiohttp.ClientError as err:
            _LOGGER.error("Mock auth connection error: %s", err)
            raise AuthenticationError(f"Cannot connect to mock server: {err}") from err

    async def login(self, username: str, password: str) -> bool:
        """Authenticate with MELCloud Home via OAuth 2.0 PKCE.

        Args:
            username: Email address
            password: Password

        Returns:
            True if authentication successful

        Raises:
            AuthenticationError: If authentication fails
            ServiceUnavailableError: If server returns 5xx
        """
        _LOGGER.debug("Starting authentication flow for user: %s", username)

        if self._debug_mode:
            return await self._login_mock(username, password)

        try:
            session = await self._ensure_session()
            code_verifier, code_challenge = self._generate_pkce()
            state = (
                base64.urlsafe_b64encode(secrets.token_bytes(16)).rstrip(b"=").decode()
            )

            # Step 1: Pushed Authorization Request (PAR)
            _LOGGER.debug("Step 1: PAR request")
            async with self._request_pacer:  # noqa: SIM117
                async with session.post(
                    f"{self._auth_base}/connect/par",
                    data={
                        "response_type": "code",
                        "state": state,
                        "code_challenge": code_challenge,
                        "code_challenge_method": "S256",
                        "client_id": OAUTH_CLIENT_ID,
                        "scope": OAUTH_SCOPES,
                        "redirect_uri": OAUTH_REDIRECT_URI,
                    },
                    headers={"User-Agent": USER_AGENT},
                ) as resp:
                    if resp.status >= 500:
                        raise ServiceUnavailableError(resp.status)
                    if resp.status != 201:
                        raise AuthenticationError(
                            f"PAR request failed: HTTP {resp.status}"
                        )
                    par_data = await resp.json()
                    request_uri = par_data["request_uri"]
                    _LOGGER.debug("PAR OK: request_uri=%s...", request_uri[:50])

            # Step 2: Authorize — follow redirects to Cognito login page
            _LOGGER.debug("Step 2: Authorize redirect to Cognito")
            authorize_url = (
                f"{self._auth_base}/connect/authorize"
                f"?client_id={OAUTH_CLIENT_ID}&request_uri={request_uri}"
            )
            async with self._request_pacer:  # noqa: SIM117
                async with session.get(
                    authorize_url,
                    headers={"User-Agent": USER_AGENT},
                    allow_redirects=True,
                ) as resp:
                    final_url = str(resp.url)

                    if resp.status >= 500:
                        raise ServiceUnavailableError(resp.status)

                    parsed = urlparse(final_url)
                    if not (
                        parsed.hostname
                        and parsed.hostname.endswith(COGNITO_DOMAIN_SUFFIX)
                        and "/login" in parsed.path
                    ):
                        raise AuthenticationError(
                            f"Expected Cognito login page, got: {final_url}"
                        )

                    html = await resp.text()
                    csrf_token = self._extract_csrf_token(html)
                    if not csrf_token:
                        raise AuthenticationError(
                            "Failed to extract CSRF token from Cognito login page"
                        )
                    cognito_login_url = final_url
                    _LOGGER.debug("Cognito login page OK")

            # Step 3: Submit credentials to Cognito
            _LOGGER.debug("Step 3: Submit credentials to Cognito")
            async with self._request_pacer:  # noqa: SIM117
                async with session.post(
                    cognito_login_url,
                    data={
                        "_csrf": csrf_token,
                        "username": username,
                        "password": password,
                        "cognitoAsfData": "",
                    },
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) "
                            "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/22F76"
                        ),
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Origin": f"https://{urlparse(cognito_login_url).hostname}",
                        "Referer": cognito_login_url,
                    },
                    allow_redirects=True,
                ) as resp:
                    final_url = str(resp.url)

                    if resp.status >= 500:
                        raise ServiceUnavailableError(resp.status)

                    body = await resp.text()

                    # Check for auth errors
                    parsed = urlparse(final_url)
                    if parsed.hostname and parsed.hostname.endswith(
                        COGNITO_DOMAIN_SUFFIX
                    ):
                        raise AuthenticationError(
                            "Authentication failed: Invalid username or password"
                        )

            # Step 4: Extract callback URL from redirect page
            _LOGGER.debug("Step 4: Extract callback URL")
            callback_match = re.search(r"/connect/authorize/callback\?([^\"' ]+)", body)
            if not callback_match:
                # Check if code is directly in URL
                code_match = re.search(r"code=([^&\"' ]+)", final_url)
                if not code_match:
                    code_match = re.search(r"code=([^&\"' ]+)", body)
                if not code_match:
                    raise AuthenticationError(
                        "Failed to extract auth code or callback URL"
                    )
                auth_code = code_match.group(1)
            else:
                callback_qs = callback_match.group(1).replace("&amp;", "&")
                callback_url = (
                    f"{self._auth_base}/connect/authorize/callback?{callback_qs}"
                )

                # Step 5: Follow callback to get melcloudhome:// redirect with auth code
                _LOGGER.debug("Step 5: Follow callback for auth code")
                async with self._request_pacer:  # noqa: SIM117
                    async with session.get(
                        callback_url,
                        headers={"User-Agent": USER_AGENT},
                        allow_redirects=False,
                    ) as cb_resp:
                        location = cb_resp.headers.get("Location", "")
                        if not location.startswith("melcloudhome://"):
                            # Follow one more redirect hop
                            redirect_url = (
                                location
                                if location.startswith("http")
                                else f"{self._auth_base}{location}"
                            )
                            async with self._request_pacer:  # noqa: SIM117
                                async with session.get(
                                    redirect_url,
                                    headers={"User-Agent": USER_AGENT},
                                    allow_redirects=False,
                                ) as cb_resp2:
                                    location = cb_resp2.headers.get("Location", "")

                        code_match = re.search(r"code=([^&]+)", location)
                        if not code_match:
                            raise AuthenticationError(
                                "Failed to extract auth code from redirect"
                            )
                        auth_code = code_match.group(1)

            _LOGGER.debug("Got auth code: %s...", auth_code[:20])

            # Step 6: Exchange code for tokens
            _LOGGER.debug("Step 6: Token exchange")
            async with self._request_pacer:  # noqa: SIM117
                async with session.post(
                    f"{self._auth_base}/connect/token",
                    data={
                        "grant_type": "authorization_code",
                        "code": auth_code,
                        "redirect_uri": OAUTH_REDIRECT_URI,
                        "code_verifier": code_verifier,
                        "client_id": OAUTH_CLIENT_ID,
                    },
                    headers={"User-Agent": USER_AGENT},
                ) as resp:
                    if resp.status >= 500:
                        raise ServiceUnavailableError(resp.status)
                    if resp.status != 200:
                        raise AuthenticationError(
                            f"Token exchange failed: HTTP {resp.status}"
                        )

                    token_data = await resp.json()
                    self._access_token = token_data["access_token"]
                    self._refresh_token = token_data.get("refresh_token")
                    self._token_expiry = time.time() + token_data.get(
                        "expires_in", 3600
                    )
                    self._authenticated = True

                    _LOGGER.info("Authentication successful")
                    return True

        except aiohttp.ClientError as err:
            raise AuthenticationError(
                f"Network error during authentication: {err}"
            ) from err
        except Exception as err:
            if isinstance(err, (AuthenticationError, ServiceUnavailableError)):
                raise
            raise AuthenticationError(
                f"Unexpected error during authentication: {err}"
            ) from err

    async def refresh_access_token(self) -> bool:
        """Refresh the access token using the stored refresh token.

        Returns:
            True if refresh successful

        Raises:
            AuthenticationError: If no refresh token or refresh rejected
        """
        if not self._refresh_token:
            raise AuthenticationError("No refresh token available")

        session = await self._ensure_session()

        async with (
            self._request_pacer,
            session.post(
                f"{self._auth_base}/connect/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self._refresh_token,
                    "client_id": OAUTH_CLIENT_ID,
                },
                headers={"User-Agent": USER_AGENT},
            ) as resp,
        ):
            if resp.status != 200:
                self._authenticated = False
                self._access_token = None
                self._refresh_token = None
                raise AuthenticationError("Refresh token rejected")

            token_data = await resp.json()
            self._access_token = token_data["access_token"]
            self._refresh_token = token_data.get("refresh_token", self._refresh_token)
            self._token_expiry = time.time() + token_data.get("expires_in", 3600)
            self._authenticated = True
            return True

    async def get_session(self) -> aiohttp.ClientSession:
        """Get authenticated session.

        Returns:
            Authenticated aiohttp ClientSession

        Raises:
            AuthenticationError: If not authenticated
        """
        if not self._authenticated:
            raise AuthenticationError("Not authenticated - call login() first")

        return await self._ensure_session()

    async def logout(self) -> None:
        """Clear token state."""
        self._authenticated = False
        self._access_token = None
        self._refresh_token = None
        self._token_expiry = 0.0

    async def close(self) -> None:
        """Close session without logout."""
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None
        self._authenticated = False

    def _extract_csrf_token(self, html: str) -> str | None:
        """Extract CSRF token from Cognito login page HTML."""
        match = re.search(r'<input[^>]+name="_csrf"[^>]+value="([^"]+)"', html)
        if match:
            return match.group(1)

        match = re.search(r'<input[^>]+value="([^"]+)"[^>]+name="_csrf"', html)
        if match:
            return match.group(1)

        # Also try the PoC pattern (name then value without input prefix)
        match = re.search(r'name="_csrf"\s+value="([^"]+)"', html)
        if match:
            return match.group(1)

        return None
