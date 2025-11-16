"""Data models for MELCloud Home API."""

from dataclasses import dataclass, field
from typing import Any


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
    capabilities: DeviceCapabilities
    schedule: list[Schedule] = field(default_factory=list)
    schedule_enabled: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AirToAirUnit":
        """Create from API response dict."""
        capabilities_data = data.get("capabilities", {})
        capabilities = DeviceCapabilities.from_dict(capabilities_data)

        schedules_data = data.get("schedule", [])
        schedules = [Schedule.from_dict(s) for s in schedules_data]

        return cls(
            id=data["id"],
            name=data.get("name", "Unknown"),
            power=data.get("power", False),
            operation_mode=data.get("operationMode", "Heat"),
            set_temperature=data.get("setTemperature"),
            room_temperature=data.get("roomTemperature"),
            set_fan_speed=data.get("setFanSpeed"),
            vane_vertical_direction=data.get("vaneVerticalDirection"),
            vane_horizontal_direction=data.get("vaneHorizontalDirection"),
            in_standby_mode=data.get("inStandbyMode", False),
            is_in_error=data.get("isInError", False),
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
