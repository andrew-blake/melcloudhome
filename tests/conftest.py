"""Shared test fixtures."""

import contextlib
import os
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio

# Add custom_components to path to allow direct API imports without loading HA integration
sys.path.insert(0, str(Path(__file__).parent.parent))

from custom_components.melcloudhome.api.auth import MELCloudHomeAuth
from custom_components.melcloudhome.api.client import MELCloudHomeClient


# Configure VCR to filter sensitive data
def scrub_body_string(body_string: str | bytes) -> str | bytes:
    """Scrub sensitive data from a body string or bytes."""
    import re

    # Handle bytes
    if isinstance(body_string, bytes):
        # Decode, scrub, encode back
        try:
            body_str = body_string.decode("utf-8")
            scrubbed_str = scrub_body_string(body_str)
            # scrubbed_str is guaranteed to be str after recursion
            assert isinstance(scrubbed_str, str)
            return scrubbed_str.encode("utf-8")
        except (UnicodeDecodeError, AttributeError):
            # If we can't decode, return as-is
            return body_string

    # Handle strings
    if not isinstance(body_string, str):
        return body_string

    # Scrub email addresses (matches most email formats)
    body_string = re.sub(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "***REDACTED_EMAIL***",
        body_string,
    )
    # Scrub first and last names from JSON
    body_string = re.sub(
        r'"firstname":"[^"]+?"', '"firstname":"***REDACTED***"', body_string
    )
    body_string = re.sub(
        r'"lastname":"[^"]+?"', '"lastname":"***REDACTED***"', body_string
    )
    # Scrub building names
    # Match building name within buildings array context
    body_string = re.sub(
        r'(\\"buildings\\":\[{[^}]*?\\"name\\":\\")[^"]+?(\\")',
        r"\1***REDACTED_BUILDING***\2",
        body_string,
    )
    body_string = re.sub(
        r'("buildings":\[{[^}]*?"name":")([^"]+?)(")',
        r"\1***REDACTED_BUILDING***\3",
        body_string,
    )
    # Scrub device display names (e.g., "givenDisplayName":"Dining Room")
    body_string = re.sub(
        r'"givenDisplayName":"[^"]+?"',
        '"givenDisplayName":"***REDACTED_DEVICE***"',
        body_string,
    )
    # Scrub username field from form data (login request)
    body_string = re.sub(
        r"username=[^&]+", "username=***REDACTED_EMAIL***", body_string
    )

    return body_string


def scrub_sensitive_request(request: Any) -> Any:
    """Scrub sensitive data from request."""
    # VCR passes request as dict during serialization
    if isinstance(request, dict):
        # Scrub request body
        if request.get("body"):
            body = request["body"]
            if isinstance(body, dict) and "string" in body:
                body["string"] = scrub_body_string(body["string"])
            elif isinstance(body, str):
                request["body"] = scrub_body_string(body)
    else:
        # If it's a Request object, try to access body attribute
        if hasattr(request, "body") and request.body and isinstance(request.body, str):
            request.body = scrub_body_string(request.body)

    return request


def scrub_sensitive_data(response: dict[str, Any]) -> dict[str, Any]:
    """Scrub sensitive data from VCR cassettes."""
    # Remove Set-Cookie headers to avoid storing session cookies
    if "set-cookie" in response["headers"]:
        response["headers"]["set-cookie"] = ["***REDACTED***"]

    # Scrub response body
    if response.get("body"):
        body = response["body"]
        if isinstance(body, dict) and "string" in body:
            body["string"] = scrub_body_string(body["string"])

    return response


@pytest.fixture(scope="module")
def vcr_config() -> dict[str, Any]:
    """VCR configuration."""
    return {
        # Store cassettes in tests/cassettes/
        "cassette_library_dir": "tests/cassettes",
        # Match requests on method and URI (ignore body/headers for simplicity)
        "match_on": ["method", "scheme", "host", "port", "path", "query"],
        # Filter out sensitive headers/data
        "filter_headers": [
            ("cookie", "***REDACTED***"),
            ("set-cookie", "***REDACTED***"),
            ("authorization", "***REDACTED***"),
        ],
        # Filter request bodies containing passwords and usernames
        "filter_post_data_parameters": [
            ("username", "***REDACTED_EMAIL***"),
            ("password", "***REDACTED***"),
            ("_csrf", "***REDACTED***"),
        ],
        # Record once, then replay
        "record_mode": "once",
        # Before saving, scrub sensitive data from requests and responses
        "before_record_request": scrub_sensitive_request,
        "before_record_response": scrub_sensitive_data,
    }


@pytest_asyncio.fixture
async def authenticated_client() -> AsyncIterator[MELCloudHomeClient]:
    """Provide an authenticated MELCloud Home client.

    Uses credentials from environment variables:
    - MELCLOUD_USER: Email address
    - MELCLOUD_PASSWORD: Password

    Note: When using VCR, credentials are only needed for initial recording.
    Subsequent runs replay from cassettes.
    """
    username = os.getenv("MELCLOUD_USER", "***PLACEHOLDER***")
    password = os.getenv("MELCLOUD_PASSWORD", "***PLACEHOLDER***")

    # Note: VCR will replay even without real credentials after first recording
    if (
        username == "***PLACEHOLDER***" or password == "***PLACEHOLDER***"
    ) and not os.path.exists("tests/cassettes"):
        pytest.skip(
            "MELCLOUD_USER and MELCLOUD_PASSWORD required for initial cassette recording"
        )

    client = MELCloudHomeClient()
    await client.login(username, password)

    yield client

    # Cleanup
    try:
        await client.logout()
    except Exception:
        pass  # Best effort cleanup
    finally:
        await client.close()


@pytest.fixture
def credentials() -> tuple[str, str]:
    """Provide test credentials from environment variables.

    Returns:
        Tuple of (username, password)

    Raises:
        pytest.skip: If credentials not available for cassette recording
    """
    username = os.getenv("MELCLOUD_USER", "***PLACEHOLDER***")
    password = os.getenv("MELCLOUD_PASSWORD", "***PLACEHOLDER***")

    if username == "***PLACEHOLDER***" or password == "***PLACEHOLDER***":
        pytest.skip("MELCLOUD_USER and MELCLOUD_PASSWORD required for recording")

    return username, password


@pytest_asyncio.fixture
async def authenticated_auth() -> AsyncIterator[MELCloudHomeAuth]:
    """Provide authenticated MELCloudHomeAuth instance.

    Uses credentials from environment variables:
    - MELCLOUD_USER: Email address
    - MELCLOUD_PASSWORD: Password

    Note: When using VCR, credentials are only needed for initial recording.
    Subsequent runs replay from cassettes.
    """
    username = os.getenv("MELCLOUD_USER", "***PLACEHOLDER***")
    password = os.getenv("MELCLOUD_PASSWORD", "***PLACEHOLDER***")

    if username == "***PLACEHOLDER***" or password == "***PLACEHOLDER***":
        pytest.skip("MELCLOUD_USER and MELCLOUD_PASSWORD required for recording")

    auth = MELCloudHomeAuth()
    await auth.login(username, password)

    yield auth

    # Cleanup
    with contextlib.suppress(Exception):
        await auth.close()


@pytest.fixture
def dining_room_unit_id() -> str:
    """ID of the Dining Room unit for testing."""
    return "0efce33f-5847-4042-88eb-aaf3ff6a76db"


@pytest.fixture
def living_room_unit_id() -> str:
    """ID of the Living Room unit for testing."""
    return "bf8d1e84-95cc-44d8-ab9b-25b87a945119"
