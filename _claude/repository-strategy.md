# Repository Strategy for HACS Distribution

**Date:** 2025-11-17
**Context:** Planning HACS distribution for MELCloud Home integration

---

## Question: Rename Current Repo vs Create New Repo?

### Option 1: Rename Current Repository (Monorepo → HACS)

**Approach:** Rename `home-automation` repo to `melcloudhome`, clean up for HACS

**Pros:**
- ✅ **Preserve Git History:** All commits, ADRs, and development history retained
- ✅ **Less Setup Work:** No need to create new repository from scratch
- ✅ **Single Source of Truth:** One repository, no synchronization needed
- ✅ **Complete Context:** All research and decisions visible
- ✅ **Existing Remote:** Already pushed to GitHub (if applicable)

**Cons:**
- ❌ **Exposes Development History:** All WIP commits, experiments, and iterations visible
- ❌ **Messy History:** Commit messages may not be "public ready"
- ❌ **Contains Non-Integration Files:**
  - Home Assistant configuration files
  - `_claude/` directory with internal notes
  - Deployment scripts with server paths/hostnames
  - `.env` references
  - Testing artifacts
- ❌ **Large Repository:** Unnecessary files bloat the repo
- ❌ **Privacy Concerns:**
  - Git history may contain sensitive paths
  - Server names, IP addresses in commits
  - Internal development notes
  - Building/room names in test data
- ❌ **Professional Appearance:** Looks like a development sandbox, not a polished integration
- ❌ **HACS Validation:** May fail if extra files confuse validation
- ❌ **User Confusion:** HACS users see irrelevant files and structure

**Cleanup Required if Choosing This Option:**
```bash
# Files to remove/gitignore
- automations.yaml
- configuration.yaml
- home-assistant.log
- secrets.yaml
- .storage/
- _claude/ (or move to docs/)
- tools/deploy_custom_component.py (or make generic)
- .env

# Git history cleanup (complex!)
- git filter-branch to remove sensitive commits?
- Risk of breaking history
- Time-consuming
```

**Effort:** 4-6 hours (cleanup + validation)

---

### Option 2: Create New Dedicated Repository (Recommended)

**Approach:** Create fresh `andrew-blake/melcloudhome` repository with clean history

**Pros:**
- ✅ **Clean History:** Fresh start with professional commit messages
- ✅ **Minimal Files:** Only integration code, no cruft
- ✅ **Privacy:** No sensitive paths, server names, or internal notes
- ✅ **Professional:** Looks polished, production-ready
- ✅ **HACS Compliant:** Exact structure HACS expects
- ✅ **User-Friendly:** Users see only what they need
- ✅ **Clear Separation:** Development repo vs distribution repo
- ✅ **Smaller Clone:** Faster for users to download
- ✅ **Easier Maintenance:** No legacy baggage

**Cons:**
- ⚠️ **Loses Git History:** Development history not in HACS repo
  - *Mitigation:* Keep development repo for historical reference
  - *Mitigation:* Link to development repo in docs if needed
- ⚠️ **Initial Setup:** 2-3 hours to create and configure
- ⚠️ **Two Repositories:** Must sync changes between repos
  - *Mitigation:* Automated sync script (simple rsync/copy)
  - *Mitigation:* Development repo becomes WIP environment

**Structure:**
```
melcloudhome/ (new, clean repo)
├── .github/
│   └── workflows/
│       ├── validate.yml
│       └── lint.yml
├── custom_components/
│   └── melcloudhome/
│       ├── __init__.py
│       ├── manifest.json
│       ├── ... (integration files)
│       └── api/  (bundled, KISS principle ✅)
├── tests/ (optional, can link to dev repo)
├── hacs.json
├── README.md (user-focused)
├── LICENSE
└── .gitignore

# Initial commit: "v1.2.0: MELCloud Home integration"
# Clean, professional history from day 1
```

**Effort:** 2-3 hours (setup + initial release)

