# Grounding agent prompt

Fill the `<…>` slots and dispatch to a fresh general-purpose agent. Keep every section.

---

You are doing a READ-ONLY grounding pass for a design in the melcloudhome repo at `<repo path>`. Edit no file except the output file below. Do not run tests, deploy, call MELCloud or Home Assistant APIs, or post to GitHub.

## Why
Find every constraint the repo already records that bears on this design, with citations, before the design is written. You are not designing. You report what the records say.

## The feature
<issue number, the problem, the evidence, and any public commitment already made>

## Design under test
<the current proposal, or "none yet: report constraints for the problem">

## Sources
0. **Premise first.** Check the issue's claims against current code and history (`git log -S`, `git show`).
1. **ADRs.** Run the inventory loop from the grounding-a-design skill (bash) over ALL of `docs/decisions/[0-9]*.md` with these terms: `<feature terms>|<mechanism terms>` (word-bounded, `grep -owiE`; never generic words). Zero hits = irrelevant; any hits = read the Decision section before classifying. Classify every ADR as shapes / constrains / context / irrelevant. Read *shapes* in full and *constrains* in the relevant sections. Never select ADRs by filename.
2. **Docs:** `docs/architecture.md`, `docs/testing-best-practices.md`, `docs/entities.md`, every `docs/api/` file matching the terms, `CLAUDE.md`, `CONTRIBUTING.md`.
3. **Records:** grep the bodies of `_claude/plans/`, `_claude/pr-reviews/` and `_claude/BACKLOG.md` for the terms (exclude `_claude/skill-dev/`). Record anything rejected and why.
4. **Code:** `<modules the design touches>` and the code they wire into.
5. **Tests and tools:** tests, cassettes and `tools/` files matching the terms; how similar features are tested.
6. **GitHub:** `<issues and PRs>`, plus any they link. Check the issue's premise against current code (`git log -S`). Ignore accounts flagged in the memory `feedback_suspicious_first_time_contributor_detection.md`.
7. **Memories** in the project's Claude memory directory matching the terms: claims to check against the code.
8. **HA core source and developer docs** for anything HA validates or bridges (service validation, HomeKit, Google), and HA core's `melcloud_home` integration and its library for parity questions. Quote the source.

## Output
Write ONE file: `_claude/plans/<YYYY-MM-DD>-<topic>-grounding.md`, with these sections in this order:

1. **ADR inventory**: every ADR with title, status, term hits and classification.
2. **Constraints**: numbered. Each one: the constraint in one sentence; citation (file:line, ADR + section, issue/PR, URL); kind (`decision`, `convention`, `rejected-option`, `fact`); effect on the design (`supports`, `conflicts` with what exactly, or `new`).
3. **Conflicts with the design under test**: each restated with the design element it hits.
4. **Gaps**: tests, docs, mock server, tooling and behaviour the design doesn't cover yet.
5. **Sources read that held nothing relevant**: one line each.
6. **Open decisions**: what the records leave undecided, each with options.

Mark anything inferred rather than read as `(inferred)`. Don't soften a conflict. If two sources disagree, report both. British English, no em dashes.

Reply with: the file path, the number of constraints, the conflicts in full, and the five most important gaps.
