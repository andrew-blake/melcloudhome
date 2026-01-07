"""MELCloud Home API client library."""

from .auth import MELCloudHomeAuth
from .client import MELCloudHomeClient
from .const_ata import (
    FAN_SPEEDS,
    OPERATION_MODES,
    VANE_HORIZONTAL_DIRECTIONS,
    VANE_VERTICAL_DIRECTIONS,
)
from .const_shared import BASE_URL, USER_AGENT
from .exceptions import ApiError, AuthenticationError, MELCloudHomeError
from .models import Building, UserContext
from .models_ata import AirToAirUnit, DeviceCapabilities, Schedule

__all__ = [
    # Constants
    "BASE_URL",
    "FAN_SPEEDS",
    "OPERATION_MODES",
    "USER_AGENT",
    "VANE_HORIZONTAL_DIRECTIONS",
    "VANE_VERTICAL_DIRECTIONS",
    # Models
    "AirToAirUnit",
    "ApiError",
    "AuthenticationError",
    "Building",
    "DeviceCapabilities",
    "MELCloudHomeAuth",
    # Client
    "MELCloudHomeClient",
    # Exceptions
    "MELCloudHomeError",
    "Schedule",
    "UserContext",
]
