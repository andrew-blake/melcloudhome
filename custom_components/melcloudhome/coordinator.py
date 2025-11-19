"""Data update coordinator for MELCloud Home integration."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
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
        # Perform initial energy fetch
        await self._async_update_energy_data()

        # Schedule periodic energy updates (30 minutes)
        self._cancel_energy_updates = async_track_time_interval(
            self.hass,
            self._async_update_energy_data,
            ENERGY_UPDATE_INTERVAL,
        )

    @callback  # type: ignore[misc]
    async def _async_update_energy_data(self, now: datetime | None = None) -> None:
        """Update energy data for all units (called every 30 minutes)."""
        if not self.data:
            return

        try:
            to_time = datetime.now(UTC)
            from_time = to_time - timedelta(hours=1)

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

                        energy = self.client.parse_energy_response(data)
                        self._energy_data[unit.id] = energy

                        if energy is not None:
                            _LOGGER.debug(
                                "Energy data for unit %s: %.3f kWh",
                                unit.name,
                                energy,
                            )
                        else:
                            _LOGGER.debug(
                                "No energy data available for unit %s",
                                unit.name,
                            )

                    except Exception as err:
                        _LOGGER.error(
                            "Error fetching energy for unit %s: %s",
                            unit.name,
                            err,
                        )
                        # Keep previous value in cache on error

            # Update unit objects with new energy data
            self._update_unit_energy_data()

            # Notify listeners (sensors) of energy update
            self.async_update_listeners()

        except Exception as err:
            _LOGGER.error("Error updating energy data: %s", err)

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
