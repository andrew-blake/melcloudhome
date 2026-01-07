"""Shared API constants for MELCloud Home API Client.

These constants are used by both ATA and ATW device types.
"""

import os

# API Base URLs
BASE_URL = "https://melcloudhome.com"  # Production
MOCK_BASE_URL = os.getenv(
    "MELCLOUD_MOCK_URL", "http://localhost:8080"
)  # Development (configurable via env var for Docker Compose)

# Required User-Agent to avoid bot detection
# CRITICAL: Must use Chrome User-Agent or requests will be blocked
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"

# Shared API Endpoints (used by both ATA and ATW)
API_USER_CONTEXT = "/api/user/context"
API_TELEMETRY_ACTUAL = "/api/telemetry/actual"
API_TELEMETRY_OPERATION_MODE = "/api/telemetry/operationmode/{unit_id}"
API_TELEMETRY_ENERGY = "/api/telemetry/energy/{unit_id}"

# API Response Field Names (used in parsing responses - shared across device types)
API_FIELD_MEASURE_DATA = "measureData"
API_FIELD_VALUES = "values"
API_FIELD_VALUE = "value"
API_FIELD_BUILDINGS = "buildings"

# Authentication URLs
COGNITO_BASE_URL = "https://live-melcloudhome.auth.eu-west-1.amazoncognito.com"
AUTH_BASE_URL = "https://auth.melcloudhome.com"
COGNITO_DOMAIN_SUFFIX = ".amazoncognito.com"

# Schedule Days (0 = Sunday) - Shared by both ATA and ATW schedules
SCHEDULE_DAY_SUNDAY = 0
SCHEDULE_DAY_MONDAY = 1
SCHEDULE_DAY_TUESDAY = 2
SCHEDULE_DAY_WEDNESDAY = 3
SCHEDULE_DAY_THURSDAY = 4
SCHEDULE_DAY_FRIDAY = 5
SCHEDULE_DAY_SATURDAY = 6

SCHEDULE_DAYS_WEEKDAYS = [1, 2, 3, 4, 5]
SCHEDULE_DAYS_WEEKEND = [0, 6]
SCHEDULE_DAYS_ALL = [0, 1, 2, 3, 4, 5, 6]

__all__ = [
    "API_FIELD_BUILDINGS",
    "API_FIELD_MEASURE_DATA",
    "API_FIELD_VALUE",
    "API_FIELD_VALUES",
    "API_TELEMETRY_ACTUAL",
    "API_TELEMETRY_ENERGY",
    "API_TELEMETRY_OPERATION_MODE",
    "API_USER_CONTEXT",
    "AUTH_BASE_URL",
    "BASE_URL",
    "COGNITO_BASE_URL",
    "COGNITO_DOMAIN_SUFFIX",
    "MOCK_BASE_URL",
    "SCHEDULE_DAYS_ALL",
    "SCHEDULE_DAYS_WEEKDAYS",
    "SCHEDULE_DAYS_WEEKEND",
    "SCHEDULE_DAY_FRIDAY",
    "SCHEDULE_DAY_MONDAY",
    "SCHEDULE_DAY_SATURDAY",
    "SCHEDULE_DAY_SUNDAY",
    "SCHEDULE_DAY_THURSDAY",
    "SCHEDULE_DAY_TUESDAY",
    "SCHEDULE_DAY_WEDNESDAY",
    "USER_AGENT",
]
