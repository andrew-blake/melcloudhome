"""Energy tracking for MELCloud Home integration."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.storage import Store

from .api.client import MELCloudHomeClient
from .api.models import AirToAirUnit, UserContext
from .const import DATA_LOOKBACK_HOURS_ENERGY

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Storage version for energy data persistence
STORAGE_VERSION = 1
STORAGE_KEY = "melcloudhome_energy_data"


class EnergyTracker:
    """Manages energy data polling, accumulation, and persistence."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: MELCloudHomeClient,
        execute_with_retry: Callable[
            [Callable[[], Awaitable[Any]], str], Awaitable[Any]
        ],
        get_coordinator_data: Callable[[], UserContext | None],
    ) -> None:
        """Initialize energy tracker.

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

        # Energy data cache (cumulative totals in kWh)
        self._energy_data: dict[str, float | None] = {}
        # Cumulative energy tracking (running totals in kWh)
        self._energy_cumulative: dict[str, float] = {}
        # Per-hour value tracking for delta calculation (handles progressive updates)
        # Structure: {unit_id: {timestamp: kwh_value}}
        self._energy_hour_values: dict[str, dict[str, float]] = {}
        # Persistent storage
        self._store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)

    async def async_setup(self) -> None:
        """Set up energy tracker and load persisted data."""
        _LOGGER.info("Setting up energy tracker")

        # Load persisted energy data from storage
        stored_data = await self._store.async_load()
        if stored_data:
            self._energy_cumulative = stored_data.get("cumulative", {})
            self._energy_hour_values = stored_data.get("hour_values", {})

            # Backward compatibility: migrate from legacy format
            if not self._energy_hour_values:
                if "last_hour" in stored_data:
                    # Initialize empty hour_values for existing units
                    for unit_id in self._energy_cumulative:
                        self._energy_hour_values[unit_id] = {}
                    _LOGGER.info(
                        "Migrated %d device(s) from legacy storage format",
                        len(self._energy_cumulative),
                    )
                else:
                    _LOGGER.debug("No stored energy data found, starting fresh")
            else:
                _LOGGER.info(
                    "Restored energy data for %d device(s) from storage",
                    len(self._energy_cumulative),
                )
        else:
            _LOGGER.info("No stored energy data found, starting fresh")

    async def async_update_energy_data(self, now: datetime | None = None) -> None:
        """Update energy data for all units (called every 30 minutes).

        Orchestrates energy data updates by delegating to focused helper methods.
        Accumulates hourly energy values into cumulative totals.
        Prevents double-counting by tracking last processed hour per device.

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

    def _is_first_initialization(self, unit_id: str) -> bool:
        """Check if this is first energy data for unit.

        Args:
            unit_id: Unit ID to check

        Returns:
            True if no energy hours tracked yet, False otherwise
        """
        return len(self._energy_hour_values.get(unit_id, {})) == 0

    def _initialize_unit_tracking(
        self,
        unit: AirToAirUnit,
        values: list[dict[str, Any]],
    ) -> None:
        """Initialize energy tracking for a new unit.

        Mark all current hour values as seen but don't add them to cumulative
        total (avoid inflating with historical data).

        Args:
            unit: Unit to initialize tracking for
            values: List of hourly energy values from API
        """
        for value_entry in values:
            hour_timestamp = value_entry["time"]
            wh_value = float(value_entry["value"])
            kwh_value = wh_value / 1000.0
            self._energy_hour_values[unit.id][hour_timestamp] = kwh_value

        _LOGGER.info(
            "Initializing energy tracking for %s at 0.0 kWh "
            "(marked %d hour(s) as seen, will track deltas from next update)",
            unit.name,
            len(values),
        )

    def _update_cumulative_values(
        self,
        unit: AirToAirUnit,
        values: list[dict[str, Any]],
    ) -> None:
        """Update cumulative energy values with new hourly data.

        Processes each hourly value with delta tracking to prevent
        double-counting. Only adds deltas when values increase.

        Args:
            unit: Unit to update cumulative values for
            values: List of hourly energy values from API
        """
        for value_entry in values:
            hour_timestamp = value_entry["time"]
            wh_value = float(value_entry["value"])
            kwh_value = wh_value / 1000.0

            # Get previous value for this specific hour (default 0 if new)
            previous_value = self._energy_hour_values[unit.id].get(hour_timestamp, 0.0)

            if kwh_value > previous_value:
                # Value increased - add the DELTA
                delta = kwh_value - previous_value
                self._energy_cumulative[unit.id] += delta
                self._energy_hour_values[unit.id][hour_timestamp] = kwh_value

                _LOGGER.info(
                    "Energy: %s - Hour %s: +%.3f kWh delta (%.3f→%.3f) cumulative: %.3f kWh",
                    unit.name,
                    hour_timestamp[:16],
                    delta,
                    previous_value,
                    kwh_value,
                    self._energy_cumulative[unit.id],
                )
            elif kwh_value < previous_value:
                # Unexpected decrease - log warning, keep previous value
                _LOGGER.warning(
                    "Energy: %s - Hour %s decreased from %.3f to %.3f kWh - "
                    "keeping previous value (possible API issue)",
                    unit.name,
                    hour_timestamp[:16],
                    previous_value,
                    kwh_value,
                )
                # Don't update stored value, keep previous
            # else: value unchanged, no action needed

    async def _update_unit_energy(self, unit: AirToAirUnit) -> None:
        """Update energy data for a single unit.

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

        # Initialize hour values dict if needed
        if unit.id not in self._energy_hour_values:
            self._energy_hour_values[unit.id] = {}

        # Initialize cumulative total if first time
        if unit.id not in self._energy_cumulative:
            self._energy_cumulative[unit.id] = 0.0

        # Check if this is first initialization and process accordingly
        if self._is_first_initialization(unit.id):
            self._initialize_unit_tracking(unit, values)
        else:
            self._update_cumulative_values(unit, values)

        # Store cumulative total for this unit
        self._energy_data[unit.id] = self._energy_cumulative[unit.id]

        _LOGGER.debug(
            "Total energy for %s: %.3f kWh",
            unit.name,
            self._energy_cumulative[unit.id],
        )

    async def _save_energy_data(self) -> None:
        """Save energy cumulative totals and per-hour values to storage."""
        try:
            data = {
                "cumulative": self._energy_cumulative,
                "hour_values": self._energy_hour_values,
            }
            await self._store.async_save(data)
            _LOGGER.debug("Saved energy data to storage")
        except Exception as err:
            _LOGGER.error("Error saving energy data: %s", err)

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
