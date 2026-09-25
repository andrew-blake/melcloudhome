"""Energy tracking for MELCloud Home integration (ATW devices)."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta, tzinfo
from functools import partial
from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import ConfigEntryAuthFailed

from .api.client_atw import ATWControlClient
from .api.models import UserContext
from .api.models_atw import AirToWaterUnit
from .api.parsing import energy_report_windows
from .energy_tracker_base import EnergyTrackerBase
from .helpers import resolve_unit_timezone

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Base storage key: pre-#290 shared (legacy) name, and the stem of the
# per-account key "melcloudhome_energy_data_atw_<account hash>". Not dead code:
# the migration in EnergyTrackerBase.async_setup still reads the legacy file.
STORAGE_KEY = "melcloudhome_energy_data_atw"


class ATWEnergyTracker(EnergyTrackerBase):
    """ATW energy tracker (tracks consumed + produced energy, calculates COP).

    Extends EnergyTrackerBase with ATW-specific API integration.
    Tracks two measures:
    - "consumed" (combined-energy interval_energy_consumed)
    - "produced" (combined-energy interval_energy_produced)

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
        account_suffix: str,
    ) -> None:
        """Initialize ATW energy tracker.

        Args:
            hass: Home Assistant instance
            client: ATW control client with the energy report method
            execute_with_retry: Coordinator's retry wrapper for API calls
            get_coordinator_data: Callable to get current coordinator data
            account_suffix: Per-account storage suffix (account_storage_suffix)
        """
        super().__init__(hass, f"{STORAGE_KEY}_{account_suffix}", STORAGE_KEY)
        self._client = client
        self._execute_with_retry = execute_with_retry
        self._get_coordinator_data = get_coordinator_data

        # Energy data cache (for quick access)
        self._energy_consumed: dict[str, float | None] = {}
        self._energy_produced: dict[str, float | None] = {}
        self._cop: dict[str, float | None] = {}

        # Units already warned about an unusable zone (once per unit per run).
        self._zone_warned: set[str] = set()

    async def async_update_energy_data(self, now: datetime | None = None) -> None:
        """Fetches yesterday's and today's combined-energy report for each ATW
        unit and accumulates deltas into cumulative totals. Calculates COP.

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
                        await self._update_unit_energy(unit, now or datetime.now(UTC))
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

    async def _update_unit_energy(self, unit: AirToWaterUnit, now: datetime) -> None:
        """Update energy data for a single ATW unit from combined-energy.

        Fetches yesterday's and today's local days (never one multi-day window,
        ADR-027), drops hours from before tracking began, and hands the rest to
        the base tracker's delta tracking. A failed day is skipped for this poll
        only: both days are fetched again next time. If every window's fetch
        raised, the unit's energy is left untouched for this poll (stays
        "unknown" until a fetch first succeeds) rather than finalizing a fake
        0.0 from an untouched cumulative total. First initialization additionally
        waits for both days to succeed in the same poll, so a lone successful
        day never seeds the baseline while the other day's pre-install hours
        are still unseen.
        """
        tz = await self._resolve_zone(unit, now)
        combined: dict[str, list[dict[str, str]]] = {"consumed": [], "produced": []}
        windows = energy_report_windows(now, tz)
        failed_days = 0
        for from_utc, to_utc in windows:
            try:
                day = await self._execute_with_retry(
                    partial(
                        self._client.get_energy_report, unit.id, from_utc, to_utc, tz
                    ),
                    f"get_energy_report({unit.name})",
                )
            except ConfigEntryAuthFailed:
                raise  # the caller (async_update_energy_data) logs it and moves on to the next unit
            except Exception as err:
                _LOGGER.warning(
                    "Energy report for ATW unit %s (%s to %s) failed, skipping that day this poll: %s",
                    unit.name,
                    from_utc.isoformat(),
                    to_utc.isoformat(),
                    err,
                )
                failed_days += 1
                continue
            if day:  # a None/empty result still counts as fetched
                for measure, values in combined.items():
                    values.extend(day.get(measure, []))

        if failed_days == len(windows):
            return

        for measure, values in combined.items():
            if not values:
                _LOGGER.debug(
                    "No %s energy data available for unit %s", measure, unit.name
                )
                continue
            if self._is_first_initialization(unit.id, measure):
                if failed_days:
                    _LOGGER.debug(
                        "Deferring first-init %s energy tracking for %s until "
                        "both report days are fetched successfully",
                        measure,
                        unit.name,
                    )
                    continue
                self._initialize_unit_tracking(
                    unit.id, unit.name, measure, values, values_in_kwh=True
                )
            else:
                self._update_cumulative_values(
                    unit.id,
                    unit.name,
                    measure,
                    self._drop_pre_tracking_hours(unit.id, measure, values),
                    values_in_kwh=True,
                )

        self._energy_consumed[unit.id] = self._energy_cumulative[unit.id]["consumed"]
        self._energy_produced[unit.id] = self._energy_cumulative[unit.id]["produced"]
        self._calculate_cop(unit)

    async def _resolve_zone(self, unit: AirToWaterUnit, now: datetime) -> tzinfo:
        """The unit's zone, warning once per unit if it can't give correct keys.

        resolve_unit_timezone returns the datetime.UTC object only when it had
        to fall back (a real zone, even "UTC", comes back as a ZoneInfo). Both
        a fallback and a non-whole-hour offset produce hour keys that won't
        match stored telemetry keys; the unit is processed anyway (ADR-027).
        """
        tz = await resolve_unit_timezone(self._hass, unit.time_zone)
        offset = tz.utcoffset(now) or timedelta(0)
        if (
            tz is UTC or offset % timedelta(hours=1)
        ) and unit.id not in self._zone_warned:
            self._zone_warned.add(unit.id)
            _LOGGER.warning(
                "ATW unit %s has no usable time zone for energy (timeZone=%r): "
                "either none was resolved, so UTC is assumed, or its offset "
                "isn't a whole number of hours; energy hour keys may not "
                "match earlier readings",
                unit.name,
                unit.time_zone,
            )
        return tz

    def _drop_pre_tracking_hours(
        self, unit_id: str, measure: str, values: list[dict[str, str]]
    ) -> list[dict[str, str]]:
        """Drop hours older than the oldest stored hour for this unit and measure.

        Yesterday's window reaches further back than telemetry's 23 hours did,
        so on a young install it can hold hours from before tracking began.
        Compares parsed times, not key strings, because migrated keys may differ
        in format. Older hours are only ever pre-tracking: pruning keeps the
        newest stored key, so storage always reaches back past an outage.
        """
        stored: dict[str, float] = (
            self._energy_hour_values[unit_id][measure]
            if unit_id in self._energy_hour_values
            and measure in self._energy_hour_values[unit_id]
            else {}
        )
        stored_times = [
            t for key in stored if (t := self._parse_hour_timestamp(key)) is not None
        ]
        if not stored_times:
            return values
        floor = min(stored_times)
        return [
            v
            for v in values
            if (t := self._parse_hour_timestamp(v["time"])) is not None and t >= floor
        ]

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
