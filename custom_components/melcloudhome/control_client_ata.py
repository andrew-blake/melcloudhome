"""ATA device control client for MELCloud Home integration."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from homeassistant.core import HomeAssistant

from .api.client import MELCloudHomeClient
from .api.models import AirToAirUnit
from .control_client_base import ControlClientBase

_LOGGER = logging.getLogger(__name__)


class ATAControlClient(ControlClientBase):
    """Handles ATA device control operations with retry logic and debounced refresh.

    Every accepted write is applied to the coordinator's copy of the unit, so
    an entity shows a command at once rather than one refresh later (ADR-026).
    Fetch the copy after the write, not before it: a poll
    completing mid-write replaces every unit object, and a reference taken
    earlier would update one no entity reads. Fetching afterwards favours our
    value over a poll that landed meanwhile; the next poll settles it.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        client: MELCloudHomeClient,
        execute_with_retry: Callable[
            [Callable[[], Awaitable[Any]], str], Awaitable[Any]
        ],
        get_device: Callable[[str], AirToAirUnit | None],
        async_request_refresh: Callable[[], Awaitable[None]],
        async_update_listeners: Callable[[], None],
    ) -> None:
        """Initialize ATA control client.

        Args:
            hass: Home Assistant instance
            client: MELCloud Home API client
            execute_with_retry: Coordinator's retry wrapper for API calls
            get_device: Callable to get ATA device by ID
            async_request_refresh: Callable to request coordinator refresh
            async_update_listeners: Called after each accepted write
        """
        # Initialize base class (provides shared debouncing logic)
        super().__init__(hass, async_update_listeners)

        self._client = client
        self._execute_with_retry = execute_with_retry
        self._get_device = get_device
        self._async_request_refresh = async_request_refresh

    async def async_set_power_and_mode(
        self, unit_id: str, power: bool, mode: str, fan_speed: str | None = None
    ) -> None:
        """Set power, operation mode and optionally fan speed in one API call.

        Used for every power-on that knows the mode, so the unit never sees an
        operationMode=null window, which can fault a multi-zone outdoor unit.

        `fan_speed` exists so a power-on that also sets a speed is one request.
        Sent separately they are spaced by the pacer's minimum, and a command
        arriving that close behind another to the same unit can be accepted by
        the cloud and ignored by the device; ADR-026 records the observations.
        """
        _LOGGER.info(
            "Setting power+mode%s for %s to power=%s mode=%s%s",
            "+speed" if fan_speed else "",
            unit_id[-8:],
            power,
            mode,
            f" speed={fan_speed}" if fan_speed else "",
        )
        await self._execute_with_retry(
            lambda: self._client.ata.set_power_and_mode(
                unit_id, power, mode, fan_speed
            ),
            f"set_power_and_mode({unit_id}, {power}, {mode}, {fan_speed})",
        )

        device = self._get_device(unit_id)
        if device:
            device.power = power
            device.operation_mode = mode
            if fan_speed is not None:
                device.set_fan_speed = fan_speed
            self._notify_listeners()

    async def async_set_power(
        self, unit_id: str, power: bool, fan_speed: str | None = None
    ) -> None:
        """Set power state, and optionally a fan speed, in one API call.

        Args:
            unit_id: Unit ID
            power: True=ON, False=OFF
            fan_speed: Optional fan speed to set in the same request, so a
                power-on that also sets a speed is one request rather than a
                pair the device can drop half of (ADR-026)
        """
        _LOGGER.info(
            "Setting power%s for %s to %s%s",
            "+speed" if fan_speed else "",
            unit_id[-8:],
            power,
            f" speed={fan_speed}" if fan_speed else "",
        )
        await self._execute_with_retry(
            lambda: self._client.ata.set_power(unit_id, power, fan_speed),
            f"set_power({unit_id}, {power}, {fan_speed})",
        )

        device = self._get_device(unit_id)
        if device:
            device.power = power
            if fan_speed is not None:
                device.set_fan_speed = fan_speed
            self._notify_listeners()

    async def async_set_temperature(self, unit_id: str, temperature: float) -> None:
        """Set target temperature with automatic session recovery.

        Args:
            unit_id: Unit ID
            temperature: Target temperature in Celsius
        """
        _LOGGER.info("Setting temperature for %s to %.1f°C", unit_id[-8:], temperature)
        await self._execute_with_retry(
            lambda: self._client.ata.set_temperature(unit_id, temperature),
            f"set_temperature({unit_id}, {temperature})",
        )

        device = self._get_device(unit_id)
        if device:
            device.set_temperature = temperature
            self._notify_listeners()

    async def async_set_fan_speed(self, unit_id: str, fan_speed: str) -> None:
        """Set fan speed with automatic session recovery.

        Args:
            unit_id: Unit ID
            fan_speed: Fan speed string
        """
        _LOGGER.info("Setting fan speed for %s to %s", unit_id[-8:], fan_speed)
        await self._execute_with_retry(
            lambda: self._client.ata.set_fan_speed(unit_id, fan_speed),
            f"set_fan_speed({unit_id}, {fan_speed})",
        )

        device = self._get_device(unit_id)
        if device:
            device.set_fan_speed = fan_speed
            self._notify_listeners()

    async def async_set_vane_vertical(self, unit_id: str, vertical: str) -> None:
        """Set vertical vane position with automatic session recovery.

        The horizontal axis is left untouched (sent as null). This matches the
        official MELCloud app and avoids a server-side validation quirk that
        silently drops cross-axis updates on units without horizontal vanes
        (issue #100).

        Args:
            unit_id: Unit ID
            vertical: Vertical vane position
        """
        _LOGGER.info("Setting vertical vane for %s to %s", unit_id[-8:], vertical)
        await self._execute_with_retry(
            lambda: self._client.ata.set_vane_vertical(unit_id, vertical),
            f"set_vane_vertical({unit_id}, {vertical})",
        )

        device = self._get_device(unit_id)
        if device:
            device.vane_vertical_direction = vertical
            self._notify_listeners()

    async def async_set_vane_horizontal(self, unit_id: str, horizontal: str) -> None:
        """Set horizontal vane position with automatic session recovery.

        The vertical axis is left untouched (sent as null). See
        async_set_vane_vertical for rationale (issue #100).

        Args:
            unit_id: Unit ID
            horizontal: Horizontal vane position
        """
        _LOGGER.info("Setting horizontal vane for %s to %s", unit_id[-8:], horizontal)
        await self._execute_with_retry(
            lambda: self._client.ata.set_vane_horizontal(unit_id, horizontal),
            f"set_vane_horizontal({unit_id}, {horizontal})",
        )

        device = self._get_device(unit_id)
        if device:
            device.vane_horizontal_direction = horizontal
            self._notify_listeners()
