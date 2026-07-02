"""Base class for energy tracking with delta accumulation and persistence."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.storage import Store

from .const import HOUR_VALUE_RETENTION_HOURS, MAX_PLAUSIBLE_HOURLY_ENERGY_KWH

if TYPE_CHECKING:
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

            # Backward compatibility: migrate from v1.3.4 single-measure to v2.0 multi-measure
            # v1.3.4: {unit_id: cumulative_kwh} - single float value
            # v2.0: {unit_id: {measure: cumulative_kwh}} - dict of measures
            # This migration ensures users upgrading from v1.3.4 stable don't lose their energy data
            if cumulative_data:
                # Check if any value is NOT a dict (v1.3.4 format)
                has_v1_format = any(
                    not isinstance(v, dict) for v in cumulative_data.values()
                )
                if has_v1_format:
                    # Migrate v1.3.4 cumulative format
                    for unit_id, value in cumulative_data.items():
                        self._energy_cumulative[unit_id]["consumed"] = float(value)

                    # Migrate v1.3.4 hour_values format (always {unit_id: {timestamp: kwh}})
                    if hour_values_data:
                        for unit_id, hours in hour_values_data.items():
                            self._energy_hour_values[unit_id]["consumed"].update(hours)

                    _LOGGER.info(
                        "Migrated %d device(s) from v1.3.4 storage format",
                        len(cumulative_data),
                    )
                else:
                    # Restore from v2.0 format into defaultdicts
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

        # Self-heal installs that accumulated a corrupt reading before the
        # sanity check existed, and bound storage growth (see GitHub issue
        # #161). Persist immediately so the correction survives even if no
        # new energy data arrives.
        if self._clean_hour_values(datetime.now(UTC)):
            await self._save_energy_data()

    @staticmethod
    def _parse_hour_timestamp(hour_timestamp: str) -> datetime | None:
        """Parse a stored hour_values key into a UTC-aware datetime.

        Returns None if the timestamp can't be parsed (defensive - should
        not happen with well-formed data, but a corrupt/foreign key must
        not crash cleanup).
        """
        try:
            hour_dt = datetime.fromisoformat(hour_timestamp)
        except ValueError:
            return None
        return hour_dt if hour_dt.tzinfo else hour_dt.replace(tzinfo=UTC)

    def _clean_hour_values(self, now: datetime) -> bool:
        """Purge implausible and stale entries from persisted hour_values.

        Two independent, unconditionally-safe cleanup passes over the same
        data, run on every load:

        - Implausible: a corrupt cloud reading (e.g. a 16-bit counter wrap,
          ~6553.6 kWh for one hour) could already have been added to a
          unit's cumulative total and recorded in hour_values before the
          sanity check in _update_cumulative_values existed. Undo it by
          subtracting the stored value back out of cumulative and dropping
          the entry, so a future legitimate reading for that hour is
          accepted fresh. See GitHub issue #161.
        - Stale: hour_values only needs to cover the API's lookback window
          (DATA_LOOKBACK_HOURS_ENERGY) - once an hour falls outside that
          window the API will never return it again, so the entry can
          never be looked up again. Without pruning, this dict grows
          without bound for the lifetime of the install.

          The single most-recent plausible, parseable entry per unit +
          measure is always kept regardless of age. Emptying hour_values
          entirely would make _is_first_initialization() think the device
          had never been tracked, silently absorbing the next real poll
          as "historical" instead of counting it - worse than the
          unbounded growth this pruning is meant to fix.

        Args:
            now: Current time (UTC), used to determine entry age for the
                staleness check.

        Returns:
            True if any entry was changed (caller should persist).
        """
        cutoff = now - timedelta(hours=HOUR_VALUE_RETENTION_HOURS)
        changed = False
        stale_count = 0
        for unit_id, measures in self._energy_hour_values.items():
            for measure, hours in measures.items():
                parsed = {
                    hour_timestamp: self._parse_hour_timestamp(hour_timestamp)
                    for hour_timestamp, value in hours.items()
                    if value <= MAX_PLAUSIBLE_HOURLY_ENERGY_KWH
                }
                dated = {k: v for k, v in parsed.items() if v is not None}
                sentinel = max(dated, key=lambda k: dated[k]) if dated else None

                for hour_timestamp, value in list(hours.items()):
                    if value > MAX_PLAUSIBLE_HOURLY_ENERGY_KWH:
                        del hours[hour_timestamp]
                        before = self._energy_cumulative[unit_id][measure]
                        self._energy_cumulative[unit_id][measure] = max(
                            0.0, before - value
                        )
                        changed = True
                        _LOGGER.warning(
                            "Energy (%s): %s - Hour %s: purging implausible "
                            "historical value %.1f kWh from cumulative total "
                            "(%.3f -> %.3f kWh). See GitHub issue #161.",
                            measure,
                            unit_id,
                            hour_timestamp[:16],
                            value,
                            before,
                            self._energy_cumulative[unit_id][measure],
                        )
                        continue

                    if hour_timestamp == sentinel:
                        continue

                    hour_dt = parsed.get(hour_timestamp)
                    if hour_dt is None or hour_dt >= cutoff:
                        continue

                    del hours[hour_timestamp]
                    changed = True
                    stale_count += 1

        if stale_count:
            _LOGGER.debug(
                "Pruned %d stale hour_values entr%s older than %d hours",
                stale_count,
                "y" if stale_count == 1 else "ies",
                HOUR_VALUE_RETENTION_HOURS,
            )
        return changed

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
        values_in_kwh: bool = False,
    ) -> None:
        """Initialize energy tracking for a new unit + measure.

        Mark all current hour values as seen but don't add them to cumulative
        total (avoid inflating with historical data).

        Args:
            unit_id: Unit ID to initialize
            unit_name: Unit name (for logging)
            measure: Measure name (e.g., "consumed", "produced")
            values: List of hourly energy values from API
            values_in_kwh: If True, values are already in kWh (ATW). If False, convert from Wh (ATA).
        """
        # Mark all hours as seen (defaultdict auto-creates nested structure)
        for value_entry in values:
            hour_timestamp = value_entry["time"]
            raw_value = float(value_entry["value"])
            # ATW API returns kWh, ATA API returns Wh
            kwh_value = raw_value if values_in_kwh else raw_value / WH_TO_KWH_FACTOR

            if kwh_value > MAX_PLAUSIBLE_HOURLY_ENERGY_KWH:
                # Corrupt reading from cloud (e.g. 16-bit counter wrap) - don't
                # seed the baseline with it, or a later legitimate value would
                # look like a "decrease" and be ignored. See GitHub issue #161.
                _LOGGER.warning(
                    "Energy (%s): %s (%s) - Hour %s implausible value %.1f kWh "
                    "exceeds sanity ceiling (%.1f kWh) - skipping",
                    measure,
                    unit_name,
                    unit_id,
                    hour_timestamp[:16],
                    kwh_value,
                    MAX_PLAUSIBLE_HOURLY_ENERGY_KWH,
                )
                continue

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
        values_in_kwh: bool = False,
    ) -> None:
        """Update cumulative energy values with new hourly data.

        Processes each hourly value with delta tracking to prevent
        double-counting. Only adds deltas when values increase.

        Args:
            unit_id: Unit ID to update
            unit_name: Unit name (for logging)
            measure: Measure name (e.g., "consumed", "produced")
            values: List of hourly energy values from API
            values_in_kwh: If True, values are already in kWh (ATW). If False, convert from Wh (ATA).
        """
        # defaultdict auto-creates nested structure, no manual initialization needed
        for value_entry in values:
            hour_timestamp = value_entry["time"]
            raw_value = float(value_entry["value"])
            # ATW API returns kWh, ATA API returns Wh
            kwh_value = raw_value if values_in_kwh else raw_value / WH_TO_KWH_FACTOR

            if kwh_value > MAX_PLAUSIBLE_HOURLY_ENERGY_KWH:
                # Corrupt reading from cloud (e.g. 16-bit counter wrap) - reject
                # without persisting so a later legitimate value for this hour
                # is still accepted normally. See GitHub issue #161.
                _LOGGER.warning(
                    "Energy (%s): %s (%s) - Hour %s implausible value %.1f kWh "
                    "exceeds sanity ceiling (%.1f kWh) - rejecting reading",
                    measure,
                    unit_name,
                    unit_id,
                    hour_timestamp[:16],
                    kwh_value,
                    MAX_PLAUSIBLE_HOURLY_ENERGY_KWH,
                )
                continue

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
