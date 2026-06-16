"""Exceptions for MELCloud Home API Client."""


class MELCloudHomeError(Exception):
    """Base exception for MELCloud Home API."""


class AuthenticationError(MELCloudHomeError):
    """Authentication failed or session expired."""


class ApiError(MELCloudHomeError):
    """API request failed."""


class ServiceUnavailableError(ApiError):
    """MELCloud service is unavailable (HTTP 5xx)."""

    def __init__(self, status_code: int) -> None:
        super().__init__(
            f"MELCloud service unavailable (HTTP {status_code}). "
            "This is a server-side issue — try again later"
        )


class RateLimitError(MELCloudHomeError):
    """Rate limit exceeded."""


class DeviceNotFoundError(MELCloudHomeError):
    """Device not found."""


class InvalidParameterError(MELCloudHomeError):
    """Invalid parameter value."""
