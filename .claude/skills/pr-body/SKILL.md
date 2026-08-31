---
name: pr-body
description:
  Use when composing or revising a pull request description in this repo,
  including PRs that sit in a stack.
---

# PR Body

## Overview

A PR body tells a reviewer what changed, what to check, and what risk they are
accepting by merging. It is written from the diff and the linked decision
record.

## Source contract

Inputs: `git diff <base>..HEAD`, `git diff --shortstat <base>..HEAD`, the linked
ADR/plan/issue, and `.github/pull_request_template.md`.

**Resolve the base from the branch; a caller need not supply it.**
`gh stack view --json` names the branch below this one in a stack; that is the
base. With no stack, the base is the trunk. Sanity-check either answer against
`git log --oneline <base>..HEAD`: the commits shown must be this branch's own
work, and a parent's commits appearing there means the base is wrong.

The session transcript is not an input. A sentence that exists because of
something that happened while the work was done (an investigation, a wrong turn,
a precedent you discovered, an objection raised earlier) belongs in the ADR or
nowhere.

## Handoff

Three rules that bind even if you read nothing else. Detail and reasoning:
**REQUIRED: follow `handoff.md`.**

- A subagent writes the body. The author names the branch and passes the ADR
  paths and a list of verified facts, no narrative. The writer resolves the base
  itself.
- The body goes in a file, never pasted into chat as the deliverable.
- If that file already exists, ask before writing and wait for the answer.

## The shape

Three sections are required, from `.github/pull_request_template.md`. Three more
are conditional, each on something you can check rather than judge. Nothing
else: a named-but-optional section is how a template rots, and Motivation,
Background, Implementation notes and Screenshots all invite the narrative the
source contract removes.

The file opens with the title as an H1, so the one line a reviewer reads first
is reviewed and versioned with the body rather than improvised at the command
line.

Write every paragraph, bullet and checkbox as one unwrapped line. GitHub
renders a newline inside a paragraph as a line break, so hard-wrapped prose
ships its wrapping to the reviewer; the prettier step in `handoff.md` repairs
it, but composing unwrapped is what keeps the diff of a later edit readable.

**Write the title last, from the finished body.** Composing the body is what
establishes what the change is; a title written first frames the body instead,
and you cannot tell whether a title merely repeats the Summary's opening
sentence until that sentence exists.

Rules, all drawn from this repo's merged titles:

- Conventional-commit form, `type(scope): summary`. Lowercase after the colon,
  no trailing period.
- Types in use here: `fix`, `feat`, `refactor`, `perf`, `docs`, `ci`, `chore`,
  `test`. Scope is the area touched: `atw`, `ata`, `sensor`, `coordinator`,
  `i18n`, `mock`, `diagnostics`, `dev`.
- **Type by the effect on a user, not by the shape of the diff.** Something
  broken now working is a `fix` even when the diff adds a lot; #257, #258 and
  #266 are all endpoint or parsing changes typed that way.
- 50 to 75 characters. The merged corpus runs 53 to 82 and clusters there;
  GitHub truncates beyond about 70 in some views.
- Name what changed. The why belongs to the Summary, and the title should not
  restate its first sentence.
