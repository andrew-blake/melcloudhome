"""MELCloud Home API client library."""

from .auth import MELCloudHomeAuth
from .client import MELCloudHomeClient
from .const_shared import BASE_URL, USER_AGENT
from .exceptions import ApiError, AuthenticationError, MELCloudHomeError
from .models import Building, UserContext
from .models_ata import AirToAirCapabilities, AirToAirUnit
from .models_atw import AirToWaterUnit

__all__ = [
    "BASE_URL",
    "USER_AGENT",
    "AirToAirCapabilities",
    "AirToAirUnit",
    "AirToWaterUnit",
    "ApiError",
    "AuthenticationError",
    "Building",
    "MELCloudHomeAuth",
    "MELCloudHomeClient",
    "MELCloudHomeError",
    "UserContext",
]
