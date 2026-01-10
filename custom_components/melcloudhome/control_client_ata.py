"""ATA device control client for MELCloud Home integration."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant

from .api.client import MELCloudHomeClient
from .api.models import AirToAirUnit
from .control_client_base import ControlClientBase

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)


class ATAControlClient(ControlClientBase):
    """Handles ATA device control operations with retry logic and debounced refresh."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: MELCloudHomeClient,
        execute_with_retry: Callable[
            [Callable[[], Awaitable[Any]], str], Awaitable[Any]
        ],
        get_device: Callable[[str], AirToAirUnit | None],
        async_request_refresh: Callable[[], Awaitable[None]],
    ) -> None:
        """Initialize ATA control client.

        Args:
            hass: Home Assistant instance
            client: MELCloud Home API client
            execute_with_retry: Coordinator's retry wrapper for API calls
            get_device: Callable to get ATA device by ID
            async_request_refresh: Callable to request coordinator refresh
        """
        # Initialize base class (provides shared debouncing logic)
        super().__init__(hass)

        self._client = client
        self._execute_with_retry = execute_with_retry
        self._get_device = get_device
        self._async_request_refresh = async_request_refresh

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
