"""Shared data models for MELCloud Home API.

Contains Building and UserContext which are used by both ATA and ATW devices.
Device-specific models are in models_ata.py and models_atw.py.
"""

from dataclasses import dataclass, field
from typing import Any

from . import const_ata, const_atw, const_shared
from .models_ata import AirToAirUnit
from .models_atw import AirToWaterUnit

__all__ = [
    "Building",
    "UserContext",
]


# ==============================================================================
# Shared Models
# ==============================================================================


@dataclass
class Building:
    """Building containing units.

    Attributes:
        id: Unique building identifier
        name: Building name
        is_guest: True if this is a guest/shared building, False if owned
        air_to_air_units: List of ATA units in this building
        air_to_water_units: List of ATW units in this building
    """

    id: str
    name: str
    is_guest: bool = False
    air_to_air_units: list[AirToAirUnit] = field(default_factory=list)
    air_to_water_units: list[AirToWaterUnit] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any], is_guest: bool = False) -> "Building":
        """Create from API response dict.

        Args:
            data: Building data from API
            is_guest: Whether this building is a guest/shared building
        """
        # Parse A2A units (existing)
        a2a_units_data = data.get(const_ata.API_FIELD_AIR_TO_AIR_UNITS, [])
        a2a_units = [AirToAirUnit.from_dict(u) for u in a2a_units_data]

        # Parse A2W units (NEW)
        a2w_units_data = data.get(const_atw.API_FIELD_AIR_TO_WATER_UNITS, [])
        a2w_units = [AirToWaterUnit.from_dict(u) for u in a2w_units_data]

        return cls(
            id=data["id"],
            name=data.get("name", "Unknown"),
            is_guest=is_guest,
            air_to_air_units=a2a_units,
            air_to_water_units=a2w_units,
        )


@dataclass
class UserContext:
    """User context containing all buildings and devices."""

    buildings: list[Building] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UserContext":
        """Create from API response dict.

        Parses buildings from multiple sources:
        - buildings: Buildings owned by the user (is_guest=False)
        - guestBuildings: Buildings shared with the user (is_guest=True)
        """
        buildings: list[Building] = []

        # Parse owned buildings
        owned_buildings_data = data.get(const_shared.API_FIELD_BUILDINGS, [])
        for building_data in owned_buildings_data:
            buildings.append(Building.from_dict(building_data, is_guest=False))

        # Parse guest buildings (shared buildings where user is a guest)
        guest_buildings_data = data.get("guestBuildings", [])
        for building_data in guest_buildings_data:
            buildings.append(Building.from_dict(building_data, is_guest=True))

        return cls(buildings=buildings)

    def get_all_units(self) -> list[AirToAirUnit]:
        """Get all A2A units across all buildings."""
        units = []
        for building in self.buildings:
            units.extend(building.air_to_air_units)
        return units

    def get_all_air_to_air_units(self) -> list[AirToAirUnit]:
        """Get all A2A units across all buildings (explicit method name)."""
        return self.get_all_units()

    def get_all_air_to_water_units(self) -> list[AirToWaterUnit]:
        """Get all A2W units across all buildings."""
        units = []
        for building in self.buildings:
            units.extend(building.air_to_water_units)
        return units

    def get_unit_by_id(self, unit_id: str) -> AirToAirUnit | None:
        """Get A2A unit by ID."""
        for unit in self.get_all_units():
            if unit.id == unit_id:
                return unit
        return None

    def get_air_to_water_unit_by_id(self, unit_id: str) -> AirToWaterUnit | None:
        """Get A2W unit by ID."""
        for unit in self.get_all_air_to_water_units():
            if unit.id == unit_id:
                return unit
        return None
