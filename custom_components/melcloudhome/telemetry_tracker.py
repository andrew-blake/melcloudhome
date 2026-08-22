"""Telemetry tracking for MELCloud Home ATW devices.

Fetches every water-temperature measure for a unit in one report request, keeps
the newest reading per measure, and lets the HA recorder derive statistics from
the resulting state updates.
"""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from datetime import datetime
from functools import partial
from typing import TYPE_CHECKING, Any

from .api.client import MELCloudHomeClient
from .api.models import AirToWaterUnit, UserContext
from .api.parsing import Reading
from .const import (
    ATW_TELEMETRY_MEASURES,
    ATW_TELEMETRY_MEASURES_BOILER,
    ATW_TELEMETRY_MEASURES_ZONE1,
    ATW_TELEMETRY_MEASURES_ZONE2,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Jitter configuration for telemetry polling (all values in seconds)
# Reduced from original values since RequestPacer handles base rate limiting
TELEMETRY_INTER_DEVICE_JITTER_MIN = 0.1
TELEMETRY_INTER_DEVICE_JITTER_MAX = 1.0


class TelemetryTracker:
    """Manages telemetry data polling for ATW devices."""

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

        # Telemetry data cache (latest readings for sensor state)
        # Structure: {unit_id: {measure_name: Reading}}
        self._telemetry_data: dict[str, dict[str, Reading | None]] = {}

        # Units already warned about a zone-2-less response (see
        # _warn_if_zone2_missing)
        self._warned_missing_zone2: set[str] = set()

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
        """Update water temperatures for a single ATW unit.

        Args:
            unit: AirToWaterUnit to update telemetry for
        """
        _LOGGER.debug("Fetching water temperatures for %s (%s)", unit.name, unit.id)

        if unit.id not in self._telemetry_data:
            self._telemetry_data[unit.id] = {}

        # Raises on a failed request, and that is the point: the caller logs it
        # and the cache keeps its previous readings, whose age last_reading
        # shows. A response that arrives and omits a measure is the other case,
        # handled below.
        readings = await self._execute_with_retry(
            partial(self._client.get_atw_water_temperatures, unit.id),
            f"get_water_temperatures({unit.name})",
        )

        # The report returns every dataset regardless of the unit's hardware,
        # filling absent ones with a constant 25 placeholder, so the capability
        # filter that used to decide what to REQUEST now decides what to keep
        # (#266). Same rules, same outcome, one request.
        wanted = list(ATW_TELEMETRY_MEASURES)
        if unit.capabilities and unit.capabilities.has_zone2:
            wanted.extend(ATW_TELEMETRY_MEASURES_ZONE1)
            wanted.extend(ATW_TELEMETRY_MEASURES_ZONE2)
        if unit.capabilities and unit.capabilities.has_boiler:
            wanted.extend(ATW_TELEMETRY_MEASURES_BOILER)

        self._warn_if_zone2_missing(unit, readings)

        for measure in wanted:
            reading = readings.get(measure)
            if reading is None:
                # The fetch succeeded and this measure was not in it, so the
                # sensor reads unknown rather than keeping a value the endpoint
                # is no longer reporting (ADR-020).
                _LOGGER.debug("No %s reading for %s", measure, unit.name)
            self._telemetry_data[unit.id][measure] = reading

        _LOGGER.debug(
            "Water temperatures for %s: %s", unit.name, self._telemetry_data[unit.id]
        )

    def _warn_if_zone2_missing(
        self, unit: AirToWaterUnit, readings: dict[str, Reading]
    ) -> None:
        """Warn once per unit if a two-zone unit gets no zone-2 datasets.

        Zone-2 datasets have never been observed on this endpoint - every unit
        reachable when the switch was made was single-zone - so including them
        for a unit that has zone 2 is an assumption (ADR-023), not a measured
        fact. This is how we find out if it is wrong. The sensors themselves
        read unknown in that case; this names the cause.

        WARNING, not debug: it is user-visible at prod's default log level by
        design, and it is the outcome the assumption turns on. Do not soften it.
        """
        if not (unit.capabilities and unit.capabilities.has_zone2):
            return
        if unit.id in self._warned_missing_zone2:
            return
        if any(m in readings for m in ATW_TELEMETRY_MEASURES_ZONE2):
            return

        self._warned_missing_zone2.add(unit.id)
        _LOGGER.warning(
            "%s has a second zone but the water-temperature report returned no "
            "zone-2 datasets (received: %s). Zone 2 flow and return "
            "temperatures will read unknown. Please report this at "
            "https://github.com/andrew-blake/melcloudhome/issues",
            unit.name,
            sorted(readings),
        )

    def update_unit_telemetry_data(self, units: dict[str, AirToWaterUnit]) -> None:
        """Update telemetry data on ATW unit objects from cache.

        Args:
            units: Dictionary of unit_id -> AirToWaterUnit to update
        """
        for unit_id, unit in units.items():
            # Copy cached values to unit object (for sensor access)
            unit.telemetry = self._telemetry_data.get(unit_id, {}).copy()
