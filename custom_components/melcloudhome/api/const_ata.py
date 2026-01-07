"""Air-to-Air (A/C) constants for MELCloud Home API Client."""

from .const_shared import (
    BASE_URL,
    USER_AGENT,
)

# API Response Field Names - ATA
API_FIELD_AIR_TO_AIR_UNITS = "airToAirUnits"

# API Endpoints - ATA
API_CONTROL_UNIT = "/api/ataunit/{unit_id}"
API_ERROR_LOG = "/api/ataunit/{unit_id}/errorlog"

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

# Vane Direction Mappings (Control API numeric strings <-> word strings)
# Used for normalization when API returns "0"-"7" but we use "Auto", "One"-"Five", "Swing"
VANE_NUMERIC_TO_WORD = {
    "0": VANE_AUTO,
    "1": VANE_POSITION_ONE,
    "2": VANE_POSITION_TWO,
    "3": VANE_POSITION_THREE,
    "4": VANE_POSITION_FOUR,
    "5": VANE_POSITION_FIVE,
    "7": VANE_SWING,
}

VANE_WORD_TO_NUMERIC = {v: k for k, v in VANE_NUMERIC_TO_WORD.items()}

# Fan Speed Mappings (Control API numeric strings <-> word strings)
# Used for normalization when API returns "0"-"5" but we use "Auto", "One"-"Five"
FAN_SPEED_NUMERIC_TO_WORD = {
    "0": FAN_SPEED_AUTO,
    "1": FAN_SPEED_ONE,
    "2": FAN_SPEED_TWO,
    "3": FAN_SPEED_THREE,
    "4": FAN_SPEED_FOUR,
    "5": FAN_SPEED_FIVE,
}

FAN_SPEED_WORD_TO_NUMERIC = {v: k for k, v in FAN_SPEED_NUMERIC_TO_WORD.items()}

# American-to-British spelling mappings for horizontal vanes
# Some API responses use American spelling, normalize to British
VANE_HORIZONTAL_AMERICAN_TO_BRITISH = {
    "CenterLeft": VANE_CENTER_LEFT,
    "Center": VANE_CENTER,
    "CenterRight": VANE_CENTER_RIGHT,
}

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
