"""Protocol definitions for MELCloud Home integration.

This module defines protocols (structural subtyping) for better testability
and decoupling. Entities depend on protocols rather than concrete coordinator
implementations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from .api.models import AirToAirUnit, AirToWaterUnit, Building, UserContext


class CoordinatorProtocol(Protocol):
    """Protocol defining the coordinator interface used by entities.

    This protocol allows entities to depend on an interface rather than
    the concrete MELCloudHomeCoordinator class. Benefits:

    1. Testability - Can create lightweight test doubles
    2. Decoupling - Entities don't need full coordinator import
    3. Interface documentation - Clear contract for what entities need
    4. Type safety - Mypy verifies protocol compliance
    """

    # Data access properties
    @property
    def data(self) -> UserContext:
        """Get current user context data with buildings and units."""
        ...

    # Device lookup methods
    def get_device(self, unit_id: str) -> AirToAirUnit | None:
        """Get ATA device by ID.

        Args:
            unit_id: Device unit ID to look up

        Returns:
            AirToAirUnit device if found, None otherwise
        """
        ...

    def get_atw_device(self, unit_id: str) -> AirToWaterUnit | None:
        """Get ATW device by ID.

        Args:
            unit_id: ATW device unit ID to look up

        Returns:
            AirToWaterUnit device if found, None otherwise
        """
        ...

    def get_building_for_ata_device(self, unit_id: str) -> Building | None:
        """Get the building that contains the specified ATA device.

        Args:
            unit_id: ATA device unit ID

        Returns:
            Building containing the device, or None if not found
        """
        ...

    def get_building_for_atw_device(self, unit_id: str) -> Building | None:
        """Get the building that contains the specified ATW device.

        Args:
            unit_id: ATW device unit ID

        Returns:
            Building containing the device, or None if not found
        """
        ...

    def get_unit_energy(self, unit_id: str) -> float | None:
        """Get cached energy consumption for a unit.

        Args:
            unit_id: Unit ID to query

        Returns:
            Cumulative energy in kWh, or None if not available
        """
        ...

    # ATA (Air-to-Air) control methods
    async def async_set_power(self, unit_id: str, power: bool) -> None:
        """Set power state for ATA unit.

        Args:
            unit_id: ATA unit ID
            power: True to turn on, False to turn off
        """
        ...

    async def async_set_mode(self, unit_id: str, mode: str) -> None:
        """Set operation mode for ATA unit.

        Args:
            unit_id: ATA unit ID
            mode: Operation mode (e.g., "Heat", "Cool", "Dry")
        """
        ...

    async def async_set_temperature(self, unit_id: str, temperature: float) -> None:
        """Set target temperature for ATA unit.

        Args:
            unit_id: ATA unit ID
            temperature: Target temperature in Celsius
        """
        ...

    async def async_set_fan_speed(self, unit_id: str, fan_speed: str) -> None:
        """Set fan speed for ATA unit.

        Args:
            unit_id: ATA unit ID
            fan_speed: Fan speed (e.g., "Auto", "One", "Two")
        """
        ...

    async def async_set_vanes(
        self,
        unit_id: str,
        vertical: str,
        horizontal: str,
    ) -> None:
        """Set vane positions for ATA unit.

        Args:
            unit_id: ATA unit ID
            vertical: Vertical vane position
            horizontal: Horizontal vane position
        """
        ...

    # ATW (Air-to-Water) control methods
    async def async_set_power_atw(self, unit_id: str, power: bool) -> None:
        """Set power state for ATW heat pump.

        Args:
            unit_id: ATW unit ID
            power: True to turn on, False to turn off
        """
        ...

    async def async_set_temperature_zone1(
        self, unit_id: str, temperature: float
    ) -> None:
        """Set Zone 1 target temperature for ATW unit.

        Args:
            unit_id: ATW unit ID
            temperature: Target temperature in Celsius
        """
        ...

    async def async_set_temperature_zone2(
        self, unit_id: str, temperature: float
    ) -> None:
        """Set Zone 2 target temperature for ATW unit.

        Args:
            unit_id: ATW unit ID
            temperature: Target temperature in Celsius
        """
        ...

    async def async_set_mode_zone1(self, unit_id: str, mode: str) -> None:
        """Set Zone 1 heating strategy for ATW unit.

        Args:
            unit_id: ATW unit ID
            mode: Heating strategy (e.g., "RoomTemperature", "FlowTemperature")
        """
        ...

    async def async_set_mode_zone2(self, unit_id: str, mode: str) -> None:
        """Set Zone 2 heating strategy for ATW unit.

        Args:
            unit_id: ATW unit ID
            mode: Heating strategy
        """
        ...

    async def async_set_dhw_temperature(self, unit_id: str, temperature: float) -> None:
        """Set DHW tank target temperature for ATW unit.

        Args:
            unit_id: ATW unit ID
            temperature: Target DHW temperature in Celsius
        """
        ...

    async def async_set_forced_hot_water(self, unit_id: str, enabled: bool) -> None:
        """Enable/disable forced DHW priority mode for ATW unit.

        Args:
            unit_id: ATW unit ID
            enabled: True to enable forced DHW, False to disable
        """
        ...

    async def async_set_standby_mode(self, unit_id: str, standby: bool) -> None:
        """Enable/disable standby mode for ATW unit.

        Args:
            unit_id: ATW unit ID
            standby: True to enable standby, False to disable
        """
        ...

    # Refresh control
    async def async_request_refresh_debounced(self, delay: float = 2.0) -> None:
        """Request a coordinator refresh with debouncing.

        Args:
            delay: Delay in seconds before refresh (debounce time)
        """
        ...

    def async_update_listeners(self) -> None:
        """Notify all listeners that data has been updated.

        This is inherited from DataUpdateCoordinator and used to notify
        entities when data changes outside the normal update cycle.
        """
        ...
