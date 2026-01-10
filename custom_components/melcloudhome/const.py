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

# Type alias for any device unit (ATA or ATW)
DeviceUnit = Union["AirToAirUnit", "AirToWaterUnit"]

__all__ = [
    "CONF_DEBUG_MODE",
    "DOMAIN",
    "PLATFORMS",
    "UPDATE_INTERVAL",
    "DeviceUnit",
]
