# Release Process

This document describes the release process for MELCloud Home integration, including standard releases, beta releases, and post-release announcements.

**Last Updated:** 2026-04-19

---

## Standard Release Workflow

Releases follow GitHub Flow with branch protection. All changes must go through pull requests.

### Step-by-Step Process

```bash
# 1. Ensure all feature/fix PRs are merged to main
# 2. Create release branch from main
git checkout main
git pull
git checkout -b release/v1.3.4

# 3. Bump version (updates manifest.json and adds CHANGELOG template)
make version-patch   # 1.3.3 → 1.3.4 (bug fixes, security)
make version-minor   # 1.3.3 → 1.4.0 (new features)
make version-major   # 1.4.0 → 2.0.0 (breaking changes)

# 4. Edit CHANGELOG.md to add proper release notes
#    - The make command creates a basic template with "Changed" only
#    - Add appropriate sections: Added, Fixed, Security, Removed, etc.
#    - Follow Keep a Changelog format: https://keepachangelog.com/en/1.0.0/
#    - Write user-facing language (see CHANGELOG Guidelines below)

# 5. Update README.md "What's New" section (REQUIRED, enforced by workflow)
#    - Update the heading to match release version (e.g. "## What's New in v1.3.4")
#    - Add a one-paragraph user-facing summary of key changes
#    - The release workflow validates this matches the tag base version

# 6. Commit the version bump
git add CHANGELOG.md README.md custom_components/melcloudhome/manifest.json
git commit -m "chore: prepare v1.3.4 release"
git push -u origin release/v1.3.4

# 7. Create and merge release PR
gh pr create --title "Release v1.3.4" --body "Prepare v1.3.4 release"
gh pr merge <pr-number> --squash  # or merge via GitHub UI

# 8. Create and push release tag (on main after PR merged)
git checkout main
git pull
make release         # Creates tag and validates CHANGELOG
git push --tags      # Triggers automated GitHub release workflow
```

### Automated GitHub Release Workflow

When you push a tag (e.g., `v1.3.4` or `v1.3.4-beta.1`), GitHub Actions automatically:

1. **Validates**
   - `manifest.json` version matches the tag's **base version** (tag suffix stripped)
   - `README.md` "What's New in vX.Y.Z" heading matches the base version
   - `CHANGELOG.md` has a `[X.Y.Z]` entry for the base version
2. **Tests** - Runs the full test suite (format, lint, type-check, API tests, HA integration tests)
3. **Extracts release notes** - Parses CHANGELOG.md to extract notes for this version
4. **Detects pre-release** - Tags with `-alpha.N` / `-beta.N` / `-rc.N` are marked as pre-release
5. **Creates GitHub release** - Publishes release with extracted notes
6. **Fails if** - Version mismatch (manifest/README/CHANGELOG), missing CHANGELOG entry, or any test failures

The release appears at <https://github.com/andrew-blake/melcloudhome/releases>. Pre-releases are only visible to HACS users who have enabled the "Show beta versions" switch.

---

## CHANGELOG Guidelines

