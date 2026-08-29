"""Air-to-Air (A/C) data models for MELCloud Home API."""

import logging
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Any

from .const_ata import (
    ACTUAL_FAN_SPEEDS,
    FAN_SPEED_NUMERIC_TO_WORD,
    OPERATION_MODE_HEAT,
    VANE_HORIZONTAL_AMERICAN_TO_BRITISH,
    VANE_HORIZONTAL_DIRECTIONS,
    VANE_NUMERIC_TO_WORD,
)
from .parsing import (
    Reading,
    parse_bool as _parse_bool,
    parse_float as _parse_float,
    strip_line_breaks,
)

_LOGGER = logging.getLogger(__name__)


@lru_cache(maxsize=20)
def _warn_unknown_fan_speed(speed: str, unit_name: str) -> None:
    """Log an unrecognised fan speed, once per unit that reports it.

    Cached for the side effect rather than the return value: `from_dict` runs on
    every poll and every socket-triggered refresh, so without this a single
    unrecognised value would write a warning every few seconds. `maxsize` bounds
    the record and evicts the oldest, so a unit reporting varying rubbish cannot
    grow it without limit or silence it permanently.
    """
    _LOGGER.warning(
        "%s reported the fan speed %s, which this integration does not "
        "recognise, so its actual fan speed sensor will show as unknown",
        unit_name,
        strip_line_breaks(speed),
    )


def _parse_actual_fan_speed(value: object, unit_name: str) -> str | None:
    """Return a recognised ActualFanSpeed word, or None having warned once.

    The sensor built on this field is a device_class=ENUM, and HA raises on a
    state write outside an ENUM's options. Returning None leaves the sensor
    reading `unknown`, degrading one sensor rather than failing the write.

    Numeric forms are rejected rather than mapped. The socket sends this field
    numerically but discards values before they reach here, and every captured
    /context serves words, so a numeric map would handle a variation never seen
    on this path and would consume the warning that is how we would find out.
    """
    if value is None or value == "":
        return None
    text = str(value)
    if text in ACTUAL_FAN_SPEEDS:
        return text
    _warn_unknown_fan_speed(text, unit_name)
    return None


@dataclass
class ProtectionModeState:
    """Shared shape for frost/overheat protection and holiday mode.

    Sourced from GET /context, where these objects are null until a mode has
    ever been configured on a unit, then persist even when disabled.
    """

    enabled: bool
    active: bool
    min: float | None = None
    max: float | None = None
    start_date: str | None = None
    end_date: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ProtectionModeState | None":
        """Create from an API frostProtection/overheatProtection/holidayMode object."""
        if not data:
            return None
        return cls(
            enabled=_parse_bool(data.get("enabled")),
            active=_parse_bool(data.get("active")),
            min=_parse_float(data.get("min")),
            max=_parse_float(data.get("max")),
            start_date=data.get("startDate"),
            end_date=data.get("endDate"),
        )


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
    # What the unit is running, as opposed to set_fan_speed's request.
    # Reports "Off", never "Auto". Lags by the unit's upload interval.
    actual_fan_speed: str | None
    vane_vertical_direction: str | None
    vane_horizontal_direction: str | None
    in_standby_mode: bool
    is_in_error: bool
    error_code: str | None
    rssi: int | None
    time_zone: str | None  # IANA name from /context, e.g. "Europe/Stockholm"
    capabilities: AirToAirCapabilities
    # Energy monitoring (set by coordinator, not from main API)
    energy_consumed: float | None = None  # kWh
    # Outdoor temperature monitoring (set by coordinator via trendsummary API).
    # Idle units stop uploading, so recorded_at can lag hours behind (issue #171)
    outdoor_temp_reading: Reading | None = None
    has_outdoor_temp_sensor: bool = False  # Runtime discovery flag
    # Set by the coordinator when the outdoor-temp poll itself raised (e.g. a
    # real HTTP error), distinct from a successful poll finding no genuine
    # reading. Cleared on the next successful poll. Diagnostic-only signal
    # for telling "endpoint failing for this unit" apart from "no data yet".
    outdoor_temp_last_error: str | None = None
    outdoor_temp_last_error_at: datetime | None = None  # UTC-aware
    # When a poll last completed, whatever it found (UTC-aware). Separates a
    # stale endpoint from a stalled poll when read against recorded_at.
    outdoor_temp_last_poll_at: datetime | None = None
    # Protection modes (from GET /context; null until ever configured on this unit)
    frost_protection: ProtectionModeState | None = None
    overheat_protection: ProtectionModeState | None = None
    holiday_mode: ProtectionModeState | None = None

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

        # Parse error code - convert empty string to None
        error_code_value = settings.get("ErrorCode", "")
        error_code = error_code_value if error_code_value else None

        name = strip_line_breaks(data.get("givenDisplayName") or "Unknown")

        return cls(
            id=data["id"],
            name=name,
            power=_parse_bool(settings.get("Power")),
            operation_mode=settings.get("OperationMode", OPERATION_MODE_HEAT),
            set_temperature=_parse_float(settings.get("SetTemperature")),
            room_temperature=_parse_float(settings.get("RoomTemperature")),
            set_fan_speed=normalize_fan_speed(settings.get("SetFanSpeed")),
            # Not normalize_fan_speed: that maps "0" to "Auto", which a running
            # unit cannot be. Anything unrecognised becomes None here, so the
            # ENUM sensor reads `unknown` rather than raising on the state write.
            actual_fan_speed=_parse_actual_fan_speed(
                settings.get("ActualFanSpeed"), name
            ),
            vane_vertical_direction=normalize_vertical_vane(
                settings.get("VaneVerticalDirection")
            ),
            vane_horizontal_direction=normalize_horizontal_vane(
                settings.get("VaneHorizontalDirection")
            ),
            in_standby_mode=_parse_bool(settings.get("InStandbyMode")),
            is_in_error=_parse_bool(settings.get("IsInError")),
            error_code=error_code,
            rssi=data.get("rssi"),
            time_zone=data.get("timeZone"),
            capabilities=capabilities,
            frost_protection=ProtectionModeState.from_dict(data.get("frostProtection")),
            overheat_protection=ProtectionModeState.from_dict(
                data.get("overheatProtection")
            ),
            holiday_mode=ProtectionModeState.from_dict(data.get("holidayMode")),
        )
