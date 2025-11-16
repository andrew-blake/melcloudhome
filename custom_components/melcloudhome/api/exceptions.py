"""Exceptions for MELCloud Home API Client."""


class MELCloudHomeError(Exception):
    """Base exception for MELCloud Home API."""


class AuthenticationError(MELCloudHomeError):
    """Authentication failed or session expired."""


class ApiError(MELCloudHomeError):
    """API request failed."""


class RateLimitError(MELCloudHomeError):
    """Rate limit exceeded."""


class DeviceNotFoundError(MELCloudHomeError):
    """Device not found."""


class InvalidParameterError(MELCloudHomeError):
    """Invalid parameter value."""
