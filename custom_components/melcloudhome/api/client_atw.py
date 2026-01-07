"""Air-to-Water (Heat Pump) control client for MELCloud Home API."""

import logging
from typing import TYPE_CHECKING, Any

from .const_atw import (
    API_ATW_CONTROL_UNIT,
    ATW_OPERATION_MODES_ZONE,
    ATW_TEMP_MAX_DHW,
    ATW_TEMP_MAX_ZONE,
    ATW_TEMP_MIN_DHW,
    ATW_TEMP_MIN_ZONE,
)

if TYPE_CHECKING:
    from .client import MELCloudHomeClient

_LOGGER = logging.getLogger(__name__)


class ATWControlClient:
    """Air-to-Water control client."""

    def __init__(self, base_client: "MELCloudHomeClient") -> None:
        """Initialize ATW control client.

        Args:
            base_client: Base MELCloudHomeClient instance for API requests
        """
        self._client = base_client

    async def _update_atw_unit(self, unit_id: str, payload: dict[str, Any]) -> None:
        """Send sparse update to ATW unit.

        Args:
            unit_id: ATW unit ID
            payload: Fields to update (others will be set to None)

        Raises:
            AuthenticationError: If not authenticated
            ApiError: If API request fails

        Note:
            API requires ALL control fields present in payload.
            Changed fields have values, unchanged fields are None.
        """
        # Build complete payload with nulls for unchanged fields
        full_payload = {
            "power": None,
            "setTankWaterTemperature": None,
            "forcedHotWaterMode": None,
            "setTemperatureZone1": None,
            "setTemperatureZone2": None,
            "operationModeZone1": None,
            "operationModeZone2": None,
            "inStandbyMode": None,
            "setHeatFlowTemperatureZone1": None,
            "setCoolFlowTemperatureZone1": None,
            "setHeatFlowTemperatureZone2": None,
            "setCoolFlowTemperatureZone2": None,
            **payload,  # Override with actual values
        }

        # Send request (returns None, follows ATA pattern)
        await self._client._api_request(
            "PUT", API_ATW_CONTROL_UNIT.format(unit_id=unit_id), json=full_payload
        )

    async def set_power(self, unit_id: str, power: bool) -> None:
        """Power entire ATW heat pump ON/OFF.

        Args:
            unit_id: ATW unit ID
            power: True=ON, False=OFF

        Raises:
            AuthenticationError: If not authenticated
            ApiError: If API request fails

        Note:
            Powers off ENTIRE system (all zones + DHW).
        """
        payload = {"power": power}
        await self._update_atw_unit(unit_id, payload)

    async def set_temperature_zone1(self, unit_id: str, temperature: float) -> None:
        """Set Zone 1 target temperature.

        Args:
            unit_id: ATW unit ID
            temperature: Target temp in Celsius (10-30°C)

        Raises:
            ValueError: If temperature out of safe range
            AuthenticationError: If not authenticated
            ApiError: If API request fails
        """
        # Validate against hardcoded safe defaults (never trust API ranges)
        if not ATW_TEMP_MIN_ZONE <= temperature <= ATW_TEMP_MAX_ZONE:
            raise ValueError(
                f"Zone temperature must be between {ATW_TEMP_MIN_ZONE} and "
                f"{ATW_TEMP_MAX_ZONE}°C, got {temperature}"
            )

        payload = {"setTemperatureZone1": temperature}
        await self._update_atw_unit(unit_id, payload)

    async def set_temperature_zone2(self, unit_id: str, temperature: float) -> None:
        """Set Zone 2 target temperature.

        Args:
            unit_id: ATW unit ID
            temperature: Target temp in Celsius (10-30°C)

        Raises:
            ValueError: If temperature out of safe range
            AuthenticationError: If not authenticated
            ApiError: If API request fails

        Note:
            Does NOT validate has_zone2 capability (coordinator's responsibility).
            API will return error if Zone 2 not available.
        """
        # Validate temperature range only (static validation)
        if not ATW_TEMP_MIN_ZONE <= temperature <= ATW_TEMP_MAX_ZONE:
            raise ValueError(
                f"Zone temperature must be between {ATW_TEMP_MIN_ZONE} and "
                f"{ATW_TEMP_MAX_ZONE}°C, got {temperature}"
            )

        payload = {"setTemperatureZone2": temperature}
        await self._update_atw_unit(unit_id, payload)

    async def set_mode_zone1(self, unit_id: str, mode: str) -> None:
        """Set Zone 1 heating strategy.

        Args:
            unit_id: ATW unit ID
            mode: One of ATW_OPERATION_MODES_ZONE:
                - "HeatRoomTemperature" (thermostat control)
                - "HeatFlowTemperature" (direct flow temp)
                - "HeatCurve" (weather compensation)

        Raises:
            ValueError: If mode not in ATW_OPERATION_MODES_ZONE
            AuthenticationError: If not authenticated
            ApiError: If API request fails
        """
        # Validate mode using constants
        if mode not in ATW_OPERATION_MODES_ZONE:
            raise ValueError(
                f"Zone mode must be one of {ATW_OPERATION_MODES_ZONE}, got {mode}"
            )

        payload = {"operationModeZone1": mode}
        await self._update_atw_unit(unit_id, payload)

    async def set_mode_zone2(self, unit_id: str, mode: str) -> None:
        """Set Zone 2 heating strategy.

        Args:
            unit_id: ATW unit ID
            mode: One of ATW_OPERATION_MODES_ZONE

        Raises:
            ValueError: If mode not in ATW_OPERATION_MODES_ZONE
            AuthenticationError: If not authenticated
            ApiError: If API request fails

        Note:
            Does NOT validate has_zone2 capability (coordinator's responsibility).
        """
        if mode not in ATW_OPERATION_MODES_ZONE:
            raise ValueError(
                f"Zone mode must be one of {ATW_OPERATION_MODES_ZONE}, got {mode}"
            )

        payload = {"operationModeZone2": mode}
        await self._update_atw_unit(unit_id, payload)

    async def set_dhw_temperature(self, unit_id: str, temperature: float) -> None:
        """Set DHW tank target temperature.

        Args:
            unit_id: ATW unit ID
            temperature: Target temp in Celsius (40-60°C)

        Raises:
            ValueError: If temperature out of safe range
            AuthenticationError: If not authenticated
            ApiError: If API request fails
        """
        # Validate against hardcoded safe DHW range
        if not ATW_TEMP_MIN_DHW <= temperature <= ATW_TEMP_MAX_DHW:
            raise ValueError(
                f"DHW temperature must be between {ATW_TEMP_MIN_DHW} and "
                f"{ATW_TEMP_MAX_DHW}°C, got {temperature}"
            )

        payload = {"setTankWaterTemperature": temperature}
        await self._update_atw_unit(unit_id, payload)

    async def set_forced_hot_water(self, unit_id: str, enabled: bool) -> None:
        """Enable/disable forced DHW priority mode.

        Args:
            unit_id: ATW unit ID
            enabled: True=DHW priority (suspends zone heating)
                    False=Normal balanced operation

        Raises:
            AuthenticationError: If not authenticated
            ApiError: If API request fails

        Note:
            When enabled, 3-way valve prioritizes DHW tank heating.
            Zone heating is suspended until DHW reaches target.
        """
        payload = {"forcedHotWaterMode": enabled}
        await self._update_atw_unit(unit_id, payload)

    async def set_standby_mode(self, unit_id: str, standby: bool) -> None:
        """Enable/disable standby mode.

        Args:
            unit_id: ATW unit ID
            standby: True=standby (frost protection only)
                    False=normal operation

        Raises:
            AuthenticationError: If not authenticated
            ApiError: If API request fails
        """
        payload = {"inStandbyMode": standby}
        await self._update_atw_unit(unit_id, payload)
