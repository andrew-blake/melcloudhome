"""Air-to-Water (Heat Pump) data models for MELCloud Home API."""

import logging
from dataclasses import dataclass, field
from typing import Any

from .const_atw import ATW_MODE_HEAT_ROOM_TEMP, ATW_STATUS_STOP
from .parsing import (
    parse_bool as _parse_bool,
    parse_float as _parse_float,
)

_LOGGER = logging.getLogger(__name__)


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

    # Cooling Support
    has_cooling_mode: bool = False

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
            has_cooling_mode=data.get("hasCoolingMode", False),
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

    # Holiday Mode & Frost Protection (read-only state)
    holiday_mode_enabled: bool = False
    frost_protection_enabled: bool = False

    # Telemetry data (flow/return temperatures from telemetry API)
    # Populated by TelemetryTracker, read by sensors
    # Structure: {measure_name: temperature_celsius}
    telemetry: dict[str, float | None] = field(default_factory=dict)

    # Energy data (populated by EnergyTrackerATW)
    energy_consumed: float | None = None  # kWh (cumulative)
    energy_produced: float | None = None  # kWh (cumulative)
    cop: float | None = None  # Coefficient of Performance (produced/consumed)

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

        # Extract cooling mode flag from settings (some devices report it here)
        # Check settings first, then fall back to capabilities
        has_cooling_from_settings = _parse_bool(settings.get("HasCoolingMode"))
        if has_cooling_from_settings:
            # Override capabilities with settings value
            capabilities.has_cooling_mode = True

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
            operation_status=settings.get("OperationMode", ATW_STATUS_STOP),
            # Zone 1
            operation_mode_zone1=settings.get(
                "OperationModeZone1", ATW_MODE_HEAT_ROOM_TEMP
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
            ftc_model=int(settings.get("FTCModel", "3")),
            # Capabilities
            capabilities=capabilities,
            # Holiday Mode & Frost Protection
            holiday_mode_enabled=holiday_enabled,
            frost_protection_enabled=frost_enabled,
        )
