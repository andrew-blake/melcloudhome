"""Base class for energy tracking with delta accumulation and persistence."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.storage import Store

if TYPE_CHECKING:
    from datetime import datetime

    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Storage version for energy data persistence
STORAGE_VERSION = 1

# Wh to kWh conversion factor
WH_TO_KWH_FACTOR = 1000.0


class EnergyTrackerBase(ABC):
    """Base class for energy tracking with delta accumulation and persistence.

    Provides shared infrastructure for both ATA and ATW energy tracking:
    - Delta tracking: Prevents double-counting by tracking per-hour values
    - First-init pattern: Marks historical data as seen without counting it
    - Persistence: Saves/loads cumulative totals and hour values to HA Store
    - Multi-measure support: Tracks multiple measures per unit (consumed, produced, etc.)

    Storage structure:
        {
            "cumulative": {
                "unit_id": {
                    "measure_name": cumulative_kwh,
                    ...
                },
                ...
            },
            "hour_values": {
                "unit_id": {
                    "measure_name": {
                        "timestamp": kwh_value,
                        ...
                    },
                    ...
                },
                ...
            }
        }

    Subclasses must implement:
        - async_update_energy_data(): Fetch and process energy data
    """

    def __init__(self, hass: HomeAssistant, storage_key: str) -> None:
        """Initialize base energy tracker.

        Args:
            hass: Home Assistant instance
            storage_key: Storage key for persistence (e.g., "melcloudhome_energy_data")
        """
        self._hass = hass

        # Cumulative energy tracking (running totals in kWh)
        # Structure: {unit_id: {measure: cumulative_kwh}}
        # Using defaultdict for automatic nested dict creation with 0.0 defaults
        self._energy_cumulative: defaultdict[str, defaultdict[str, float]] = (
            defaultdict(lambda: defaultdict(float))
        )

        # Per-hour value tracking for delta calculation
        # Structure: {unit_id: {measure: {hour_timestamp: kwh_value}}}
        # Using defaultdict for automatic nested dict creation
        self._energy_hour_values: defaultdict[
            str, defaultdict[str, defaultdict[str, float]]
        ] = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))

        # Persistent storage
        self._store: Store = Store(hass, STORAGE_VERSION, storage_key)

    @abstractmethod
    async def async_update_energy_data(self, now: datetime | None = None) -> None:
        """Fetch and process energy data for all units.

        Subclasses must implement device-type-specific logic (ATA vs ATW).

        Args:
            now: Optional current time (for testing)
        """
        ...

    async def async_setup(self) -> None:
        """Set up energy tracker and load persisted data."""
        _LOGGER.info("Setting up energy tracker (storage key: %s)", self._store.key)

        # Load persisted energy data from storage
        stored_data = await self._store.async_load()
        if stored_data:
            cumulative_data = stored_data.get("cumulative", {})
            hour_values_data = stored_data.get("hour_values", {})

            # Backward compatibility: migrate from v1.x single-measure format to v2.0 multi-measure format
            # v1.x format (stable): {unit_id: cumulative_kwh} - single float value
            # v2.0 format (beta): {unit_id: {measure: cumulative_kwh}} - dict of measures
            # This migration ensures users upgrading from v1.x don't lose their energy data
            if cumulative_data:
                # Check if any value is NOT a dict (legacy format)
                has_legacy_format = any(
                    not isinstance(v, dict) for v in cumulative_data.values()
                )
                if has_legacy_format:
                    # Migrate legacy cumulative format
                    for unit_id, value in cumulative_data.items():
                        self._energy_cumulative[unit_id]["consumed"] = float(value)

                    # Migrate legacy hour_values format if present
                    # Legacy: {unit_id: {timestamp: kwh}} -> New: {unit_id: {measure: {timestamp: kwh}}}
                    if hour_values_data:
                        for unit_id, hours in hour_values_data.items():
                            # Check if this is legacy format (dict of timestamp: kwh)
                            if hours and not any(
                                isinstance(v, dict) for v in hours.values()
                            ):
                                # Legacy format - migrate to new format with "consumed" measure
                                self._energy_hour_values[unit_id]["consumed"].update(
                                    hours
                                )
                            else:
                                # Already new format - restore as-is
                                for measure, hour_dict in hours.items():
                                    self._energy_hour_values[unit_id][measure].update(
                                        hour_dict
                                    )

                    _LOGGER.info(
                        "Migrated %d device(s) from legacy storage format",
                        len(cumulative_data),
                    )
                else:
                    # Restore from new format into defaultdicts
                    for unit_id, measures in cumulative_data.items():
                        self._energy_cumulative[unit_id].update(measures)

                    for unit_id, measures in hour_values_data.items():
                        for measure, hours in measures.items():
                            self._energy_hour_values[unit_id][measure].update(hours)

                    _LOGGER.info(
                        "Restored energy data for %d device(s) from storage",
                        len(cumulative_data),
                    )
            else:
                _LOGGER.debug("No stored energy data found, starting fresh")
        else:
            _LOGGER.info("No stored energy data found, starting fresh")

    def _is_first_initialization(self, unit_id: str, measure: str) -> bool:
        """Check if this is first energy data for unit + measure.

        Args:
            unit_id: Unit ID to check
            measure: Measure name (e.g., "consumed", "produced")

        Returns:
            True if no energy hours tracked yet, False otherwise
        """
        return (
            unit_id not in self._energy_hour_values
            or measure not in self._energy_hour_values[unit_id]
            or len(self._energy_hour_values[unit_id][measure]) == 0
        )

    def _initialize_unit_tracking(
        self,
        unit_id: str,
        unit_name: str,
        measure: str,
        values: list[dict[str, Any]],
    ) -> None:
        """Initialize energy tracking for a new unit + measure.

        Mark all current hour values as seen but don't add them to cumulative
        total (avoid inflating with historical data).

        Args:
            unit_id: Unit ID to initialize
            unit_name: Unit name (for logging)
            measure: Measure name (e.g., "consumed", "produced")
            values: List of hourly energy values from API
        """
        # Mark all hours as seen (defaultdict auto-creates nested structure)
        for value_entry in values:
            hour_timestamp = value_entry["time"]
            wh_value = float(value_entry["value"])
            kwh_value = wh_value / WH_TO_KWH_FACTOR
            self._energy_hour_values[unit_id][measure][hour_timestamp] = kwh_value

        _LOGGER.info(
            "Initializing %s tracking for %s (%s) at 0.0 kWh "
            "(marked %d hour(s) as seen, will track deltas from next update)",
            measure,
            unit_name,
            unit_id,
            len(values),
        )

    def _update_cumulative_values(
        self,
        unit_id: str,
        unit_name: str,
        measure: str,
        values: list[dict[str, Any]],
    ) -> None:
        """Update cumulative energy values with new hourly data.

        Processes each hourly value with delta tracking to prevent
        double-counting. Only adds deltas when values increase.

        Args:
            unit_id: Unit ID to update
            unit_name: Unit name (for logging)
            measure: Measure name (e.g., "consumed", "produced")
            values: List of hourly energy values from API
        """
        # defaultdict auto-creates nested structure, no manual initialization needed
        for value_entry in values:
            hour_timestamp = value_entry["time"]
            wh_value = float(value_entry["value"])
            kwh_value = wh_value / WH_TO_KWH_FACTOR

            # Get previous value for this specific hour (default 0.0 from defaultdict)
            previous_value = self._energy_hour_values[unit_id][measure].get(
                hour_timestamp, 0.0
            )

            if kwh_value > previous_value:
                # Value increased - add the DELTA
                delta = kwh_value - previous_value
                self._energy_cumulative[unit_id][measure] += delta
                self._energy_hour_values[unit_id][measure][hour_timestamp] = kwh_value

                _LOGGER.info(
                    "Energy (%s): %s (%s) - Hour %s: +%.3f kWh delta (%.3f→%.3f) cumulative: %.3f kWh",
                    measure,
                    unit_name,
                    unit_id,
                    hour_timestamp[:16],
                    delta,
                    previous_value,
                    kwh_value,
                    self._energy_cumulative[unit_id][measure],
                )
            elif kwh_value < previous_value:
                # Unexpected decrease - log warning, keep previous value
                _LOGGER.warning(
                    "Energy (%s): %s (%s) - Hour %s decreased from %.3f to %.3f kWh - "
                    "keeping previous value (possible API issue)",
                    measure,
                    unit_name,
                    unit_id,
                    hour_timestamp[:16],
                    previous_value,
                    kwh_value,
                )
                # Don't update stored value, keep previous
            # else: value unchanged, no action needed

    async def _save_energy_data(self) -> None:
        """Save energy cumulative totals and per-hour values to storage."""
        try:
            # Convert defaultdicts to regular dicts for JSON serialization
            data = {
                "cumulative": {k: dict(v) for k, v in self._energy_cumulative.items()},
                "hour_values": {
                    k: {m: dict(h) for m, h in v.items()}
                    for k, v in self._energy_hour_values.items()
                },
            }
            await self._store.async_save(data)
            _LOGGER.debug("Saved energy data to storage")
        except Exception as err:
            _LOGGER.error("Error saving energy data: %s", err)
