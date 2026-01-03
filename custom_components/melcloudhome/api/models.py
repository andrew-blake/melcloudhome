"""Data models for MELCloud Home API."""

import logging
from dataclasses import dataclass, field
from typing import Any

_LOGGER = logging.getLogger(__name__)


# ==============================================================================
# Shared Parsing Utilities
# ==============================================================================


def _parse_bool(value: str | bool | None) -> bool:
    """Parse boolean from API string value.

    API returns booleans as string "True"/"False". This helper converts
    them to Python bool, handling edge cases.

    Args:
        value: String "True"/"False", bool, or None

    Returns:
        Parsed boolean (False if None)
    """
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).lower() == "true"


def _parse_float(value: str | float | None) -> float | None:
    """Parse float from API string value.

    API returns numbers as strings. This helper converts them to float,
    handling edge cases like empty strings and invalid values.

    Args:
        value: String number, float, empty string, or None

    Returns:
        Parsed float or None if unparsable
    """
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _parse_int(value: str | int | None) -> int | None:
    """Parse int from API string value.

    API sometimes returns integers as strings (e.g., HasZone2="0").
    This helper converts them to int, handling edge cases.

    Args:
        value: String number, int, empty string, or None

    Returns:
        Parsed int or None if unparsable
    """
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


# ==============================================================================
# Air-to-Air (A/C) Models
# ==============================================================================


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
            power=_parse_bool(settings.get("Power")),
            operation_mode=settings.get("OperationMode", "Heat"),
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
            schedule=schedules,
            schedule_enabled=data.get("scheduleEnabled", False),
        )


# ==============================================================================
# Air-to-Water (Heat Pump) Models
# ==============================================================================


@dataclass
class AirToWaterCapabilities:
    """ATW device capability flags and limits.

    CRITICAL: Always uses safe hardcoded defaults for temperature ranges.
    API-reported ranges are unreliable (known bug history).
    """

    # DHW Support
    has_hot_water: bool = True
    min_set_tank_temperature: float = 40.0  # Safe default (HARDCODED)
    max_set_tank_temperature: float = 60.0  # Safe default (HARDCODED)

    # Zone 1 Support (always present)
    min_set_temperature: float = 10.0  # Zone 1, safe default (HARDCODED)
    max_set_temperature: float = 30.0  # Zone 1, safe default (HARDCODED)
    has_half_degrees: bool = False  # Temperature increment capability

    # Zone 2 Support (usually false)
    has_zone2: bool = False

    # Thermostat Support
    has_thermostat_zone1: bool = True
    has_thermostat_zone2: bool = True  # Capability flag (not actual support)

    # Heating Support
    has_heat_zone1: bool = True
    has_heat_zone2: bool = False

    # Energy Monitoring
    has_measured_energy_consumption: bool = False
    has_measured_energy_production: bool = False
    has_estimated_energy_consumption: bool = True
    has_estimated_energy_production: bool = True

    # FTC Model (controller type)
    ftc_model: int = 3

    # Demand Side Control
    has_demand_side_control: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AirToWaterCapabilities":
        """Create from API response dict.

        ALWAYS uses safe hardcoded temperature defaults.
        API values are parsed but ignored due to known reliability issues.
        """
        if not data:
            return cls()

        # Parse API values but IGNORE temperature ranges (use hardcoded)
        api_min_tank = data.get("minSetTankTemperature", 0)
        api_max_tank = data.get("maxSetTankTemperature", 60)
        api_min_zone = data.get("minSetTemperature", 10)
        api_max_zone = data.get("maxSetTemperature", 30)

        # Log if API values differ from safe defaults (for debugging)
        if api_min_tank != 40 or api_max_tank != 60:
            _LOGGER.debug(
                "API reported DHW range %s-%s°C, using safe default 40-60°C",
                api_min_tank,
                api_max_tank,
            )

        if api_min_zone != 10 or api_max_zone != 30:
            _LOGGER.debug(
                "API reported Zone range %s-%s°C, using safe default 10-30°C",
                api_min_zone,
                api_max_zone,
            )

        return cls(
            has_hot_water=data.get("hasHotWater", True),
            # ALWAYS use safe defaults (not API values)
            min_set_tank_temperature=40.0,
            max_set_tank_temperature=60.0,
            min_set_temperature=10.0,
            max_set_temperature=30.0,
            has_half_degrees=data.get("hasHalfDegrees", False),
            has_zone2=data.get("hasZone2", False),
            has_thermostat_zone1=data.get("hasThermostatZone1", True),
            has_thermostat_zone2=data.get("hasThermostatZone2", True),
            has_heat_zone1=data.get("hasHeatZone1", True),
            has_heat_zone2=data.get("hasHeatZone2", False),
            has_measured_energy_consumption=data.get(
                "hasMeasuredEnergyConsumption", False
            ),
            has_measured_energy_production=data.get(
                "hasMeasuredEnergyProduction", False
            ),
            has_estimated_energy_consumption=data.get(
                "hasEstimatedEnergyConsumption", True
            ),
            has_estimated_energy_production=data.get(
                "hasEstimatedEnergyProduction", True
            ),
            ftc_model=data.get("ftcModel", 3),
            has_demand_side_control=data.get("hasDemandSideControl", True),
        )


