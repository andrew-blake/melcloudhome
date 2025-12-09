"""Data update coordinator for MELCloud Home integration."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api.client import MELCloudHomeClient
from .api.exceptions import ApiError, AuthenticationError
from .api.models import AirToAirUnit, Building, UserContext
from .const import DOMAIN, UPDATE_INTERVAL

if TYPE_CHECKING:
    from homeassistant.helpers.event import CALLBACK_TYPE

_LOGGER = logging.getLogger(__name__)

# Energy update interval (30 minutes)
ENERGY_UPDATE_INTERVAL = timedelta(minutes=30)

# Storage version for energy data persistence
STORAGE_VERSION = 1
STORAGE_KEY = "melcloudhome_energy_data"


class MELCloudHomeCoordinator(DataUpdateCoordinator[UserContext]):
    """Class to manage fetching MELCloud Home data."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: MELCloudHomeClient,
        email: str,
        password: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client
        self._email = email
        self._password = password
        # Caches for O(1) lookups
        self._unit_to_building: dict[str, Building] = {}
        self._units: dict[str, AirToAirUnit] = {}
        # Energy data cache and polling
        self._energy_data: dict[str, float | None] = {}
        self._cancel_energy_updates: CALLBACK_TYPE | None = None
        # Cumulative energy tracking (running totals in kWh)
        self._energy_cumulative: dict[str, float] = {}
        # Per-hour value tracking for delta calculation (handles progressive updates)
        # Structure: {unit_id: {timestamp: kwh_value}}
        self._energy_hour_values: dict[str, dict[str, float]] = {}
        # Persistent storage for energy data
        self._store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        # Re-authentication lock to prevent concurrent re-auth attempts
        self._reauth_lock = asyncio.Lock()
        # Debounced refresh to prevent race conditions from rapid service calls
        self._refresh_debounce_task: asyncio.Task | None = None

    async def _async_update_data(self) -> UserContext:
        """Fetch data from API endpoint."""
        # If not authenticated yet, login first
        if not self.client.is_authenticated:
            _LOGGER.debug("Not authenticated, logging in")
            await self.client.login(self._email, self._password)

        # Use retry helper for consistency
        context: UserContext = await self._execute_with_retry(
            self.client.get_user_context,
            "coordinator_update",
        )

        # Update caches for O(1) lookups
        self._rebuild_caches(context)
        return context

    def _rebuild_caches(self, context: UserContext) -> None:
        """Rebuild lookup caches from context data."""
        self._unit_to_building.clear()
        self._units.clear()

        for building in context.buildings:
            for unit in building.air_to_air_units:
                self._units[unit.id] = unit
                self._unit_to_building[unit.id] = building

        # Update energy data for units
        self._update_unit_energy_data()

    def _update_unit_energy_data(self) -> None:
        """Update energy data on unit objects from cache."""
        for unit_id, unit in self._units.items():
            unit.energy_consumed = self._energy_data.get(unit_id)

    async def async_setup(self) -> None:
        """Set up the coordinator with energy polling."""
        _LOGGER.info("Setting up energy polling for MELCloud Home")

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

        # Perform initial energy fetch
        try:
            await self._async_update_energy_data()
            _LOGGER.info("Initial energy fetch completed")
        except Exception as err:
            _LOGGER.error("Error during initial energy fetch: %s", err, exc_info=True)

        # Schedule periodic energy updates (30 minutes)
        self._cancel_energy_updates = async_track_time_interval(
            self.hass,
            self._async_update_energy_data,
            ENERGY_UPDATE_INTERVAL,
        )
        _LOGGER.info("Energy polling scheduled (every 30 minutes)")

    async def _async_update_energy_data(self, now: datetime | None = None) -> None:
        """Update energy data for all units (called every 30 minutes).

        Accumulates hourly energy values into cumulative totals.
        Prevents double-counting by tracking last processed hour per device.
        """
        if not self.data:
            return

        try:
            to_time = datetime.now(UTC)
            # Fetch last 48 hours to handle progressive updates and outages
            from_time = to_time - timedelta(hours=48)

            for building in self.data.buildings:
                for unit in building.air_to_air_units:
                    if not unit.capabilities.has_energy_consumed_meter:
                        continue

                    try:
                        _LOGGER.debug(
                            "Fetching energy data for unit %s (%s)",
                            unit.name,
                            unit.id,
                        )

                        # V4: Wrap with retry for automatic session recovery
                        data = await self._execute_with_retry(
                            partial(
                                self.client.get_energy_data,
                                unit.id,
                                from_time,
                                to_time,
                                "Hour",
                            ),
                            f"get_energy_data({unit.name})",
                        )

                        if not data or not data.get("measureData"):
                            _LOGGER.debug(
                                "No energy data available for unit %s", unit.name
                            )
                            continue

                        # Process all hourly values
                        values = data["measureData"][0].get("values", [])
                        if not values:
                            continue

                        # Initialize hour values dict if needed
                        if unit.id not in self._energy_hour_values:
                            self._energy_hour_values[unit.id] = {}

                        # Initialize cumulative total if first time
                        if unit.id not in self._energy_cumulative:
                            self._energy_cumulative[unit.id] = 0.0

                        # Check if this is first initialization (no hours tracked yet)
                        is_first_init = len(self._energy_hour_values[unit.id]) == 0

                        if is_first_init:
                            # First initialization: mark all current hours as seen
                            # but DON'T add them (avoid inflating with historical data)
                            for value_entry in values:
                                hour_timestamp = value_entry["time"]
                                wh_value = float(value_entry["value"])
                                kwh_value = wh_value / 1000.0
                                self._energy_hour_values[unit.id][hour_timestamp] = (
                                    kwh_value
                                )

                            _LOGGER.info(
                                "Initializing energy tracking for %s at 0.0 kWh "
                                "(marked %d hour(s) as seen, will track deltas from next update)",
                                unit.name,
                                len(values),
                            )
                        else:
                            # Normal operation: process each hourly value with delta tracking
                            for value_entry in values:
                                hour_timestamp = value_entry["time"]
                                wh_value = float(value_entry["value"])
                                kwh_value = wh_value / 1000.0

                                # Get previous value for this specific hour (default 0 if new)
                                previous_value = self._energy_hour_values[unit.id].get(
                                    hour_timestamp, 0.0
                                )

                                if kwh_value > previous_value:
                                    # Value increased - add the DELTA
                                    delta = kwh_value - previous_value
                                    self._energy_cumulative[unit.id] += delta
                                    self._energy_hour_values[unit.id][
                                        hour_timestamp
                                    ] = kwh_value

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

                        # Store cumulative total for this unit
                        self._energy_data[unit.id] = self._energy_cumulative[unit.id]

                        _LOGGER.debug(
                            "Total energy for %s: %.3f kWh",
                            unit.name,
                            self._energy_cumulative[unit.id],
                        )

                    except (ConfigEntryAuthFailed, HomeAssistantError):
                        # V4 FIX: Re-raise auth failures - must trigger repair UI
                        # Don't swallow these - user needs to know credentials are broken
                        raise
                    except Exception as err:
                        # Keep broad handling for non-critical errors (network, parsing, etc.)
                        _LOGGER.error(
                            "Error fetching energy for unit %s: %s",
                            unit.name,
                            err,
                        )
                        # Keep previous cumulative value on error

            # Update unit objects with new energy data
            self._update_unit_energy_data()

            # Save energy data to persistent storage
            await self._save_energy_data()

            # Notify listeners (sensors) of energy update
            self.async_update_listeners()

        except Exception as err:
            _LOGGER.error("Error updating energy data: %s", err)

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
        """Get cached energy data for a unit (in kWh)."""
        return self._energy_data.get(unit_id)

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        if self._cancel_energy_updates:
            self._cancel_energy_updates()
        await self.client.close()

    def get_unit(self, unit_id: str) -> AirToAirUnit | None:
        """Get unit by ID - O(1) lookup."""
        return self._units.get(unit_id)

    def get_building_for_unit(self, unit_id: str) -> Building | None:
        """Get the building that contains the specified unit - O(1) lookup."""
        return self._unit_to_building.get(unit_id)

    async def _execute_with_retry(
        self,
        operation: Callable[[], Awaitable[Any]],
        operation_name: str = "API operation",
    ) -> Any:
        """
        Execute operation with automatic re-auth on session expiry.

        Uses double-check pattern to prevent concurrent re-auth attempts:
        1. Try operation
        2. If 401, acquire lock
        3. Try again (double-check - another task may have fixed it)
        4. If still 401, re-authenticate
        5. Retry after successful re-auth

        Args:
            operation: Async callable to execute (no arguments)
            operation_name: Human-readable name for logging

        Returns:
            Result of operation

        Raises:
            ConfigEntryAuthFailed: If re-authentication fails (triggers HA repair UI)
            HomeAssistantError: For other API errors

        Note: This changes behavior from UpdateFailed to ConfigEntryAuthFailed,
        which immediately shows repair UI instead of retrying with backoff.
        """
        try:
            # First attempt
            return await operation()

        except AuthenticationError:
            # Session expired - use lock to prevent concurrent re-auth
            async with self._reauth_lock:
                # Double-check: another task may have already re-authenticated
                try:
                    _LOGGER.debug(
                        "%s failed with session expired, retrying after lock",
                        operation_name,
                    )
                    return await operation()
                except AuthenticationError:
                    # Still expired, re-authenticate
                    _LOGGER.info(
                        "Session still expired, attempting re-authentication for %s",
                        operation_name,
                    )
                    try:
                        await self.client.login(self._email, self._password)
                        _LOGGER.info("Re-authentication successful")
                    except AuthenticationError as err:
                        _LOGGER.error("Re-authentication failed: %s", err)
                        raise ConfigEntryAuthFailed(
                            "Re-authentication failed. Please reconfigure the integration."
                        ) from err

            # Retry operation after successful re-auth (outside lock)
            _LOGGER.debug("Retrying %s after successful re-auth", operation_name)
            try:
                return await operation()
            except AuthenticationError as err:
                # Still failing after re-auth - credentials are invalid
                _LOGGER.error("%s failed even after re-auth", operation_name)
                raise ConfigEntryAuthFailed(
                    "Authentication failed after re-auth. Please reconfigure."
                ) from err

        except ApiError as err:
            _LOGGER.error("API error during %s: %s", operation_name, err)
            raise HomeAssistantError(f"API error: {err}") from err

    async def async_set_power(self, unit_id: str, power: bool) -> None:
        """Set power state with automatic session recovery."""
        # Skip if already in desired state (prevents duplicate API calls)
        unit = self.get_unit(unit_id)
        if unit and unit.power == power:
            _LOGGER.debug(
                "Power already %s for %s, skipping API call", power, unit_id[-8:]
            )
            return

        _LOGGER.info("Setting power for %s to %s", unit_id[-8:], power)
        await self._execute_with_retry(
            lambda: self.client.set_power(unit_id, power),
            f"set_power({unit_id}, {power})",
        )

    async def async_set_mode(self, unit_id: str, mode: str) -> None:
        """Set operation mode with automatic session recovery."""
        # Skip if already in desired state
        unit = self.get_unit(unit_id)
        if unit and unit.operation_mode == mode:
            _LOGGER.debug(
                "Mode already %s for %s, skipping API call", mode, unit_id[-8:]
            )
            return

        _LOGGER.info("Setting mode for %s to %s", unit_id[-8:], mode)
        await self._execute_with_retry(
            lambda: self.client.set_mode(unit_id, mode),
            f"set_mode({unit_id}, {mode})",
        )

    async def async_set_temperature(self, unit_id: str, temperature: float) -> None:
        """Set target temperature with automatic session recovery."""
        # Skip if already at desired temperature
        unit = self.get_unit(unit_id)
        if unit and unit.set_temperature == temperature:
            _LOGGER.debug(
                "Temperature already %.1f°C for %s, skipping API call",
                temperature,
                unit_id[-8:],
            )
            return

        _LOGGER.info("Setting temperature for %s to %.1f°C", unit_id[-8:], temperature)
        await self._execute_with_retry(
            lambda: self.client.set_temperature(unit_id, temperature),
            f"set_temperature({unit_id}, {temperature})",
        )

    async def async_set_fan_speed(self, unit_id: str, fan_speed: str) -> None:
        """Set fan speed with automatic session recovery."""
        # Skip if already at desired fan speed
        unit = self.get_unit(unit_id)
        if unit and unit.set_fan_speed == fan_speed:
            _LOGGER.debug(
                "Fan speed already %s for %s, skipping API call",
                fan_speed,
                unit_id[-8:],
            )
            return

        _LOGGER.info("Setting fan speed for %s to %s", unit_id[-8:], fan_speed)
        await self._execute_with_retry(
            lambda: self.client.set_fan_speed(unit_id, fan_speed),
            f"set_fan_speed({unit_id}, {fan_speed})",
        )

    async def async_set_vanes(
        self,
        unit_id: str,
        vertical: str,
        horizontal: str,
    ) -> None:
        """Set vane positions with automatic session recovery."""
        # Skip if already at desired vane positions
        unit = self.get_unit(unit_id)
        if (
            unit
            and unit.vane_vertical_direction == vertical
            and unit.vane_horizontal_direction == horizontal
        ):
            _LOGGER.debug(
                "Vanes already V:%s H:%s for %s, skipping API call",
                vertical,
                horizontal,
                unit_id[-8:],
            )
            return

        _LOGGER.info(
            "Setting vanes for %s to V:%s H:%s", unit_id[-8:], vertical, horizontal
        )
        await self._execute_with_retry(
            lambda: self.client.set_vanes(unit_id, vertical, horizontal),
            f"set_vanes({unit_id}, {vertical}, {horizontal})",
        )

    async def async_request_refresh_debounced(self, delay: float = 2.0) -> None:
        """Request a coordinator refresh with debouncing.

        Multiple rapid calls will cancel previous timers and only refresh once
        after the last call settles. This prevents race conditions when scenes
        or automations make multiple rapid service calls.

        Args:
            delay: Seconds to wait before refreshing (default 2.0)
        """
        # Cancel any pending refresh
        if self._refresh_debounce_task and not self._refresh_debounce_task.done():
            self._refresh_debounce_task.cancel()
            _LOGGER.debug("Cancelled pending debounced refresh, resetting timer")

        async def _delayed_refresh():
            """Wait then refresh."""
            await asyncio.sleep(delay)
            _LOGGER.debug("Debounced refresh executing after %.1fs delay", delay)
            await self.async_request_refresh()

        self._refresh_debounce_task = self.hass.async_create_task(_delayed_refresh())
