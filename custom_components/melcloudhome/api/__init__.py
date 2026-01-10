"""MELCloud Home API client library."""

from .auth import MELCloudHomeAuth
from .client import MELCloudHomeClient
from .const_shared import BASE_URL, USER_AGENT
from .exceptions import ApiError, AuthenticationError, MELCloudHomeError
from .models import Building, UserContext
from .models_ata import AirToAirUnit, DeviceCapabilities
from .models_atw import AirToWaterUnit

__all__ = [
    "BASE_URL",
    "USER_AGENT",
    "AirToAirUnit",
    "AirToWaterUnit",
    "ApiError",
    "AuthenticationError",
    "Building",
    "DeviceCapabilities",
    "MELCloudHomeAuth",
    "MELCloudHomeClient",
    "MELCloudHomeError",
    "UserContext",
]
