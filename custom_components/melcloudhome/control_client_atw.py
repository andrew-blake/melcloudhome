"""ATW device control client for MELCloud Home integration."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .api.client import MELCloudHomeClient
from .api.models import AirToWaterUnit
from .control_client_base import ControlClientBase

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)


class ATWControlClient(ControlClientBase):
    """Handles ATW device control operations with retry logic and debounced refresh."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: MELCloudHomeClient,
        execute_with_retry: Callable[
            [Callable[[], Awaitable[Any]], str], Awaitable[Any]
        ],
        get_atw_device: Callable[[str], AirToWaterUnit | None],
        async_request_refresh: Callable[[], Awaitable[None]],
    ) -> None:
        """Initialize ATW control client.

        Args:
            hass: Home Assistant instance
            client: MELCloud Home API client
            execute_with_retry: Coordinator's retry wrapper for API calls
            get_atw_device: Callable to get ATW device by ID
            async_request_refresh: Callable to request coordinator refresh
        """
        # Initialize base class (provides shared debouncing logic)
        super().__init__(hass)

        self._client = client
        self._execute_with_retry = execute_with_retry
        self._get_atw_device = get_atw_device
        self._async_request_refresh = async_request_refresh

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
