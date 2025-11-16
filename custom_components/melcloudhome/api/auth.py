"""Authentication handling for MELCloud Home API."""

import logging
import re
from typing import Any

import aiohttp
from aiohttp import TraceConfig, TraceRequestEndParams, TraceRequestStartParams

from .const import BASE_URL, USER_AGENT
from .exceptions import AuthenticationError

_LOGGER = logging.getLogger(__name__)


class MELCloudHomeAuth:
    """Handle MELCloud Home authentication via AWS Cognito OAuth."""

    def __init__(self) -> None:
        """Initialize authenticator."""
        self._session: aiohttp.ClientSession | None = None
        self._authenticated = False

        # AWS Cognito OAuth configuration (from discovery docs)
        self._cognito_base = (
            "https://live-melcloudhome.auth.eu-west-1.amazoncognito.com"
        )
        self._auth_base = "https://auth.melcloudhome.com"

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
                    c for c in session.cookie_jar if "melcloudhome.com" in c["domain"]
                ]
                if melcloud_cookies:
                    _LOGGER.debug(
                        "  Cookie jar has %d melcloudhome.com cookie(s)",
                        len(melcloud_cookies),
                    )

        trace_config.on_request_start.append(on_request_start)
        trace_config.on_request_end.append(on_request_end)

        return trace_config

    async def login(self, username: str, password: str) -> bool:
        """
        Authenticate with MELCloud Home using Playwright.

        Uses headless browser to complete OAuth flow and extract session cookies.

        Args:
            username: Email address
            password: Password

        Returns:
            True if authentication successful

        Raises:
            AuthenticationError: If authentication fails
        """
        _LOGGER.debug("Starting Playwright authentication for user: %s", username)

        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                # Launch browser (headless=False for debugging)
                _LOGGER.debug("Launching browser")
                browser = await p.chromium.launch(headless=False, slow_mo=1000)

                # Create browser context with standard user agent
                context = await browser.new_context(
                    user_agent=USER_AGENT,
                    viewport={"width": 1280, "height": 720},
                )

                page = await context.new_page()

                try:
                    # Navigate to login page
                    _LOGGER.debug("Navigating to login page")
                    await page.goto(
                        f"{BASE_URL}/bff/login?returnUrl=/dashboard", timeout=30000
                    )

                    # Wait for page to load
                    await page.wait_for_load_state("load")
                    _LOGGER.debug("Page loaded")

                    # Check if there are iframes
                    iframes = page.frames
                    _LOGGER.debug(f"Found {len(iframes)} frames on page")

                    # Wait for the username input to be visible (try all frames)
                    username_input = None
                    for frame in iframes:
                        try:
                            username_input = await frame.wait_for_selector(
                                "#signInFormUsername", state="attached", timeout=2000
                            )
                            if username_input:
                                _LOGGER.debug(
                                    f"Found username input in frame: {frame.url}"
                                )
                                # Fill credentials in this frame
                                await frame.fill("#signInFormUsername", username)
                                await frame.fill("#signInFormPassword", password)
                                _LOGGER.debug("Credentials filled successfully")

                                # Click submit button
                                await frame.click('input[name="signInSubmitButton"]')
                                _LOGGER.debug("Submit button clicked")
                                break
                        except Exception as e:
                            _LOGGER.debug(f"Input not in frame {frame.url}: {e}")
                            continue

                    if not username_input:
                        raise AuthenticationError(
                            "Could not find login form in any frame"
                        )

                    # Wait for redirect to dashboard
                    _LOGGER.debug("Waiting for authentication redirect")
                    try:
                        await page.wait_for_url("**/dashboard", timeout=30000)
                        _LOGGER.info("Successfully reached dashboard")
                    except Exception as e:
                        # Check where we actually ended up
                        current_url = page.url
                        _LOGGER.warning(
                            "Did not reach dashboard. Current URL: %s", current_url
                        )
                        _LOGGER.debug("Wait exception: %s", e)

                        # Take a screenshot for debugging
                        await page.screenshot(path="/tmp/melcloud_after_login.png")
                        _LOGGER.debug(
                            "Screenshot saved to /tmp/melcloud_after_login.png"
                        )

                        if (
                            "amazoncognito.com/login" in current_url
                            or "error" in current_url.lower()
                        ):
                            raise AuthenticationError(
                                f"Login failed - still at: {current_url}"
                            ) from e
                        # If we're at melcloudhome.com but not /dashboard, continue anyway
                        if "melcloudhome.com" in current_url:
                            _LOGGER.warning("Continuing despite not reaching dashboard")
                        else:
                            raise AuthenticationError(
                                f"Unexpected URL after login: {current_url}"
                            ) from e

                    # Extract cookies from browser context
                    _LOGGER.debug("Extracting cookies from browser")
                    playwright_cookies = await context.cookies()

                    # Filter and transfer session cookies to aiohttp
                    session = await self._ensure_session()
                    cookie_count = 0

                    for cookie in playwright_cookies:
                        # Only transfer __Secure- cookies from melcloudhome.com
                        if cookie.get("domain") == "melcloudhome.com" and cookie[
                            "name"
                        ].startswith("__Secure-"):
                            # Add to aiohttp cookie jar
                            session.cookie_jar.update_cookies(
                                {cookie["name"]: cookie["value"]},
                                response_url=f"https://melcloudhome.com{cookie.get('path', '/')}",
                            )
                            cookie_count += 1
                            _LOGGER.debug("Transferred cookie: %s", cookie["name"])

                    _LOGGER.info(
                        "Transferred %d session cookies to aiohttp", cookie_count
                    )

                    if cookie_count == 0:
                        raise AuthenticationError(
                            "No session cookies found after login"
                        )

                    self._authenticated = True
                    return True

                finally:
                    # Clean up browser resources
                    await context.close()
                    await browser.close()
                    _LOGGER.debug("Browser closed")

        except ImportError as err:
            raise AuthenticationError(
                "Playwright not installed. Run: pip install playwright && playwright install chromium"
            ) from err
        except Exception as err:
            if isinstance(err, AuthenticationError):
                raise
            _LOGGER.error("Unexpected error during Playwright authentication: %s", err)
            raise AuthenticationError(f"Authentication failed: {err}") from err

    def _get_session_cookies(self) -> dict[str, str]:
        """
        Extract session cookies from jar.

        aiohttp has issues with __Secure- prefixed cookies, so we manually extract them.
        Only returns the actual session cookies, not OAuth flow cookies.

        Returns:
            Dictionary of cookie name -> value for melcloudhome.com session cookies
        """
        if not self._session:
            return {}

        cookies = {}
        for cookie in self._session.cookie_jar:
            # Get cookies for melcloudhome.com domain only (not auth or cognito subdomains)
            domain = cookie.get("domain", "")
            # Only include session cookies (the __Secure- ones)
            if domain == "melcloudhome.com" and cookie.key.startswith("__Secure-"):
                cookies[cookie.key] = cookie.value

        return cookies

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
            # Cookies should now be sent automatically by aiohttp
            async with session.get(
                f"{BASE_URL}/api/user/context",
                headers={"Accept": "application/json"},
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
                # Call logout endpoint
                await self._session.get(f"{BASE_URL}/bff/logout")
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
