"""Tests for tools/prose_check.py, the project's prose-convention checker.

Run with: make test-api
"""

from tools.prose_check import check


def test_flags_an_em_dash() -> None:
    assert any(
        "em dash" in f for f in check("A value — the newest one.", committed=True)
    )


def test_ignores_text_inside_code_fences() -> None:
    text = "The poll runs every 30 minutes.\n\n```\nvalue — sample\n```\n"
    assert not any("em dash" in f for f in check(text, committed=True))


def test_a_plain_sentence_has_no_findings() -> None:
    text = "The integration requests one hour of readings for each unit.\n"
    assert check(text, committed=True) == []


def test_flags_a_sentence_that_defers_to_a_source() -> None:
    findings = check(
        "Automations fire on those polls. `docs/entities.md` says so.\n", committed=True
    )
    assert any("appeal to a source" in f for f in findings)


def test_flags_since_for_a_reader_to_check() -> None:
    findings = check(
        "It has run only in the suite, since no fetch failed.\n", committed=True
    )
    assert any(": since: " in f for f in findings)


def test_flags_contrast_markers() -> None:
    for text in (
        "The fetch is paced, not batched.\n",
        "It keeps the value rather than clearing it.\n",
        "It logs a warning instead of an error.\n",
    ):
        assert any("contrast" in f for f in check(text, committed=True)), text
