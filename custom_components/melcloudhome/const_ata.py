"""Air-to-Air (A/C) constants for MELCloud Home integration."""

from typing import TYPE_CHECKING

from homeassistant.components.climate import HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import CoordinatorEntity

if TYPE_CHECKING:
    from .api.models import AirToAirUnit, Building

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


# =================================================================
# Base Entity Class
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
        return self.coordinator.get_ata_device(self._unit_id)  # type: ignore[no-any-return]

    def get_building(self) -> "Building | None":
        """Get building from coordinator - O(1) cached lookup."""
        return self.coordinator.get_building_for_ata_device(self._unit_id)  # type: ignore[no-any-return]

    @property
    def available(self) -> bool:
        """Entity available if coordinator updated, device exists, not in error."""
        if not self.coordinator.last_update_success:
            return False
        device = self.get_device()
        if device is None:
            return False
        return not device.is_in_error
