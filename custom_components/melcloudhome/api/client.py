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
    API_REPORT_COMFORT_GRAPH,
    API_REPORT_TRENDSUMMARY,
    API_TELEMETRY_ACTUAL,
    API_TELEMETRY_ENERGY,
    API_USER_CONTEXT,
    BASE_URL,
    MOCK_BASE_URL,
    MOCK_WS_HASH_URL,
    MOCK_WS_HOST,
    USER_AGENT,
    WS_HASH_URL,
    WS_HOST,
)
from .exceptions import ApiError, AuthenticationError, ServiceUnavailableError
from .models import UserContext
from .pacing import RequestPacer
from .parsing import Reading

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
        self._ws_hash_url = MOCK_WS_HASH_URL if debug_mode else WS_HASH_URL
        self._ws_host = MOCK_WS_HOST if debug_mode else WS_HOST
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

    @property
    def ws_host(self) -> str:
        """WebSocket host for this client's mode (mock in debug mode)."""
        return self._ws_host

    async def async_ws_session(self) -> Any:
        """Return the authenticated aiohttp session (for the WebSocket).

        Shares the same session (and User-Agent) as REST requests.
        """
        return await self._auth.get_session()

    async def async_get_ws_hash(self) -> str:
        """Fetch a real-time WebSocket credential ("hash") for this account.

        Exchanges the mobile-BFF bearer for a ``{"hash", "userId"}`` document
        at the Lambda token endpoint, mirroring what the official app does.
        Refreshes the access token first if it is expired, so callers don't
        need to. Returns the ``hash`` used to open ``ws_host/?hash=<hash>``.

        Raises:
            AuthenticationError: if the endpoint rejects the bearer (401/403).
            ApiError: for any other non-200 response.
        """
        # Proactive refresh — same pattern as _api_request.
        if self._auth.is_token_expired and self._auth.refresh_token:
            async with self._refresh_lock:
                if self._auth.is_token_expired:
                    await self._auth.refresh_access_token()
                    if self._on_tokens_refreshed:
                        self._on_tokens_refreshed()

        session = await self._auth.get_session()
        headers = {"Authorization": f"Bearer {self._auth.access_token}"}
        async with session.get(self._ws_hash_url, headers=headers) as resp:
            if resp.status in (401, 403):
                raise AuthenticationError(
                    f"WebSocket token endpoint rejected credentials ({resp.status})"
                )
            if resp.status != 200:
                raise ApiError(f"WebSocket token endpoint returned {resp.status}")
            data = await resp.json()

        ws_hash = data.get("hash")
        if not ws_hash:
            raise ApiError("WebSocket token response missing 'hash'")
        return str(ws_hash)

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
                        _LOGGER.debug("Proactive token refresh successful")
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
                if kwargs.get("json") is not None:
                    _LOGGER.debug("API Request payload: %s", kwargs["json"])

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
        assert data is not None, "UserContext should never return None"  # noqa: S101 # assert guards internal invariant, not a security boundary
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

    def _parse_outdoor_temp(self, response: dict[str, Any] | list) -> Reading | None:
        """Extract outdoor temperature and its timestamp from trendsummary response.

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

        The response mixes genuine unit readings with synthetic chart points
        the server appends: bucket-aligned repeats of the last value (e.g.
        08:00:00, 09:00:00) and a final point stamped with the query's own
        "to" parameter echoed back verbatim. Genuine readings carry the unit's
        actual upload time with arbitrary seconds (e.g. 07:15:24), so points
        with seconds == 0 are treated as synthetic and skipped — the caller
        sends a seconds-aligned "to" precisely so the echo point is caught by
        the same rule. A genuine reading landing exactly on :00 seconds is
        rare and costs at most falling back to the previous reading.

        Args:
            response: Trendsummary API response (list or dict)

        Returns:
            A Reading (temperature in Celsius, UTC-aware datetime of the
            reading), or None if the response holds no genuine reading. The
            timestamp lets consumers detect stale data: units stop uploading
            outdoor temperature while idle, so the latest reading can be
            hours old (issues #152, #171). The "x" timestamps are naive but
            confirmed UTC: across ~1,700 genuine readings from
            actively-uploading units, none led the UTC query time, which
            local-time (BST, UTC+1) stamps would by up to an hour.
        """
        # Mobile BFF wraps the report in a list
        report = response[0] if isinstance(response, list) and response else response
        datasets = report.get("datasets", []) if isinstance(report, dict) else []
        for dataset in datasets:
            label = dataset.get("label", "")
            if "OUTDOOR_TEMPERATURE" in label:
                for point in reversed(dataset.get("data", [])):
                    recorded_at = point.get("x")
                    if recorded_at is None:
                        continue
                    timestamp = datetime.fromisoformat(str(recorded_at)).replace(
                        tzinfo=UTC
                    )
                    if timestamp.second == 0:
                        continue  # Synthetic chart point, not a unit reading
                    value = point.get("y")
                    if value is None:
                        continue  # Reading without a value; try older points
                    return Reading(float(value), timestamp)
                return None  # No genuine reading in the window
        return None  # No outdoor temp dataset found

    async def _get_report_outdoor_temperature(
        self, endpoint: str, unit_id: str, lookback: timedelta, log_label: str
    ) -> Reading | None:
        """Shared implementation for get_outdoor_temperature/get_atw_outdoor_temperature.

        Both query a /report/v1/ endpoint with period=Hourly and parse the
        same response shape via _parse_outdoor_temp - they differ only in
        endpoint, lookback window, and log wording.

        "to" is truncated to seconds=0 so the server's to-echo point is
        identifiable as synthetic (see _parse_outdoor_temp).

        Raises whatever _api_request/_parse_outdoor_temp raise - callers
        must handle failures. This is deliberate: a real error (e.g. a 500)
        must be distinguishable from a successful poll finding no genuine
        reading, so the coordinator can record it for diagnostics (issue
        #251) instead of both cases looking identically like "no data yet".
        """
        now = datetime.now(UTC).replace(second=0, microsecond=0)
        from_time = now - lookback

        # Format: 2026-01-12T20:00:00.0000000 (7 decimal places for nanoseconds)
        params = {
            "unitId": unit_id,
            "period": "Hourly",
            "from": from_time.strftime("%Y-%m-%dT%H:%M:%S.0000000"),
            "to": now.strftime("%Y-%m-%dT%H:%M:%S.0000000"),
        }

        response = await self._api_request("GET", endpoint, params=params)
        if response is None:
            _LOGGER.debug(
                "%s returned None for unit %s (from=%s, to=%s)",
                log_label,
                unit_id,
                params["from"],
                params["to"],
            )
            return None
        return self._parse_outdoor_temp(response)

    async def get_outdoor_temperature(self, unit_id: str) -> Reading | None:
        """Get latest outdoor temperature for an ATA unit.

        Queries trendsummary with Hourly period, which is the only period
        whose datapoints carry genuine reading timestamps — Daily returns
        30-minute bucket aggregates whose labels are not reading times and
        whose values can diverge from the actual latest reading (issue #152's
        quality problems, plus a midnight-rollover artifact where the freshest
        Daily label leads the query time by up to an hour).

        48h lookback: units stop uploading while idle, so a short window
        returns no genuine readings for them (the bug behind #111). Live
        response-time spikes (500 errors seen at 168h/7 days) show the
        server slows sharply past ~72h, so 48h trades some idle-unit
        tolerance for reliability and being a better-behaved API client.
        The coordinator keeps the previous value when this returns None.

        Args:
            unit_id: ATA unit UUID

        Returns:
            A Reading (temperature in Celsius, UTC-aware datetime of the
            reading), or None if not available
        """
        return await self._get_report_outdoor_temperature(
            API_REPORT_TRENDSUMMARY, unit_id, timedelta(hours=48), "trendsummary"
        )

    async def get_atw_outdoor_temperature(self, unit_id: str) -> Reading | None:
        """Get latest outdoor temperature for an ATW unit.

        ATW's live /context OutdoorTemperature can be present but silently
        wrong (issue #251) or absent entirely, with no way to tell which from
        the value alone, so this always queries the comfort-graph report
        instead of ever trusting the live value.

        Uses period=Hourly with a 24h window: comfort-graph's Hourly period
        hard-fails (500) for windows starting more than ~4 days back
        regardless of width, so unlike ATA's 48h trendsummary lookback this
        can't reach further back. 24h comfortably covers the largest observed
        reporting gap (3.5h) between genuine readings, with margin.

        Reuses _parse_outdoor_temp's UTC-timestamp assumption, which was
        empirically justified for ATA's trendsummary endpoint - verified
        separately for comfort-graph (2026-08-17): across 108 genuine
        readings over a 24h window for a real ATW unit, none led the UTC
        query time, which local-time (CEST, UTC+2 in August) stamps would by
        up to two hours.

        Args:
            unit_id: ATW unit UUID

        Returns:
            A Reading (temperature in Celsius, UTC-aware datetime of the
            reading), or None if not available
        """
        return await self._get_report_outdoor_temperature(
            API_REPORT_COMFORT_GRAPH, unit_id, timedelta(hours=24), "comfort-graph"
        )

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
