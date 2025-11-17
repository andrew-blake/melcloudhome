"""Constants for the MELCloud Home integration."""

from datetime import timedelta

from homeassistant.components.climate import (
    HVACMode,
)

DOMAIN = "melcloudhome"
UPDATE_INTERVAL = timedelta(seconds=60)
PLATFORMS = ["climate"]

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

# Vane position mappings
VANE_POSITIONS = ["Auto", "Swing", "One", "Two", "Three", "Four", "Five"]
