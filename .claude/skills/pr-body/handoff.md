# PR body handoff

Mechanics for producing and handing over a PR body. The writing rules are in
`SKILL.md`.

## Dispatch a fresh agent to write it

Whoever did the work cannot un-know how it went, and that knowledge shapes the
body around the session. So the author gathers, and a subagent writes.

Pass it exactly this:

- the branch, and nothing about its base; the writer resolves that itself
- the paths of the ADR, plan or issue that hold the evidence
- **a list of verified facts** for the Testing section: what ran, what it
  showed, and what was not done

Pass no narrative. Test counts and soak results are facts and belong in the
list; the story of obtaining them is what stays behind. If a fact cannot be
stated without its story, it belongs in the ADR.

**Facts you can establish, establish.** Run `make test-api`,
`make test-integration`, `make test-e2e`, `make pre-commit`, and grep the diff
for what it shows. A suite you ran beats a suite someone told you about, and it
beats a note in a file claiming someone ran it.

**Check the running dev environment before writing any box off.** `docker ps`,
then the integration's own log lines in `ha-melcloud-dev`. Live-API and live-HA
behaviour that no test reproduces is often recorded there (request counts and
their status codes, missing-measure events, startup errors), and it is the one
source of evidence a repo-only search never finds.

**Run them against the branch you are describing.** `git diff` reads refs, so
the diff needs no checkout. Anything you _run_ reads the working tree, so a
suite executed on another branch reports another branch's result.

Compare `git branch --show-current` to the target before running anything. If
they differ, add a worktree rather than moving the shared tree:

```bash
git worktree add ../melcloudhome-worktrees/<name> --detach <branch>
```

Run `uv sync --group reverse-engineering` inside it, run the suites from there,
and remove it when done. A checkout would move a tree that other sessions and a
bind-mounted dev container are using, and each would start seeing different
code. A worktree also holds its branch for the whole run: a single check of the
shared tree proves the branch at that instant, and another session can move it
while your suites are still going.

The body itself is written into the main checkout, whichever worktree the suites
ran in.

The `make test-*` targets pin one Docker project name with fixed container names
and tear it down on exit, so two runs at once kill each other. A suite failing
while another session is testing is an artefact until it fails again on its own.

A claim you cannot establish and were not told stays an unchecked box. That is
the safe direction: an unchecked box understates coverage, and a checked one
that nobody verified is how a reviewer ends up trusting a test that never ran.

A suite the diff cannot reach is a third case, and it gets a reason rather than
a bare box. A bare unchecked box there reads as something forgotten:

```markdown
- [ ] `make test-e2e`: not run; the diff is one dev-only script and a lovelace
      JSON, neither on an e2e path.
```

Take no facts from a file left in `_claude/pr-bodies/` by an earlier session.
Its title cannot tell you whether a human confirmed those lines or a previous
agent asserted them.

The agent reads this skill, composes from the diff, and reports back the path.

## Review what the writer reports

A clean-scoring body can still be wrong on facts, so check the writer's claims
before handing the path on. A checked box can be stale as easily as false,
established once and left standing while the code moved past it, so ask what tip
each check was made against. A **targeted** read of the archive is the tool:
grep the lines a claim is about. A checkbox claim costs eight lines to confirm;
reading the whole thing pulls its prose in for no gain.

One shape of claim cannot be checked that way. "The archive never mentions X" is
an absence over the whole file, and no targeted read establishes it. Either the
writer cites where it looked, or you pass the claim on as the writer's
unverified assertion. Report what you confirmed and what you took on trust,
separately: a summary saying the claims hold, when two of them were never
reachable, is the same defect in your own report that you were checking the body
for.

## Write it to a file

Write to `_claude/pr-bodies/<branch>.md`, with slashes in the branch name
replaced by hyphens, and hand over the path. Review happens in an editor, so
never paste a body into chat instead.

**If that file already exists, stop before opening it.** An edit in progress is
invisible from here: the file is its only record, and `_claude/` is gitignored
so there is no second copy.

1. Note that it exists and when it was written:
   `date -u -r <file> "+%Y-%m-%d %H:%M:%S"`. Do not read its contents **before
   the writer is dispatched**. The decision needs the file's existence, not its
   wording, and a previous body in the caller's context is what shapes the next
   one like it. That risk ends once the writer has composed from the diff.
2. Ask the author whether to archive it. Ask before writing anything, and wait
   for the answer.
3. On yes, rename it to `<name>-old-<timestamp>.md` in the same directory,
   timestamp from `date -u "+%Y-%m-%d-%H-%M-%S"`: UTC, hyphenated so it needs no
   quoting.
4. Dispatch the writer and give it the archived path. Reading the archive is the
   writer's job: it reconciles the old body against the verified facts and
   reports every conflict it finds, which is how a fabrication in the previous
   version gets caught.

On no, the author is keeping their version. Hand back the path and stop. If they
instead want that version edited, it is not a fresh compose: read it, keep their
wording, and change only what they name.

**Timestamps are UTC, from `date -u`.** `stat -f "%Sm" -t "…UTC"` formats local
time and labels it UTC regardless, which reads an hour off under BST. A commit's
time in UTC is
`TZ=UTC git log -1 --format=%cd --date=format-local:"%Y-%m-%d %H:%M:%S"`.

**Whether an existing body is current is a question about the code, not about
neighbouring files.** Compare its mtime to the branch tip's commit time and
check the tree is clean. Another file being newer, whether a fact list or a
sibling branch's body, carries no information about this body at all.

Before handing it over, format it and check it:

```bash
npx --yes prettier@3 --prose-wrap preserve --write _claude/pr-bodies/<name>.md
grep -n '—' _claude/pr-bodies/<name>.md   # em dashes: rewrite, see SKILL.md
```

`--prose-wrap preserve` is deliberate. It fixes list spacing, trailing
whitespace, table alignment and the final newline while leaving long lines
alone, because GitHub reflows paragraphs and a hard-wrapped body reads badly
there. Do not run markdownlint on a body: its line-length rule fires on prose
that is meant to be unwrapped, and following it would break the convention.

## Creating the PR from the file

The H1 is the title, so it is not part of the body. Passing the whole file would
print the title twice:

```bash
BODY=_claude/pr-bodies/<name>.md
gh pr create --base <base> --head <branch> \
  --title "$(sed -n '1s/^# //p' "$BODY")" \
  --body-file <(tail -n +3 "$BODY")
```

`tail -n +3` drops the H1 and the blank line under it. For a stack, create the
lower PR first, put its number in the layer above, then
`gh stack link <lower> <upper>` to register the stack on GitHub: a correct base
chain alone leaves the PRs unlinked in the stack view.

Creating the PR is not part of this skill. Hand over the path and let the author
run it.

End by giving the path to the new file, the archived path if one was made, the
word count against `git diff --shortstat`, and any decision left for the author:
an unchecked box, or a claim you could not verify. Print the body itself only
when asked for it.
