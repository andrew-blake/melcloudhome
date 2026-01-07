"""Shared data models for MELCloud Home API.

Contains Building and UserContext which are used by both ATA and ATW devices.
Device-specific models are in models_ata.py and models_atw.py.
"""

from dataclasses import dataclass, field
from typing import Any

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
    """Building containing units."""

    id: str
    name: str
    air_to_air_units: list[AirToAirUnit] = field(default_factory=list)
    air_to_water_units: list[AirToWaterUnit] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Building":
        """Create from API response dict."""
        # Parse A2A units (existing)
        a2a_units_data = data.get("airToAirUnits", [])
        a2a_units = [AirToAirUnit.from_dict(u) for u in a2a_units_data]

        # Parse A2W units (NEW)
        a2w_units_data = data.get("airToWaterUnits", [])
        a2w_units = [AirToWaterUnit.from_dict(u) for u in a2w_units_data]

        return cls(
            id=data["id"],
            name=data.get("name", "Unknown"),
            air_to_air_units=a2a_units,
            air_to_water_units=a2w_units,
        )


@dataclass
class UserContext:
    """User context containing all buildings and devices."""

    buildings: list[Building] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UserContext":
        """Create from API response dict."""
        buildings_data = data.get("buildings", [])
        buildings = [Building.from_dict(b) for b in buildings_data]

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
