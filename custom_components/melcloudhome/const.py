"""Constants for the MELCloud Home integration."""

from collections.abc import Callable
from datetime import timedelta
from functools import wraps
from typing import TYPE_CHECKING, Any, Union

from homeassistant.components.climate import HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import CoordinatorEntity

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
    "HeatRoomTemperature": "room",  # Display: "Room" (via translation)
    "HeatFlowTemperature": "flow",  # Display: "Flow" (via translation)
    "HeatCurve": "curve",  # Display: "Curve" (via translation)
}

HA_TO_ATW_PRESET = {v: k for k, v in ATW_TO_HA_PRESET.items()}

# ATW Preset modes list (lowercase - translated via translations/en.json)
ATW_PRESET_MODES = ["room", "flow", "curve"]

# Water Heater Operation Modes (match MELCloud Home app terminology)
# Capitalized for display - HACS integrations don't support translations for operation modes
WATER_HEATER_FORCED_DHW_TO_HA = {
    False: "Auto",  # Normal operation, zone heating priority
    True: "Force DHW",  # DHW priority mode, forces hot water heating
}

WATER_HEATER_HA_TO_FORCED_DHW = {
    "Auto": False,
    "Force DHW": True,
}

# ATW Temperature limits
ATW_TEMP_MIN_ZONE = 10  # °C
ATW_TEMP_MAX_ZONE = 30  # °C
ATW_TEMP_MIN_DHW = 40  # °C
ATW_TEMP_MAX_DHW = 60  # °C
ATW_TEMP_STEP = 1  # °C


# =================================================================
# Generic Entity Helpers (works for both ATA and ATW)
# =================================================================


def create_entity_name(unit: DeviceUnit, suffix: str = "") -> str | None:
    """Generate short entity name for has_entity_name=True.

    With has_entity_name=True, entity_id is generated as:
    {domain}.{device_name}_{entity_name}

    Device name already contains UUID (melcloudhome_bf2d_5666),
    so entity name should just be the descriptive part.

    Args:
        unit: ATA or ATW unit (kept for signature compatibility)
        suffix: Entity suffix (e.g., "Room Temperature", "Zone 1", "Tank")
                Empty string for base entities (returns None)

    Returns:
        Short entity name or None for device-name-only entities

    Examples:
        >>> create_entity_name(unit, "Room Temperature")
        "Room Temperature"

        >>> create_entity_name(unit, "")
        None  # Base ATA climate uses device name only
    """
    return suffix.strip() if suffix else None


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

    # Extract UUID fragments for stable device naming
    unit_id_clean = unit.id.replace("-", "")
    device_name = f"melcloudhome_{unit_id_clean[:4]}_{unit_id_clean[-4:]}"

    # Determine model string based on unit type
    if isinstance(unit, AirToWaterUnit):
        model = f"Air-to-Water Heat Pump (Ecodan FTC{unit.ftc_model} via MELCloud Home)"
    else:  # AirToAirUnit
        model = "Air-to-Air Heat Pump (via MELCloud Home)"

    return DeviceInfo(
        identifiers={(DOMAIN, unit.id)},
        name=device_name,
        manufacturer="Mitsubishi Electric",
        model=model,
        suggested_area=building.name,
    )


# Backwards-compatible aliases (for existing ATW code)
create_atw_entity_name = create_entity_name
create_atw_device_info = create_device_info


# =================================================================
# Base Entity Classes (extract common patterns)
# =================================================================


class ATAEntityBase(CoordinatorEntity):  # type: ignore[misc]
    """Base class for ATA entities with shared lookup and availability logic.

    Provides:
    - O(1) device and building lookups via coordinator cache
    - Standardized availability logic

    Subclasses must set in __init__:
    - self._unit_id: str
    - self._building_id: str
    - self._entry: ConfigEntry
    - self._attr_unique_id
    - self._attr_name
    - self._attr_device_info
    """

    _attr_has_entity_name = True  # Use device name + entity name pattern
    _unit_id: str
    _building_id: str
    _entry: ConfigEntry

    def get_device(self) -> "AirToAirUnit | None":
        """Get device from coordinator - O(1) cached lookup.

        Changed from property to method to clarify this is an action, not attribute.
        """
        return self.coordinator.get_unit(self._unit_id)  # type: ignore[no-any-return]

    def get_building(self) -> "Building | None":
        """Get building from coordinator - O(1) cached lookup."""
        return self.coordinator.get_building_for_unit(self._unit_id)  # type: ignore[no-any-return]

    @property
    def available(self) -> bool:
        """Entity available if coordinator updated, device exists, not in error."""
        if not self.coordinator.last_update_success:
            return False
        device = self.get_device()
        if device is None:
            return False
        return not device.is_in_error


class ATWEntityBase(CoordinatorEntity):  # type: ignore[misc]
    """Base class for ATW entities with shared lookup and availability logic.

    Provides:
    - O(1) device and building lookups via coordinator cache
    - Standardized availability logic

    Subclasses must set in __init__:
    - self._unit_id: str
    - self._building_id: str
    - self._entry: ConfigEntry
    - self._attr_unique_id
    - self._attr_name
    - self._attr_device_info
    """

    _attr_has_entity_name = True  # Use device name + entity name pattern
    _unit_id: str
    _building_id: str
    _entry: ConfigEntry

    def get_device(self) -> "AirToWaterUnit | None":
        """Get device from coordinator - O(1) cached lookup.

        Changed from property to method to clarify this is an action, not attribute.
        """
        return self.coordinator.get_atw_unit(self._unit_id)  # type: ignore[no-any-return]

    def get_building(self) -> "Building | None":
        """Get building from coordinator - O(1) cached lookup."""
        return self.coordinator.get_building_for_atw_unit(self._unit_id)  # type: ignore[no-any-return]

    @property
    def available(self) -> bool:
        """Entity available if coordinator updated, device exists, not in error."""
        if not self.coordinator.last_update_success:
            return False
        device = self.get_device()
        if device is None:
            return False
        return not device.is_in_error


def with_debounced_refresh(
    delay: float = 2.0,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator for automatic debounced refresh after service calls.

    Eliminates manual refresh calls in every service method (Issue #10).
    Prevents race conditions from rapid service calls.

    Args:
        delay: Seconds to wait before refreshing (default 2.0)

    Usage:
        @with_debounced_refresh()
        async def async_set_temperature(self, **kwargs):
            temperature = kwargs.get("temperature")
            await self.coordinator.async_set_temperature(self._unit_id, temperature)
            # Refresh happens automatically - no manual call needed
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            result = await func(self, *args, **kwargs)
            await self.coordinator.async_request_refresh_debounced(delay)
            return result

        return wrapper

    return decorator