---

### Option 3: Current Repo Becomes Development Environment

**Approach:** Keep current repo as private/WIP, create separate HACS repo

**This Repository (home-automation):**
- ✅ Remains a development/testing environment
- ✅ Contains all research, ADRs, notes, experiments
- ✅ Deployment scripts, tools, HA config
- ✅ Internal documentation (_claude/)
- ✅ VCR test cassettes with redacted data
- ✅ Complete development history
- ✅ Work-in-progress experiments

**Purpose:**
- Development and testing
- Research and documentation
- API client development
- Integration development before HACS release
- Historical reference

**Workflow:**
```bash
# In development repo
cd /Users/ablake/Development/home-automation/home-assistant
# Make changes, test, iterate
uv run python tools/deploy_custom_component.py melcloudhome --reload

# When ready to release
# Copy to HACS repo
rsync -av --exclude='.git' custom_components/melcloudhome/ \
  ../melcloudhome/custom_components/melcloudhome/

cd ../melcloudhome
git add .
git commit -m "Release v1.2.0: Add sensor platform"
git tag v1.2.0
git push origin main
git push origin v1.2.0
```

---

## Recommendation: Option 2 + Option 3 Combined

**Best Approach:** Create new HACS repo + keep current as dev environment

### Current Repository: Development Environment
- **Name:** Keep as `home-automation` (or rename to `melcloudhome-dev`)
- **Visibility:** Private or public (your choice)
- **Purpose:**
  - Integration development and testing
  - Research and documentation (ADRs, findings)
  - Deployment tools and scripts
  - Home Assistant configuration
  - VCR test cassettes
  - Complete git history
- **Contents:**
  - Everything that's currently here
  - Continue development as usual
  - Tools, scripts, _claude/ directory
  - ADRs, research docs

### New HACS Repository: Distribution
- **Name:** `andrew-blake/melcloudhome`
- **Visibility:** Public
- **Purpose:**
  - HACS distribution
  - User installations
  - Issue tracking
  - Releases and changelog
- **Contents:**
  - `custom_components/melcloudhome/` (with bundled API ✅)
  - HACS configuration files
  - User-facing README
  - LICENSE
  - GitHub Actions for validation
  - Clean, professional git history

### Workflow: Development → Distribution

```bash
# 1. Develop in current repo
cd ~/Development/home-automation/home-assistant
# Make changes, test locally
uv run python tools/deploy_custom_component.py melcloudhome --reload
# Run tests
uv run pytest
# Update docs

# 2. When ready for release, sync to HACS repo
./tools/sync_to_hacs.sh  # Simple script to copy integration files

# 3. Release from HACS repo
cd ~/melcloudhome
git commit -m "Release v1.2.0: Add sensor platform"
git tag -a v1.2.0 -m "Release v1.2.0"
git push origin main --tags
# Create GitHub Release via web UI

# 4. Users install via HACS
# They only see clean HACS repo
```

### Sync Script Example

```bash
#!/bin/bash
# tools/sync_to_hacs.sh

HACS_REPO="$HOME/melcloudhome"

# Copy integration files
rsync -av --delete \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  custom_components/melcloudhome/ \
  "$HACS_REPO/custom_components/melcloudhome/"

# Copy docs (selected)
cp README.md "$HACS_REPO/"
cp LICENSE "$HACS_REPO/"

echo "✅ Synced to HACS repo: $HACS_REPO"
echo "Next steps:"
echo "  cd $HACS_REPO"
echo "  git status"
echo "  git commit -m 'Update: ...'"
echo "  git tag -a vX.Y.Z -m 'Release vX.Y.Z'"
```

---

## API Client: Bundled in HACS Repo (KISS Principle ✅)

**Decision:** Keep API client bundled in `custom_components/melcloudhome/api/`

