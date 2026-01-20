"""Energy tracking for MELCloud Home integration (ATW devices)."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import TYPE_CHECKING, Any

from .api.client_atw import ATWControlClient
from .api.models import UserContext
from .api.models_atw import AirToWaterUnit
from .const import DATA_LOOKBACK_HOURS_ENERGY
from .energy_tracker_base import EnergyTrackerBase

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Storage key for ATW energy data
STORAGE_KEY = "melcloudhome_energy_data_atw"


class ATWEnergyTracker(EnergyTrackerBase):
    """ATW energy tracker (tracks consumed + produced energy, calculates COP).

    Extends EnergyTrackerBase with ATW-specific API integration.
    Tracks two measures:
    - "consumed" (interval_energy_consumed)
    - "produced" (interval_energy_produced)

    Also calculates COP (Coefficient of Performance) from produced/consumed ratio.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        client: ATWControlClient,
        execute_with_retry: Callable[
            [Callable[[], Awaitable[Any]], str], Awaitable[Any]
        ],
        get_coordinator_data: Callable[[], UserContext | None],
    ) -> None:
        """Initialize ATW energy tracker.

        Args:
            hass: Home Assistant instance
            client: ATW control client with energy API methods
            execute_with_retry: Coordinator's retry wrapper for API calls
            get_coordinator_data: Callable to get current coordinator data
        """
        super().__init__(hass, STORAGE_KEY)
        self._client = client
        self._execute_with_retry = execute_with_retry
        self._get_coordinator_data = get_coordinator_data

        # Energy data cache (for quick access)
        self._energy_consumed: dict[str, float | None] = {}
        self._energy_produced: dict[str, float | None] = {}
        self._cop: dict[str, float | None] = {}

    async def async_update_energy_data(self, now: datetime | None = None) -> None:
        """Update energy data for all ATW units (called every 30 minutes).

        Fetches interval_energy_consumed and interval_energy_produced for each
        ATW unit and accumulates deltas into cumulative totals. Calculates COP.

        Args:
            now: Optional current time (for testing)
        """
        coordinator_data = self._get_coordinator_data()
        if not coordinator_data:
            return

        try:
            for building in coordinator_data.buildings:
                for unit in building.air_to_water_units:
                    # Check if unit has energy capabilities
                    if not (
                        unit.capabilities.has_estimated_energy_consumption
                        or unit.capabilities.has_measured_energy_consumption
                    ):
                        continue

                    try:
                        await self._update_unit_energy(unit)
                    except Exception as err:
                        # Log but continue with other units
                        _LOGGER.error(
                            "Error fetching energy for ATW unit %s: %s",
                            unit.name,
                            err,
                        )

            # Save energy data to persistent storage
            await self._save_energy_data()

        except Exception as err:
            _LOGGER.error("Error updating ATW energy data: %s", err)

    async def _update_unit_energy(self, unit: AirToWaterUnit) -> None:
        """Update energy data for a single ATW unit.

        Fetches both consumed and produced measures, uses base class delta
        tracking, and calculates COP.

        Args:
            unit: AirToWaterUnit to update energy data for

        Raises:
            ConfigEntryAuthFailed: Re-raised for repair UI
            Exception: Logged but not raised for non-critical errors
        """
        _LOGGER.debug(
            "Fetching energy data for ATW unit %s (%s)",
            unit.name,
            unit.id,
        )

        # Setup time range for energy data fetch
        to_time = datetime.now(UTC)
        from_time = to_time - timedelta(hours=DATA_LOOKBACK_HOURS_ENERGY)

        # Fetch both consumed and produced
        await self._update_measure(unit, "consumed", from_time, to_time)
        await self._update_measure(unit, "produced", from_time, to_time)

        # Update caches from cumulative data (defaultdict guarantees structure exists)
        self._energy_consumed[unit.id] = self._energy_cumulative[unit.id]["consumed"]
        self._energy_produced[unit.id] = self._energy_cumulative[unit.id]["produced"]

        # Calculate COP from both measures
        self._calculate_cop(unit)

    async def _update_measure(
        self,
        unit: AirToWaterUnit,
        measure: str,
        from_time: datetime,
        to_time: datetime,
    ) -> None:
        """Update a single energy measure for a unit.

        Args:
            unit: Unit to update
            measure: "consumed" or "produced"
            from_time: Start time
            to_time: End time
        """
        # Choose API method based on measure using dynamic dispatch
        method_name = f"get_energy_{measure}"
        api_method = getattr(self._client, method_name, None)
        if not api_method:
            raise ValueError(f"Unknown energy measure: {measure}")

        # Wrap with retry for automatic session recovery
        data = await self._execute_with_retry(
            partial(api_method, unit.id, from_time, to_time, "Hour"),
            f"get_energy_{measure}({unit.name})",
        )

        if not data or not data.get("measureData"):
            _LOGGER.debug("No %s energy data available for unit %s", measure, unit.name)
            return

        # Process all hourly values
        values = data["measureData"][0].get("values", [])
        if not values:
            return

        # Use base class methods for delta tracking
        # ATW energy API returns kWh, not Wh (unlike ATA)
        if self._is_first_initialization(unit.id, measure):
            self._initialize_unit_tracking(
                unit.id, unit.name, measure, values, values_in_kwh=True
            )
        else:
            self._update_cumulative_values(
                unit.id, unit.name, measure, values, values_in_kwh=True
            )

    def _calculate_cop(self, unit: AirToWaterUnit) -> None:
        """Calculate COP (Coefficient of Performance) for a unit.

        COP = energy_produced / energy_consumed

        Args:
            unit: Unit to calculate COP for
        """
        consumed = self._energy_consumed.get(unit.id)
        produced = self._energy_produced.get(unit.id)

        if consumed is not None and produced is not None and consumed > 0:
            cop = produced / consumed
            self._cop[unit.id] = cop
            _LOGGER.debug(
                "COP for %s: %.2f (produced=%.3f kWh, consumed=%.3f kWh)",
                unit.name,
                cop,
                produced,
                consumed,
            )
        else:
            # Can't calculate COP (missing data or consumed=0)
            self._cop[unit.id] = None
            if consumed == 0:
                _LOGGER.debug(
                    "COP for %s: None (consumed energy is zero)",
                    unit.name,
                )

    def get_energy_consumed(self, unit_id: str) -> float | None:
        """Get consumed energy for a unit (in kWh).

        Args:
            unit_id: Unit ID to query

        Returns:
            Cumulative consumed energy in kWh, or None if not available
        """
        return self._energy_consumed.get(unit_id)

    def get_energy_produced(self, unit_id: str) -> float | None:
        """Get produced energy for a unit (in kWh).

        Args:
            unit_id: Unit ID to query

        Returns:
            Cumulative produced energy in kWh, or None if not available
        """
        return self._energy_produced.get(unit_id)

    def get_cop(self, unit_id: str) -> float | None:
        """Get COP (Coefficient of Performance) for a unit.

        Args:
            unit_id: Unit ID to query

        Returns:
            COP (produced/consumed ratio), or None if not calculable
        """
        return self._cop.get(unit_id)

    def update_unit_energy_data(self, units: dict[str, AirToWaterUnit]) -> None:
        """Update energy data on unit objects from cache.

        Args:
            units: Dictionary of unit_id -> AirToWaterUnit to update
        """
        for unit_id, unit in units.items():
            unit.energy_consumed = self._energy_consumed.get(unit_id)
            unit.energy_produced = self._energy_produced.get(unit_id)
            unit.cop = self._cop.get(unit_id)
