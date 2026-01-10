"""Air-to-Air (A/C) constants for MELCloud Home API Client."""

# API Response Field Names - ATA
API_FIELD_AIR_TO_AIR_UNITS = "airToAirUnits"

# API Endpoints - ATA
API_CONTROL_UNIT = "/api/ataunit/{unit_id}"

# Operation Modes (Control API - Strings)
# CRITICAL: AUTO mode is "Automatic" NOT "Auto"!
OPERATION_MODE_HEAT = "Heat"

OPERATION_MODES = [
    "Heat",
    "Cool",
    "Automatic",
    "Dry",
    "Fan",
]

# Fan Speeds (Control API - Strings)
# CRITICAL: These are STRINGS, not integers!
FAN_SPEEDS = [
    "Auto",
    "One",
    "Two",
    "Three",
    "Four",
    "Five",
]

# Vane Directions (Control API - Strings)
VANE_VERTICAL_DIRECTIONS = [
    "Auto",
    "Swing",
    "One",
    "Two",
    "Three",
    "Four",
    "Five",
]

# Horizontal-specific positions (British spelling per API)
VANE_HORIZONTAL_DIRECTIONS = [
    "Auto",
    "Swing",
    "Left",
    "LeftCentre",
    "Centre",
    "RightCentre",
    "Right",
]

# Vane Direction Mappings (Control API numeric strings <-> word strings)
# Used for normalization when API returns "0"-"7" but we use "Auto", "One"-"Five", "Swing"
VANE_NUMERIC_TO_WORD = {
    "0": "Auto",
    "1": "One",
    "2": "Two",
    "3": "Three",
    "4": "Four",
    "5": "Five",
    "7": "Swing",
}

VANE_WORD_TO_NUMERIC = {v: k for k, v in VANE_NUMERIC_TO_WORD.items()}

# Fan Speed Mappings (Control API numeric strings <-> word strings)
# Used for normalization when API returns "0"-"5" but we use "Auto", "One"-"Five"
FAN_SPEED_NUMERIC_TO_WORD = {
    "0": "Auto",
    "1": "One",
    "2": "Two",
    "3": "Three",
    "4": "Four",
    "5": "Five",
}

# American-to-British spelling mappings for horizontal vanes
# Some API responses use American spelling, normalize to British
VANE_HORIZONTAL_AMERICAN_TO_BRITISH = {
    "CenterLeft": "LeftCentre",
    "Center": "Centre",
    "CenterRight": "RightCentre",
}

# Temperature Ranges (Celsius)
TEMP_MIN_HEAT = 10.0
TEMP_MAX_HEAT = 31.0
TEMP_MIN_COOL_DRY = 16.0
TEMP_STEP = 0.5

# Note: Headers are constructed inline by the API client

__all__ = [
    "API_CONTROL_UNIT",
    "API_FIELD_AIR_TO_AIR_UNITS",
    "FAN_SPEEDS",
    "FAN_SPEED_NUMERIC_TO_WORD",
    "OPERATION_MODES",
    "OPERATION_MODE_HEAT",
    "TEMP_MAX_HEAT",
    "TEMP_MIN_COOL_DRY",
    "TEMP_MIN_HEAT",
    "TEMP_STEP",
    "VANE_HORIZONTAL_AMERICAN_TO_BRITISH",
    "VANE_HORIZONTAL_DIRECTIONS",
    "VANE_NUMERIC_TO_WORD",
    "VANE_VERTICAL_DIRECTIONS",
    "VANE_WORD_TO_NUMERIC",
]
