---
name: grounding-a-design
description: Use when about to propose, brainstorm, review or revise a design, fix approach or plan for a feature or behaviour change in this repo, including "brief" or "quick" design requests, read-only design tasks, and answering "what are the weak points?"
---

# Grounding a design

Designs that contradict this repo's ADRs, plans, reviews and issue threads get reversed in review. **Read the records before proposing; never pick them from memory, filenames or keywords.**

**No design text before the source inventory exists.** A brief, quick or read-only request shortens the design. The inventory stays.

**Reviewing a design that has a grounding file** (`_claude/plans/*-grounding.md`): audit it. Spot-check its citations, then look for what it couldn't know: newer measurements, logs, code changed since. Skip to step 5.

## Step 1: Check the premise

Read the whole issue thread, newest comment first (`gh issue view N --json body,comments`): it outranks memories and older notes. If the issue cites code, read that code. If it claims something exists or was built, check history (`git log -S<symbol>`, `git show`). Titles state what the reporter wanted. Accounts flagged in the memory `feedback_suspicious_first_time_contributor_detection.md` are noise. If the premise fails, still do step 2.

## Step 2: Inventory every ADR

Terms decide what you find. Use the **feature's** names and the **mechanisms** it touches, e.g. `last_reading|reading_fn`, `_run_startup_fetch`, `cumulative|hour_values`, `should_create_fn`, `pacer|_execute_with_retry`. No generic words (`data`, `sensor`, `building`); `unknown` and `stale` are overloaded here. Run under bash:

```bash
TERMS='your_field|your_symbol|mechanism_symbol'   # replace
for f in docs/decisions/[0-9]*.md; do
  printf '%-60.60s | %s\n' "$(head -1 "$f")" \
    "$(grep -owiE "$TERMS" "$f" | sort | uniq -c | sort -rn | head -5 | tr '\n' ' ')"
done
```

Classify every row: *shapes* (read in full), *constrains* (read matching sections), *context*, *irrelevant*. Zero hits: irrelevant. A hit whose line is plainly unrelated, or only a generic or overloaded word (`switch`, `binary_sensor`, `unknown`): context or irrelevant, with the line quoted. Otherwise read the Decision section before classifying. Follow ADR-to-ADR citations in *shapes* ADRs: a zero-hit ADR they cite gets read too.

## Step 3: Read the other records

Grep each for your terms; read what matches. Skip a source only with the reason stated.

- `docs/architecture.md`, `docs/testing-best-practices.md`, `docs/entities.md`, `docs/api/`
- `_claude/plans/`, `_claude/pr-reviews/`, `_claude/BACKLOG.md` bodies (not `_claude/skill-dev/`): rejected options live here
- **Live measurements** in progress (soaks, logs) and the scripts producing them
- Tests, cassettes, `tools/mock_melcloud_server.py`; memories, checked against code
- **HA core source** for anything HA validates or bridges (service validation, HomeKit, Google); core's `melcloud_home` for parity issues. Not local: read it on GitHub, cite an ADR's recorded verification with its HA version, or label the point *unverified*.

## Step 4: Delegate the reading when it's large

Can't delegate or write files: do steps 2 and 3 yourself and put the inventory first, or first in the design section when the caller sets the format. Otherwise, with more than two *shapes* ADRs or more than one module, give `grounding-agent-prompt.md` (this directory) to a fresh agent.

## Step 5: Design or review from the constraints

Cite the constraint behind each decision. Mark claims *measured*, *read* or *judgement*. Check each weak point before stating it, or label it *unverified*: with no live system to test against, that is a valid outcome. If none survive, the design holds. A design ends with **Open decisions** and their options; a review folds the options into its weak points.

## Rationalisations

| Excuse | Reality |
|---|---|
| "It's brief / quick / read-only" | Someone acts on it. |
| "I know which ADRs matter" | Recall found 5 of 13 on #350. |
| "Filenames show which apply" | Baselines missed constraints that way. |
| "The memory says X" | A dated claim. Check the code. |
| "Stated a risk naming an unopened ADR" | Open it, or label it *unverified*. |
