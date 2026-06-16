"""VCR-specific test fixtures for API tests.

These fixtures ensure deterministic behavior during VCR cassette
recording and replay.
"""

import hashlib
import secrets

import pytest


@pytest.fixture(autouse=True)
def deterministic_pkce(monkeypatch):
    """Seed secrets.token_bytes for deterministic PKCE during VCR tests.

    Without this, VCR replay fails because match_on includes query strings
    containing random state/code_challenge/request_uri values that differ
    on each run.

    The seeded function produces the same bytes on every run, so PKCE values
    (and therefore query strings) are identical during recording and replay.
    """
    counter = [0]

    def seeded_token_bytes(n=32):
        counter[0] += 1
        return hashlib.sha256(f"vcr-seed-{counter[0]}-{n}".encode()).digest()[:n]

    monkeypatch.setattr(secrets, "token_bytes", seeded_token_bytes)
