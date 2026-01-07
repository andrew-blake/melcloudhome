"""Constants for the MELCloud Home integration.

This module provides backward compatibility by re-exporting from
const_ata and const_atw.
"""

from collections.abc import Callable
from datetime import timedelta
from functools import wraps
from typing import TYPE_CHECKING, Any, Union

# Re-export ATA constants
from .const_ata import (
    FAN_SPEEDS,
    HA_TO_MELCLOUD_MODE,
    MELCLOUD_TO_HA_MODE,
    VANE_HORIZONTAL_POSITIONS,
    VANE_POSITIONS,
    ATAEntityBase,
)

# Re-export ATW constants
from .const_atw import (
    ATW_PRESET_MODES,
    ATW_TEMP_MAX_DHW,
    ATW_TEMP_MAX_ZONE,
    ATW_TEMP_MIN_DHW,
    ATW_TEMP_MIN_ZONE,
    ATW_TEMP_STEP,
    ATW_TO_HA_PRESET,
    HA_TO_ATW_PRESET,
    WATER_HEATER_FORCED_DHW_TO_HA,
    WATER_HEATER_HA_TO_FORCED_DHW,
    ATWEntityBase,
)

if TYPE_CHECKING:
    from .api.models import AirToAirUnit, AirToWaterUnit

# Type alias for any device unit (ATA or ATW)
DeviceUnit = Union["AirToAirUnit", "AirToWaterUnit"]

# Domain and update interval (shared)
DOMAIN = "melcloudhome"
UPDATE_INTERVAL = timedelta(seconds=60)
PLATFORMS = ["climate"]

# Configuration keys
CONF_DEBUG_MODE = "debug_mode"

__all__ = [
    "ATW_PRESET_MODES",
    "ATW_TEMP_MAX_DHW",
    "ATW_TEMP_MAX_ZONE",
    "ATW_TEMP_MIN_DHW",
    "ATW_TEMP_MIN_ZONE",
    "ATW_TEMP_STEP",
    "ATW_TO_HA_PRESET",
    "CONF_DEBUG_MODE",
    "DOMAIN",
    "FAN_SPEEDS",
    "HA_TO_ATW_PRESET",
    "HA_TO_MELCLOUD_MODE",
    "MELCLOUD_TO_HA_MODE",
    "PLATFORMS",
    "UPDATE_INTERVAL",
    "VANE_HORIZONTAL_POSITIONS",
    "VANE_POSITIONS",
    "WATER_HEATER_FORCED_DHW_TO_HA",
    "WATER_HEATER_HA_TO_FORCED_DHW",
    "ATAEntityBase",
    "ATWEntityBase",
    "DeviceUnit",
    "with_debounced_refresh",
]


# =================================================================
# Shared Decorator
# =================================================================


def with_debounced_refresh(
    delay: float = 2.0,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator for automatic debounced refresh after service calls.

    Eliminates manual refresh calls in every service method (Issue #10).
    Prevents race conditions from rapid service calls.

    Args:
        delay: Seconds to wait before refreshing (default 2.0)

    Usage:
        @with_debounced_refresh()
        async def async_set_temperature(self, **kwargs):
            temperature = kwargs.get("temperature")
            await self.coordinator.async_set_temperature(self._unit_id, temperature)
            # Refresh happens automatically - no manual call needed
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            result = await func(self, *args, **kwargs)
            await self.coordinator.async_request_refresh_debounced(delay)
            return result

        return wrapper

    return decorator
