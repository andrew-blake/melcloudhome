"""ATA device diagnostics serialization for MELCloud Home."""

from __future__ import annotations

from typing import Any

from .api.models_ata import AirToAirUnit
from .diagnostics_shared import serialize_outdoor_temp_fields


def serialize_ata_unit(unit: AirToAirUnit) -> dict[str, Any]:
    """Serialize ATA unit for diagnostics.

    Args:
        unit: ATA unit to serialize

    Returns:
        Dictionary with ATA-specific diagnostic fields
    """
    return {
        "id": unit.id,
        "name": "***REDACTED***",
        "power": unit.power,
        "operation_mode": unit.operation_mode,
        "set_temperature": unit.set_temperature,
        "room_temperature": unit.room_temperature,
        "set_fan_speed": unit.set_fan_speed,
        "vane_vertical_direction": unit.vane_vertical_direction,
        "vane_horizontal_direction": unit.vane_horizontal_direction,
        "has_energy_consumed_meter": (
            unit.capabilities.has_energy_consumed_meter if unit.capabilities else None
        ),
        "outdoor_temperature": unit.outdoor_temperature,
        **serialize_outdoor_temp_fields(unit),
    }
