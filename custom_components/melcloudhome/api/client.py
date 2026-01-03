"""MELCloud Home API client."""

import logging
from typing import Any

import aiohttp

from .auth import MELCloudHomeAuth
from .const import BASE_URL, MOCK_BASE_URL, TEMP_MAX_HEAT, TEMP_MIN_HEAT, TEMP_STEP
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

    async def set_power(self, unit_id: str, power: bool) -> None:
        """
        Turn device on or off.

        Args:
            unit_id: Device ID (UUID)
            power: True to turn on, False to turn off

        Raises:
            AuthenticationError: If not authenticated
            ApiError: If API request fails
        """
        payload = {
            "power": power,
            "operationMode": None,
            "setFanSpeed": None,
            "vaneHorizontalDirection": None,
            "vaneVerticalDirection": None,
            "setTemperature": None,
            "temperatureIncrementOverride": None,
            "inStandbyMode": None,
        }

        await self._api_request(
            "PUT",
            f"/api/ataunit/{unit_id}",
            json=payload,
        )

    async def set_temperature(self, unit_id: str, temperature: float) -> None:
        """
        Set target temperature.

        Args:
            unit_id: Device ID (UUID)
            temperature: Target temperature in Celsius (10.0-31.0, 0.5° increments)

        Raises:
            AuthenticationError: If not authenticated
            ApiError: If API request fails
            ValueError: If temperature is out of range
        """
        if not TEMP_MIN_HEAT <= temperature <= TEMP_MAX_HEAT:
            raise ValueError(
                f"Temperature must be between {TEMP_MIN_HEAT} and {TEMP_MAX_HEAT}°C"
            )

        # Check if temperature is in correct increments
        if (temperature / TEMP_STEP) % 1 != 0:
            raise ValueError(f"Temperature must be in {TEMP_STEP}° increments")

        payload = {
            "power": None,
            "operationMode": None,
            "setFanSpeed": None,
            "vaneHorizontalDirection": None,
            "vaneVerticalDirection": None,
            "setTemperature": temperature,
            "temperatureIncrementOverride": None,
            "inStandbyMode": None,
        }

        await self._api_request(
            "PUT",
            f"/api/ataunit/{unit_id}",
            json=payload,
        )

    async def set_mode(self, unit_id: str, mode: str) -> None:
        """
        Set operation mode.

        Args:
            unit_id: Device ID (UUID)
            mode: Operation mode - "Heat", "Cool", "Automatic", "Dry", or "Fan"

        Raises:
            AuthenticationError: If not authenticated
            ApiError: If API request fails
            ValueError: If mode is invalid
        """
        valid_modes = {"Heat", "Cool", "Automatic", "Dry", "Fan"}
        if mode not in valid_modes:
            raise ValueError(f"Invalid mode: {mode}. Must be one of {valid_modes}")

        payload = {
            "power": None,
            "operationMode": mode,
            "setFanSpeed": None,
            "vaneHorizontalDirection": None,
            "vaneVerticalDirection": None,
            "setTemperature": None,
            "temperatureIncrementOverride": None,
            "inStandbyMode": None,
        }

        await self._api_request(
            "PUT",
            f"/api/ataunit/{unit_id}",
            json=payload,
        )

    async def set_fan_speed(self, unit_id: str, speed: str) -> None:
        """
        Set fan speed.

        Args:
            unit_id: Device ID (UUID)
            speed: Fan speed - "Auto", "One", "Two", "Three", "Four", or "Five"

        Raises:
            AuthenticationError: If not authenticated
            ApiError: If API request fails
            ValueError: If speed is invalid
        """
        valid_speeds = {"Auto", "One", "Two", "Three", "Four", "Five"}
        if speed not in valid_speeds:
            raise ValueError(
                f"Invalid fan speed: {speed}. Must be one of {valid_speeds}"
            )

        payload = {
            "power": None,
            "operationMode": None,
            "setFanSpeed": speed,
            "vaneHorizontalDirection": None,
            "vaneVerticalDirection": None,
            "setTemperature": None,
            "temperatureIncrementOverride": None,
            "inStandbyMode": None,
        }

        await self._api_request(
            "PUT",
            f"/api/ataunit/{unit_id}",
            json=payload,
        )

    async def set_vanes(self, unit_id: str, vertical: str, horizontal: str) -> None:
        """
        Set vane directions.

        Args:
            unit_id: Device ID (UUID)
            vertical: Vertical direction - "Auto", "Swing", "One", "Two", "Three",
                      "Four", or "Five"
            horizontal: Horizontal direction - "Auto", "Swing", "Left", "LeftCentre",
                        "Centre", "RightCentre", or "Right" (British spelling)

        Raises:
            AuthenticationError: If not authenticated
            ApiError: If API request fails
            ValueError: If vertical or horizontal is invalid
        """
        valid_vertical = {"Auto", "Swing", "One", "Two", "Three", "Four", "Five"}
        # Horizontal uses British-spelled named positions (official API format)
        valid_horizontal = {
            "Auto",
            "Swing",
            "Left",
            "LeftCentre",
            "Centre",
            "RightCentre",
            "Right",
        }

        if vertical not in valid_vertical:
            raise ValueError(
                f"Invalid vertical direction: {vertical}. "
                f"Must be one of {valid_vertical}"
            )

        if horizontal not in valid_horizontal:
            raise ValueError(
                f"Invalid horizontal direction: {horizontal}. "
                f"Must be one of {valid_horizontal}"
            )

        # Denormalize VERTICAL vane direction: convert word strings back to numeric
        # strings that the API expects (API returns "0", "1", etc. which we normalize
        # to "Auto", "One", etc. for HA, but need to convert back when sending)
        vertical_to_numeric = {
            "Auto": "0",
            "Swing": "7",
            "One": "1",
            "Two": "2",
            "Three": "3",
            "Four": "4",
            "Five": "5",
        }

        vertical_numeric = vertical_to_numeric.get(vertical, vertical)
        # Horizontal uses named strings (British spelling) - send as-is
        horizontal_string = horizontal

        payload = {
            "power": None,
            "operationMode": None,
            "setFanSpeed": None,
            "vaneHorizontalDirection": horizontal_string,
            "vaneVerticalDirection": vertical_numeric,
            "setTemperature": None,
            "temperatureIncrementOverride": None,
            "inStandbyMode": None,
        }

        await self._api_request(
            "PUT",
            f"/api/ataunit/{unit_id}",
            json=payload,
        )

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
