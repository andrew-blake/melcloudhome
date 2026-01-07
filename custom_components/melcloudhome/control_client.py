"""Control client for MELCloud Home integration."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import HomeAssistantError

from .api.client import MELCloudHomeClient
from .api.models import AirToAirUnit, AirToWaterUnit

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class ControlClient:
    """Handles device control operations with retry logic and debounced refresh."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: MELCloudHomeClient,
        execute_with_retry: Callable[
            [Callable[[], Awaitable[Any]], str], Awaitable[Any]
        ],
        get_device: Callable[[str], AirToAirUnit | None],
        get_atw_device: Callable[[str], AirToWaterUnit | None],
        async_request_refresh: Callable[[], Awaitable[None]],
    ) -> None:
        """Initialize control client.

        Args:
            hass: Home Assistant instance
            client: MELCloud Home API client
            execute_with_retry: Coordinator's retry wrapper for API calls
            get_device: Callable to get ATA device by ID
            get_atw_device: Callable to get ATW device by ID
            async_request_refresh: Callable to request coordinator refresh
        """
        self._hass = hass
        self._client = client
        self._execute_with_retry = execute_with_retry
        self._get_device = get_device
        self._get_atw_device = get_atw_device
        self._async_request_refresh = async_request_refresh
        # Debounced refresh to prevent race conditions from rapid service calls
        self._refresh_debounce_task: asyncio.Task | None = None

    # =================================================================
    # Air-to-Air (A2A) Control Methods
    # =================================================================

    async def async_set_power(self, unit_id: str, power: bool) -> None:
        """Set power state with automatic session recovery.

        Args:
            unit_id: Unit ID
            power: True=ON, False=OFF
        """
        # Skip if already in desired state (prevents duplicate API calls)
        device = self._get_device(unit_id)
        if device and device.power == power:
            _LOGGER.debug(
                "Power already %s for %s, skipping API call", power, unit_id[-8:]
            )
            return

        _LOGGER.info("Setting power for %s to %s", unit_id[-8:], power)
        await self._execute_with_retry(
            lambda: self._client.ata.set_power(unit_id, power),
            f"set_power({unit_id}, {power})",
        )

    async def async_set_mode(self, unit_id: str, mode: str) -> None:
        """Set operation mode with automatic session recovery.

        Args:
            unit_id: Unit ID
            mode: Operation mode string
        """
        # Skip if already in desired state
        device = self._get_device(unit_id)
        if device and device.operation_mode == mode:
            _LOGGER.debug(
                "Mode already %s for %s, skipping API call", mode, unit_id[-8:]
            )
            return

        _LOGGER.info("Setting mode for %s to %s", unit_id[-8:], mode)
        await self._execute_with_retry(
            lambda: self._client.ata.set_mode(unit_id, mode),
            f"set_mode({unit_id}, {mode})",
        )

    async def async_set_temperature(self, unit_id: str, temperature: float) -> None:
        """Set target temperature with automatic session recovery.

        Args:
            unit_id: Unit ID
            temperature: Target temperature in Celsius
        """
        # Skip if already at desired temperature
        device = self._get_device(unit_id)
        if device and device.set_temperature == temperature:
            _LOGGER.debug(
                "Temperature already %.1f°C for %s, skipping API call",
                temperature,
                unit_id[-8:],
            )
            return

        _LOGGER.info("Setting temperature for %s to %.1f°C", unit_id[-8:], temperature)
        await self._execute_with_retry(
            lambda: self._client.ata.set_temperature(unit_id, temperature),
            f"set_temperature({unit_id}, {temperature})",
        )

    async def async_set_fan_speed(self, unit_id: str, fan_speed: str) -> None:
        """Set fan speed with automatic session recovery.

        Args:
            unit_id: Unit ID
            fan_speed: Fan speed string
        """
        # Skip if already at desired fan speed
        device = self._get_device(unit_id)
        if device and device.set_fan_speed == fan_speed:
            _LOGGER.debug(
                "Fan speed already %s for %s, skipping API call",
                fan_speed,
                unit_id[-8:],
            )
            return

        _LOGGER.info("Setting fan speed for %s to %s", unit_id[-8:], fan_speed)
        await self._execute_with_retry(
            lambda: self._client.ata.set_fan_speed(unit_id, fan_speed),
            f"set_fan_speed({unit_id}, {fan_speed})",
        )

    async def async_set_vanes(
        self,
        unit_id: str,
        vertical: str,
        horizontal: str,
    ) -> None:
        """Set vane positions with automatic session recovery.

        Args:
            unit_id: Unit ID
            vertical: Vertical vane position
            horizontal: Horizontal vane position
        """
        # Skip if already at desired vane positions
        device = self._get_device(unit_id)
        if (
            device
            and device.vane_vertical_direction == vertical
            and device.vane_horizontal_direction == horizontal
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
            lambda: self._client.ata.set_vanes(unit_id, vertical, horizontal),
            f"set_vanes({unit_id}, {vertical}, {horizontal})",
        )

    # =================================================================
    # Air-to-Water (A2W) Heat Pump Control Methods
    # =================================================================

    async def _execute_atw_control(
        self,
        unit_id: str,
        control_name: str,
        control_fn: Callable[[AirToWaterUnit], Awaitable[None]],
        pre_check: Callable[[AirToWaterUnit], None] | None = None,
    ) -> None:
        """Generic ATW control method with validation and retry.

        Args:
            unit_id: ATW unit ID
            control_name: Human-readable control name for logging
            control_fn: Control function that takes unit and executes API call
            pre_check: Optional validation function (raises HomeAssistantError if invalid)

        Raises:
            HomeAssistantError: If unit not found or pre-check fails
        """
        # Get cached unit
        atw_device = self._get_atw_device(unit_id)
        if not atw_device:
            raise HomeAssistantError(f"ATW unit {unit_id} not found")

        # Run pre-check if provided (e.g., Zone 2 capability validation)
        if pre_check:
            pre_check(atw_device)

        # Log the operation
        _LOGGER.info(
            "Setting %s for ATW unit %s",
            control_name,
            unit_id[-8:],
        )

        # Execute with automatic retry on session expiry
        await self._execute_with_retry(
            lambda: control_fn(atw_device),
            f"{control_name}({unit_id})",
        )

    async def async_set_power_atw(self, unit_id: str, power: bool) -> None:
        """Set ATW heat pump power with automatic session recovery.

        Args:
            unit_id: ATW unit ID
            power: True=ON, False=OFF
        """
        return await self._execute_atw_control(
            unit_id=unit_id,
            control_name="power",
            control_fn=lambda unit: self._client.atw.set_power_atw(unit.id, power),
        )

    async def async_set_temperature_zone1(
        self, unit_id: str, temperature: float
    ) -> None:
        """Set Zone 1 target temperature.

        Args:
            unit_id: ATW unit ID
            temperature: Target temp in Celsius (10-30°C)
        """
        return await self._execute_atw_control(
            unit_id=unit_id,
            control_name="Zone 1 temperature",
            control_fn=lambda unit: self._client.atw.set_temperature_zone1(
                unit.id, temperature
            ),
        )

    async def async_set_temperature_zone2(
        self, unit_id: str, temperature: float
    ) -> None:
        """Set Zone 2 target temperature.

        Args:
            unit_id: ATW unit ID
            temperature: Target temp in Celsius (10-30°C)

        Raises:
            HomeAssistantError: If device doesn't have Zone 2
        """

        def _check_zone2(unit: AirToWaterUnit) -> None:
            if not unit.capabilities.has_zone2:
                raise HomeAssistantError(f"Device '{unit.name}' does not have Zone 2")

        return await self._execute_atw_control(
            unit_id=unit_id,
            control_name="Zone 2 temperature",
            control_fn=lambda unit: self._client.atw.set_temperature_zone2(
                unit.id, temperature
            ),
            pre_check=_check_zone2,
        )

    async def async_set_mode_zone1(self, unit_id: str, mode: str) -> None:
        """Set Zone 1 heating strategy.

        Args:
            unit_id: ATW unit ID
            mode: One of ATW_OPERATION_MODES_ZONE
        """
        return await self._execute_atw_control(
            unit_id=unit_id,
            control_name="Zone 1 mode",
            control_fn=lambda unit: self._client.atw.set_mode_zone1(unit.id, mode),
        )

    async def async_set_mode_zone2(self, unit_id: str, mode: str) -> None:
        """Set Zone 2 heating strategy.

        Args:
            unit_id: ATW unit ID
            mode: One of ATW_OPERATION_MODES_ZONE

        Raises:
            HomeAssistantError: If device doesn't have Zone 2
        """

        def _check_zone2(unit: AirToWaterUnit) -> None:
            if not unit.capabilities.has_zone2:
                raise HomeAssistantError(f"Device '{unit.name}' does not have Zone 2")

        return await self._execute_atw_control(
            unit_id=unit_id,
            control_name="Zone 2 mode",
            control_fn=lambda unit: self._client.atw.set_mode_zone2(unit.id, mode),
            pre_check=_check_zone2,
        )

    async def async_set_dhw_temperature(self, unit_id: str, temperature: float) -> None:
        """Set DHW tank target temperature.

        Args:
            unit_id: ATW unit ID
            temperature: Target temp in Celsius (40-60°C)
        """
        return await self._execute_atw_control(
            unit_id=unit_id,
            control_name="DHW temperature",
            control_fn=lambda unit: self._client.atw.set_dhw_temperature(
                unit.id, temperature
            ),
        )

    async def async_set_forced_hot_water(self, unit_id: str, enabled: bool) -> None:
        """Enable/disable forced DHW priority mode.

        Args:
            unit_id: ATW unit ID
            enabled: True=DHW priority, False=normal
        """
        return await self._execute_atw_control(
            unit_id=unit_id,
            control_name="forced DHW",
            control_fn=lambda unit: self._client.atw.set_forced_hot_water(
                unit.id, enabled
            ),
        )

    async def async_set_standby_mode(self, unit_id: str, standby: bool) -> None:
        """Enable/disable standby mode.

        Args:
            unit_id: ATW unit ID
            standby: True=standby, False=normal
        """
        return await self._execute_atw_control(
            unit_id=unit_id,
            control_name="standby mode",
            control_fn=lambda unit: self._client.atw.set_standby_mode(unit.id, standby),
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

        async def _delayed_refresh() -> None:
            """Wait then refresh."""
            await asyncio.sleep(delay)
            _LOGGER.debug("Debounced refresh executing after %.1fs delay", delay)
            await self._async_request_refresh()

        self._refresh_debounce_task = self._hass.async_create_task(_delayed_refresh())
