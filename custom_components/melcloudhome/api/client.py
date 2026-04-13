"""MELCloud Home API client.

Provides unified API access using the Facade pattern:
- Shared authentication and HTTP request handling
- Device-specific control via composed clients (self.ata, self.atw)
- Shared energy tracking and user context methods
"""

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import aiohttp

from .auth import MELCloudHomeAuth
from .client_ata import ATAControlClient
from .client_atw import ATWControlClient
from .const_shared import (
    API_FIELD_MEASURE_DATA,
    API_FIELD_VALUE,
    API_FIELD_VALUES,
    API_REPORT_TRENDSUMMARY,
    API_TELEMETRY_ACTUAL,
    API_TELEMETRY_ENERGY,
    API_USER_CONTEXT,
    BASE_URL,
    MOCK_BASE_URL,
    USER_AGENT,
)
from .exceptions import ApiError, AuthenticationError, ServiceUnavailableError
from .models import UserContext
from .pacing import RequestPacer

_LOGGER = logging.getLogger(__name__)


class MELCloudHomeClient:
    """Client for MELCloud Home API."""

    def __init__(
        self,
        debug_mode: bool = False,
        request_pacer: RequestPacer | None = None,
    ) -> None:
        """Initialize the client.

        Args:
            debug_mode: If True, use mock server at http://melcloud-mock:8080
            request_pacer: Optional RequestPacer instance (for testing)
        """
        self._debug_mode = debug_mode
        self._base_url = MOCK_BASE_URL if debug_mode else BASE_URL
        self._user_context: UserContext | None = None
        self._on_tokens_refreshed: Callable[[], None] | None = None
        self._refresh_lock = asyncio.Lock()

        # Request pacing to prevent rate limiting (shared across all requests)
        self._request_pacer = request_pacer or RequestPacer()

        # Auth needs RequestPacer to prevent rate limiting during login
        self._auth = MELCloudHomeAuth(
            debug_mode=debug_mode, request_pacer=self._request_pacer
        )

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

    def restore_tokens(
        self,
        access_token: str | None,
        refresh_token: str | None,
        token_expiry: float,
    ) -> None:
        """Restore persisted token state."""
        self._auth.restore_tokens(access_token, refresh_token, token_expiry)

    def get_token_snapshot(self) -> dict[str, Any]:
        """Return current token state for persistence."""
        return self._auth.get_token_snapshot()

    @property
    def has_refresh_token(self) -> bool:
        """Check if a refresh token is available."""
        return self._auth.refresh_token is not None

    def set_on_tokens_refreshed(self, callback: Callable[[], None]) -> None:
        """Register callback for when tokens are refreshed proactively."""
        self._on_tokens_refreshed = callback

    async def refresh_access_token(self) -> bool:
        """Refresh the access token using stored refresh token."""
        return await self._auth.refresh_access_token()

    async def _api_request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        """Make an API request.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path (e.g., "/context")
            **kwargs: Additional arguments to pass to aiohttp request

        Returns:
            JSON response as dict, or None if 304 Not Modified

        Raises:
            AuthenticationError: If not authenticated
            ApiError: If API request fails
        """
        # Proactive token refresh BEFORE acquiring pacer — refresh_access_token
        # also acquires the pacer, so nesting would deadlock (asyncio.Lock is
        # not reentrant). Lock prevents concurrent refreshes from racing on
        # single-use refresh tokens.
        if self._auth.is_token_expired and self._auth.refresh_token:
            async with self._refresh_lock:
                # Double-check after acquiring lock — another request may have
                # already refreshed while we waited
                if self._auth.is_token_expired:
                    try:
                        await self._auth.refresh_access_token()
                        _LOGGER.info("Proactive token refresh successful")
                        if self._on_tokens_refreshed:
                            self._on_tokens_refreshed()
                    except AuthenticationError:
                        _LOGGER.warning(
                            "Proactive token refresh failed, will retry via login"
                        )

        async with self._request_pacer:
            if not self._auth.is_authenticated:
                raise AuthenticationError("Not authenticated - call login() first")

            try:
                session = await self._auth.get_session()

                # Bearer auth headers (no CSRF, no referer needed)
                headers = kwargs.pop("headers", {})
                headers.setdefault("Accept", "application/json")
                headers.setdefault("User-Agent", USER_AGENT)
                if self._auth.access_token:
                    headers["Authorization"] = f"Bearer {self._auth.access_token}"

                url = f"{self._base_url}{endpoint}"

                _LOGGER.debug("API Request: %s %s", method, endpoint)

                async with session.request(
                    method, url, headers=headers, **kwargs
                ) as resp:
                    _LOGGER.debug(
                        "API Response: %s %s [%d]", method, endpoint, resp.status
                    )

                    # Handle 304 Not Modified (telemetry endpoints may return this)
                    if resp.status == 304:
                        _LOGGER.debug("API Response: 304 Not Modified - no new data")
                        return None

                    # Handle authentication errors
                    if resp.status == 401:
                        raise AuthenticationError(
                            "Session expired - please login again"
                        )

                    # Handle server errors (MELCloud outage)
                    if resp.status >= 500:
                        raise ServiceUnavailableError(resp.status)

                    # Handle other client errors
                    if resp.status >= 400:
                        try:
                            error_data = await resp.json(content_type=None)
                            error_msg = error_data.get("message", f"HTTP {resp.status}")
                        except Exception:
                            error_msg = f"HTTP {resp.status}"

                        raise ApiError(f"API request failed: {error_msg}")

                    # Parse and return JSON response
                    # Some endpoints (like control) return empty body
                    if resp.content_length == 0 or resp.content_type == "":
                        return {}

                    # content_type=None because mobile BFF returns text/plain
                    result: dict[str, Any] = await resp.json(content_type=None)
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
        data = await self._api_request("GET", API_USER_CONTEXT)
        assert data is not None, "UserContext should never return None"
        self._user_context = UserContext.from_dict(data)
        return self._user_context

    # =================================================================
    # Energy/Telemetry Methods (Shared)
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
        endpoint = API_TELEMETRY_ENERGY.format(unit_id=unit_id)
        params = {
            "from": from_time.strftime("%Y-%m-%d %H:%M"),
            "to": to_time.strftime("%Y-%m-%d %H:%M"),
            "interval": interval,
            "measure": "cumulative_energy_consumed_since_last_upload",
        }

        return await self._api_request(
            "GET",
            endpoint,
            params=params,
        )

    def _parse_outdoor_temp(self, response: dict[str, Any] | list) -> float | None:
        """Extract outdoor temperature from trendsummary response.

        Response format (mobile BFF wraps in a list):
        [
          {
            "datasets": [
              {
                "label": "REPORT.TREND_SUMMARY_REPORT.DATASET.LABELS.OUTDOOR_TEMPERATURE",
                "data": [{"x": "2026-01-12T20:00:00", "y": 11}, ...]
              }
            ]
          }
        ]

        Args:
            response: Trendsummary API response (list or dict)

        Returns:
            Outdoor temperature in Celsius, or None if not available
        """
        # Mobile BFF wraps the report in a list
        report = response[0] if isinstance(response, list) and response else response
        datasets = report.get("datasets", []) if isinstance(report, dict) else []
        for dataset in datasets:
            label = dataset.get("label", "")
            if "OUTDOOR_TEMPERATURE" in label:
                data = dataset.get("data", [])
                if data:
                    # Return latest value (last datapoint)
                    value = data[-1].get("y")
                    return float(value) if value is not None else None
        return None  # No outdoor temp dataset found

    async def get_outdoor_temperature(self, unit_id: str) -> float | None:
        """Get latest outdoor temperature for an ATA unit.

        Queries trendsummary endpoint for last hour, extracts most recent
        outdoor temperature from the OUTDOOR_TEMPERATURE dataset.

        Args:
            unit_id: ATA unit UUID

        Returns:
            Outdoor temperature in Celsius, or None if not available
        """
        # Build time range: last 1 hour
        now = datetime.now(UTC)
        from_time = now - timedelta(hours=1)

        # Format: 2026-01-12T20:00:00.0000000 (7 decimal places for nanoseconds)
        params = {
            "unitId": unit_id,
            "period": "Hourly",
            "from": from_time.strftime("%Y-%m-%dT%H:%M:%S.0000000"),
            "to": now.strftime("%Y-%m-%dT%H:%M:%S.0000000"),
        }

        try:
            response = await self._api_request(
                "GET", API_REPORT_TRENDSUMMARY, params=params
            )
            if response is None:
                _LOGGER.debug(
                    "Trendsummary returned None for unit %s (from=%s, to=%s)",
                    unit_id,
                    params["from"],
                    params["to"],
                )
                return None
            return self._parse_outdoor_temp(response)
        except Exception:
            # Log at debug level - outdoor temp is nice-to-have, not critical
            _LOGGER.debug(
                "Failed to fetch outdoor temperature for unit %s",
                unit_id,
                exc_info=True,
            )
            return None

    async def get_telemetry_actual(
        self,
        unit_id: str,
        from_time: Any,  # datetime
        to_time: Any,  # datetime
        measure: str,
    ) -> dict[str, Any] | None:
        """
        Get actual telemetry data for ATW device.

        Args:
            unit_id: ATW device UUID
            from_time: Start time (UTC-aware datetime)
            to_time: End time (UTC-aware datetime)
            measure: Measure name (snake_case: "flow_temperature", etc.)

        Returns:
            Telemetry data with timestamped values, or None if 304 Not Modified

        Example response:
            {
                "measureData": [{
                    "deviceId": "unit-uuid",
                    "type": "flowTemperature",
                    "values": [
                        {"time": "2026-01-14 10:00:00.000000000", "value": "45.2"},
                        {"time": "2026-01-14 10:01:00.000000000", "value": "45.3"},
                    ]
                }]
            }

        Raises:
            AuthenticationError: Session expired (401)
            ApiError: API request failed
        """
        params = {
            "from": from_time.strftime("%Y-%m-%d %H:%M"),
            "to": to_time.strftime("%Y-%m-%d %H:%M"),
            "measure": measure,
        }

        return await self._api_request(
            "GET",
            API_TELEMETRY_ACTUAL.format(unit_id=unit_id),
            params=params,
        )

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
        if not data or API_FIELD_MEASURE_DATA not in data:
            return None

        measure_data = data.get(API_FIELD_MEASURE_DATA, [])
        if not measure_data:
            return None

        values = measure_data[0].get(API_FIELD_VALUES, [])
        if not values:
            return None

        # Get most recent value
        latest = values[-1]
        value_str = latest.get(API_FIELD_VALUE)
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
