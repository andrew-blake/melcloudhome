# Security Tooling

This document describes the automated and manual security tooling used to harden the MELCloud Home repository. It's written to be self-contained — useful for onboarding a new contributor or a fresh Claude Code session with no prior context on this repo.

MELCloud Home is a Home Assistant custom integration distributed via HACS to a public GitHub repository with real-world users. It has no dedicated security team — tooling is chosen to give a solo maintainer high-confidence automated coverage with low noise.

## Overview

| Layer | Tool | Runs |
|---|---|---|
| Local pre-commit | `gitleaks` | Every commit |
| Local pre-commit | `ruff` (with `S` / flake8-bandit rules) | Every commit |
| Local pre-commit | `detect-private-key` (pre-commit-hooks) | Every commit |
| CI | `gitleaks-action` | Every push/PR |
| CI | CodeQL (`security-and-quality` query suite) | Push to main, PR, weekly |
| CI | `osv-scanner` | PR touching lockfile, weekly |
| CI | `zizmor` (GitHub Actions workflow linter) | Push to main, PR, weekly |
| CI | Dependabot | Weekly, GitHub Actions + pip |
| Manual | `zizmor --persona auditor` with GH token | Before any PR touching `.github/workflows/` (https://github.com/andrew-blake/melcloudhome/tree/main/.github/workflows) |
| Manual | VCR cassette scrubbing review | Before committing any new HTTP cassette |
| Process | `SECURITY.md` + GitHub Security Advisories | Vulnerability disclosure intake |

## Pre-commit hooks — `.pre-commit-config.yaml` (https://github.com/andrew-blake/melcloudhome/blob/main/.pre-commit-config.yaml)

Run locally on every commit (and on push for the custom `block-push-to-main` hook):

- **`gitleaks`** (`gitleaks/gitleaks`, pinned `v8.30.1`) — scans staged changes for secret patterns (API keys, tokens, credentials) before they're committed. This is the primary line of defense against committing live credentials.
- **`ruff-check`** with the `S` rule set enabled (flake8-bandit security linting — see below) — catches common Python security anti-patterns (e.g. `subprocess` with `shell=True`, hardcoded passwords, insecure `random`, disabled TLS verification) at lint time, not just in CI.
- **`detect-private-key`** (from `pre-commit/pre-commit-hooks`) — blocks commits containing PEM/SSH private key material.
- **`block-push-to-main`** — a local script hook (`scripts/pre-push-block-main.sh` (https://github.com/andrew-blake/melcloudhome/blob/main/scripts/pre-push-block-main.sh)) that refuses any push targeting `refs/heads/main` directly, enforcing PR-only workflow at the git level rather than relying on remembering to branch.

Install with `pre-commit install` (or via the project's `make` setup). Run all hooks manually with `make pre-commit`.

## Ruff security rules (`pyproject.toml`)

The `[tool.ruff.lint]` section enables rule set `"S"` — this is [flake8-bandit](https://docs.astral.sh/ruff/rules/#flake8-bandit-s) ported into ruff, giving fast, in-editor security linting (e.g. detecting `eval`, weak crypto, insecure deserialization, SSRF-prone patterns) without needing a separate bandit invocation.

Per-file ignores narrow noisy rules to where they're legitimate, e.g.:
- Tests: dummy passwords and bare `assert` (`S101`, `S105`, `S106`)
- Dev/mock tooling (`tools/**`): bind-all interfaces, fixture passwords, non-cryptographic `random`, disabled TLS verify, `subprocess` usage — all intentional in throwaway dev tooling, never shipped to end users
- `telemetry_tracker.py`: one narrowly-scoped `random` ignore for non-security timing jitter (the actual OAuth/PKCE flow uses the `secrets` module, not `random`)

Each ignore should carry an inline justification comment — don't add a blanket per-file ignore without one.

## CI workflows — `.github/workflows/` (https://github.com/andrew-blake/melcloudhome/tree/main/.github/workflows)

### `secret-scan.yml` (https://github.com/andrew-blake/melcloudhome/blob/main/.github/workflows/secret-scan.yml) — gitleaks (CI backstop)
Runs `gitleaks/gitleaks-action` on every push to `main` and every PR. This is the server-side backstop for the local pre-commit hook — catches secrets that slipped through (e.g. a contributor who skipped hook install, or a hook bypass).

### `codeql.yml` (https://github.com/andrew-blake/melcloudhome/blob/main/.github/workflows/codeql.yml) — CodeQL
GitHub's semantic code analysis engine, configured with `queries: security-and-quality` (broader than the default query suite). Runs on push to main, on PRs, and weekly via cron. Findings surface in the repo's Security tab. This repo deliberately runs a **custom** CodeQL workflow rather than GitHub's zero-config "default setup" — the default setup didn't allow the broader query suite or fine-grained scheduling.

Known CodeQL gotcha: the `py/log-injection` query only recognizes a sanitizer function as a barrier if *every* return path in that function is unconditional. A sanitizer with branching logic (e.g. `if cond: return x; return y`) won't be recognized as sanitizing, even if both branches are safe — CodeQL flags call sites as still-tainted. Restructure to a single unconditional return/expression if you need the query to recognize it.

### `dep-audit.yml` (https://github.com/andrew-blake/melcloudhome/blob/main/.github/workflows/dep-audit.yml) — OSV Scanner
Runs `google/osv-scanner-action` against the exported `uv.lock` (converted to `requirements.txt` format for scanning) on a weekly schedule and whenever `uv.lock`/`pyproject.toml` change in a PR. Checks Python dependencies against the [OSV (Open Source Vulnerabilities) database](https://osv.dev/).

Ignored findings (with required justification) live in `osv-scanner.toml` (https://github.com/andrew-blake/melcloudhome/blob/main/osv-scanner.toml) at the repo root, e.g.:
```toml
[[IgnoredVulns]]
id = "GHSA-hg6j-4rv6-33pg"
reason = "aiohttp CVE fixed in 3.14.0. Upgrade blocked on vcrpy incompatibility with aiohttp 3.14 (see issue #124). Dev/CI dep only — end users get HA-bundled aiohttp."
```
Each ignore entry must explain *why* it can't be fixed yet and what would unblock it — these are revisited, not permanent.

Note: `pip-audit` was tried first but is unusable on at least one maintainer's machine (uv-managed Python's `ensurepip` SIGABRTs) — `osv-scanner` was adopted instead and has been reliable.

### `zizmor.yml` (https://github.com/andrew-blake/melcloudhome/blob/main/.github/workflows/zizmor.yml) — GitHub Actions workflow security linter
Runs [zizmor](https://github.com/zizmorcore/zizmor) (via `zizmorcore/zizmor-action`) against all workflow files on push to main, PRs, and weekly. Uploads SARIF results to the Security tab (`security-events: write` permission). Catches GitHub Actions-specific vulnerabilities: unpinned third-party actions, overly broad `permissions:`, secrets exposed to untrusted `pull_request_target` contexts, command injection via unsanitized `${{ }}` expression interpolation, missing `concurrency` groups, etc.

CI runs zizmor in its **default persona**, which only surfaces high-confidence findings. See the manual step below — the default persona is *not* sufficient before merging workflow changes.

### Dependabot — `.github/dependabot.yml` (https://github.com/andrew-blake/melcloudhome/blob/main/.github/dependabot.yml)
Weekly automated PRs for both `github-actions` and `pip` ecosystems. Notable config choices:
- Major version bumps are ignored by default (manual review required) — minor/patch are grouped into one PR to reduce noise.
- 7-day cooldown on new releases before Dependabot opens a PR (avoids pulling in a version that gets yanked days later).
- `gh pr merge` does **not** work on Dependabot PRs that touch workflow files — GitHub restricts the default `GITHUB_TOKEN`'s scope for security reasons. Comment `@dependabot merge` on the PR instead.

## Manual / on-demand tooling

### `zizmor --persona auditor` before workflow PRs
Before merging *any* PR that touches `.github/workflows/` (https://github.com/andrew-blake/melcloudhome/tree/main/.github/workflows), run the full auditor persona locally with a real GitHub token (needed to resolve action SHAs back to tags for the `stale-action-refs` check):

```bash
GH_TOKEN=$(gh auth token) uv run zizmor --persona auditor .
```

The auditor persona adds checks the CI's default persona misses: `stale-action-refs`, `undocumented-permissions`, `anonymous-definition`, `concurrency-limits`. These were missed by CI-only checking on a prior workflow PR — hence the explicit manual step.

`zizmor --fix=all` only auto-fixes `unpinned-uses` (rewriting a tag pin to a SHA pin). Everything else (stale refs, missing concurrency limits, undocumented permissions, anonymous workflow_call inputs) needs a manual edit.

Known acceptable `# zizmor: ignore[rule]` suppressions already in place, each with a justification comment in the workflow file itself:
- `stale-action-refs` on `hacs/action` and `home-assistant/actions/hassfest` — these actions don't publish versioned tags, so pinning to `main`/`master` is intentional, not an oversight.
- `secrets-outside-env` on `CODECOV_TOKEN` in the test workflow — a coverage-reporting token doesn't warrant the overhead of a GitHub deployment environment.

### VCR cassette scrubbing
Integration/API tests record real HTTP interactions as VCR cassettes (`tests/**/cassettes/`). Before committing a *new* or *re-recorded* cassette, confirm scrubbing covers it — cassettes have previously leaked device MAC addresses, building/unit names, email addresses, and OAuth codes/state params into fixture files. Scrubbers live in the VCR test setup and redact these fields, but the gitleaks pre-commit hook is a backstop, not the primary control — a new field added to a captured payload won't match a generic secret pattern, so don't rely on gitleaks alone to catch PII in cassettes.

### Vulnerability disclosure — `SECURITY.md` (https://github.com/andrew-blake/melcloudhome/blob/main/SECURITY.md)
Public vulnerability reporting is routed through **GitHub Security Advisories** (`https://github.com/<owner>/<repo>/security/advisories`), not public issues. Documented response targets: initial response within 72 hours, status update within 14 days. `SECURITY.md` also states the supported-version policy (latest stable only).

## Branch / repo-level protections

These aren't files in the repo but are part of the same hardening effort, configured via GitHub repo settings / API:

- Branch protection on `main`: required status checks (strict mode), but **admin bypass is intentionally left on** — with a single maintainer, `enforce_admins` would block the maintainer's own merges entirely. This is a deliberate accepted trade-off, not an oversight.
- A tag protection ruleset on `v*` prevents accidental deletion or mutation of published release tags.
- GitHub's *default* (zero-config) Code Scanning setup is disabled in favor of the custom `codeql.yml` workflow above — the two are mutually exclusive, and default setup doesn't allow the broader query suite.
- Advanced GHAS-only secret scanning features (non-provider pattern detection, push-time validity checks against live credentials) are **not available** on a free public repository — don't recommend re-enabling them; they require GitHub Advanced Security, which is paid-tier for public repos beyond what's bundled free.

## Things that are knowingly *not* fixed (and why)

Not every flagged issue gets remediated immediately — some are accepted risks or are blocked upstream. When triaging a new finding, check whether it overlaps with one of these before treating it as new:

- A dependency's transitive pin can block a CVE fix even when a patched version exists upstream — e.g. a dev/test-only tool may pin a vulnerable version range of one of its own dependencies. If the vulnerable package is confined to a non-shipped dependency group (check `pyproject.toml` dependency groups — HACS users only get the runtime deps, not dev/test/reverse-engineering groups), this lowers severity to "fix when upstream unblocks it" rather than urgent.
- Low-severity findings tied to maintainer-count trade-offs (like the branch-protection admin bypass above) may be accepted rather than fixed, when fixing would block the only maintainer from shipping at all.

When closing out a finding as "accepted" rather than "fixed," record *why* (not just that it was triaged) somewhere durable — a closed GitHub issue, a `# noqa`/`# zizmor: ignore` comment with reasoning, or an entry in `osv-scanner.toml` — so the next person (or the next audit) doesn't have to re-derive the reasoning from scratch.

## Useful links

- [zizmor](https://github.com/zizmorcore/zizmor) — GitHub Actions security linter
- [zizmor audit personas](https://docs.zizmor.sh/audits/) — what each persona checks
- [gitleaks](https://github.com/gitleaks/gitleaks) — secret scanner
- [OSV Scanner](https://github.com/google/osv-scanner) / [osv.dev](https://osv.dev/) — dependency vulnerability database and scanner
- [CodeQL](https://codeql.github.com/) / [CodeQL query suites](https://codeql.github.com/docs/codeql-cli/query-suites-and-help-files/)
- [ruff flake8-bandit (`S`) rules](https://docs.astral.sh/ruff/rules/#flake8-bandit-s)
- [GitHub Security Advisories](https://docs.github.com/en/code-security/security-advisories)
- [Dependabot configuration options](https://docs.github.com/en/code-security/dependabot/dependabot-version-updates/configuration-options-for-the-dependabot.yml-file)
