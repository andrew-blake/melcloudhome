"""Telemetry tracking for MELCloud Home ATW devices.

SIMPLIFIED APPROACH (validated via spike):
- Fetch telemetry from API
- Update sensor state with latest value
- HA recorder auto-creates statistics (no manual import needed)
"""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import TYPE_CHECKING, Any

from .api.client import MELCloudHomeClient
from .api.models import AirToWaterUnit, UserContext
from .const import ATW_TELEMETRY_MEASURES, DATA_LOOKBACK_HOURS_TELEMETRY

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Jitter configuration for telemetry polling (all values in seconds)
# Reduced from original values since RequestPacer handles base rate limiting
TELEMETRY_INTER_DEVICE_JITTER_MIN = 0.1
TELEMETRY_INTER_DEVICE_JITTER_MAX = 1.0
TELEMETRY_INTER_MEASURE_JITTER_MIN = 0.1
TELEMETRY_INTER_MEASURE_JITTER_MAX = 0.5


class TelemetryTracker:
    """Manages telemetry data polling for ATW devices.

    Simplified approach (no manual statistics import):
    - Fetch telemetry from API (4-hour sparse data)
    - Extract latest value for sensor state
    - HA recorder auto-creates statistics from sensor state updates
    """

    def __init__(
        self,
        hass: HomeAssistant,
        client: MELCloudHomeClient,
        execute_with_retry: Callable[
            [Callable[[], Awaitable[Any]], str], Awaitable[Any]
        ],
        get_coordinator_data: Callable[[], UserContext | None],
    ) -> None:
        """Initialize telemetry tracker.

        Args:
            hass: Home Assistant instance
            client: MELCloud Home API client
            execute_with_retry: Coordinator's retry wrapper for API calls
            get_coordinator_data: Callable to get current coordinator data
        """
        self._hass = hass
        self._client = client
        self._execute_with_retry = execute_with_retry
        self._get_coordinator_data = get_coordinator_data

        # Telemetry data cache (latest values for sensor state)
        # Structure: {unit_id: {measure_name: temperature_celsius}}
        self._telemetry_data: dict[str, dict[str, float | None]] = {}

    async def async_setup(self) -> None:
        """Set up telemetry tracker."""
        _LOGGER.info("Setting up telemetry tracker")

    async def async_update_telemetry_data(self, now: datetime | None = None) -> None:
        """Update telemetry data for all ATW units.

        Fetches telemetry for all measures, updates sensor state with latest value.
        HA recorder automatically creates statistics from sensor state updates.

        Args:
            now: Optional current time (for testing)
        """
        coordinator_data = self._get_coordinator_data()
        if not coordinator_data:
            return

        try:
            for building in coordinator_data.buildings:
                for i, unit in enumerate(building.air_to_water_units):
                    try:
                        await self._update_unit_telemetry(unit)

                        # Inter-device jitter (except last device)
                        if i < len(building.air_to_water_units) - 1:
                            jitter = random.uniform(
                                TELEMETRY_INTER_DEVICE_JITTER_MIN,
                                TELEMETRY_INTER_DEVICE_JITTER_MAX,
                            )
                            _LOGGER.debug(
                                "Inter-device jitter: %.1fs before next device", jitter
                            )
                            await asyncio.sleep(jitter)

                    except Exception as err:
                        _LOGGER.error(
                            "Error fetching telemetry for unit %s: %s",
                            unit.name,
                            err,
                        )

        except Exception as err:
            _LOGGER.error("Error updating telemetry data: %s", err)

    async def _update_unit_telemetry(self, unit: AirToWaterUnit) -> None:
        """Update telemetry data for a single ATW unit.

        Args:
            unit: AirToWaterUnit to update telemetry for
        """
        _LOGGER.debug("Fetching telemetry for unit %s (%s)", unit.name, unit.id)

        # Initialize unit cache if needed
        if unit.id not in self._telemetry_data:
            self._telemetry_data[unit.id] = {}

        # Fetch each measure with jitter
        for i, measure in enumerate(ATW_TELEMETRY_MEASURES):
            try:
                await self._fetch_measure(unit, measure)

                # Jitter between measures (except last one)
                if i < len(ATW_TELEMETRY_MEASURES) - 1:
                    jitter = random.uniform(
                        TELEMETRY_INTER_MEASURE_JITTER_MIN,
                        TELEMETRY_INTER_MEASURE_JITTER_MAX,
                    )
                    _LOGGER.debug("Measure jitter: %.1fs before next measure", jitter)
                    await asyncio.sleep(jitter)

            except Exception as err:
                _LOGGER.error(
                    "Error fetching telemetry measure %s for %s: %s",
                    measure,
                    unit.name,
                    err,
                )

    async def _fetch_measure(self, unit: AirToWaterUnit, measure: str) -> None:
        """Fetch telemetry for a single measure.

        Args:
            unit: ATW unit
            measure: Measure name (e.g., "flow_temperature")
        """
        # Setup time range (last 4 hours for sparse data)
        to_time = datetime.now(UTC)
        from_time = to_time - timedelta(hours=DATA_LOOKBACK_HOURS_TELEMETRY)

        # Fetch telemetry data
        data = await self._execute_with_retry(
            partial(
                self._client.get_telemetry_actual,
                unit.id,
                from_time,
                to_time,
                measure,
            ),
            f"get_telemetry({unit.name}, {measure})",
        )

        if not data or not data.get("measureData"):
            _LOGGER.debug("No telemetry data available for %s - %s", unit.name, measure)
            return

        values = data["measureData"][0].get("values", [])
        if not values:
            _LOGGER.debug("Empty telemetry values for %s - %s", unit.name, measure)
            return

        # Update sensor state with LATEST value
        # HA recorder will auto-create statistics from state updates
        latest_value = float(values[-1]["value"])
        self._telemetry_data[unit.id][measure] = latest_value

        _LOGGER.debug(
            "Telemetry: %s - %s = %.1f°C (latest of %d datapoints)",
            unit.name,
            measure,
            latest_value,
            len(values),
        )

    def get_telemetry_value(self, unit_id: str, measure: str) -> float | None:
        """Get cached telemetry value for sensor state.

        Args:
            unit_id: Unit ID
            measure: Measure name

        Returns:
            Temperature in °C, or None if not available
        """
        return self._telemetry_data.get(unit_id, {}).get(measure)

    def update_unit_telemetry_data(self, units: dict[str, AirToWaterUnit]) -> None:
        """Update telemetry data on ATW unit objects from cache.

        Args:
            units: Dictionary of unit_id -> AirToWaterUnit to update
        """
        for unit_id, unit in units.items():
            # Copy cached values to unit object (for sensor access)
            unit.telemetry = self._telemetry_data.get(unit_id, {}).copy()