@dataclass
class AirToWaterUnit:
    """Air-to-water heat pump unit.

    Represents ONE physical device with TWO functional capabilities:
    - Zone 1: Space heating (underfloor/radiators)
    - DHW: Domestic hot water tank

    CRITICAL: 3-way valve limitation - can only heat Zone OR DHW at a time.
    """

    # Device Identity
    id: str
    name: str

    # Power State
    power: bool
    in_standby_mode: bool

    # Operation Status (READ-ONLY)
    # Indicates WHAT the 3-way valve is doing RIGHT NOW
    # Values: "Stop", "HotWater", or zone mode string
    operation_status: str

    # Zone 1 Control
    operation_mode_zone1: str  # HOW to heat zone (HeatRoomTemperature, etc.)
    set_temperature_zone1: float | None  # Target room temperature (10-30°C)
    room_temperature_zone1: float | None  # Current room temperature

    # Zone 2 (usually not present)
    has_zone2: bool

    # DHW (Domestic Hot Water)
    set_tank_water_temperature: float | None  # Target DHW temp (40-60°C)
    tank_water_temperature: float | None  # Current DHW temp
    forced_hot_water_mode: bool  # DHW priority enabled

    # Device Status
    is_in_error: bool
    error_code: str | None
    rssi: int | None  # WiFi signal strength

    # Device Info
    ftc_model: int

    # Capabilities
    capabilities: AirToWaterCapabilities

    # Fields with defaults MUST come after fields without defaults
    operation_mode_zone2: str | None = None
    set_temperature_zone2: float | None = None
    room_temperature_zone2: float | None = None

    # Schedule (read-only for now - creation deferred)
    schedule: list[dict[str, Any]] = field(default_factory=list)
    schedule_enabled: bool = False

    # Holiday Mode & Frost Protection (read-only state)
    holiday_mode_enabled: bool = False
    frost_protection_enabled: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AirToWaterUnit":
        """Create from API response dict.

        The API returns device state as a list of name-value pairs in the 'settings' array.
        Example: [{"name": "Power", "value": "True"}, {"name": "SetTemperatureZone1", "value": "21"}, ...]

        This method parses the settings array and handles type conversions.
        """
        # Parse capabilities
        capabilities_data = data.get("capabilities", {})
        capabilities = AirToWaterCapabilities.from_dict(capabilities_data)

        # Parse settings array into dict for easy access
        settings_list = data.get("settings", [])
        settings = {item["name"]: item["value"] for item in settings_list}

        # Extract Zone 2 flag (can be string "0"/"1" or int)
        has_zone2_value = settings.get("HasZone2", "0")
        if isinstance(has_zone2_value, str):
            has_zone2 = has_zone2_value != "0" and has_zone2_value.lower() != "false"
        else:
            has_zone2 = bool(has_zone2_value)

        # Parse schedule (basic parsing - creation not supported yet)
        schedule_data = data.get("schedule", [])

        # Parse holiday mode and frost protection
        holiday_data = data.get("holidayMode", {})
        holiday_enabled = holiday_data.get("enabled", False) if holiday_data else False

        frost_data = data.get("frostProtection", {})
        frost_enabled = frost_data.get("enabled", False) if frost_data else False

        # Parse error code - convert empty string to None
        error_code_value = settings.get("ErrorCode", "")
        error_code = error_code_value if error_code_value else None

        return cls(
            # Identity
            id=data["id"],
            name=data.get("givenDisplayName", "Unknown"),
            # Power
            power=_parse_bool(settings.get("Power")),
            in_standby_mode=_parse_bool(settings.get("InStandbyMode")),
            # Operation Status (READ-ONLY)
            # CRITICAL: This is "OperationMode" in API but renamed to avoid confusion
            # with operationModeZone1 (which is the control field)
            operation_status=settings.get("OperationMode", "Stop"),
            # Zone 1
            operation_mode_zone1=settings.get(
                "OperationModeZone1", "HeatRoomTemperature"
            ),
            set_temperature_zone1=_parse_float(settings.get("SetTemperatureZone1")),
            room_temperature_zone1=_parse_float(settings.get("RoomTemperatureZone1")),
            # Zone 2 (if present)
            has_zone2=has_zone2,
            operation_mode_zone2=settings.get("OperationModeZone2")
            if has_zone2
            else None,
            set_temperature_zone2=_parse_float(settings.get("SetTemperatureZone2"))
            if has_zone2
            else None,
            room_temperature_zone2=_parse_float(settings.get("RoomTemperatureZone2"))
            if has_zone2
            else None,
            # DHW
            set_tank_water_temperature=_parse_float(
                settings.get("SetTankWaterTemperature")
            ),
            tank_water_temperature=_parse_float(settings.get("TankWaterTemperature")),
            forced_hot_water_mode=_parse_bool(settings.get("ForcedHotWaterMode")),
            # Status
            is_in_error=_parse_bool(settings.get("IsInError")),
            error_code=error_code,
            rssi=data.get("rssi"),
            # Device Info
            ftc_model=data.get("ftcModel", 3),
            # Capabilities
            capabilities=capabilities,
            # Schedule (read-only)
            schedule=schedule_data,
            schedule_enabled=data.get("scheduleEnabled", False),
            # Holiday Mode & Frost Protection
            holiday_mode_enabled=holiday_enabled,
            frost_protection_enabled=frost_enabled,
        )