- **Try the positive form before reaching for a contrast.** Merged titles do use
  `X, not Y` (#255, #257, #264), but reframing around what is being removed came
  out shorter than the original in every one of those cases, and it names the
  actionable half: `stop trusting live context for outdoor temperature` beats
  `source outdoor temperature from comfort-graph, not live context` by 13
  characters and says the same thing. Keep the contrast only when the positive
  form loses a fact.

```markdown
# fix(atw): source water temperatures from the internaltemperatures report
```

Then, in order:

1. `## Summary`: **required.** What changed and why, from the diff, citing the
   related `#number` inline. One pointer to the ADR, plan or issue that holds
   the evidence.
2. `## Key changes`: **when the diff touches more than five files.** One bullet
   per behaviour a reviewer can verify in the diff. Below that, fold it into the
   Summary.
3. `## What changes for users`: **when a user will notice something**, such as a
   state that reads differently, a discontinuity in recorded history, an
   automation that has to adapt. One section, one bullet each, with the remedy.
   Internal changes nobody outside the repo can observe do not belong here.
4. `## Risks accepted`: **when merging accepts a known risk**, such as an
   assumption shipped without evidence, a downside taken deliberately. Say what
   the risk is, what it costs if it turns out wrong, how it would be detected,
   and how it would be undone. This is what a maintainer hunts for months later
   when the risk lands.
5. `## AI Disclosure`: **required.** Reproduce the template's two boxes and
   leave **both unchecked**. The second reads "I reviewed and ran the change
   myself", a claim about the human author that nobody else can make for them.
   They tick one before opening the PR.
6. `## Testing`: **required.** What ran and what it showed. An unchecked box for
   anything a reviewer would otherwise assume was covered.

A checked box asserts the claim holds at the current tip. Something verified
before later commits landed is unverified again, so a box can age out of true
without anyone editing it.

**Word every box as the claim it asserts, never as a negation.** Ticking is what
makes the claim true, so `- [ ] No prod soak` inverts its own meaning the moment
someone ticks it. Write the claim, `- [ ] Prod deployment and soak`, and put why
it is unticked after it, as a note that gets deleted when the box is earned.

An unticked box says what **you** did not verify. It does not assert that nobody
did: other sessions, other machines and runs that left no artefact in the repo
are all invisible from here. "Not run here" is warranted; "has not happened" is
not.

## When the base is another branch

If `<base>` is not the trunk, the PR sits in a stack. Four things follow:

- Diff against the parent: `git diff <parent>..HEAD`. Diffing against the trunk
  shows the parent's changes as if they were yours.
- The Summary's first line names what this builds on and what it needs from it.
  One line. The parent PR describes itself, so restating any of its content
  belongs nowhere. Cite the parent's PR number if it has one; before that, name
  the branch and expect a number to replace it.
- **Write a stack bottom-up.** The lower layer needs nothing from the layer
  above, so it is drafted, opened and numbered first, which is what gives the
  layer above both a number to cite and a body to measure against.
- Compare this body's `wc -w` against the parent's before handing it over. A
  layer smaller than its parent gets a shorter body.

## Name the category

State why a fact matters. Never restate the fact.

| write this                                       | not this                        |
| ------------------------------------------------ | ------------------------------- |
| for real devices the prefix is the building name | one of them is a street address |
| the cassette carries account identifiers         | the account is `<address>`      |
| the log names a shared device                    | the device is `<name>`          |

A body is public the moment the PR opens. Applies to device names, building
names, addresses, account identifiers and UUIDs.

## Evidence lives in the record

Measurements, probe counts, failure rates, rejected alternatives and provenance
go in the ADR or plan. The body carries the conclusion and a link. A number
repeated in both places dates the body the moment it is re-measured.

Design rationale for a tool lives in that tool's docstring.

## Proportion

Measure the prose sections. The Testing list and the disclosure boxes sit
outside the count: their length tracks how much was verified, and trimming them
to hit a number is the one cut that loses a reviewer something.

Weigh it against review surface rather than raw lines. Deleted fixtures,
cassettes and generated files inflate `--shortstat` without adding anything to
read, so count the files someone must actually review.

Compare like with like. The merged corpus predates `What changes for users` and
`Risks accepted`, so its numbers describe `Summary` plus `Key changes` and
nothing else: about 40 words for a two-line i18n fix (#255, 2 files), 200 for a
20-file endpoint change (#257), 390 for an 11-file feature (#268), 550 for a
33-file refactor (#269). Hold those two sections against that range.

The other two sections are justified by whether their content is real, not by a
word budget: a user-visible change nobody would otherwise notice, and a risk
somebody inherits by merging, are both worth their length. Cutting them to hit a
number removes the part of the body a reviewer most needs.

So when a body reads long, the question is whether `Summary` and `Key changes`
have drifted past the corpus for a comparable review surface. File count
predicts length poorly, and padding to reach a number is always wrong.

Across a stack, compare against the parent's body. With no parent body written
yet, use the calibration above and say in your handover that the comparison was
unavailable.

## Common mistakes

Observed in baseline testing, every one of these from an author who had the diff
in front of them.

| mistake                                                                                                     | fix                                                                                                                            |
| ----------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| Restating a sensitive value the reason merely refers to                                                     | Name the category                                                                                                              |
| Opening with how the problem was discovered                                                                 | Open with what changed                                                                                                         |
| Reproducing the ADR's measurement table                                                                     | One clause plus the link                                                                                                       |
| "moved from X to Y", "previously", "used to"                                                                | State current behaviour only                                                                                                   |
| Any negation carrying the emphasis: `X, not Y`, `X rather than Y`, `isn't an option`, `is not the argument` | Say what is true, positively. Contrast two real options by naming both                                                         |
| Rebutting a position the PR never raises                                                                    | Delete the paragraph                                                                                                           |
| Explaining why a card, flag or graph exists                                                                 | Put it in the docstring                                                                                                        |
| Arguing for the method instead of reporting what ran                                                        | Say what ran and what it showed. A Testing preamble that defends the approach is commentary                                    |
| An em dash                                                                                                  | A colon where it introduces an elaboration, commas or brackets where it wraps an aside. A body full of them reads as generated |
| Hard-wrapping paragraphs or bullets                                                                         | One line each; GitHub renders the wrap as line breaks                                                                          |
| Every box checked when verification is partial                                                              | Leave the box unchecked and say why                                                                                            |
| Overwriting a body that was handed over for editing                                                         | Read it first, keep the author's wording, report the change                                                                    |
