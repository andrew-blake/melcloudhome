# Release Process

This document describes the release process for MELCloud Home integration, including standard releases and beta releases for community testing.

**Last Updated:** 2026-01-25

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

# 3. Bump version and create CHANGELOG template
make version-patch   # 1.3.3 → 1.3.4 (bug fixes, security)
make version-minor   # 1.3.3 → 1.4.0 (new features)
make version-major   # 1.4.0 → 2.0.0 (breaking changes)
# This updates manifest.json and adds a basic CHANGELOG template

# 4. Edit CHANGELOG.md to add proper release notes
#    The make command creates a basic template with just "Changed" section
#    Manually add appropriate sections: Added, Fixed, Security, Removed, etc.
#    Follow Keep a Changelog format: https://keepachangelog.com/en/1.0.0/

# 5. Commit the version bump
git add CHANGELOG.md custom_components/melcloudhome/manifest.json
git commit -m "chore: Prepare v1.3.4 release"
git push -u origin release/v1.3.4

# 6. Create and merge release PR
gh pr create --title "Release v1.3.4" --body "Prepare v1.3.4 release"
gh pr merge <pr-number> --squash  # or merge via GitHub UI

# 7. Create and push release tag (on main after PR merged)
git checkout main
git pull
make release         # Creates tag and validates CHANGELOG
git push --tags      # Triggers automated GitHub release workflow
```

### Automated GitHub Release Workflow

When you push a tag (e.g., `v1.3.4`), GitHub Actions automatically:

1. **Validates** - Checks manifest.json version matches tag, verifies CHANGELOG entry exists
2. **Tests** - Runs full test suite (format, lint, type-check, API tests, HA integration tests)
3. **Extracts release notes** - Parses CHANGELOG.md to extract notes for this version
4. **Creates GitHub release** - Publishes release with extracted notes
5. **Fails if** - Version mismatch, missing CHANGELOG entry, or any test failures

The release appears at: <https://github.com/andrew-blake/melcloudhome/releases>

---

## CHANGELOG Guidelines

Follow [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format:

**Standard sections (use only these):**

- `Added` - New features
- `Changed` - Changes in existing functionality
- `Deprecated` - Soon-to-be removed features
- `Removed` - Removed features
- `Fixed` - Bug fixes
- `Security` - Security fixes

**Rules:**

- Do NOT use custom sections like "Documentation" or "Technical Details"
- Keep entries concise and factual (no marketing language)
- Date format: YYYY-MM-DD (ISO 8601)
- The `make version-*` command creates a template with "Changed" section only - add other sections as needed

---

## Beta Release Process

Beta releases enable HACS users to opt-in to pre-release testing. Use for experimental features, hardware-specific support, or breaking changes requiring community validation.

### When to Use Beta Releases

**✅ Use beta releases for:**

- Experimental features (e.g., ATW heat pump support)
- Hardware-specific features requiring real-world testing
- Breaking changes requiring user validation
- Major refactoring with regression risk

**❌ Don't use beta releases for:**

- Bug fixes (use patch: `make version-patch`)
- Documentation updates
- Internal refactoring (no user impact)
- Small feature additions (low risk)

### Creating a Beta Release

```bash
# 1. Edit manifest.json manually
# Change version: "1.3.4" → "2.0.0-beta.1"

# 2. Update CHANGELOG.md
# Add new entry: ## [2.0.0-beta.1] - YYYY-MM-DD
# Mark as beta and include HACS instructions (see template below)

# 3. Commit and create PR
git add custom_components/melcloudhome/manifest.json CHANGELOG.md
git commit -m "chore: Release 2.0.0-beta.1"
git push -u origin feature/atw-beta
gh pr create --title "Beta: ATW heat pump support" \
  --body "Pre-release for community testing"
gh pr merge --squash

# 4. Tag and release
git checkout main && git pull
git tag -a v2.0.0-beta.1 -m "Release v2.0.0-beta.1"
git push --tags
# GitHub Actions automatically:
# - Detects "-beta." in version
# - Marks as pre-release (HACS users with beta switch see it)
# - Validates, tests, and publishes
```

### Beta CHANGELOG Template

Include this in beta CHANGELOG entries:

```markdown
## [2.0.0-beta.1] - YYYY-MM-DD

**This is a beta release for community testing.**

### Added
- ATW heat pump support with zone control
- Energy monitoring for compatible devices

### Changed
- API client architecture to support multi-device types

**How to test this beta:**
1. Enable beta releases in HACS:
   - Go to **Settings → Devices & Services → Integrations → HACS**
   - Find **MELCloud Home** in your repository list
   - Enable the **"Show beta versions"** switch entity (disabled by default)
2. Install this beta version (will appear in available updates)
3. Report issues: https://github.com/andrew-blake/melcloudhome/issues

**What to test:**
- Add ATW device and verify zone control works
- Check energy sensors appear for compatible devices
- Test automation with new entities
```

### Incrementing Beta Versions

```bash
# Fix bugs reported by beta testers, then:
# 1. Edit manifest.json: "2.0.0-beta.1" → "2.0.0-beta.2"
# 2. Update CHANGELOG.md with fixes
# 3. Commit, merge PR, tag as v2.0.0-beta.2
# 4. Push tags
```

### Graduating Beta to Stable

```bash
# After successful beta testing:
# 1. Edit manifest.json: "2.0.0-beta.2" → "2.0.0"
# 2. Update CHANGELOG.md:
#    - Add ## [2.0.0] entry
#    - Consolidate beta notes into stable release notes
# 3. Commit, merge PR, tag as v2.0.0
# 4. Push tags
# GitHub Actions detects stable version (no suffix)
# All HACS users see the update
```

---

## Quick Reference

**Version bump commands:**

```bash
make version-patch   # Bug fixes, security (1.3.3 → 1.3.4)
make version-minor   # New features (1.3.3 → 1.4.0)
make version-major   # Breaking changes (1.4.0 → 2.0.0)
```

**Create release:**

```bash
make release         # Creates tag, validates CHANGELOG
git push --tags      # Triggers GitHub Actions
```

**Beta release:**

- Manually edit `manifest.json` with `-beta.N` suffix
- Tag with same version: `v2.0.0-beta.1`
- GitHub Actions auto-detects and marks as pre-release
