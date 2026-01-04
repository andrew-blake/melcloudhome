"""Constants for MELCloud Home API Client."""

# API Base URLs
BASE_URL = "https://melcloudhome.com"  # Production
MOCK_BASE_URL = "http://localhost:8080"  # Development (local mock server)

# Required User-Agent to avoid bot detection
# CRITICAL: Must use Chrome User-Agent or requests will be blocked
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"

# API Endpoints
API_USER_CONTEXT = "/api/user/context"
API_CONTROL_UNIT = "/api/ataunit/{unit_id}"
API_ERROR_LOG = "/api/ataunit/{unit_id}/errorlog"
API_SCHEDULE_CREATE = "/api/cloudschedule/{unit_id}"
API_SCHEDULE_DELETE = "/api/cloudschedule/{unit_id}/{schedule_id}"
API_SCHEDULE_ENABLED = "/api/cloudschedule/{unit_id}/enabled"
API_TELEMETRY_ACTUAL = "/api/telemetry/actual"
API_TELEMETRY_OPERATION_MODE = "/api/telemetry/operationmode/{unit_id}"
API_TELEMETRY_ENERGY = "/api/telemetry/energy/{unit_id}"

# Operation Modes (Control API - Strings)
# CRITICAL: AUTO mode is "Automatic" NOT "Auto"!
OPERATION_MODE_HEAT = "Heat"
OPERATION_MODE_COOL = "Cool"
OPERATION_MODE_AUTO = "Automatic"
OPERATION_MODE_DRY = "Dry"
OPERATION_MODE_FAN = "Fan"

OPERATION_MODES = [
    OPERATION_MODE_HEAT,
    OPERATION_MODE_COOL,
    OPERATION_MODE_AUTO,
    OPERATION_MODE_DRY,
    OPERATION_MODE_FAN,
]

# Operation Modes (Schedule API - Integers)
# Different from Control API!
SCHEDULE_MODE_HEAT = 1
SCHEDULE_MODE_DRY = 2
SCHEDULE_MODE_COOL = 3
SCHEDULE_MODE_FAN = 4
SCHEDULE_MODE_AUTO = 5

# Mapping: Control API strings -> Schedule API integers
OPERATION_MODE_TO_SCHEDULE = {
    OPERATION_MODE_HEAT: SCHEDULE_MODE_HEAT,
    OPERATION_MODE_DRY: SCHEDULE_MODE_DRY,
    OPERATION_MODE_COOL: SCHEDULE_MODE_COOL,
    OPERATION_MODE_FAN: SCHEDULE_MODE_FAN,
    OPERATION_MODE_AUTO: SCHEDULE_MODE_AUTO,
}

# Mapping: Schedule API integers -> Control API strings
SCHEDULE_TO_OPERATION_MODE = {v: k for k, v in OPERATION_MODE_TO_SCHEDULE.items()}

# Fan Speeds (Control API - Strings)
# CRITICAL: These are STRINGS, not integers!
FAN_SPEED_AUTO = "Auto"
FAN_SPEED_ONE = "One"
FAN_SPEED_TWO = "Two"
FAN_SPEED_THREE = "Three"
FAN_SPEED_FOUR = "Four"
FAN_SPEED_FIVE = "Five"

FAN_SPEEDS = [
    FAN_SPEED_AUTO,
    FAN_SPEED_ONE,
    FAN_SPEED_TWO,
    FAN_SPEED_THREE,
    FAN_SPEED_FOUR,
    FAN_SPEED_FIVE,
]

# Fan Speeds (Schedule API - Integers)
SCHEDULE_FAN_SPEED_AUTO = 0
SCHEDULE_FAN_SPEED_ONE = 1
SCHEDULE_FAN_SPEED_TWO = 2
SCHEDULE_FAN_SPEED_THREE = 3
SCHEDULE_FAN_SPEED_FOUR = 4
SCHEDULE_FAN_SPEED_FIVE = 5

# Mapping: Control API strings -> Schedule API integers
FAN_SPEED_TO_SCHEDULE = {
    FAN_SPEED_AUTO: SCHEDULE_FAN_SPEED_AUTO,
    FAN_SPEED_ONE: SCHEDULE_FAN_SPEED_ONE,
    FAN_SPEED_TWO: SCHEDULE_FAN_SPEED_TWO,
    FAN_SPEED_THREE: SCHEDULE_FAN_SPEED_THREE,
    FAN_SPEED_FOUR: SCHEDULE_FAN_SPEED_FOUR,
    FAN_SPEED_FIVE: SCHEDULE_FAN_SPEED_FIVE,
}

# Mapping: Schedule API integers -> Control API strings
SCHEDULE_TO_FAN_SPEED = {v: k for k, v in FAN_SPEED_TO_SCHEDULE.items()}

# Vane Directions (Control API - Strings)
VANE_AUTO = "Auto"
VANE_SWING = "Swing"
VANE_POSITION_ONE = "One"
VANE_POSITION_TWO = "Two"
VANE_POSITION_THREE = "Three"
VANE_POSITION_FOUR = "Four"
VANE_POSITION_FIVE = "Five"

