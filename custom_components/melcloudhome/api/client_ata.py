"""Air-to-Air (A/C) control client for MELCloud Home API."""

import logging
from typing import TYPE_CHECKING, Any

from .const_ata import (
    API_CONTROL_UNIT,
    FAN_SPEEDS,
    OPERATION_MODES,
    TEMP_MAX_HEAT,
    TEMP_MIN_HEAT,
    VANE_HORIZONTAL_DIRECTIONS,
    VANE_VERTICAL_DIRECTIONS,
    VANE_WORD_TO_NUMERIC,
)

if TYPE_CHECKING:
    from .client import MELCloudHomeClient

_LOGGER = logging.getLogger(__name__)


class ATAControlClient:
    """Air-to-Air control client."""

    def __init__(self, base_client: "MELCloudHomeClient") -> None:
        """Initialize ATA control client.

        Args:
            base_client: Base MELCloudHomeClient instance for API requests
        """
        self._client = base_client

    def _build_ata_control_payload(self, **updates: Any) -> dict[str, Any]:
        """Build ATA control payload with null defaults.

        The API requires ALL control fields to be present in every request.
        Fields being updated should have values, all others should be None.

        Args:
            **updates: Fields to update (e.g., power=True, setTemperature=22.5)

        Returns:
            Complete payload dictionary for ATA control endpoint

        Example:
            >>> self._build_ata_control_payload(power=True)
            {"power": True, "operationMode": None, ...}
        """
        payload = {
            "power": None,
            "operationMode": None,
            "setFanSpeed": None,
            "vaneHorizontalDirection": None,
            "vaneVerticalDirection": None,
            "setTemperature": None,
            "temperatureIncrementOverride": None,
            "inStandbyMode": None,
        }
        payload.update(updates)
        return payload

    async def set_power(self, unit_id: str, power: bool) -> None:
        """
        Turn device on or off.

        Args:
            unit_id: Device ID (UUID)
            power: True to turn on, False to turn off

        Raises:
            AuthenticationError: If not authenticated
            ApiError: If API request fails
        """
        payload = self._build_ata_control_payload(power=power)

        await self._client._api_request(
            "PUT",
            API_CONTROL_UNIT.format(unit_id=unit_id),
            json=payload,
        )

    async def set_temperature(self, unit_id: str, temperature: float) -> None:
        """
        Set target temperature.

        Args:
            unit_id: Device ID (UUID)
            temperature: Target temperature in Celsius (10.0-31.0)

        Raises:
            AuthenticationError: If not authenticated
            ApiError: If API request fails
            ValueError: If temperature is out of range

        Note:
            Temperature step validation removed - climate entity handles this
            via target_temperature_step based on hasHalfDegreeIncrements capability.
        """
        if not TEMP_MIN_HEAT <= temperature <= TEMP_MAX_HEAT:
            raise ValueError(
                f"Temperature must be between {TEMP_MIN_HEAT} and {TEMP_MAX_HEAT}°C"
            )

        payload = self._build_ata_control_payload(setTemperature=temperature)

        await self._client._api_request(
            "PUT",
            API_CONTROL_UNIT.format(unit_id=unit_id),
            json=payload,
        )

    async def set_mode(self, unit_id: str, mode: str) -> None:
        """
        Set operation mode.

        Args:
            unit_id: Device ID (UUID)
            mode: Operation mode - "Heat", "Cool", "Automatic", "Dry", or "Fan"

        Raises:
            AuthenticationError: If not authenticated
            ApiError: If API request fails
            ValueError: If mode is invalid
        """
        valid_modes = set(OPERATION_MODES)
        if mode not in valid_modes:
            raise ValueError(f"Invalid mode: {mode}. Must be one of {valid_modes}")

        payload = self._build_ata_control_payload(operationMode=mode)

        await self._client._api_request(
            "PUT",
            API_CONTROL_UNIT.format(unit_id=unit_id),
            json=payload,
        )

    async def set_fan_speed(self, unit_id: str, speed: str) -> None:
        """
        Set fan speed.

        Args:
            unit_id: Device ID (UUID)
            speed: Fan speed - "Auto", "One", "Two", "Three", "Four", or "Five"

        Raises:
            AuthenticationError: If not authenticated
            ApiError: If API request fails
            ValueError: If speed is invalid
        """
        valid_speeds = set(FAN_SPEEDS)
        if speed not in valid_speeds:
            raise ValueError(
                f"Invalid fan speed: {speed}. Must be one of {valid_speeds}"
            )

        payload = self._build_ata_control_payload(setFanSpeed=speed)

        await self._client._api_request(
            "PUT",
            API_CONTROL_UNIT.format(unit_id=unit_id),
            json=payload,
        )

    async def set_vanes(self, unit_id: str, vertical: str, horizontal: str) -> None:
        """
        Set vane directions.

        Args:
            unit_id: Device ID (UUID)
            vertical: Vertical direction - "Auto", "Swing", "One", "Two", "Three",
                      "Four", or "Five"
            horizontal: Horizontal direction - "Auto", "Swing", "Left", "LeftCentre",
                        "Centre", "RightCentre", or "Right" (British spelling)

        Raises:
            AuthenticationError: If not authenticated
            ApiError: If API request fails
            ValueError: If vertical or horizontal is invalid
        """
        valid_vertical = set(VANE_VERTICAL_DIRECTIONS)
        # Horizontal uses British-spelled named positions (official API format)
        valid_horizontal = set(VANE_HORIZONTAL_DIRECTIONS)

        if vertical not in valid_vertical:
            raise ValueError(
                f"Invalid vertical direction: {vertical}. "
                f"Must be one of {valid_vertical}"
            )

        if horizontal not in valid_horizontal:
            raise ValueError(
                f"Invalid horizontal direction: {horizontal}. "
                f"Must be one of {valid_horizontal}"
            )

        # Denormalize VERTICAL vane direction: convert word strings back to numeric
        # strings that the API expects (API returns "0", "1", etc. which we normalize
        # to "Auto", "One", etc. for HA, but need to convert back when sending)
        vertical_numeric = VANE_WORD_TO_NUMERIC.get(vertical, vertical)
        # Horizontal uses named strings (British spelling) - send as-is
        horizontal_string = horizontal

        payload = self._build_ata_control_payload(
            vaneVerticalDirection=vertical_numeric,
            vaneHorizontalDirection=horizontal_string,
        )

        await self._client._api_request(
            "PUT",
            API_CONTROL_UNIT.format(unit_id=unit_id),
            json=payload,
        )
