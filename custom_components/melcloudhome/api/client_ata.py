"""Air-to-Air (A/C) control client for MELCloud Home API."""

from typing import TYPE_CHECKING, Any

from .coalescing import WriteCoalescer
from .const_ata import (
    API_CONTROL_UNIT,
    FAN_SPEEDS,
    OPERATION_MODES,
    TEMP_MAX_HEAT,
    TEMP_MIN_HEAT,
    VANE_HORIZONTAL_DIRECTIONS,
    VANE_VERTICAL_DIRECTIONS,
)

if TYPE_CHECKING:
    from .client import MELCloudHomeClient


class ATAControlClient:
    """Air-to-Air control client."""

    def __init__(self, base_client: "MELCloudHomeClient") -> None:
        """Initialize ATA control client.

        Args:
            base_client: Base MELCloudHomeClient instance for API requests
        """
        self._client = base_client
        self._coalescer = WriteCoalescer(self._send_control)

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

    async def _update_ata_unit(self, unit_id: str, **updates: Any) -> None:
        """Send a sparse control update, merged with any arriving alongside it.

        Callers pass only the fields they are setting. Keeping callers sparse is
        what lets two writes arriving together be merged without one write's
        nulls erasing the other's values.
        """
        await self._coalescer.submit(unit_id, updates)

    async def _send_control(self, unit_id: str, updates: dict[str, Any]) -> None:
        """Send one unit's collected fields as a single request."""
        payload = self._build_ata_control_payload(**updates)
        await self._client._api_request(
            "PUT",
            API_CONTROL_UNIT.format(unit_id=unit_id),
            json=payload,
        )

    def _validate_mode(self, mode: str) -> None:
        """Raise ValueError if mode is not a valid OPERATION_MODES entry."""
        valid_modes = set(OPERATION_MODES)
        if mode not in valid_modes:
            raise ValueError(f"Invalid mode: {mode}. Must be one of {valid_modes}")

    def _validate_fan_speed(self, speed: str) -> None:
        """Raise ValueError if speed is not a valid FAN_SPEEDS entry.

        The server takes a combination of fields and has been seen to accept one
        it cannot honour, answering 200 and silently dropping the part it did not
        like (issue #100). A bad speed riding along with a power-on would fail
        that way rather than being refused, so it is refused here instead.
        """
        valid_speeds = set(FAN_SPEEDS)
        if speed not in valid_speeds:
            raise ValueError(
                f"Invalid fan speed: {speed}. Must be one of {valid_speeds}"
            )

    async def set_power(
        self, unit_id: str, power: bool, fan_speed: str | None = None
    ) -> None:
        """
        Turn device on or off.

        Args:
            unit_id: Device ID (UUID)
            power: True to turn on, False to turn off
            fan_speed: Optional fan speed to set in the same request

        Raises:
            AuthenticationError: If not authenticated
            ApiError: If API request fails
            ValueError: If fan_speed is invalid
        """
        if fan_speed is not None:
            self._validate_fan_speed(fan_speed)

        # A unit reporting no mode to preserve is powered on through here rather
        # than set_power_and_mode, and it needs the speed folded in for the same
        # reason: two requests to one unit are spaced by the pacer's minimum, and
        # a command that close behind another can be accepted by the cloud and
        # ignored by the device (ADR-026).
        extra = {} if fan_speed is None else {"setFanSpeed": fan_speed}
        await self._update_ata_unit(unit_id, power=power, **extra)

    async def set_power_and_mode(
        self, unit_id: str, power: bool, mode: str, fan_speed: str | None = None
    ) -> None:
        """
        Turn device on/off and set operation mode in a single atomic API call.

        Sending power and mode together avoids the window where a power-on with
        operationMode=null can be misinterpreted by the outdoor unit as a mode
        conflict, which causes fault/flashing on multi-zone systems.

        Args:
            unit_id: Device ID (UUID)
            power: True to turn on, False to turn off
            mode: Operation mode - "Heat", "Cool", "Automatic", "Dry", or "Fan"
            fan_speed: Optional fan speed to set in the same request

        Raises:
            AuthenticationError: If not authenticated
            ApiError: If API request fails
            ValueError: If mode is invalid
        """
        self._validate_mode(mode)
        if fan_speed is not None:
            self._validate_fan_speed(fan_speed)

        # Carrying the speed here is what keeps a power-on and a speed change one
        # request instead of two. Two requests to one unit are spaced by the
        # pacer's minimum, and a command that close behind another can be
        # accepted by the cloud and ignored by the device; see ADR-026.
        extra = {} if fan_speed is None else {"setFanSpeed": fan_speed}
        await self._update_ata_unit(unit_id, power=power, operationMode=mode, **extra)

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

        await self._update_ata_unit(unit_id, setTemperature=temperature)

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
        self._validate_mode(mode)

        await self._update_ata_unit(unit_id, operationMode=mode)

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
        self._validate_fan_speed(speed)

        await self._update_ata_unit(unit_id, setFanSpeed=speed)

    async def set_vane_vertical(self, unit_id: str, vertical: str) -> None:
        """
        Set vertical vane direction only. Sends null for the horizontal axis.

        Decoupling the two axes matches the official MELCloud app's behavior
        and avoids server-side cross-axis validation silently dropping the
        request on units without horizontal vanes (issue #100).

        Args:
            unit_id: Device ID (UUID)
            vertical: Vertical direction - "Auto", "Swing", "One", "Two", "Three",
                      "Four", or "Five"

        Raises:
            AuthenticationError: If not authenticated
            ApiError: If API request fails
            ValueError: If vertical is invalid
        """
        if vertical not in set(VANE_VERTICAL_DIRECTIONS):
            raise ValueError(
                f"Invalid vertical direction: {vertical}. "
                f"Must be one of {set(VANE_VERTICAL_DIRECTIONS)}"
            )

        await self._update_ata_unit(unit_id, vaneVerticalDirection=vertical)

    async def set_vane_horizontal(self, unit_id: str, horizontal: str) -> None:
        """
        Set horizontal vane direction only. Sends null for the vertical axis.

        See set_vane_vertical for rationale (issue #100).

        Args:
            unit_id: Device ID (UUID)
            horizontal: Horizontal direction - "Auto", "Swing", "Left", "LeftCentre",
                        "Centre", "RightCentre", or "Right" (British spelling)

        Raises:
            AuthenticationError: If not authenticated
            ApiError: If API request fails
            ValueError: If horizontal is invalid
        """
        if horizontal not in set(VANE_HORIZONTAL_DIRECTIONS):
            raise ValueError(
                f"Invalid horizontal direction: {horizontal}. "
                f"Must be one of {set(VANE_HORIZONTAL_DIRECTIONS)}"
            )

        await self._update_ata_unit(unit_id, vaneHorizontalDirection=horizontal)
