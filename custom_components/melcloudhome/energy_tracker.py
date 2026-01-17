"""Energy tracking for MELCloud Home integration (ATA devices)."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import TYPE_CHECKING, Any

from .api.client import MELCloudHomeClient
from .api.models import AirToAirUnit, UserContext
from .const import DATA_LOOKBACK_HOURS_ENERGY
from .energy_tracker_base import EnergyTrackerBase

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Storage key for ATA energy data
STORAGE_KEY = "melcloudhome_energy_data"


class EnergyTracker(EnergyTrackerBase):
    """ATA energy tracker (tracks consumed energy only).

    Extends EnergyTrackerBase with ATA-specific API integration.
    Tracks one measure: "consumed" (cumulative_energy_consumed_since_last_upload).
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
        """Initialize ATA energy tracker.

        Args:
            hass: Home Assistant instance
            client: MELCloud Home API client
            execute_with_retry: Coordinator's retry wrapper for API calls
            get_coordinator_data: Callable to get current coordinator data
        """
        super().__init__(hass, STORAGE_KEY)
        self._client = client
        self._execute_with_retry = execute_with_retry
        self._get_coordinator_data = get_coordinator_data

        # Energy data cache (cumulative totals in kWh) - for quick access
        self._energy_data: dict[str, float | None] = {}

    async def async_update_energy_data(self, now: datetime | None = None) -> None:
        """Update energy data for all ATA units (called every 30 minutes).

        Fetches cumulative_energy_consumed_since_last_upload for each ATA unit
        and accumulates deltas into cumulative totals.

        Args:
            now: Optional current time (for testing)
        """
        coordinator_data = self._get_coordinator_data()
        if not coordinator_data:
            return

        try:
            for building in coordinator_data.buildings:
                for unit in building.air_to_air_units:
                    if not unit.capabilities.has_energy_consumed_meter:
                        continue

                    try:
                        await self._update_unit_energy(unit)
                    except Exception as err:
                        # Log but continue with other units
                        _LOGGER.error(
                            "Error fetching energy for unit %s: %s",
                            unit.name,
                            err,
                        )

            # Save energy data to persistent storage
            await self._save_energy_data()

        except Exception as err:
            _LOGGER.error("Error updating energy data: %s", err)

    async def _update_unit_energy(self, unit: AirToAirUnit) -> None:
        """Update energy data for a single ATA unit.

        Fetches cumulative_energy_consumed_since_last_upload and uses
        base class delta tracking to prevent double-counting.

        Args:
            unit: AirToAirUnit to update energy data for

        Raises:
            ConfigEntryAuthFailed: Re-raised for repair UI
            Exception: Logged but not raised for non-critical errors
        """
        _LOGGER.debug(
            "Fetching energy data for unit %s (%s)",
            unit.name,
            unit.id,
        )

        # Setup time range for energy data fetch
        to_time = datetime.now(UTC)
        from_time = to_time - timedelta(hours=DATA_LOOKBACK_HOURS_ENERGY)

        # Wrap with retry for automatic session recovery
        data = await self._execute_with_retry(
            partial(
                self._client.get_energy_data,
                unit.id,
                from_time,
                to_time,
                "Hour",
            ),
            f"get_energy_data({unit.name})",
        )

        if not data or not data.get("measureData"):
            _LOGGER.debug("No energy data available for unit %s", unit.name)
            return

        # Process all hourly values
        values = data["measureData"][0].get("values", [])
        if not values:
            return

        # Use base class methods for delta tracking
        measure = "consumed"

        # Check if this is first initialization and process accordingly
        if self._is_first_initialization(unit.id, measure):
            self._initialize_unit_tracking(unit.id, unit.name, measure, values)
        else:
            self._update_cumulative_values(unit.id, unit.name, measure, values)

        # Cache cumulative total for quick access
        self._energy_data[unit.id] = self._energy_cumulative[unit.id][measure]

        _LOGGER.debug(
            "Total energy for %s: %.3f kWh",
            unit.name,
            self._energy_cumulative[unit.id][measure],
        )

    def get_unit_energy(self, unit_id: str) -> float | None:
        """Get cached energy data for a unit (in kWh).

        Args:
            unit_id: Unit ID to query

        Returns:
            Cumulative energy in kWh, or None if not available
        """
        return self._energy_data.get(unit_id)

    def update_unit_energy_data(self, units: dict[str, AirToAirUnit]) -> None:
        """Update energy data on unit objects from cache.

        Args:
            units: Dictionary of unit_id -> AirToAirUnit to update
        """
        for unit_id, unit in units.items():
            unit.energy_consumed = self._energy_data.get(unit_id)
