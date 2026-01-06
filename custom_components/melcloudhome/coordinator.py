"""Data update coordinator for MELCloud Home integration."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api.client import MELCloudHomeClient
from .api.exceptions import ApiError, AuthenticationError
from .api.models import AirToAirUnit, AirToWaterUnit, Building, UserContext
from .const import DOMAIN, UPDATE_INTERVAL
from .control_client import ControlClient
from .energy_tracker import EnergyTracker

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
        # ATW unit caches (same pattern as ATA)
        self._atw_unit_to_building: dict[str, Building] = {}
        self._atw_units: dict[str, AirToWaterUnit] = {}
        # Energy tracking cancellation callback
        self._cancel_energy_updates: CALLBACK_TYPE | None = None
        # Re-authentication lock to prevent concurrent re-auth attempts
        self._reauth_lock = asyncio.Lock()

        # Initialize energy tracker
        self.energy_tracker = EnergyTracker(
            hass=hass,
            client=client,
            execute_with_retry=self._execute_with_retry,
            get_coordinator_data=lambda: self.data,
        )

        # Initialize control client
        self.control_client = ControlClient(
            hass=hass,
            client=client,
            execute_with_retry=self._execute_with_retry,
            get_unit=self.get_unit,
            get_atw_unit=self.get_atw_unit,
            async_request_refresh=self.async_request_refresh,
        )

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
        self._atw_unit_to_building.clear()
        self._atw_units.clear()

        for building in context.buildings:
            # Cache A2A units (existing)
            for unit in building.air_to_air_units:
                self._units[unit.id] = unit
                self._unit_to_building[unit.id] = building

            # Cache A2W units
            for atw_unit in building.air_to_water_units:
                self._atw_units[atw_unit.id] = atw_unit
                self._atw_unit_to_building[atw_unit.id] = building

        # Update energy data for units using energy tracker
        self.energy_tracker.update_unit_energy_data(self._units)

    async def async_setup(self) -> None:
        """Set up the coordinator with energy polling."""
        _LOGGER.info("Setting up energy polling for MELCloud Home")

        # Set up energy tracker
        await self.energy_tracker.async_setup()

        # Perform initial energy fetch
        try:
            await self.energy_tracker.async_update_energy_data()
            _LOGGER.info("Initial energy fetch completed")

            # Update unit objects with new energy data
            self.energy_tracker.update_unit_energy_data(self._units)

            # Notify listeners (sensors) of energy update
            self.async_update_listeners()
        except Exception as err:
            _LOGGER.error("Error during initial energy fetch: %s", err, exc_info=True)

        # Schedule periodic energy updates (30 minutes)
        async def _update_energy_with_listeners(now):
            """Update energy and notify listeners."""
            await self.energy_tracker.async_update_energy_data(now)
            self.energy_tracker.update_unit_energy_data(self._units)
            self.async_update_listeners()

        self._cancel_energy_updates = async_track_time_interval(
            self.hass,
            _update_energy_with_listeners,
            ENERGY_UPDATE_INTERVAL,
        )
        _LOGGER.info("Energy polling scheduled (every 30 minutes)")

    def get_unit_energy(self, unit_id: str) -> float | None:
        """Get cached energy data for a unit (in kWh).

        Args:
            unit_id: Unit ID to query

        Returns:
            Cumulative energy in kWh, or None if not available
        """
        return self.energy_tracker.get_unit_energy(unit_id)

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

    def get_atw_unit(self, unit_id: str) -> AirToWaterUnit | None:
        """Get ATW unit by ID from cache.

        Args:
            unit_id: ATW unit ID

        Returns:
            Cached AirToWaterUnit if found, None otherwise
        """
        return self._atw_units.get(unit_id)

    def get_building_for_atw_unit(self, unit_id: str) -> Building | None:
        """Get the building that contains the specified ATW unit - O(1) lookup.

        Args:
            unit_id: ATW unit ID

        Returns:
            Building containing the unit, or None if not found
        """
        return self._atw_unit_to_building.get(unit_id)

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

    # =================================================================
    # Air-to-Air (A2A) Control Methods - Delegate to ControlClient
    # =================================================================

    async def async_set_power(self, unit_id: str, power: bool) -> None:
        """Set power state with automatic session recovery."""
        return await self.control_client.async_set_power(unit_id, power)

    async def async_set_mode(self, unit_id: str, mode: str) -> None:
        """Set operation mode with automatic session recovery."""
        return await self.control_client.async_set_mode(unit_id, mode)

    async def async_set_temperature(self, unit_id: str, temperature: float) -> None:
        """Set target temperature with automatic session recovery."""
        return await self.control_client.async_set_temperature(unit_id, temperature)

    async def async_set_fan_speed(self, unit_id: str, fan_speed: str) -> None:
        """Set fan speed with automatic session recovery."""
        return await self.control_client.async_set_fan_speed(unit_id, fan_speed)

    async def async_set_vanes(
        self,
        unit_id: str,
        vertical: str,
        horizontal: str,
    ) -> None:
        """Set vane positions with automatic session recovery."""
        return await self.control_client.async_set_vanes(unit_id, vertical, horizontal)

    # =================================================================
    # Air-to-Water (A2W) Heat Pump Control Methods - Delegate to ControlClient
    # =================================================================

    async def async_set_power_atw(self, unit_id: str, power: bool) -> None:
        """Set ATW heat pump power with automatic session recovery."""
        return await self.control_client.async_set_power_atw(unit_id, power)

    async def async_set_temperature_zone1(
        self, unit_id: str, temperature: float
    ) -> None:
        """Set Zone 1 target temperature."""
        return await self.control_client.async_set_temperature_zone1(
            unit_id, temperature
        )

    async def async_set_temperature_zone2(
        self, unit_id: str, temperature: float
    ) -> None:
        """Set Zone 2 target temperature."""
        return await self.control_client.async_set_temperature_zone2(
            unit_id, temperature
        )

    async def async_set_mode_zone1(self, unit_id: str, mode: str) -> None:
        """Set Zone 1 heating strategy."""
        return await self.control_client.async_set_mode_zone1(unit_id, mode)

    async def async_set_mode_zone2(self, unit_id: str, mode: str) -> None:
        """Set Zone 2 heating strategy."""
        return await self.control_client.async_set_mode_zone2(unit_id, mode)

    async def async_set_dhw_temperature(self, unit_id: str, temperature: float) -> None:
        """Set DHW tank target temperature."""
        return await self.control_client.async_set_dhw_temperature(unit_id, temperature)

    async def async_set_forced_hot_water(self, unit_id: str, enabled: bool) -> None:
        """Enable/disable forced DHW priority mode."""
        return await self.control_client.async_set_forced_hot_water(unit_id, enabled)

    async def async_set_standby_mode(self, unit_id: str, standby: bool) -> None:
        """Enable/disable standby mode."""
        return await self.control_client.async_set_standby_mode(unit_id, standby)

    async def async_request_refresh_debounced(self, delay: float = 2.0) -> None:
        """Request a coordinator refresh with debouncing."""
        return await self.control_client.async_request_refresh_debounced(delay)