**Rationale:**
- ✅ **KISS:** Simpler for users (no external dependencies)
- ✅ **Faster to HACS:** No PyPI package needed
- ✅ **Easier maintenance:** One repository
- ✅ **Version coupling:** Integration and API always in sync
- ✅ **No dependency conflicts:** Self-contained

**Structure in HACS Repo:**
```
custom_components/melcloudhome/
├── __init__.py
├── manifest.json
├── config_flow.py
├── coordinator.py
├── climate.py
├── sensor.py           # New in v1.2
├── binary_sensor.py    # New in v1.2
├── diagnostics.py
├── strings.json
├── translations/
└── api/                # Bundled API client (KISS) ✅
    ├── __init__.py
    ├── auth.py
    ├── client.py
    ├── models.py
    ├── exceptions.py
    └── const.py
```

**manifest.json:**
```json
{
  "domain": "melcloudhome",
  "name": "MELCloud Home",
  "requirements": [],  # Empty - no external deps ✅
  ...
}
```

**Future Consideration:**
- If other projects want to use the API client
- If API client needs independent versioning
- If community requests PyPI package
- Then: Extract to separate package (v1.4+)
- Until then: Keep bundled (KISS)

---

## Summary: Recommended Approach

### ✅ Two-Repository Strategy

| Repository | Purpose | Visibility | Contents |
|------------|---------|------------|----------|
| **home-automation** (current) | Development & Testing | Private/Public | Everything: integration, tools, research, HA config, ADRs |
| **melcloudhome** (new) | HACS Distribution | Public | Clean integration only: custom_components/, hacs.json, README |

### ✅ Bundled API Client (KISS)

Keep API client in `custom_components/melcloudhome/api/` (no PyPI package)

### Workflow

1. **Develop** in current repo (all tools, testing, iteration)
2. **Sync** to HACS repo when ready (simple rsync script)
3. **Release** from HACS repo (git tag + GitHub Release)
4. **Users** install via HACS (clean, professional experience)

### Advantages of This Approach

- ✅ Clean, professional HACS repository
- ✅ Complete development environment preserved
- ✅ Privacy maintained (no sensitive info in HACS repo)
- ✅ Simple for users (bundled API, no external deps)
- ✅ Flexible for development (keep all tools and notes)
- ✅ Clear separation of concerns
- ✅ Fast to implement (2-3 hours for HACS repo setup)

### Effort Comparison

| Approach | Setup Effort | Maintenance | Risk | User Experience |
|----------|--------------|-------------|------|-----------------|
| Rename current | 4-6h cleanup | Medium | High (sensitive data) | Poor (messy) |
| New clean repo | 2-3h setup | Low | Low | Excellent |

**Decision: Create new HACS repository (Option 2 + 3 combined)**

---

## Next Steps

1. ✅ Complete v1.2 development in current repo
2. ✅ Create new `andrew-blake/melcloudhome` repository
3. ✅ Set up HACS structure (hacs.json, workflows, README)
4. ✅ Create sync script for easy updates
5. ✅ Initial v1.2.0 release in HACS repo
6. ✅ Test installation as HACS custom repository
7. ✅ Submit to HACS default repository

## Questions Answered

**Q: Will this existing repo become a Home Assistant integration development WIP environment?**

**A: Yes! Perfect use case.** This repo continues as your development environment with all tools, research, documentation, and testing infrastructure. The HACS repo becomes the clean, user-facing distribution channel.

**Q: Initially I think the HACS repo should have the API component as an included module. What do you think? KISS**

**A: Absolutely agree! KISS principle 100%.** Keep the API bundled in `custom_components/melcloudhome/api/` for v1.2+. No PyPI package needed unless there's future demand (v1.4+). Simpler for users, easier to maintain, faster to HACS.

---

## References

- [ADR-001: Bundled API Client](../docs/decisions/001-bundled-api-client.md) - Original bundling decision
- [HACS Documentation](https://hacs.xyz/docs/publish/integration/)
- [Session 9 Research Findings](./_claude/session-9-research-findings.md) - HACS requirements
