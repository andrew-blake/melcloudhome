"""Wi-Fi signal polling for ATA and ATW units (#350, ADR-028).

/context's top-level rssi stopped updating in September 2026, so the signal
comes from the telemetry rssi series the vendor app charts. The request and
response are identical for both device types, so one tracker serves both.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from typing import Any

from homeassistant.exceptions import ConfigEntryAuthFailed

from .api.client import MELCloudHomeClient
from .api.models import AirToAirUnit, AirToWaterUnit
from .api.parsing import Reading

_LOGGER = logging.getLogger(__name__)


@dataclass
class _UnitWifiSignal:
    """What the tracker knows about one unit, keyed by unit id."""

    reading: Reading | None = None
    last_poll_at: datetime | None = None
    last_error: str | None = None
    last_error_at: datetime | None = None


class WifiSignalTracker:
    """Fetches each unit's newest Wi-Fi signal and applies it to unit objects.

    State is held by unit id, because every /context poll replaces the unit
    objects: the coordinator calls apply() from _rebuild_caches so a reading
    survives the replacement.
    """

    def __init__(
        self,
        client: MELCloudHomeClient,
        execute_with_retry: Callable[
            [Callable[[], Awaitable[Any]], str], Awaitable[Any]
        ],
        get_units: Callable[[], Iterable[AirToAirUnit | AirToWaterUnit]],
    ) -> None:
        """Initialize the tracker.

        Args:
            client: MELCloud Home API client
            execute_with_retry: Coordinator's retry wrapper for API calls
            get_units: Returns the coordinator's current unit objects, both types
        """
        self._client = client
        self._execute_with_retry = execute_with_retry
        self._get_units = get_units
        self._state: dict[str, _UnitWifiSignal] = {}

    async def async_update(self) -> None:
        """Fetch every unit once, sequentially, then apply the results.

        A unit's failure costs that unit only and never raises from here.
        A failed fetch and an empty response both keep the previous reading:
        on this endpoint an empty response is the server withholding data it
        has already served (ADR-028's carve-out from ADR-020). A rejected
        login (ConfigEntryAuthFailed) stops the batch.

        Logs one WARNING when a unit starts failing and one when it recovers.
        _execute_with_retry still logs each 5xx and ApiError itself, as it
        does for outdoor temperature.

        ponytail: state for a unit that leaves the account is kept, bounded by
        the units ever seen. If it returns, its reading and streak resume,
        which matches keep-previous. Prune here if accounts churn units.
        """
        for unit in list(self._get_units()):
            state = self._state.setdefault(unit.id, _UnitWifiSignal())
            try:
                reading = await self._execute_with_retry(
                    partial(self._client.get_wifi_signal, unit.id),
                    f"get_wifi_signal({unit.name})",
                )
            except ConfigEntryAuthFailed:
                # Credentials were rejected and the /context poll has started
                # the reauth flow. Stop the batch rather than attempt a full
                # login for every remaining unit.
                _LOGGER.debug("Wi-Fi signal batch stopped: re-authentication needed")
                break
            except Exception as err:
                failed_at = datetime.now(UTC)
                was_failing = state.last_error is not None
                state.last_poll_at = failed_at
                state.last_error = f"{type(err).__name__}: {err}"
                state.last_error_at = failed_at
                _LOGGER.debug(
                    "Failed to fetch Wi-Fi signal for %s", unit.name, exc_info=True
                )
                if not was_failing:
                    _LOGGER.warning(
                        "Wi-Fi signal for %s failed and the sensor will keep its "
                        "previous value until a fetch succeeds: %s",
                        unit.name,
                        state.last_error,
                    )
                continue

            if state.last_error is not None:
                # Warning, not info: at WARNING the failure would otherwise
                # read as never closing.
                _LOGGER.warning("Wi-Fi signal for %s is working again", unit.name)
            state.last_poll_at = datetime.now(UTC)
            state.last_error = None
            state.last_error_at = None
            if reading is not None:
                state.reading = reading
            _LOGGER.debug("Wi-Fi signal for %s: %s", unit.name, reading)

        self.apply()

    def apply(self) -> None:
        """Copy each unit's state onto its current unit object.

        A unit with no state yet keeps the model's None defaults.
        """
        for unit in self._get_units():
            if (state := self._state.get(unit.id)) is None:
                continue
            unit.wifi_signal_reading = state.reading
            unit.wifi_signal_last_poll_at = state.last_poll_at
            unit.wifi_signal_last_error = state.last_error
            unit.wifi_signal_last_error_at = state.last_error_at
