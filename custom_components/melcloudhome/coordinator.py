"""Data update coordinator for MELCloud Home integration."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api.client import MELCloudHomeClient
from .api.exceptions import ApiError, AuthenticationError
from .api.models import AirToAirUnit, AirToWaterUnit, Building, UserContext
from .const import (
    DOMAIN,
    UPDATE_INTERVAL,
    UPDATE_INTERVAL_ENERGY,
    UPDATE_INTERVAL_TELEMETRY,
)
from .control_client_ata import ATAControlClient
from .control_client_atw import ATWControlClient
from .energy_tracker_ata import ATAEnergyTracker
from .energy_tracker_atw import ATWEnergyTracker
from .telemetry_tracker import TelemetryTracker

if TYPE_CHECKING:
    from homeassistant.helpers.event import CALLBACK_TYPE

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
        # ATW unit caches (same pattern as ATA)
        self._atw_unit_to_building: dict[str, Building] = {}
        self._atw_units: dict[str, AirToWaterUnit] = {}
        # Energy tracking cancellation callback
        self._cancel_energy_updates: CALLBACK_TYPE | None = None
        # SPIKE: Telemetry tracking cancellation callback
        self._cancel_telemetry_updates: CALLBACK_TYPE | None = None
        # Re-authentication lock to prevent concurrent re-auth attempts
        self._reauth_lock = asyncio.Lock()

        # Initialize ATA energy tracker
        self.energy_tracker = ATAEnergyTracker(
            hass=hass,
            client=client,
            execute_with_retry=self._execute_with_retry,
            get_coordinator_data=lambda: self.data,
        )

        # Initialize ATW energy tracker
        self.energy_tracker_atw = ATWEnergyTracker(
            hass=hass,
            client=client.atw,  # Pass ATW-specific client, not facade
            execute_with_retry=self._execute_with_retry,
            get_coordinator_data=lambda: self.data,
        )

        # Initialize telemetry tracker
        self.telemetry_tracker = TelemetryTracker(
            hass=hass,
            client=client,
            execute_with_retry=self._execute_with_retry,
            get_coordinator_data=lambda: self.data,
        )

        # Initialize ATA control client
        self.control_client_ata = ATAControlClient(
            hass=hass,
            client=client,
            execute_with_retry=self._execute_with_retry,
            get_device=self.get_ata_device,
            async_request_refresh=self.async_request_refresh,
        )

        # Initialize ATW control client
        self.control_client_atw = ATWControlClient(
            hass=hass,
            client=client,
            execute_with_retry=self._execute_with_retry,
            get_atw_device=self.get_atw_device,
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

        # Debug logging: Log verbose device states (controlled by HA logger config)
        for building in context.buildings:
            # Log ATA (Air-to-Air) devices
            for ata_unit in building.air_to_air_units:
                _LOGGER.debug(
                    "ATA Poll: %s | Power=%s | Mode=%s | Temp: %s°C→%s°C | Fan=%s",
                    ata_unit.name,
                    ata_unit.power,
                    ata_unit.operation_mode,
                    ata_unit.room_temperature,
                    ata_unit.set_temperature,
                    ata_unit.set_fan_speed,
                )

            # Log ATW (Air-to-Water) devices
            for atw_unit in building.air_to_water_units:
                _LOGGER.debug(
                    "ATW Poll: %s | Power=%s | Standby=%s | OpStatus=%s | OpModeZ1=%s | ForcedDHW=%s | Z1: %s°C→%s°C | DHW: %s°C→%s°C",
                    atw_unit.name,
                    atw_unit.power,
                    atw_unit.in_standby_mode,
                    atw_unit.operation_status,
                    atw_unit.operation_mode_zone1,
                    atw_unit.forced_hot_water_mode,
                    atw_unit.room_temperature_zone1,
                    atw_unit.set_temperature_zone1,
                    atw_unit.tank_water_temperature,
                    atw_unit.set_tank_water_temperature,
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

        # Update energy data for ATA units using energy tracker
        self.energy_tracker.update_unit_energy_data(self._units)

        # Update energy data for ATW units using ATW energy tracker
        self.energy_tracker_atw.update_unit_energy_data(self._atw_units)

        # Update telemetry data for ATW units using telemetry tracker
        self.telemetry_tracker.update_unit_telemetry_data(self._atw_units)

    async def _update_single_energy_tracker(
        self,
        tracker: Any,
        units_dict: dict[str, Any],
        now: Any = None,
    ) -> None:
        """Update a single energy tracker and its units.

        Args:
            tracker: Energy tracker instance (energy_tracker or energy_tracker_atw)
            units_dict: Dictionary of units to update (self._units or self._atw_units)
            now: Optional timestamp for scheduled updates
        """
        await tracker.async_update_energy_data(now)
        tracker.update_unit_energy_data(units_dict)

    async def _fetch_and_update_tracker(
        self,
        tracker_name: str,
        fetch_method: Callable[[], Awaitable[None]],
        update_method: Callable[[dict[str, Any]], None],
        units_dict: dict[str, Any],
    ) -> None:
        """Fetch and update a tracker (energy or telemetry).

        Args:
            tracker_name: Human-readable tracker name for logging (e.g., "ATA energy")
            fetch_method: Async method to fetch data (e.g., tracker.async_update_energy_data)
            update_method: Method to update units (e.g., tracker.update_unit_energy_data)
            units_dict: Dictionary of units to update (self._units or self._atw_units)
        """
        try:
            await fetch_method()
            _LOGGER.info("Initial %s fetch completed", tracker_name)
            update_method(units_dict)
        except Exception as err:
            _LOGGER.error(
                "Error during initial %s fetch: %s",
                tracker_name,
                err,
                exc_info=True,
            )

    async def async_setup(self) -> None:
        """Set up the coordinator with energy polling."""
        _LOGGER.info("Setting up energy polling for MELCloud Home")

        # Set up both energy trackers
        await self.energy_tracker.async_setup()
        await self.energy_tracker_atw.async_setup()

        # Perform initial energy fetch for both ATA and ATW units in parallel
        # Use return_exceptions=True to ensure one failure doesn't block the other
        await asyncio.gather(
            self._fetch_and_update_tracker(
                "ATA energy",
                self.energy_tracker.async_update_energy_data,
                self.energy_tracker.update_unit_energy_data,
                self._units,
            ),
            self._fetch_and_update_tracker(
                "ATW energy",
                self.energy_tracker_atw.async_update_energy_data,
                self.energy_tracker_atw.update_unit_energy_data,
                self._atw_units,
            ),
            return_exceptions=True,
        )

        # Notify listeners once after both energy fetches complete
        self.async_update_listeners()

        # Schedule periodic energy updates (30 minutes)
        async def _update_energy_with_listeners(now):
            """Update energy and notify listeners."""
            # Update both trackers in parallel for efficiency
            await asyncio.gather(
                self._update_single_energy_tracker(
                    self.energy_tracker, self._units, now
                ),
                self._update_single_energy_tracker(
                    self.energy_tracker_atw, self._atw_units, now
                ),
                return_exceptions=True,
            )
            self.async_update_listeners()

        self._cancel_energy_updates = async_track_time_interval(
            self.hass,
            _update_energy_with_listeners,
            UPDATE_INTERVAL_ENERGY,
        )
        _LOGGER.info("Energy polling scheduled (every 30 minutes)")

        # Setup telemetry tracker
        await self.telemetry_tracker.async_setup()

        # Perform initial telemetry fetch
        await self._fetch_and_update_tracker(
            "telemetry",
            self.telemetry_tracker.async_update_telemetry_data,
            self.telemetry_tracker.update_unit_telemetry_data,
            self._atw_units,
        )

        # Notify listeners after telemetry fetch
        self.async_update_listeners()

        # Schedule periodic telemetry updates (60 minutes)
        async def _update_telemetry_with_listeners(now):
            """Update telemetry and notify listeners."""
            await self.telemetry_tracker.async_update_telemetry_data(now)
            self.telemetry_tracker.update_unit_telemetry_data(self._atw_units)
            self.async_update_listeners()

        self._cancel_telemetry_updates = async_track_time_interval(
            self.hass,
            _update_telemetry_with_listeners,
            UPDATE_INTERVAL_TELEMETRY,
        )
        _LOGGER.info("Telemetry polling scheduled (every 60 minutes)")

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
        if self._cancel_telemetry_updates:
            self._cancel_telemetry_updates()
        await self.client.close()

    def get_ata_device(self, unit_id: str) -> AirToAirUnit | None:
        """Get ATA device by ID - O(1) lookup."""
        return self._units.get(unit_id)

    def get_building_for_ata_device(self, unit_id: str) -> Building | None:
        """Get the building that contains the specified ATA device - O(1) lookup."""
        return self._unit_to_building.get(unit_id)

    def get_atw_device(self, unit_id: str) -> AirToWaterUnit | None:
        """Get ATW device by ID from cache.

        Args:
            unit_id: ATW device unit ID

        Returns:
            Cached AirToWaterUnit device if found, None otherwise
        """
        return self._atw_units.get(unit_id)

    def get_building_for_atw_device(self, unit_id: str) -> Building | None:
        """Get the building that contains the specified ATW device - O(1) lookup.

        Args:
            unit_id: ATW device unit ID

        Returns:
            Building containing the device, or None if not found
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
    # Air-to-Air (A2A) Control Methods - Delegate to ATAControlClient
    # =================================================================

    async def async_set_power(self, unit_id: str, power: bool) -> None:
        """Set power state with automatic session recovery."""
        return await self.control_client_ata.async_set_power(unit_id, power)

    async def async_set_mode(self, unit_id: str, mode: str) -> None:
        """Set operation mode with automatic session recovery."""
        return await self.control_client_ata.async_set_mode(unit_id, mode)

    async def async_set_temperature(self, unit_id: str, temperature: float) -> None:
        """Set target temperature with automatic session recovery."""
        return await self.control_client_ata.async_set_temperature(unit_id, temperature)

    async def async_set_fan_speed(self, unit_id: str, fan_speed: str) -> None:
        """Set fan speed with automatic session recovery."""
        return await self.control_client_ata.async_set_fan_speed(unit_id, fan_speed)

    async def async_set_vanes(
        self,
        unit_id: str,
        vertical: str,
        horizontal: str,
    ) -> None:
        """Set vane positions with automatic session recovery."""
        return await self.control_client_ata.async_set_vanes(
            unit_id, vertical, horizontal
        )

    # =================================================================
    # Air-to-Water (A2W) Heat Pump Control Methods - Delegate to ATWControlClient
    # =================================================================

    async def async_set_power_atw(self, unit_id: str, power: bool) -> None:
        """Set ATW heat pump power with automatic session recovery."""
        return await self.control_client_atw.async_set_power(unit_id, power)

    async def async_set_temperature_zone1(
        self, unit_id: str, temperature: float
    ) -> None:
        """Set Zone 1 target temperature."""
        return await self.control_client_atw.async_set_temperature_zone1(
            unit_id, temperature
        )

    async def async_set_temperature_zone2(
        self, unit_id: str, temperature: float
    ) -> None:
        """Set Zone 2 target temperature."""
        return await self.control_client_atw.async_set_temperature_zone2(
            unit_id, temperature
        )

    async def async_set_mode_zone1(self, unit_id: str, mode: str) -> None:
        """Set Zone 1 heating strategy."""
        return await self.control_client_atw.async_set_mode_zone1(unit_id, mode)

    async def async_set_mode_zone2(self, unit_id: str, mode: str) -> None:
        """Set Zone 2 heating strategy."""
        return await self.control_client_atw.async_set_mode_zone2(unit_id, mode)

    async def async_set_dhw_temperature(self, unit_id: str, temperature: float) -> None:
        """Set DHW tank target temperature."""
        return await self.control_client_atw.async_set_dhw_temperature(
            unit_id, temperature
        )

    async def async_set_forced_hot_water(self, unit_id: str, enabled: bool) -> None:
        """Enable/disable forced DHW priority mode."""
        return await self.control_client_atw.async_set_forced_hot_water(
            unit_id, enabled
        )

    async def async_set_standby_mode(self, unit_id: str, standby: bool) -> None:
        """Enable/disable standby mode."""
        return await self.control_client_atw.async_set_standby_mode(unit_id, standby)

    async def async_request_refresh_debounced(self, delay: float = 2.0) -> None:
        """Request a coordinator refresh with debouncing."""
        return await self.control_client_ata.async_request_refresh_debounced(delay)
