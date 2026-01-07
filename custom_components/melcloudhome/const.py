"""Shared constants for the MELCloud Home integration.

Device-specific constants are in const_ata.py and const_atw.py.
"""

from collections.abc import Callable
from datetime import timedelta
from functools import wraps
from typing import TYPE_CHECKING, Any, Union

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
