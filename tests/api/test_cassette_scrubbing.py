"""Guard against re-committing live session credentials in VCR cassettes.

The VCR scrubber redacts response Set-Cookie headers (tests/conftest.py). If it
regresses — or a cassette is recorded with an unfixed scrubber — the auth flow's
IdentityServer session cookies get committed, and `.AspNetCore.Identity.Application`
authenticates on its own (no password). These are semantic secrets with no
recognisable pattern, so gitleaks can't catch them; this text scan can.
"""

from pathlib import Path

import pytest

CASSETTES = sorted((Path(__file__).parent / "cassettes").glob("*.yaml"))

# Session-credential cookie names that must never appear with a value. The
# recorded Set-Cookie form is `<name>=<value>`; the redacted form is
# `'***REDACTED***'`, which contains no `<name>=`.
FORBIDDEN = (
    ".AspNetCore.Identity.Application=",
    "idsrv.session=",
    "idsrv.external=",
    "csrf-state=",
    "csrf-state-legacy=",
)


@pytest.mark.parametrize("cassette", CASSETTES, ids=lambda p: p.name)
def test_cassette_has_no_session_cookies(cassette: Path) -> None:
    text = cassette.read_text()
    leaked = [name for name in FORBIDDEN if name in text]
    assert not leaked, (
        f"{cassette.name} contains unredacted session cookies {leaked}. "
        "Re-run the scrubber over it (see tests/conftest.py scrub_sensitive_data)."
    )


def test_cassette_corpus_not_empty() -> None:
    # Guards against the glob silently matching nothing and the parametrized
    # test vacuously passing.
    assert CASSETTES, "no cassettes found to scan"
