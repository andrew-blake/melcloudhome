"""Data update coordinator for MELCloud Home integration."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api.client import MELCloudHomeClient
from .api.exceptions import ApiError, AuthenticationError
from .api.models import Building, UserContext
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

    async def _async_update_data(self) -> UserContext:
        """Fetch data from API endpoint."""
        try:
            return await self.client.get_user_context()
        except AuthenticationError:
            # Session expired - try to re-authenticate
            _LOGGER.info("Session expired, attempting to re-authenticate")
            try:
                await self.client.login(self._email, self._password)
                return await self.client.get_user_context()
            except AuthenticationError as err:
                # Re-authentication failed - credentials are invalid
                _LOGGER.error("Re-authentication failed: %s", err)
                raise UpdateFailed(
                    "Re-authentication failed. Please reconfigure the integration."
                ) from err
        except ApiError as err:
            _LOGGER.error("Error communicating with API: %s", err)
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        await self.client.close()

    def get_building_for_unit(self, unit_id: str) -> Building | None:
        """Get the building that contains the specified unit."""
        if not self.data:
            return None

        for building in self.data.buildings:
            for unit in building.air_to_air_units:
                if unit.id == unit_id:
                    return building  # type: ignore[no-any-return]

        return None
