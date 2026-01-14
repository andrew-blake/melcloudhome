"""Shared constants for the MELCloud Home integration.

Device-specific constants are in const_ata.py and const_atw.py.
"""

from datetime import timedelta
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from .api.models import AirToAirUnit, AirToWaterUnit

# =================================================================
# Shared Constants
# =================================================================

# Domain and update interval (shared by all device types)
DOMAIN = "melcloudhome"
UPDATE_INTERVAL = timedelta(seconds=60)
PLATFORMS = ["climate"]

# Configuration keys
CONF_DEBUG_MODE = "debug_mode"

# Energy polling configuration
UPDATE_INTERVAL_ENERGY = timedelta(minutes=30)
DATA_LOOKBACK_HOURS_ENERGY = 48

# Telemetry polling configuration
UPDATE_INTERVAL_TELEMETRY = timedelta(minutes=60)  # Hourly (temps change slowly)
DATA_LOOKBACK_HOURS_TELEMETRY = 4  # Sparse data, 4 hours sufficient

# ATW telemetry measures
ATW_TELEMETRY_MEASURES = [
    "flow_temperature",
    "return_temperature",
    "flow_temperature_zone1",
    "return_temperature_zone1",
    "flow_temperature_boiler",
    "return_temperature_boiler",
]

# Type alias for any device unit (ATA or ATW)
DeviceUnit = Union["AirToAirUnit", "AirToWaterUnit"]

__all__ = [
    "ATW_TELEMETRY_MEASURES",
    "CONF_DEBUG_MODE",
    "DATA_LOOKBACK_HOURS_ENERGY",
    "DATA_LOOKBACK_HOURS_TELEMETRY",
    "DOMAIN",
    "PLATFORMS",
    "UPDATE_INTERVAL",
    "UPDATE_INTERVAL_ENERGY",
    "UPDATE_INTERVAL_TELEMETRY",
    "DeviceUnit",
]
