"""Air-to-Water (Heat Pump) constants for MELCloud Home API Client."""

# ==============================================================================
# Air-to-Water (Heat Pump) Constants
# ==============================================================================

# API Response Field Names - ATW
API_FIELD_AIR_TO_WATER_UNITS = "airToWaterUnits"

# API Endpoints - ATW
API_ATW_CONTROL_UNIT = "/api/atwunit/{unit_id}"
API_ATW_ERROR_LOG = "/api/atwunit/{unit_id}/errorlog"
API_ATW_SCHEDULE_CREATE = "/api/atwcloudschedule/{unit_id}"
API_ATW_SCHEDULE_DELETE = "/api/atwcloudschedule/{unit_id}/{schedule_id}"
API_ATW_SCHEDULE_ENABLED = "/api/atwcloudschedule/{unit_id}/enabled"
API_HOLIDAY_MODE = "/api/holidaymode"
API_FROST_PROTECTION = "/api/protection/frost"

# Operation Modes - Zone Control (Control API - Strings)
# These determine HOW the zone is heated
ATW_MODE_HEAT_ROOM_TEMP = "HeatRoomTemperature"  # Thermostat mode
ATW_MODE_HEAT_FLOW_TEMP = "HeatFlowTemperature"  # Direct flow control (DEFERRED)
ATW_MODE_HEAT_CURVE = "HeatCurve"  # Weather compensation

# Operation Modes - Zone Control (Schedule API - Integers)
# Schedule API uses integer enums instead of strings
ATW_MODE_INT_HEAT_ROOM_TEMP = 0  # Maps to "HeatRoomTemperature"
ATW_MODE_INT_HEAT_FLOW_TEMP = 1  # Maps to "HeatFlowTemperature"
ATW_MODE_INT_HEAT_CURVE = 2  # Maps to "HeatCurve"

ATW_OPERATION_MODES_ZONE = [
    ATW_MODE_HEAT_ROOM_TEMP,
    ATW_MODE_HEAT_FLOW_TEMP,
    ATW_MODE_HEAT_CURVE,
]

# Operation Status Values (Read-only STATUS field)
# These indicate WHAT the 3-way valve is doing RIGHT NOW
ATW_STATUS_STOP = "Stop"  # Idle (target reached)
ATW_STATUS_HOT_WATER = "HotWater"  # Heating DHW tank
# Status can also be zone mode string when heating zone

ATW_OPERATION_STATUSES = [
    ATW_STATUS_STOP,
    ATW_STATUS_HOT_WATER,
    ATW_MODE_HEAT_ROOM_TEMP,
    ATW_MODE_HEAT_FLOW_TEMP,
    ATW_MODE_HEAT_CURVE,
]

# Temperature Ranges (Celsius) - SAFE HARDCODED DEFAULTS
# DO NOT use API-reported ranges (known to be unreliable)
ATW_TEMP_MIN_ZONE = 10.0  # Zone 1 minimum (underfloor heating)
ATW_TEMP_MAX_ZONE = 30.0  # Zone 1 maximum (underfloor heating)
ATW_TEMP_MIN_DHW = 40.0  # DHW tank minimum
ATW_TEMP_MAX_DHW = 60.0  # DHW tank maximum
ATW_TEMP_STEP = 0.5  # Temperature increment (most systems)

# Note: Flow temperature ranges DEFERRED (Phase 2)
# ATW_TEMP_MIN_FLOW = 30.0    # Likely range for flow temp mode
# ATW_TEMP_MAX_FLOW = 60.0    # Likely range for flow temp mode