# Horizontal-specific positions (British spelling per API)
VANE_LEFT = "Left"
VANE_CENTER_LEFT = "LeftCentre"
VANE_CENTER = "Centre"
VANE_CENTER_RIGHT = "RightCentre"
VANE_RIGHT = "Right"

VANE_VERTICAL_DIRECTIONS = [
    VANE_AUTO,
    VANE_SWING,
    VANE_POSITION_ONE,
    VANE_POSITION_TWO,
    VANE_POSITION_THREE,
    VANE_POSITION_FOUR,
    VANE_POSITION_FIVE,
]

VANE_HORIZONTAL_DIRECTIONS = [
    VANE_AUTO,
    VANE_SWING,
    VANE_LEFT,
    VANE_CENTER_LEFT,
    VANE_CENTER,
    VANE_CENTER_RIGHT,
    VANE_RIGHT,
]

# Vane Directions (Schedule API - Integers)
SCHEDULE_VANE_POSITION_ONE = 1
SCHEDULE_VANE_POSITION_TWO = 2
SCHEDULE_VANE_POSITION_THREE = 3
SCHEDULE_VANE_POSITION_FOUR = 4
SCHEDULE_VANE_POSITION_FIVE = 5
SCHEDULE_VANE_AUTO = 6
SCHEDULE_VANE_SWING = 7

# Mapping: Vertical vane strings -> Schedule integers
VANE_VERTICAL_TO_SCHEDULE = {
    VANE_POSITION_ONE: SCHEDULE_VANE_POSITION_ONE,
    VANE_POSITION_TWO: SCHEDULE_VANE_POSITION_TWO,
    VANE_POSITION_THREE: SCHEDULE_VANE_POSITION_THREE,
    VANE_POSITION_FOUR: SCHEDULE_VANE_POSITION_FOUR,
    VANE_POSITION_FIVE: SCHEDULE_VANE_POSITION_FIVE,
    VANE_AUTO: SCHEDULE_VANE_AUTO,
    VANE_SWING: SCHEDULE_VANE_SWING,
}

# Mapping: Horizontal vane strings -> Schedule integers
VANE_HORIZONTAL_TO_SCHEDULE = {
    VANE_LEFT: SCHEDULE_VANE_POSITION_ONE,
    VANE_CENTER_LEFT: SCHEDULE_VANE_POSITION_TWO,
    VANE_CENTER: SCHEDULE_VANE_POSITION_THREE,
    VANE_CENTER_RIGHT: SCHEDULE_VANE_POSITION_FOUR,
    VANE_RIGHT: SCHEDULE_VANE_POSITION_FIVE,
    VANE_AUTO: SCHEDULE_VANE_AUTO,
    VANE_SWING: SCHEDULE_VANE_SWING,
}

# Reverse mappings
SCHEDULE_TO_VANE_VERTICAL = {v: k for k, v in VANE_VERTICAL_TO_SCHEDULE.items()}
SCHEDULE_TO_VANE_HORIZONTAL = {v: k for k, v in VANE_HORIZONTAL_TO_SCHEDULE.items()}

# Temperature Ranges (Celsius)
TEMP_MIN_HEAT = 10.0
TEMP_MAX_HEAT = 31.0
TEMP_MIN_COOL_DRY = 16.0
TEMP_MAX_COOL_DRY = 31.0
TEMP_MIN_AUTO = 16.0
TEMP_MAX_AUTO = 31.0
TEMP_STEP = 0.5

# Default Polling Interval (seconds)
# CRITICAL: Minimum 60 seconds to avoid rate limiting
DEFAULT_SCAN_INTERVAL = 60

# Headers for API requests
# CRITICAL: ALL API requests require x-csrf: 1 and referer headers or they return 401
HEADERS_JSON = {
    "Content-Type": "application/json; charset=utf-8",
    "User-Agent": USER_AGENT,
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "x-csrf": "1",
    "referer": f"{BASE_URL}/dashboard",
}

# For state-changing operations (PUT, POST, DELETE)
HEADERS_CSRF = HEADERS_JSON  # Same as HEADERS_JSON since x-csrf is always required

# Schedule Days (0 = Sunday)
SCHEDULE_DAY_SUNDAY = 0
SCHEDULE_DAY_MONDAY = 1
SCHEDULE_DAY_TUESDAY = 2
SCHEDULE_DAY_WEDNESDAY = 3
SCHEDULE_DAY_THURSDAY = 4
SCHEDULE_DAY_FRIDAY = 5
SCHEDULE_DAY_SATURDAY = 6

SCHEDULE_DAYS_WEEKDAYS = [1, 2, 3, 4, 5]
SCHEDULE_DAYS_WEEKEND = [0, 6]
SCHEDULE_DAYS_ALL = [0, 1, 2, 3, 4, 5, 6]

# ==============================================================================
# Air-to-Water (Heat Pump) Constants
# ==============================================================================

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
