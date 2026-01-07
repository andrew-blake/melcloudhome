"""MELCloud Home API client.

This module provides backward compatibility by composing ATAControlClient
and ATWControlClient while keeping shared methods (auth, context, energy).
"""

import logging
from typing import Any

import aiohttp

from .auth import MELCloudHomeAuth
from .client_ata import ATAControlClient
from .client_atw import ATWControlClient
from .const_ata import BASE_URL, MOCK_BASE_URL
from .exceptions import ApiError, AuthenticationError
from .models import AirToAirUnit, UserContext

_LOGGER = logging.getLogger(__name__)


class MELCloudHomeClient:
    """Client for MELCloud Home API."""

    def __init__(self, debug_mode: bool = False) -> None:
        """Initialize the client.

        Args:
            debug_mode: If True, use mock server at http://melcloud-mock:8080
        """
        self._debug_mode = debug_mode
        self._base_url = MOCK_BASE_URL if debug_mode else BASE_URL
        self._auth = MELCloudHomeAuth(debug_mode=debug_mode)
        self._user_context: UserContext | None = None

        # Composition: Delegate ATA and ATW control to specialized clients
        self.ata = ATAControlClient(self)
        self.atw = ATWControlClient(self)

        if debug_mode:
            _LOGGER.info(
                "🔧 Debug mode enabled - using mock server at %s", self._base_url
            )

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
            headers.setdefault("referer", f"{self._base_url}/dashboard")

            url = f"{self._base_url}{endpoint}"

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
                # Some endpoints (like control) return empty body
                if resp.content_length == 0 or resp.content_type == "":
                    return {}

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

    # =================================================================
    # Backward Compatibility Wrappers for ATA Methods
    # =================================================================

    async def set_power(self, unit_id: str, power: bool) -> None:
        """Turn device on or off (backward compatibility wrapper)."""
        return await self.ata.set_power(unit_id, power)

    async def set_temperature(self, unit_id: str, temperature: float) -> None:
        """Set target temperature (backward compatibility wrapper)."""
        return await self.ata.set_temperature(unit_id, temperature)

    async def set_mode(self, unit_id: str, mode: str) -> None:
        """Set operation mode (backward compatibility wrapper)."""
        return await self.ata.set_mode(unit_id, mode)

    async def set_fan_speed(self, unit_id: str, speed: str) -> None:
        """Set fan speed (backward compatibility wrapper)."""
        return await self.ata.set_fan_speed(unit_id, speed)

    async def set_vanes(self, unit_id: str, vertical: str, horizontal: str) -> None:
        """Set vane directions (backward compatibility wrapper)."""
        return await self.ata.set_vanes(unit_id, vertical, horizontal)

    # =================================================================
    # Energy/Telemetry Methods (Shared - used by ATA)
    # =================================================================

    async def get_energy_data(
        self,
        unit_id: str,
        from_time: Any,  # datetime
        to_time: Any,  # datetime
        interval: str = "Hour",
    ) -> dict[str, Any] | None:
        """
        Get energy consumption data for a unit.

        Args:
            unit_id: Unit UUID
            from_time: Start time (UTC-aware datetime)
            to_time: End time (UTC-aware datetime)
            interval: Aggregation interval - "Hour", "Day", "Week", or "Month"

        Returns:
            Energy telemetry data, or None if no data available (304)

        Raises:
            AuthenticationError: If session expired
            ApiError: If API request fails
        """
        endpoint = f"/api/telemetry/energy/{unit_id}"
        params = {
            "from": from_time.strftime("%Y-%m-%d %H:%M"),
            "to": to_time.strftime("%Y-%m-%d %H:%M"),
            "interval": interval,
            "measure": "cumulative_energy_consumed_since_last_upload",
        }

        try:
            # Use _api_request but need to handle 304 specially
            session = await self._auth.get_session()
            headers = {
                "Accept": "application/json",
                "x-csrf": "1",
                "referer": f"{self._base_url}/dashboard",
            }

            url = f"{self._base_url}{endpoint}"
            _LOGGER.debug("Energy API Request: GET %s", endpoint)

            async with session.get(url, params=params, headers=headers) as resp:
                _LOGGER.debug("Energy API Response: GET %s [%d]", endpoint, resp.status)

                if resp.status == 304:
                    # No new data available
                    return None

                if resp.status == 401:
                    raise AuthenticationError("Session expired - please login again")

                if resp.status >= 400:
                    try:
                        error_data = await resp.json()
                        error_msg = error_data.get("message", f"HTTP {resp.status}")
                    except Exception:
                        error_msg = f"HTTP {resp.status}"

                    raise ApiError(f"Energy API request failed: {error_msg}")

                result: dict[str, Any] = await resp.json()
                return result

        except aiohttp.ClientError as err:
            raise ApiError(f"Network error: {err}") from err

    def parse_energy_response(self, data: dict[str, Any] | None) -> float | None:
        """
        Parse energy telemetry response.

        Returns the most recent energy value in kWh.
        Converts from Wh (watt-hours) to kWh.

        Args:
            data: Energy telemetry response from API

        Returns:
            Energy value in kWh, or None if no data
        """
        if not data or "measureData" not in data:
            return None

        measure_data = data.get("measureData", [])
        if not measure_data:
            return None

        values = measure_data[0].get("values", [])
        if not values:
            return None

        # Get most recent value
        latest = values[-1]
        value_str = latest.get("value")
        if not value_str:
            return None

        try:
            # API returns values in Wh (watt-hours)
            # Convert to kWh for Home Assistant Energy Dashboard
            value_wh = float(value_str)
            return value_wh / 1000.0  # Convert Wh to kWh
        except (ValueError, TypeError) as err:
            _LOGGER.warning("Failed to parse energy value '%s': %s", value_str, err)
            return None
