"""Shared test fixtures for API tests."""

import contextlib
import hashlib
import os
import re
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pytest
import pytest_asyncio

# Add custom_components to path to allow direct API imports without loading HA integration
sys.path.insert(0, str(Path(__file__).parent.parent))


from custom_components.melcloudhome.api.auth import MELCloudHomeAuth
from custom_components.melcloudhome.api.client import MELCloudHomeClient

# Test timing constants
# These delays were originally added with the assumption that API state changes
# need time to propagate. However, the MELCloud API returns synchronously -
# state updates are immediate. VCR cassettes record requests sequentially
# without timing, so delays are unnecessary during both recording and playback.
#
# Set to 0 for maximum test performance. Can be increased for debugging or
# testing against real hardware if eventual consistency issues are suspected.

# VCR cassette tests - main control operations
# Original: 2 seconds (assumed state propagation delay)
# Actual: Unnecessary - API is synchronous, VCR responses are instant
VCR_OPERATION_DELAY = 0

# VCR cassette tests - cleanup/restore operations
# Original: 1 second (less critical operations)
# Actual: Unnecessary - same reasoning as above
VCR_RESTORE_DELAY = 0

# Mock server tests - localhost HTTP calls
# Original: 0.5 seconds (assumed localhost latency)
# Actual: Unnecessary - mock server responds in ~1-5ms
MOCK_SERVER_DELAY = 0


