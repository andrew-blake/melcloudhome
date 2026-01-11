"""Air-to-Water (Heat Pump) constants for MELCloud Home integration."""

from typing import TYPE_CHECKING

from homeassistant.components.water_heater import STATE_ECO, STATE_HIGH_DEMAND
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import CoordinatorEntity

# Import temperature constants from API (single source of truth)
from .api.const_atw import (  # noqa: F401
    ATW_TEMP_MAX_DHW,
    ATW_TEMP_MAX_ZONE,
    ATW_TEMP_MIN_DHW,
    ATW_TEMP_MIN_ZONE,
    ATW_TEMP_STEP,
)

if TYPE_CHECKING:
    from .api.models import AirToWaterUnit, Building

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

# Water Heater Operation Modes → Home Assistant Standard Modes
# Maps MELCloud forced_hot_water_mode to HA standard operation modes
# See: https://developers.home-assistant.io/docs/core/entity/water-heater/
WATER_HEATER_FORCED_DHW_TO_HA = {
    False: STATE_ECO,  # Normal balanced operation → Eco mode (energy efficient)
    True: STATE_HIGH_DEMAND,  # DHW priority mode → High demand (meet high demands)
}

WATER_HEATER_HA_TO_FORCED_DHW = {
    STATE_ECO: False,  # Eco → Auto (normal operation, zone heating priority)
    STATE_HIGH_DEMAND: True,  # High demand → Force DHW (priority mode)
}

# Note: ATW_TEMP_* constants imported from api.const_atw (floats with 0.5° precision)


# =================================================================
# Base Entity Class
# =================================================================


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
        return self.coordinator.get_atw_device(self._unit_id)  # type: ignore[no-any-return]

    def get_building(self) -> "Building | None":
        """Get building from coordinator - O(1) cached lookup."""
        return self.coordinator.get_building_for_atw_device(self._unit_id)  # type: ignore[no-any-return]

    @property
    def available(self) -> bool:
        """Entity available if coordinator updated, device exists, not in error."""
        if not self.coordinator.last_update_success:
            return False
        device = self.get_device()
        if device is None:
            return False
        return not device.is_in_error
