"""MELCloud Home API client."""

import logging
from typing import Any

import aiohttp

from .auth import MELCloudHomeAuth
from .const import BASE_URL
from .exceptions import ApiError, AuthenticationError
from .models import AirToAirUnit, UserContext

_LOGGER = logging.getLogger(__name__)


class MELCloudHomeClient:
    """Client for MELCloud Home API."""

    def __init__(self) -> None:
        """Initialize the client."""
        self._auth = MELCloudHomeAuth()
        self._user_context: UserContext | None = None

    async def login(self, username: str, password: str) -> bool:
        """
        Authenticate with MELCloud Home.

        Args:
            username: Email address
            password: Password

        Returns:
            True if authentication successful

        Raises:
            AuthenticationError: If authentication fails
        """
        return await self._auth.login(username, password)

    async def logout(self) -> None:
        """Logout and clean up session."""
        await self._auth.logout()

    async def close(self) -> None:
        """Close client session."""
        await self._auth.close()

    @property
    def is_authenticated(self) -> bool:
        """Check if client is authenticated."""
        return self._auth.is_authenticated

    async def _api_request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Make an API request.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path (e.g., "/api/user/context")
            **kwargs: Additional arguments to pass to aiohttp request

        Returns:
            JSON response as dict

        Raises:
            AuthenticationError: If not authenticated
            ApiError: If API request fails
        """
        if not self._auth.is_authenticated:
            raise AuthenticationError("Not authenticated - call login() first")

        try:
            session = await self._auth.get_session()

            # CRITICAL: All API requests require these headers
            headers = kwargs.pop("headers", {})
            headers.setdefault("Accept", "application/json")
            headers.setdefault("x-csrf", "1")
            headers.setdefault("referer", f"{BASE_URL}/dashboard")

            url = f"{BASE_URL}{endpoint}"

            _LOGGER.debug("API Request: %s %s", method, endpoint)

            async with session.request(method, url, headers=headers, **kwargs) as resp:
                _LOGGER.debug("API Response: %s %s [%d]", method, endpoint, resp.status)

                # Handle authentication errors
                if resp.status == 401:
                    raise AuthenticationError("Session expired - please login again")

                # Handle other errors
                if resp.status >= 400:
                    try:
                        error_data = await resp.json()
                        error_msg = error_data.get("message", f"HTTP {resp.status}")
                    except Exception:
                        error_msg = f"HTTP {resp.status}"

                    raise ApiError(f"API request failed: {error_msg}")

                # Parse and return JSON response
                result: dict[str, Any] = await resp.json()
                return result

        except aiohttp.ClientError as err:
            raise ApiError(f"Network error: {err}") from err

    async def get_user_context(self) -> UserContext:
        """
        Fetch user context (all buildings, devices, and state).

        This is the main endpoint that returns complete device state.

        Returns:
            UserContext with all buildings and devices

        Raises:
            AuthenticationError: If not authenticated
            ApiError: If API request fails
        """
        data = await self._api_request("GET", "/api/user/context")
        self._user_context = UserContext.from_dict(data)
        return self._user_context

    async def get_devices(self) -> list[AirToAirUnit]:
        """
        Get all air-to-air units across all buildings.

        This is a convenience method that fetches user context
        and returns a flat list of all devices.

        Returns:
            List of all air-to-air units

        Raises:
            AuthenticationError: If not authenticated
            ApiError: If API request fails
        """
        context = await self.get_user_context()
        return context.get_all_units()

    async def get_device(self, unit_id: str) -> AirToAirUnit | None:
        """
        Get a specific device by ID.

        Args:
            unit_id: Device ID (UUID)

        Returns:
            Device if found, None otherwise

        Raises:
            AuthenticationError: If not authenticated
            ApiError: If API request fails
        """
        context = await self.get_user_context()
        return context.get_unit_by_id(unit_id)
