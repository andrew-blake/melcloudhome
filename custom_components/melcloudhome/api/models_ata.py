"""Air-to-Air (A/C) data models for MELCloud Home API."""

import logging
from dataclasses import dataclass
from typing import Any

from .const_ata import (
    FAN_SPEED_NUMERIC_TO_WORD,
    OPERATION_MODE_HEAT,
    VANE_HORIZONTAL_AMERICAN_TO_BRITISH,
    VANE_HORIZONTAL_DIRECTIONS,
    VANE_NUMERIC_TO_WORD,
)
from .parsing import (
    parse_bool as _parse_bool,
    parse_float as _parse_float,
)

_LOGGER = logging.getLogger(__name__)


# ==============================================================================
# Air-to-Air (A/C) Models
# ==============================================================================


@dataclass
class AirToAirCapabilities:
    """Air-to-Air device capability flags and limits."""

    number_of_fan_speeds: int = 5
    min_temp_heat: float = 10.0
    max_temp_heat: float = 31.0
    min_temp_cool_dry: float = 16.0
    max_temp_cool_dry: float = 31.0
    min_temp_automatic: float = 16.0
    max_temp_automatic: float = 31.0
    has_half_degree_increments: bool = True
    has_extended_temperature_range: bool = True
    has_automatic_fan_speed: bool = True
    has_swing: bool = True
    has_air_direction: bool = True
    has_cool_operation_mode: bool = True
    has_heat_operation_mode: bool = True
    has_auto_operation_mode: bool = True
    has_dry_operation_mode: bool = True
    has_standby: bool = False
    has_demand_side_control: bool = False
    supports_wide_vane: bool = False
    has_energy_consumed_meter: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AirToAirCapabilities":
        """Create from API response dict."""
        if not data:
            return cls()

        # Convert camelCase keys to snake_case
        return cls(
            number_of_fan_speeds=data.get("numberOfFanSpeeds", 5),
            min_temp_heat=data.get("minTempHeat", 10.0),
            max_temp_heat=data.get("maxTempHeat", 31.0),
            min_temp_cool_dry=data.get("minTempCoolDry", 16.0),
            max_temp_cool_dry=data.get("maxTempCoolDry", 31.0),
            min_temp_automatic=data.get("minTempAutomatic", 16.0),
            max_temp_automatic=data.get("maxTempAutomatic", 31.0),
            has_half_degree_increments=data.get("hasHalfDegreeIncrements", True),
            has_extended_temperature_range=data.get(
                "hasExtendedTemperatureRange", True
            ),
            has_automatic_fan_speed=data.get("hasAutomaticFanSpeed", True),
            has_swing=data.get("hasSwing", True),
            has_air_direction=data.get("hasAirDirection", True),
            has_cool_operation_mode=data.get("hasCoolOperationMode", True),
            has_heat_operation_mode=data.get("hasHeatOperationMode", True),
            has_auto_operation_mode=data.get("hasAutoOperationMode", True),
            has_dry_operation_mode=data.get("hasDryOperationMode", True),
            has_standby=data.get("hasStandby", False),
            has_demand_side_control=data.get("hasDemandSideControl", False),
            supports_wide_vane=data.get("supportsWideVane", False),
            has_energy_consumed_meter=data.get("hasEnergyConsumedMeter", False),
        )


@dataclass
class AirToAirUnit:
    """Air-to-air unit device."""

    id: str
    name: str
    power: bool
    operation_mode: str
    set_temperature: float | None
    room_temperature: float | None
    set_fan_speed: str | None
    vane_vertical_direction: str | None
    vane_horizontal_direction: str | None
    in_standby_mode: bool
    is_in_error: bool
    rssi: int | None
    capabilities: AirToAirCapabilities
    # Energy monitoring (set by coordinator, not from main API)
    energy_consumed: float | None = None  # kWh
    # Outdoor temperature monitoring (set by coordinator via trendsummary API)
    outdoor_temperature: float | None = None  # °C
    has_outdoor_temp_sensor: bool = False  # Runtime discovery flag

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AirToAirUnit":
        """Create from API response dict.

        The API returns device state as a list of name-value pairs in the 'settings' array.
        Example: [{"name": "Power", "value": "False"}, {"name": "SetTemperature", "value": "20"}, ...]
        """
        capabilities_data = data.get("capabilities", {})
        capabilities = AirToAirCapabilities.from_dict(capabilities_data)

        # Parse settings array into dict for easy access
        settings_list = data.get("settings", [])
        settings = {item["name"]: item["value"] for item in settings_list}

        # Helper to normalize fan speed (API returns "0"-"5", we use "Auto", "One"-"Five")
        def normalize_fan_speed(value: str | None) -> str | None:
            if value is None:
                return None
            # If already a word string, return as-is
            if value in FAN_SPEED_NUMERIC_TO_WORD.values():
                return value
            # Otherwise map from numeric string
            return FAN_SPEED_NUMERIC_TO_WORD.get(value, value)

        # Helper to normalize vertical vane direction (API returns numeric strings)
        def normalize_vertical_vane(value: str | None) -> str | None:
            if value is None:
                return None
            # If already a word string, return as-is
            if value in VANE_NUMERIC_TO_WORD.values():
                return value
            # Otherwise map from numeric string
            return VANE_NUMERIC_TO_WORD.get(value, value)

        # Helper to normalize horizontal vane direction
        # API uses British-spelled named positions
        def normalize_horizontal_vane(value: str | None) -> str | None:
            if value is None:
                return None
            # Official API format (British spelling) - these are correct
            if value in VANE_HORIZONTAL_DIRECTIONS:
                return value
            # Handle American spelling variants
            if value in VANE_HORIZONTAL_AMERICAN_TO_BRITISH:
                return VANE_HORIZONTAL_AMERICAN_TO_BRITISH[value]
            # Return as-is (unknown value)
            return value

        return cls(
            id=data["id"],
            name=data.get("givenDisplayName", "Unknown"),
            power=_parse_bool(settings.get("Power")),
            operation_mode=settings.get("OperationMode", OPERATION_MODE_HEAT),
            set_temperature=_parse_float(settings.get("SetTemperature")),
            room_temperature=_parse_float(settings.get("RoomTemperature")),
            set_fan_speed=normalize_fan_speed(settings.get("SetFanSpeed")),
            vane_vertical_direction=normalize_vertical_vane(
                settings.get("VaneVerticalDirection")
            ),
            vane_horizontal_direction=normalize_horizontal_vane(
                settings.get("VaneHorizontalDirection")
            ),
            in_standby_mode=_parse_bool(settings.get("InStandbyMode")),
            is_in_error=_parse_bool(settings.get("IsInError")),
            rssi=data.get("rssi"),
            capabilities=capabilities,
        )
