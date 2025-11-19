"""Data update coordinator for MELCloud Home integration."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

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
        # Last processed hour timestamp per device (to avoid double-counting)
        self._energy_last_hour: dict[str, str] = {}
        # Persistent storage for energy data
        self._store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)

    async def _async_update_data(self) -> UserContext:
        """Fetch data from API endpoint."""
        try:
            # If not authenticated yet, login first
            if not self.client.is_authenticated:
                _LOGGER.debug("Not authenticated, logging in")
                await self.client.login(self._email, self._password)

            context = await self.client.get_user_context()

            # Update caches for O(1) lookups
            self._rebuild_caches(context)

            return context
        except AuthenticationError:
            # Session expired - try to re-authenticate
            _LOGGER.info("Session expired, attempting to re-authenticate")
            try:
                await self.client.login(self._email, self._password)
                context = await self.client.get_user_context()
                self._rebuild_caches(context)
                return context
            except AuthenticationError as err:
                # Re-authentication failed - credentials are invalid
                _LOGGER.error("Re-authentication failed: %s", err)
                raise UpdateFailed(
                    "Re-authentication failed. Please reconfigure the integration."
                ) from err
        except ApiError as err:
            _LOGGER.error("Error communicating with API: %s", err)
            raise UpdateFailed(f"Error communicating with API: {err}") from err

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
            self._energy_last_hour = stored_data.get("last_hour", {})
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
            # Fetch last 2 hours to ensure we don't miss any data
            from_time = to_time - timedelta(hours=2)

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

                        data = await self.client.get_energy_data(
                            unit.id, from_time, to_time, "Hour"
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

                        # Get last processed hour for this device
                        last_hour = self._energy_last_hour.get(unit.id)
                        is_first_init = last_hour is None

                        # Initialize cumulative total if first time
                        if unit.id not in self._energy_cumulative:
                            self._energy_cumulative[unit.id] = 0.0

                        if is_first_init:
                            # First initialization: mark all current hours as processed
                            # but DON'T add them (avoid inflating with historical data)
                            latest_hour = values[-1]["time"]
                            self._energy_last_hour[unit.id] = latest_hour
                            _LOGGER.info(
                                "Initializing energy tracking for %s at 0.0 kWh "
                                "(skipping %d hours of historical data, will track from %s)",
                                unit.name,
                                len(values),
                                latest_hour[:16],
                            )
                        else:
                            # Normal operation: process each hourly value
                            for value_entry in values:
                                hour_timestamp = value_entry["time"]
                                wh_value = float(value_entry["value"])
                                kwh_value = wh_value / 1000.0

                                # Only process NEW hours we haven't seen before
                                if hour_timestamp > last_hour:
                                    # Add this hour's consumption to cumulative total
                                    self._energy_cumulative[unit.id] += kwh_value

                                    _LOGGER.info(
                                        "Energy: %s - Hour %s: +%.3f kWh (cumulative: %.3f kWh)",
                                        unit.name,
                                        hour_timestamp[:16],
                                        kwh_value,
                                        self._energy_cumulative[unit.id],
                                    )

                                    # Update last processed hour
                                    self._energy_last_hour[unit.id] = hour_timestamp
                                else:
                                    # Already processed this hour
                                    _LOGGER.debug(
                                        "Skipping already-processed hour %s for %s",
                                        hour_timestamp[:16],
                                        unit.name,
                                    )

                        # Store cumulative total for this unit
                        self._energy_data[unit.id] = self._energy_cumulative[unit.id]

                        _LOGGER.debug(
                            "Total energy for %s: %.3f kWh",
                            unit.name,
                            self._energy_cumulative[unit.id],
                        )

                    except Exception as err:
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
        """Save energy cumulative totals and last hour timestamps to storage."""
        try:
            data = {
                "cumulative": self._energy_cumulative,
                "last_hour": self._energy_last_hour,
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
