"""Shared API constants for MELCloud Home API Client.

These constants are used by both ATA and ATW device types.
"""

import os

# API Base URLs
BASE_URL = "https://mobile.bff.melcloudhome.com"  # Production (mobile BFF)
MOCK_BASE_URL = os.getenv(
    "MELCLOUD_MOCK_URL", "http://localhost:8080"
)  # Development (configurable via env var for Docker Compose)

# User-Agent matching the mobile app
USER_AGENT = "MonitorAndControl.App.Mobile/52 CFNetwork/3860.400.51 Darwin/25.3.0"

# Shared API Endpoints (mobile BFF paths)
API_USER_CONTEXT = "/context"
API_TELEMETRY_ENERGY = "/telemetry/telemetry/energy/{unit_id}"
API_TELEMETRY_ACTUAL = "/telemetry/telemetry/actual/{unit_id}"
API_REPORT_TRENDSUMMARY = "/report/v1/trendsummary"

# API Response Field Names (used in parsing responses - shared across device types)
API_FIELD_MEASURE_DATA = "measureData"
API_FIELD_VALUES = "values"
API_FIELD_VALUE = "value"
API_FIELD_BUILDINGS = "buildings"

# OAuth Configuration
AUTH_BASE_URL = "https://auth.melcloudhome.com"
OAUTH_CLIENT_ID = "homemobile"
OAUTH_REDIRECT_URI = "melcloudhome://"
OAUTH_SCOPES = "openid profile email offline_access IdentityServerApi"

# Cognito (federated via IdentityServer, needed for credential submission)
COGNITO_BASE_URL = "https://live-melcloudhome.auth.eu-west-1.amazoncognito.com"
COGNITO_DOMAIN_SUFFIX = ".amazoncognito.com"

__all__ = [
    "API_FIELD_BUILDINGS",
    "API_FIELD_MEASURE_DATA",
    "API_FIELD_VALUE",
    "API_FIELD_VALUES",
    "API_REPORT_TRENDSUMMARY",
    "API_TELEMETRY_ACTUAL",
    "API_TELEMETRY_ENERGY",
    "API_USER_CONTEXT",
    "AUTH_BASE_URL",
    "BASE_URL",
    "COGNITO_BASE_URL",
    "COGNITO_DOMAIN_SUFFIX",
    "MOCK_BASE_URL",
    "OAUTH_CLIENT_ID",
    "OAUTH_REDIRECT_URI",
    "OAUTH_SCOPES",
    "USER_AGENT",
]
