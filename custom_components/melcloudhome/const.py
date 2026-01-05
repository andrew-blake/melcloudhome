"""Constants for the MELCloud Home integration."""

from datetime import timedelta

from homeassistant.components.climate import (
    HVACMode,
)

DOMAIN = "melcloudhome"
UPDATE_INTERVAL = timedelta(seconds=60)
PLATFORMS = ["climate"]

# Configuration keys
CONF_DEBUG_MODE = "debug_mode"

# MELCloud API uses "Automatic" not "Auto"
MELCLOUD_TO_HA_MODE = {
    "Heat": HVACMode.HEAT,
    "Cool": HVACMode.COOL,
    "Automatic": HVACMode.AUTO,
    "Dry": HVACMode.DRY,
    "Fan": HVACMode.FAN_ONLY,
}

HA_TO_MELCLOUD_MODE = {
    HVACMode.HEAT: "Heat",
    HVACMode.COOL: "Cool",
    HVACMode.AUTO: "Automatic",
    HVACMode.DRY: "Dry",
    HVACMode.FAN_ONLY: "Fan",
}

# Fan speed mappings
FAN_SPEEDS = ["Auto", "One", "Two", "Three", "Four", "Five"]

# Vane position mappings (vertical)
VANE_POSITIONS = ["Auto", "Swing", "One", "Two", "Three", "Four", "Five"]

# Horizontal vane position mappings (API uses British spelling)
VANE_HORIZONTAL_POSITIONS = [
    "Auto",
    "Swing",
    "Left",
    "LeftCentre",
    "Centre",
    "RightCentre",
    "Right",
]

# ATW (Air-to-Water) Zone Modes → Climate Preset Modes (lowercase for i18n)
# Display names in translations/en.json: "Room", "Flow", "Curve"
ATW_TO_HA_PRESET = {
    "HeatRoomTemperature": "room",  # Display: "Room"
    "HeatFlowTemperature": "flow",  # Display: "Flow"
    "HeatCurve": "curve",  # Display: "Curve"
}

HA_TO_ATW_PRESET = {v: k for k, v in ATW_TO_HA_PRESET.items()}

# ATW Preset modes list (lowercase keys, translated in en.json)
ATW_PRESET_MODES = ["room", "flow", "curve"]

# Water Heater Operation Modes (map to HA standard modes)
# Use HA constants from homeassistant.components.water_heater
# STATE_ECO, STATE_PERFORMANCE are standard HA modes
WATER_HEATER_FORCED_DHW_TO_HA = {
    False: "eco",  # Maps to STATE_ECO
    True: "performance",  # Maps to STATE_PERFORMANCE
}

WATER_HEATER_HA_TO_FORCED_DHW = {
    "eco": False,
    "performance": True,
}

# ATW Temperature limits
ATW_TEMP_MIN_ZONE = 10  # °C
ATW_TEMP_MAX_ZONE = 30  # °C
ATW_TEMP_MIN_DHW = 40  # °C
ATW_TEMP_MAX_DHW = 60  # °C
ATW_TEMP_STEP = 1  # °C
