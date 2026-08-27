"""Shared diagnostics serialization helpers for ATA and ATW units."""

from __future__ import annotations

from typing import Any

from .api.models_ata import AirToAirUnit
from .api.models_atw import AirToWaterUnit


def serialize_outdoor_temp_fields(
    unit: AirToAirUnit | AirToWaterUnit,
) -> dict[str, Any]:
    """Serialize the outdoor-temp diagnostic fields shared by ATA and ATW units."""
    reading = unit.outdoor_temp_reading
    return {
        "outdoor_temperature": reading.value if reading else None,
        "has_outdoor_temp_sensor": unit.has_outdoor_temp_sensor,
        "outdoor_temp_recorded_at": (
            reading.recorded_at.isoformat() if reading else None
        ),
        "outdoor_temp_last_error": unit.outdoor_temp_last_error,
        "outdoor_temp_last_error_at": (
            unit.outdoor_temp_last_error_at.isoformat()
            if unit.outdoor_temp_last_error_at
            else None
        ),
        "outdoor_temp_last_poll_at": (
            unit.outdoor_temp_last_poll_at.isoformat()
            if unit.outdoor_temp_last_poll_at
            else None
        ),
    }
