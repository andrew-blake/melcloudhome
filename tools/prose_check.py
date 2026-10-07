#!/usr/bin/env python3
"""Check drafted prose against this project's writing conventions.

For anything committed to the repo or posted on GitHub: ADRs, README,
CHANGELOG, docs, issue and PR text.

    uv run python tools/prose_check.py docs/decisions/025-homekit-fan-entity.md
    uv run python tools/prose_check.py --stdin --draft < draft.md

Exit code 1 if anything is flagged. Findings are advisory, not all are errors:
labelled list items and bold lead-ins legitimately open short. Read each one.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

# (label, pattern, note). Patterns run against prose with code fences removed.
PATTERNS: list[tuple[str, str, str]] = [
    ("em dash", r"—", "never, in GitHub text or chat"),
    (
        "first person plural",
        r"\b(we|our|ours|us)\b",
        "solo maintainer: 'I' in GitHub text, impersonal in ADRs",
    ),
    (
        "American spelling",
        r"\b(behavior|color|analyz\w+|organiz\w+|recogniz\w+|normaliz(?!e_to_api)\w*"
        r"|initializ\w+|customiz\w+)\b",
        "British English in prose; code identifiers are exempt",
    ),
    ("load-bearing", r"load-bearing", "state the imperative and what breaks"),
    (
        "contrast",
        r"(?i),\s+not\b|\brather than\b|\binstead of\b",
        "state the positive fact; two facts are two sentences",
    ),
    (
        "appeal to a source",
        r"(?i)\bsays so\b",
        "state the fact, or link the source; it can vouch for more than it says",
    ),
    (
        "since",
        r"(?i)\bsince\b",
        "advisory: 'because' if causal; keep only for 'from the time that'",
    ),
    (
        "not-X-but-Y tic",
        r"\b(?:is|are|was|were|it's|its)\s+not\s+[^.,;]{3,40}[,;]\s*(?:it|they|but)\b",
        "AI tic; assert the positive directly",
    ),
    (
        "hollow frame",
        r"(?im)^(?:there (?:is|are) something|worth (?:noting|saying)|in short|"
        r"to be clear|it (?:is|'s) worth|the (?:good|bad) news is)\b",
        "announces a point instead of making it",
    ),
    (
        "first person singular",
        r"\b(?:I(?:'m|'ve|'d|'ll)?|me|myself)\b(?!/)",
        "committed docs are impersonal ('Only HomeKit has been tested'); "
        "posts under the maintainer's account use 'I' (committed files only)",
    ),
    (
        "gitignored reference",
        r"_claude/",
        "dangling for anyone reading on GitHub (committed files only)",
    ),
    (
        "personal or prod reference",
        r"(?i)\b(my |our house|production instance|iphone|andrew's)\b",
        "keep real setups out of committed docs",
    ),
]

# Openers that are legitimately short: list numerals, and bold-labelled items
# such as an Alternatives section's "**Doing nothing** is core's position:".
_OK_SHORT_OPENER = re.compile(r"^(?:\d+\.|\*\*)")


def short_openers(prose: str, limit: int = 9) -> list[str]:
    """Paragraphs opening with a short declarative sentence or fragment."""
    found = []
    for para in prose.split("\n\n"):
        flat = " ".join(para.split())
        if not flat or flat.startswith(("#", "-", "|", ">")):
            continue
        first = re.split(r"(?<=[.:])\s", flat)[0]
        if len(first.split()) <= limit and not _OK_SHORT_OPENER.match(first):
            found.append(first)
    return found


def negative_openers(prose: str) -> list[str]:
    """Sentences opening on a negation where a positive assertion was available.

    Advisory. Strunk and White's "put statements in positive form" allows *not*
    for genuine denial or antithesis, so "Nothing is broken on them" is fine
    when the denial is the point, and "No version gate is added" is not, because
    it makes the reader invert it to learn the actual state. The difference is
    not detectable by pattern, so every hit needs reading.
    """
    found = []
    for para in prose.split("\n\n"):
        flat = " ".join(para.split())
        if not flat or flat.startswith(("#", "|", ">")):
            continue
        for sentence in re.split(r"(?<=[.;:])\s+", flat.lstrip("-* ")):
            if re.match(r"(?:No|Nothing|Neither|None|Never)\b", sentence):
                found.append(sentence)
    return found


def check(text: str, *, committed: bool) -> list[str]:
    prose = re.sub(r"```.*?```", "", text, flags=re.S)
    # A placeholder, not a deletion: identifiers are words, and removing them
    # makes a full sentence look like a fragment to the short-opener check.
    prose = re.sub(r"`[^`\n]+`", "CODE", prose)

    findings = []
    for label, pattern, note in PATTERNS:
        if label in ("gitignored reference", "first person singular") and not committed:
            continue
        for m in re.finditer(pattern, prose):
            line = prose[: m.start()].count("\n") + 1
            findings.append(f"{line}: {label}: {m.group(0).strip()!r} ({note})")

    for opener in short_openers(prose):
        findings.append(
            f"advisory, short opener: {opener!r} "
            "(lead with substance; noisy on technical prose, read each one)"
        )

    for sentence in negative_openers(prose):
        findings.append(
            f"advisory, negative construction: {sentence!r} "
            "(put it in positive form unless the denial is the point)"
        )
    return findings


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("paths", nargs="*", type=pathlib.Path)
    ap.add_argument("--stdin", action="store_true", help="read the draft from stdin")
    ap.add_argument(
        "--draft",
        action="store_true",
        help="not destined for the repo, so skip the gitignored-reference check",
    )
    args = ap.parse_args()

    sources = (
        [("<stdin>", sys.stdin.read())]
        if args.stdin
        else [(str(p), p.read_text()) for p in args.paths]
    )
    if not sources:
        ap.error("give a path or --stdin")

    total = 0
    for name, text in sources:
        findings = check(text, committed=not args.draft)
        total += len(findings)
        print(f"=== {name}: {len(findings) or 'no'} finding(s)")
        for f in findings:
            print(f"  {f}")
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())