class NoOpRequestPacer:
    """No-op request pacer for VCR tests.

    VCR tests replay recorded HTTP interactions without actual network calls,
    so rate limiting delays are unnecessary and just slow down tests.
    """

    def __init__(self, min_interval: float = 0.0):
        """Initialize no-op pacer (ignores min_interval)."""
        pass

    async def __aenter__(self):
        """No-op enter (no waiting)."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """No-op exit."""
        return False


# Configure pytest-socket to allow network for E2E tests
@pytest.fixture(scope="session", autouse=True)
def socket_allow_hosts():
    """Allow Docker network IPs and hostnames for E2E tests."""
    # Allow localhost, Docker bridge networks, and melcloud-mock hostname
    return [
        "localhost",
        "127.0.0.1",
        "melcloud-mock",  # Docker Compose service name
        "172.17.0.0/16",
        "172.18.0.0/16",
        "172.19.0.0/16",
    ]


# Configure VCR to filter sensitive data

# Real business-data UUIDs (unit/building/user/system/schedule/scene IDs) get
# swapped for a deterministic placeholder derived from their own hash - same
# input always maps to the same output, so an ID appearing in multiple
# places (e.g. a unit ID returned by GET /context and then used in the URI
# of a later PUT) stays consistent with itself after scrubbing, without
# needing any shared state across the separate before_record hooks VCR
# calls per interaction.
UUID_PATTERN = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
UUID_SENTINEL = "00000000-0000-0000-0000-000000000000"
# Query-string params on auth.melcloudhome.com / Cognito login-flow requests
# (nonce, state, code_challenge, ...) are reproduced byte-for-byte between
# recording and replay by the deterministic_pkce fixture (tests/api/conftest.py)
# seeding the RNG that generates them - VCR's request matching depends on
# that. Only mobile-BFF URIs carry real business-data IDs, so URI scrubbing
# is restricted to that host; body content is never used for VCR matching,
# so it's safe to scrub unconditionally regardless of host.
MOBILE_BFF_HOST = "mobile.bff.melcloudhome.com"


# vcrpy runs before_record_request/before_record_response as part of its
# match pipeline too, not only when actually writing a new interaction - so
# it fires on ordinary cassette replay just as much as on a live recording
# session. Existing cassette content already carries pseudonymized IDs
# (see tools/anonymize_har.py and the retroactive cassette scrub); scrubbing
# again on replay would hash an already-fake ID into a *different* fake ID,
# breaking both VCR's URI matching and any fixture that asserts on a known
# unit ID. Only a real recording session (real credentials, i.e. a
# maintainer intentionally re-recording against a live account) can be
# writing genuine real IDs into a cassette, so gate on that - same check
# `authenticated_client` already uses to decide whether creds are real.
def _recording_session_active() -> bool:
    return os.getenv("MELCLOUD_USER", "***PLACEHOLDER***") != "***PLACEHOLDER***" and (
        os.getenv("MELCLOUD_PASSWORD", "***PLACEHOLDER***") != "***PLACEHOLDER***"
    )


# vcrpy can also call a given hook more than once per request while hunting
# for a match during a single recording session. A pure hash isn't
# idempotent (hash(hash(x)) != hash(x)), so without this cache a value
# that's already one of our own placeholders would get hashed again on the
# second pass. Memoizing both directions makes repeat calls a no-op, same as
# the mapping dict tools/anonymize_har.py uses for the same reason.
_uuid_placeholder_cache: dict[str, str] = {}


def pseudonymize_uuid(value: str) -> str:
    """Deterministically replace a UUID with a stable, non-reversible placeholder."""
    if (
        value.lower() == UUID_SENTINEL
        or value in _uuid_placeholder_cache.values()
        or not _recording_session_active()
    ):
        return value
    if value not in _uuid_placeholder_cache:
        digest = hashlib.sha256(value.lower().encode()).hexdigest()
        placeholder = f"{digest[0:8]}-{digest[8:12]}-{digest[12:16]}-{digest[16:20]}-{digest[20:32]}"
        _uuid_placeholder_cache[value] = placeholder
    return _uuid_placeholder_cache[value]


def scrub_body_string(body_string: str | bytes) -> str | bytes:
    """Scrub sensitive data from a body string or bytes."""
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
    # Scrub building names (more robust pattern)
    # Buildings have "id" followed by "name" at the same level
    # This pattern matches all building names in both buildings and guestBuildings arrays
    body_string = re.sub(
        r'(\\"id\\":\\"[^"]+\\",\\"name\\":\\")[^"]+?(\\")',
        r"\1***REDACTED_BUILDING***\2",
        body_string,
    )
    body_string = re.sub(
        r'("id":"[^"]+","name":")([^"]+?)(")',
        r"\1***REDACTED_BUILDING***\3",
        body_string,
    )
    # Scrub device display names (e.g., "givenDisplayName":"Dining Room")
    body_string = re.sub(
        r'"givenDisplayName":"[^"]+?"',
        '"givenDisplayName":"***REDACTED_DEVICE***"',
        body_string,
    )
    # Scrub hardware identifiers (MAC addresses, EUI-64 interface IDs)
    body_string = re.sub(
        r'"connectedInterfaceIdentifier":"[^"]+?"',
        '"connectedInterfaceIdentifier":"***REDACTED_MAC***"',
        body_string,
    )
    body_string = re.sub(
        r'"macAddress":"[^"]+?"',
        '"macAddress":"***REDACTED_MAC***"',
        body_string,
    )

    # Scrub username field from form data (login request)
    body_string = re.sub(
        r"username=[^&]+", "username=***REDACTED_EMAIL***", body_string
    )

    # Scrub OAuth tokens from JSON responses
    body_string = re.sub(
        r'"access_token":"[^"]+?"', '"access_token":"***REDACTED***"', body_string
    )
    body_string = re.sub(
        r'"refresh_token":"[^"]+?"', '"refresh_token":"***REDACTED***"', body_string
    )
    body_string = re.sub(
        r'"id_token":"[^"]+?"', '"id_token":"***REDACTED***"', body_string
    )

    # Scrub real unit/building/user/system/schedule/scene IDs. Body content
    # isn't part of VCR's request matching, so this is safe unconditionally.
    body_string = UUID_PATTERN.sub(lambda m: pseudonymize_uuid(m.group()), body_string)

    return body_string


def _scrub_uri_ids(uri: str) -> str:
    """Scrub real business-data IDs from a request URI's path.

    Restricted to the mobile BFF host - never touches auth.melcloudhome.com /
    Cognito URIs, whose query strings must stay byte-identical to what
    deterministic_pkce reproduces at replay time.
    """
    if urlparse(uri).hostname != MOBILE_BFF_HOST:
        return uri
    return UUID_PATTERN.sub(lambda m: pseudonymize_uuid(m.group()), uri)


def scrub_sensitive_request(request: Any) -> Any:
    """Scrub sensitive data from request."""
    # VCR passes request as dict during serialization
    if isinstance(request, dict):
        if request.get("uri"):
            request["uri"] = _scrub_uri_ids(request["uri"])
        # Scrub request body
        if request.get("body"):
            body = request["body"]
            if isinstance(body, dict) and "string" in body:
                body["string"] = scrub_body_string(body["string"])
            elif isinstance(body, str):
                request["body"] = scrub_body_string(body)
    else:
        # If it's a Request object, try to access uri/body attributes
        if hasattr(request, "uri") and request.uri:
            request.uri = _scrub_uri_ids(request.uri)
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
        # Store cassettes in tests/api/cassettes/
        "cassette_library_dir": "tests/api/cassettes",
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
            ("code_verifier", "***REDACTED***"),
            ("code", "***REDACTED***"),
            ("refresh_token", "***REDACTED***"),
        ],
        # Record once, then replay
        "record_mode": "once",
        # Before saving, scrub sensitive data from requests and responses
        "before_record_request": scrub_sensitive_request,
        "before_record_response": scrub_sensitive_data,
    }


@pytest_asyncio.fixture
async def authenticated_client(request_pacer) -> AsyncIterator[MELCloudHomeClient]:
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
    ) and not os.path.exists("tests/api/cassettes"):
        pytest.skip(
            "MELCLOUD_USER and MELCLOUD_PASSWORD required for initial cassette recording"
        )

    client = MELCloudHomeClient(request_pacer=request_pacer)
    await client.login(username, password)

    yield client

    # Cleanup
    try:
        await client.logout()
    except Exception:  # noqa: S110 # best-effort logout in test fixture teardown
        pass
    finally:
        await client.close()


@pytest.fixture
def request_pacer():
    """Provide a no-op request pacer for VCR tests.

    VCR tests don't need rate limiting since they replay recorded interactions.
    This eliminates unnecessary delays in test execution.

    Note: RequestPacer automatically disables pacing when PYTEST_CURRENT_TEST
    environment variable is set, so this fixture is mainly for backwards compatibility.
    """
    return NoOpRequestPacer()


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
async def authenticated_auth(request_pacer) -> AsyncIterator[MELCloudHomeAuth]:
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

    auth = MELCloudHomeAuth(request_pacer=request_pacer)
    await auth.login(username, password)

    yield auth

    # Cleanup
    with contextlib.suppress(Exception):
        await auth.close()


@pytest.fixture
def dining_room_unit_id() -> str:
    """ID of the Dining Room unit for testing (pseudonymized, matches cassettes)."""
    return "4c6fd61a-c825-4cb5-300e-3d0ba2c70c01"


@pytest.fixture
def living_room_unit_id() -> str:
    """ID of the Living Room unit for testing (pseudonymized, matches cassettes)."""
    return "40e80e68-f338-e41f-787d-40a7fbaf0624"


@pytest.fixture
def atw_unit_id() -> str:
    """ID of the ATW unit for VCR testing (pseudonymized, matches cassettes)."""
    return "c7f4fe40-34e1-e8b6-ff50-17302662eb00"