Follow [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format.

### Standard sections (use only these)

- `Added` - New features
- `Changed` - Changes in existing functionality
- `Deprecated` - Soon-to-be removed features
- `Removed` - Removed features
- `Fixed` - Bug fixes
- `Security` - Security fixes

### Rules

- Do NOT use custom sections like "Documentation" or "Technical Details"
- Keep entries concise and factual (no marketing language)
- Date format: YYYY-MM-DD (ISO 8601)

### Write for users, not for git log

Every CHANGELOG line should describe **what the user experiences**, not what changed internally. Ask: "Would a non-technical HA user understand and care about this?"

- ✅ "Energy data not loading"
- ❌ "List-wrapped trendsummary response handling from mobile BFF"
- ✅ "Automatic reconnect when the MELCloud service is unavailable"
- ❌ "Fix deadlock in `_refresh_lock` with concurrent `_refresh_token` calls"
- ✅ "Vertical swing mode silently ignored on units without horizontal vanes (#100)"
- ❌ "Decouple ATA vane axes and use word-form encoding"

### Exclude beta-only regressions from stable changelog

If a bug was introduced AND fixed during the same beta cycle, stable users never experienced it — don't list it as a "Fixed" item in the stable changelog. Users interpret `Fixed` entries as problems they might have hit.

### Don't document automatic migrations

Config entry version bumps, schema migrations, or other changes that are transparent to users don't belong in the changelog. Users expect automatic upgrades.

---

## Beta Release Process

Beta releases let HACS users opt in to pre-release testing via the "Show beta versions" switch.

### When to Use Beta Releases

**✅ Use beta releases for:**

- Experimental features (e.g., ATW heat pump support)
- Hardware-specific features requiring real-world testing
- Breaking changes requiring user validation
- Major refactoring with regression risk
- Bug fixes that can't be reproduced locally (reporter needs a build to verify)

**❌ Don't use beta releases for:**

- Trivial bug fixes verified locally
- Documentation updates
- Internal refactoring (no user impact)
- Small feature additions (low risk)

### Beta version format

**This is the part that trips people up.** Look at past releases for the pattern:

| Artifact | Value |
|---|---|
| `manifest.json` version | `"2.3.1"` (base version, **no suffix**) |
| `CHANGELOG.md` heading | `## [2.3.1] - YYYY-MM-DD` (base version, **no suffix**) |
| `README.md` "What's New" | `## What's New in v2.3.1` (base version) |
| Git tag | `v2.3.1-beta.1` (**beta suffix lives only on the tag**) |

The release workflow strips the suffix from the tag (`sed 's/-.*//'`) to get `BASE_VERSION=2.3.1`, then validates manifest/README/CHANGELOG against that base. If you put `-beta.1` in the CHANGELOG heading, the workflow grep for `[2.3.1]` will fail.

### Creating a Beta Release

```bash
# 1. Create release branch from main
git checkout main && git pull
git checkout -b release/v2.3.1-beta.1

# 2. Bump manifest.json to base version (no suffix)
make version-patch   # or version-minor / version-major
#  or edit manually: "version": "2.3.1"

# 3. Update CHANGELOG.md
#    - Heading: ## [2.3.1] - YYYY-MM-DD  (base version, no -beta.N)
#    - Write user-facing entries per Guidelines above

# 4. Update README.md "What's New" heading to v2.3.1

# 5. Commit, push, open PR
git add custom_components/melcloudhome/manifest.json CHANGELOG.md README.md
git commit -m "chore: prepare v2.3.1-beta.1 release"
git push -u origin release/v2.3.1-beta.1
gh pr create --title "Release v2.3.1-beta.1" --body "Beta release for community testing"
gh pr merge --squash

# 6. Tag and push (the ONLY place beta suffix appears)
git checkout main && git pull
git tag -a v2.3.1-beta.1 -m "Release v2.3.1-beta.1"
git push --tags
# GitHub Actions: detects "-beta." in tag → marks as pre-release
```

### Incrementing Beta Versions (beta.1 → beta.2)

During beta testing, additional fixes land on `main` via normal PRs. When you're ready to cut the next beta:

```bash
# No manifest/README/CHANGELOG changes required — the base version hasn't changed.
# Just add any new fixes as bullets under the existing [2.3.1] CHANGELOG entry
# (do this in the fix PRs or a dedicated CHANGELOG update PR).

git checkout main && git pull
git tag -a v2.3.1-beta.2 -m "Release v2.3.1-beta.2"
git push --tags
```

### Graduating Beta to Stable

Once the beta has shipped long enough to feel safe (typically 3-7 days with active tester feedback):

```bash
# 1. Create a graduation branch
git checkout main && git pull
git checkout -b release/v2.3.1-stable

# 2. Update CHANGELOG.md
#    - Change the date from the beta-cut date to today's date
#    - Review every line: rewrite any internal-speak in user-facing terms
#    - Remove entries for bugs that were introduced AND fixed within the beta
#      (stable users never experienced them)
#    - Add any user-visible changes that landed on main during beta testing

# 3. Update README.md "What's New" paragraph for stable audience
#    - The version number is already correct (v2.3.1)
#    - Rewrite the summary for users who haven't been following the beta

# 4. Commit, push, open PR
git add CHANGELOG.md README.md
git commit -m "chore: update CHANGELOG and README for v2.3.1 stable release"
git push -u origin release/v2.3.1-stable
gh pr create --title "Release v2.3.1" --body "Graduate beta to stable"
gh pr merge --squash

# 5. Tag stable
git checkout main && git pull
make release          # Creates v2.3.1 tag
git push --tags       # GitHub Actions publishes stable release
```

---

## Post-Release Announcements

After any release (stable or beta), post an announcement so users know it's out. Stable releases go to GitHub Discussions. Beta releases go to the tracking issue(s) they fix, plus Discussions if notable.

### GitHub Discussions — Stable Release

Discussions don't have a `gh` CLI command; use the GraphQL API. Repository/category IDs are in `MEMORY.md` (GitHub Discussions for Releases section).

**Template:**

```markdown
# MELCloud Home v2.3.1 Released — [Key Feature Headline]

[One-sentence summary of what this release does for users.]

## What's New

- [User-facing bullet 1]
- [User-facing bullet 2]
- [User-facing bullet 3]

## Upgrade

1. Open HACS → Integrations → MELCloud Home
2. Click the three-dot menu (top right) → **Redownload**
3. Click **Download**
4. Restart Home Assistant

## Links

- [Release notes](https://github.com/andrew-blake/melcloudhome/releases/tag/v2.3.1)
- [Full changelog](https://github.com/andrew-blake/melcloudhome/blob/main/CHANGELOG.md)
- [Report issues](https://github.com/andrew-blake/melcloudhome/issues)

Thanks for using MELCloud Home!
```

### Beta Release — Post to Tracking Issue(s)

For a beta that fixes a specific reported issue, post a comment on that issue pointing users at the beta. Do NOT close the issue.

**Key principles:**

- **Don't claim "resolved"** — users on stable are still affected until stable graduation
- **Don't use internal terminology** — describe the change in user terms (e.g. "mobile app API" not "BFF")
- **Include HACS install steps inline** — most users don't know how to install a specific beta version
- **Acknowledge that waiting for stable is valid** — some users won't want to run a beta

**Template:**

```markdown
**Update: fix available in v2.3.1-beta.1**

[One sentence describing the fix in user-facing terms].
This is available now as a beta release via HACS.

If you're comfortable running a beta, upgrade via HACS — no reconfiguration needed, your existing setup will migrate automatically on restart.

1. Open HACS → Integrations → MELCloud Home
2. Click the three-dot menu (top right) → **Redownload**
3. Select **Need a different version?**
4. Select **v2.3.1-beta.1** and click Download
5. Restart Home Assistant

If you'd prefer to wait for a stable release, the integration will remain unavailable until we promote this to stable (planning a few days of testing first).

Please report any issues with the beta as a new issue.
```

Post this as a single consolidated comment. Edit it rather than posting corrections if details change.

---

## Quick Reference

**Version bump commands:**

```bash
make version-patch   # Bug fixes, security (1.3.3 → 1.3.4)
make version-minor   # New features (1.3.3 → 1.4.0)
make version-major   # Breaking changes (1.4.0 → 2.0.0)
```

**Create stable release:**

```bash
make release         # Creates tag, validates CHANGELOG
git push --tags      # Triggers GitHub Actions
```

**Create beta release:**

- Manifest/CHANGELOG/README use the **base version only** (e.g. `2.3.1`)
- Tag carries the beta suffix: `git tag -a v2.3.1-beta.1 -m ...`
- GitHub Actions auto-detects `-beta.` in the tag and marks it as pre-release

**Graduate beta to stable:**

- No manifest/README version change needed (base version was already correct)
- Update CHANGELOG date, tighten wording, drop beta-only regressions
- Tag `v2.3.1` (no suffix) and push
