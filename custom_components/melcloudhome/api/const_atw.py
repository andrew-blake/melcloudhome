"""Air-to-Water (Heat Pump) constants for MELCloud Home API Client."""

# ==============================================================================
# Air-to-Water (Heat Pump) Constants
# ==============================================================================

# API Response Field Names - ATW
API_FIELD_AIR_TO_WATER_UNITS = "airToWaterUnits"

# API Endpoints - ATW
API_ATW_CONTROL_UNIT = "/api/atwunit/{unit_id}"

# Operation Modes - Zone Control (Control API - Strings)
# These determine HOW the zone is heated or cooled

# Heating Modes
ATW_MODE_HEAT_ROOM_TEMP = "HeatRoomTemperature"  # Thermostat mode
ATW_MODE_HEAT_FLOW_TEMP = "HeatFlowTemperature"  # Direct flow control
ATW_MODE_HEAT_CURVE = "HeatCurve"  # Weather compensation

ATW_OPERATION_MODES_HEATING = [
    "HeatRoomTemperature",
    "HeatFlowTemperature",
    "HeatCurve",
]

# Cooling Modes
ATW_MODE_COOL_ROOM_TEMP = "CoolRoomTemperature"  # Thermostat mode
ATW_MODE_COOL_FLOW_TEMP = "CoolFlowTemperature"  # Direct flow control
# NOTE: CoolCurve does NOT exist (confirmed from HAR + user testing)

ATW_OPERATION_MODES_COOLING = [
    "CoolRoomTemperature",
    "CoolFlowTemperature",
]

# All operation modes (for detection)
ATW_OPERATION_MODES_ZONE = ATW_OPERATION_MODES_HEATING + ATW_OPERATION_MODES_COOLING

# Operation Status Values (Read-only STATUS field)
# These indicate WHAT the 3-way valve is doing RIGHT NOW
ATW_STATUS_STOP = "Stop"  # Idle (target reached)
# Status can also be zone mode string when heating zone (e.g., "HeatRoomTemperature", "HotWater")

# Temperature Ranges (Celsius) - SAFE HARDCODED DEFAULTS
# DO NOT use API-reported ranges (known to be unreliable)
ATW_TEMP_MIN_ZONE = 10.0  # Zone 1 minimum (underfloor heating)
ATW_TEMP_MAX_ZONE = 30.0  # Zone 1 maximum (underfloor heating)
ATW_TEMP_MIN_DHW = 40.0  # DHW tank minimum
ATW_TEMP_MAX_DHW = 60.0  # DHW tank maximum

# Note: Temperature steps are NOT constants - they're capability-dependent
# - Heating: Determined by hasHalfDegrees capability (0.5 if True, else 1.0)
# - Cooling: Always 1.0°C (confirmed from ERSC-VM2D testing, no API flag exists)
# Climate entity calculates step dynamically via target_temperature_step property

__all__ = [
    "API_ATW_CONTROL_UNIT",
    "API_FIELD_AIR_TO_WATER_UNITS",
    "ATW_MODE_COOL_FLOW_TEMP",
    "ATW_MODE_COOL_ROOM_TEMP",
    "ATW_MODE_HEAT_CURVE",
    "ATW_MODE_HEAT_FLOW_TEMP",
    "ATW_MODE_HEAT_ROOM_TEMP",
    "ATW_OPERATION_MODES_COOLING",
    "ATW_OPERATION_MODES_HEATING",
    "ATW_OPERATION_MODES_ZONE",
    "ATW_STATUS_STOP",
    "ATW_TEMP_MAX_DHW",
    "ATW_TEMP_MAX_ZONE",
    "ATW_TEMP_MIN_DHW",
    "ATW_TEMP_MIN_ZONE",
]
