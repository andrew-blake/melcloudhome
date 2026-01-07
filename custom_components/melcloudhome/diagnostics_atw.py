"""ATW device diagnostics serialization for MELCloud Home."""

from __future__ import annotations

from typing import Any

from .api.models_atw import AirToWaterUnit


def serialize_atw_unit(unit: AirToWaterUnit) -> dict[str, Any]:
    """Serialize ATW unit for diagnostics.

    Args:
        unit: ATW unit to serialize

    Returns:
        Dictionary with ATW-specific diagnostic fields
    """
    return {
        "id": unit.id,
        "name": unit.name,
        "power": unit.power,
        "in_standby_mode": unit.in_standby_mode,
        "operation_mode_zone1": unit.operation_mode_zone1,
        "set_temperature_zone1": unit.set_temperature_zone1,
        "room_temperature_zone1": unit.room_temperature_zone1,
        "operation_mode_zone2": unit.operation_mode_zone2 if unit.has_zone2 else None,
        "set_temperature_zone2": unit.set_temperature_zone2 if unit.has_zone2 else None,
        "room_temperature_zone2": (
            unit.room_temperature_zone2 if unit.has_zone2 else None
        ),
        "tank_water_temperature": unit.tank_water_temperature,
        "set_tank_water_temperature": unit.set_tank_water_temperature,
        "forced_hot_water_mode": unit.forced_hot_water_mode,
        "has_zone2": unit.has_zone2,
    }
