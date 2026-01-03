"""Data models for MELCloud Home API."""

import logging
from dataclasses import dataclass, field
from typing import Any

_LOGGER = logging.getLogger(__name__)


@dataclass
class DeviceCapabilities:
    """Device capability flags and limits."""

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
    def from_dict(cls, data: dict[str, Any]) -> "DeviceCapabilities":
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
class Schedule:
    """Schedule entry for automated device control."""

    id: str
    days: list[int]
    time: str
    power: bool
    operation_mode: int
    set_point: float | None = None
    vane_vertical_direction: int | None = None
    vane_horizontal_direction: int | None = None
    set_fan_speed: int | None = None
    enabled: bool | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Schedule":
        """Create from API response dict."""
        return cls(
            id=data["id"],
            days=data["days"],
            time=data["time"],
            power=data["power"],
            operation_mode=data["operationMode"],
            set_point=data.get("setPoint"),
            vane_vertical_direction=data.get("vaneVerticalDirection"),
            vane_horizontal_direction=data.get("vaneHorizontalDirection"),
            set_fan_speed=data.get("setFanSpeed"),
            enabled=data.get("enabled"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to API request dict."""
        return {
            "id": self.id,
            "days": self.days,
            "time": self.time,
            "power": self.power,
            "operationMode": self.operation_mode,
            "setPoint": self.set_point,
            "vaneVerticalDirection": self.vane_vertical_direction,
            "vaneHorizontalDirection": self.vane_horizontal_direction,
            "setFanSpeed": self.set_fan_speed,
            "enabled": self.enabled,
        }


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
    capabilities: DeviceCapabilities
    schedule: list[Schedule] = field(default_factory=list)
    schedule_enabled: bool = False
    # Energy monitoring (set by coordinator, not from main API)
    energy_consumed: float | None = None  # kWh

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AirToAirUnit":
        """Create from API response dict.

        The API returns device state as a list of name-value pairs in the 'settings' array.
        Example: [{"name": "Power", "value": "False"}, {"name": "SetTemperature", "value": "20"}, ...]
        """
        capabilities_data = data.get("capabilities", {})
        capabilities = DeviceCapabilities.from_dict(capabilities_data)

        schedules_data = data.get("schedule", [])
        schedules = [Schedule.from_dict(s) for s in schedules_data]

        # Parse settings array into dict for easy access
        settings_list = data.get("settings", [])
        settings = {item["name"]: item["value"] for item in settings_list}

        # Helper to parse boolean from string
        def parse_bool(value: str | bool | None) -> bool:
            if isinstance(value, bool):
                return value
            if value is None:
                return False
            return str(value).lower() == "true"

        # Helper to parse float from string
        def parse_float(value: str | float | None) -> float | None:
            if value is None or value == "":
                return None
            try:
                return float(value)
            except (ValueError, TypeError):
                return None

        # Helper to normalize fan speed (API returns "0"-"5", we use "Auto", "One"-"Five")
        def normalize_fan_speed(value: str | None) -> str | None:
            if value is None:
                return None
            # Map numeric strings to word strings
            fan_speed_map = {
                "0": "Auto",
                "1": "One",
                "2": "Two",
                "3": "Three",
                "4": "Four",
                "5": "Five",
            }
            # If already a word string, return as-is
            if value in fan_speed_map.values():
                return value
            # Otherwise map from numeric string
            return fan_speed_map.get(value, value)

        # Helper to normalize vertical vane direction (API returns numeric strings)
        def normalize_vertical_vane(value: str | None) -> str | None:
            if value is None:
                return None
            # Map numeric strings to word strings
            vane_map = {
                "0": "Auto",
                "7": "Swing",
                "1": "One",
                "2": "Two",
                "3": "Three",
                "4": "Four",
                "5": "Five",
            }
            # If already a word string, return as-is
            if value in vane_map.values():
                return value
            # Otherwise map from numeric string
            return vane_map.get(value, value)

        # Helper to normalize horizontal vane direction
        # API uses British-spelled named positions
        def normalize_horizontal_vane(value: str | None) -> str | None:
            if value is None:
                return None
            # Official API format (British spelling) - these are correct
            valid_positions = {
                "Auto",
                "Swing",
                "Left",
                "LeftCentre",
                "Centre",
                "RightCentre",
                "Right",
            }
            if value in valid_positions:
                return value
            # Handle American spelling variants
            american_to_british = {
                "CenterLeft": "LeftCentre",
                "Center": "Centre",
                "CenterRight": "RightCentre",
            }
            if value in american_to_british:
                return american_to_british[value]
            # Return as-is (unknown value)
            return value

        return cls(
            id=data["id"],
            name=data.get("givenDisplayName", "Unknown"),
            power=parse_bool(settings.get("Power")),
            operation_mode=settings.get("OperationMode", "Heat"),
            set_temperature=parse_float(settings.get("SetTemperature")),
            room_temperature=parse_float(settings.get("RoomTemperature")),
            set_fan_speed=normalize_fan_speed(settings.get("SetFanSpeed")),
            vane_vertical_direction=normalize_vertical_vane(
                settings.get("VaneVerticalDirection")
            ),
            vane_horizontal_direction=normalize_horizontal_vane(
                settings.get("VaneHorizontalDirection")
            ),
            in_standby_mode=parse_bool(settings.get("InStandbyMode")),
            is_in_error=parse_bool(settings.get("IsInError")),
            rssi=data.get("rssi"),
            capabilities=capabilities,
            schedule=schedules,
            schedule_enabled=data.get("scheduleEnabled", False),
        )


@dataclass
class Building:
    """Building containing units."""

    id: str
    name: str
    air_to_air_units: list[AirToAirUnit] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Building":
        """Create from API response dict."""
        units_data = data.get("airToAirUnits", [])
        units = [AirToAirUnit.from_dict(u) for u in units_data]

        return cls(
            id=data["id"],
            name=data.get("name", "Unknown"),
            air_to_air_units=units,
        )


@dataclass
class UserContext:
    """User context containing all buildings and devices."""

    buildings: list[Building] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UserContext":
        """Create from API response dict."""
        buildings_data = data.get("buildings", [])
        buildings = [Building.from_dict(b) for b in buildings_data]

        return cls(buildings=buildings)

    def get_all_units(self) -> list[AirToAirUnit]:
        """Get all units across all buildings."""
        units = []
        for building in self.buildings:
            units.extend(building.air_to_air_units)
        return units

    def get_unit_by_id(self, unit_id: str) -> AirToAirUnit | None:
        """Get unit by ID."""
        for unit in self.get_all_units():
            if unit.id == unit_id:
                return unit
        return None
