"""Shared diagnostics serialization helpers for ATA and ATW units."""

from __future__ import annotations

import hashlib
from typing import Any

from .api.models_ata import AirToAirUnit
from .api.models_atw import AirToWaterUnit


def pseudonymize_building_id(building_id: str) -> str:
    """A stable stand-in for a building UUID, shaped so a reader sees it's fake.

    Same input, same output across dumps; same shape as the tests'
    pseudonymize_uuid and tools/anonymize_har.py.
    """
    digest = hashlib.sha256(building_id.lower().encode()).hexdigest()[:12]
    return f"aaaaaaaa-aaaa-aaaa-aaaa-{digest}"


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


def serialize_wifi_signal_fields(
    unit: AirToAirUnit | AirToWaterUnit,
) -> dict[str, Any]:
    """Serialize the Wi-Fi signal fields shared by ATA and ATW units (ADR-028).

    An old recorded_at with a recent last_poll_at is a quiet unit; a set
    last_error is a failing fetch.
    """
    reading = unit.wifi_signal_reading
    return {
        "wifi_signal": reading.value if reading else None,
        "wifi_signal_recorded_at": (
            reading.recorded_at.isoformat() if reading else None
        ),
        "wifi_signal_last_poll_at": (
            unit.wifi_signal_last_poll_at.isoformat()
            if unit.wifi_signal_last_poll_at
            else None
        ),
        "wifi_signal_last_error": unit.wifi_signal_last_error,
        "wifi_signal_last_error_at": (
            unit.wifi_signal_last_error_at.isoformat()
            if unit.wifi_signal_last_error_at
            else None
        ),
    }
