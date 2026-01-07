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

__all__ = [
    "API_USER_CONTEXT",
    "BASE_URL",
    "MOCK_BASE_URL",
    "USER_AGENT",
]