# ==============================================================================
# Shared Models
# ==============================================================================


@dataclass
class Building:
    """Building containing units."""

    id: str
    name: str
    air_to_air_units: list[AirToAirUnit] = field(default_factory=list)
    air_to_water_units: list[AirToWaterUnit] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Building":
        """Create from API response dict."""
        # Parse A2A units (existing)
        a2a_units_data = data.get("airToAirUnits", [])
        a2a_units = [AirToAirUnit.from_dict(u) for u in a2a_units_data]

        # Parse A2W units (NEW)
        a2w_units_data = data.get("airToWaterUnits", [])
        a2w_units = [AirToWaterUnit.from_dict(u) for u in a2w_units_data]

        return cls(
            id=data["id"],
            name=data.get("name", "Unknown"),
            air_to_air_units=a2a_units,
            air_to_water_units=a2w_units,
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
        """Get all A2A units across all buildings."""
        units = []
        for building in self.buildings:
            units.extend(building.air_to_air_units)
        return units

    def get_all_air_to_air_units(self) -> list[AirToAirUnit]:
        """Get all A2A units across all buildings (explicit method name)."""
        return self.get_all_units()

    def get_all_air_to_water_units(self) -> list[AirToWaterUnit]:
        """Get all A2W units across all buildings."""
        units = []
        for building in self.buildings:
            units.extend(building.air_to_water_units)
        return units

    def get_unit_by_id(self, unit_id: str) -> AirToAirUnit | None:
        """Get A2A unit by ID."""
        for unit in self.get_all_units():
            if unit.id == unit_id:
                return unit
        return None

    def get_air_to_water_unit_by_id(self, unit_id: str) -> AirToWaterUnit | None:
        """Get A2W unit by ID."""
        for unit in self.get_all_air_to_water_units():
            if unit.id == unit_id:
                return unit
        return None
