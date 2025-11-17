"""Data update coordinator for MELCloud Home integration."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api.client import MELCloudHomeClient
from .api.exceptions import ApiError, AuthenticationError
from .api.models import AirToAirUnit, Building, UserContext
from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


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

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        await self.client.close()

    def get_unit(self, unit_id: str) -> AirToAirUnit | None:
        """Get unit by ID - O(1) lookup."""
        return self._units.get(unit_id)

    def get_building_for_unit(self, unit_id: str) -> Building | None:
        """Get the building that contains the specified unit - O(1) lookup."""
        return self._unit_to_building.get(unit_id)
