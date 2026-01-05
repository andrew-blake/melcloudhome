"""Constants for the MELCloud Home integration."""

from datetime import timedelta
from typing import TYPE_CHECKING, Union

from homeassistant.components.climate import (
    HVACMode,
)

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo

    from .api.models import AirToAirUnit, AirToWaterUnit, Building

# Type alias for any device unit (ATA or ATW)
DeviceUnit = Union["AirToAirUnit", "AirToWaterUnit"]

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


# =================================================================
# Generic Entity Helpers (Phase 3.5: Works for both ATA and ATW)
# =================================================================


def create_entity_name(unit: DeviceUnit, suffix: str = "") -> str:
    """Generate standardized entity name for ATA or ATW units.

    Works for both AirToAirUnit and AirToWaterUnit with consistent naming.

    Args:
        unit: ATA or ATW unit object
        suffix: Optional suffix (e.g., "", "Zone 1", "Tank", "Room Temperature")
                Empty string for base entities (ATA climate)

    Returns:
        Formatted name: "MELCloudHome {first_4_chars} {last_4_chars} {suffix}"

    Examples:
        >>> ata_unit = AirToAirUnit(id="0efc1234-5678-9abc-...")
        >>> create_entity_name(ata_unit, "")
        "MELCloudHome 0efc 9abc"

        >>> atw_unit = AirToWaterUnit(id="0efc1234-5678-9abc-...")
        >>> create_entity_name(atw_unit, "Zone 1")
        "MELCloudHome 0efc 9abc Zone 1"
    """
    unit_id_clean = unit.id.replace("-", "")
    base_name = f"MELCloudHome {unit_id_clean[:4]} {unit_id_clean[-4:]}"
    return f"{base_name} {suffix}".strip()


def create_device_info(unit: DeviceUnit, building: "Building") -> "DeviceInfo":
    """Create standardized device info for ATA or ATW units.

    All entities for the same unit MUST use identical identifiers
    to be grouped under one device in the Home Assistant UI.

    Works for both AirToAirUnit and AirToWaterUnit - automatically
    determines correct model string based on unit type.

    Args:
        unit: ATA or ATW unit object
        building: Building containing the unit

    Returns:
        DeviceInfo dict with identifiers, name, manufacturer, model, area
    """
    from homeassistant.helpers.device_registry import DeviceInfo

    from .api.models import AirToWaterUnit

    # Determine model string based on unit type
    if isinstance(unit, AirToWaterUnit):
        model = f"Air-to-Water Heat Pump (Ecodan FTC{unit.ftc_model})"
    else:  # AirToAirUnit
        model = "Air-to-Air Heat Pump (via MELCloud Home)"

    return DeviceInfo(
        identifiers={(DOMAIN, unit.id)},
        name=f"{building.name} {unit.name}",
        manufacturer="Mitsubishi Electric",
        model=model,
        suggested_area=building.name,
    )


# Backwards-compatible aliases (for existing ATW code)
create_atw_entity_name = create_entity_name
create_atw_device_info = create_device_info
