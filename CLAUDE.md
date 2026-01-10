# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This repository is the MELCloud Home integration for Home Assistant, distributed via HACS.

**Repository:** <https://github.com/andrew-blake/melcloudhome>

**What's included:**

1. **MELCloud Home Integration** - Custom component with full HVAC control and energy monitoring
2. **API Client** - Bundled API client library in `custom_components/melcloudhome/api/`
3. **Tests** - Comprehensive test suite with pytest and VCR cassettes
4. **Documentation** - Architecture decision records (ADRs), API reference, research notes
5. **Development Tools** - Deployment scripts, debugging utilities

## Remote System Access

The Home Assistant system runs in Docker on a remote server:

```bash
# Connect to the system
ssh ha

# Run commands with sudo
ssh ha "sudo <command>"

# Access containers
ssh ha "sudo docker ps"
ssh ha "sudo docker logs homeassistant --tail 100"
ssh ha "sudo docker exec homeassistant <command>"
```

## Diagnostics and Troubleshooting

When diagnosing issues:

1. **Check container status:** `ssh ha "sudo docker ps"`
2. **View logs:** `ssh ha "sudo docker logs homeassistant --tail 500"`
3. **Filter errors:** `ssh ha "sudo docker logs homeassistant --tail 500 2>&1 | grep -i error | tail -50"`
4. **Check integration files:** `ssh ha "sudo docker exec homeassistant ls -la /config/"`

See `.claude/skills/home-assistant-diagnostics/SKILL.md` for detailed diagnostic workflows and common issue patterns.

## MELCloud Home Integration Development

### Project Structure

```text
custom_components/melcloudhome/  # Custom component (bundled approach)
├── api/                         # Bundled API client library (see ADR-001)
│                                # - Facade pattern with device-specific clients (see ADR-011)
│                                # - ATA (air-to-air) and ATW (air-to-water) implementations
│                                # - Models, constants, auth, parsing utilities
├── *.py                         # Platform implementations
│                                # - climate, sensor, binary_sensor, water_heater, switch
│                                # - Router pattern: base files dispatch to _ata.py/_atw.py modules
│                                # - See ADR-011, ADR-012 for multi-device architecture
└── ...                          # Standard HA integration files
                                 # (config_flow, coordinator, diagnostics, helpers, etc.)

docs/
├── api/                         # API documentation
│   ├── ata-api-reference.md     # Air-to-Air API reference
│   ├── atw-api-reference.md     # Air-to-Water API reference
│   ├── device-type-comparison.md # ATA vs ATW comparison
│   └── melcloudhome-telemetry-endpoints.md
├── decisions/                   # Architecture Decision Records (ADRs)
├── research/                    # Current research documents
│   └── REVERSE_ENGINEERING.md   # Comprehensive reverse engineering guide
├── archive/research/            # Historical research and planning documents
├── testing-*.md                 # Testing standards and strategy
└── integration-review.md        # Integration review notes

tests/                           # Test suite with VCR cassettes
├── api/                         # API tests (no Docker needed)
└── integration/                 # HA integration tests (Docker required)

tools/                           # Development and deployment tools
├── reverse-engineering/         # API discovery tools (Chrome overrides, proxying)
└── deploy_to_ha.py              # Automated deployment script

openapi.yaml                     # OpenAPI 3.0.3 specification
_claude/                         # Session notes (local only, not in git)
```

### Key Decisions

- **Bundled API Client:** Library code in `api/` subfolder (KISS/YAGNI) - See [ADR-001](docs/decisions/001-bundled-api-client.md)
- **No PyPI Package:** Can migrate later if needed
- **Type Safe:** Using mypy with strict settings
- **Formatted:** Ruff for linting & formatting

### Development Workflow

**IMPORTANT: This repository uses GitHub Flow - always work in feature branches, never commit directly to main.**

```bash
# Setup
uv sync                          # Install dependencies
source .venv/bin/activate        # Activate virtual environment

# Code Quality
make format                      # Format with ruff
make lint                        # Lint with ruff
make type-check                  # Type check with mypy
make all                         # Run all checks

# Pre-commit hooks run automatically on git commit
# IMPORTANT: Always run pre-commit in advance and fix up errors before attempting to git commit
make pre-commit                      # Run pre-commit checks manually (recommended)
uv run pre-commit run --all-files    # Or run directly with uv

# Local Development Environment (Primary Workflow)
# Use this for daily development and testing with mock API
make dev-up          # Start dev environment
make dev-restart     # Restart HA after code changes
make dev-logs        # View Home Assistant logs
make dev-reset       # Reset (clear entity registry, fresh start)
make dev-rebuild     # Rebuild mock server image
make dev-down        # Stop dev environment

# See DEV-SETUP.md for complete guide:
# - Mock MELCloud API with 2 ATA + 1 ATW devices
# - Home Assistant on http://localhost:8123 (dev/dev)
# - Auto-skip onboarding, debug logging enabled

# Testing
make test                        # Run API tests (no Docker needed)
make test-ha                     # Run HA integration tests in Docker
pytest tests/api/ -v             # Run API tests only (local)
pytest tests/ --cov=custom_components.melcloudhome --cov-report term-missing -vv  # With coverage

# Integration tests require Docker (uses pytest-homeassistant-custom-component)
# Docker runs tests from tests/integration directory to avoid pytest_plugins error
# See tests/integration/Dockerfile for test environment configuration

# Production Deployment (Pre-Release Testing ONLY)
# Use this ONLY for final integration testing before releases
make deploy          # Deploy to production HA
make deploy-test     # Deploy + test via API
make deploy-watch    # Deploy + watch logs
```

### API Reverse Engineering Tools

**Purpose:** Understand MELCloud API behavior by observing the official web application without needing real hardware.

**When to use:**
- User reports unsupported device (e.g., different controller type)
- Need to verify undocumented API behavior
- Want to contribute device support without owning hardware
- Resolving API mapping questions

**Tools location:** `tools/reverse-engineering/`

**Quick reference:**

```bash
# Chrome Local Overrides (inject API data into official web app)
# 1. DevTools (F12) → Sources → Overrides
# 2. Select: tools/reverse-engineering/chrome_override
# 3. Edit: chrome_override/melcloudhome.com/api/user/context
# 4. Visit: https://melcloudhome.com
# 5. Observe what official app displays

# Request Proxying (capture control commands)
# 1. Start mock server: make dev-up
# 2. Chrome console on melcloudhome.com
# 3. Paste: tools/reverse-engineering/proxy_mutations.js
# 4. Run: blockMutations()
# 5. Use web app, check logs for captured payloads
```

**Full guides:**
- Quick start: `tools/reverse-engineering/README.md`
- Comprehensive: `docs/research/REVERSE_ENGINEERING.md`

### Branching Strategy (GitHub Flow)

**Always use feature branches for development:**

```bash
# Create feature branch
git checkout -b feature/my-feature    # For new features
git checkout -b fix/bug-description   # For bug fixes
git checkout -b docs/update-readme    # For documentation

# Make changes, commit, push
git add .
git commit -m "description"
git push -u origin feature/my-feature

# Create PR, review, merge
gh pr create --title "Title" --body "Description"
```

**Never commit directly to main** - all changes go through pull requests.

### Release Process

**Releasing a new version (with branch protection):**

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

**What happens during automated release:**

When you push a tag (e.g., `v1.3.3`), GitHub Actions automatically:
1. **Validates** - Checks manifest.json version matches tag, verifies CHANGELOG entry exists
2. **Tests** - Runs full test suite (format, lint, type-check, API tests, HA integration tests)
3. **Extracts release notes** - Parses CHANGELOG.md to extract notes for this version
4. **Creates GitHub release** - Publishes release with extracted notes
5. **Fails if** - Version mismatch, missing CHANGELOG entry, or any test failures

The release appears at: https://github.com/andrew-blake/melcloudhome/releases

**CHANGELOG format rules:**
- Use only standard sections: `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`
- Do NOT use custom sections like "Documentation" or "Technical Details"
- Keep entries concise and factual (no marketing language)
- Date format: YYYY-MM-DD (ISO 8601)
- The `make version-*` command creates a template with "Changed" section only - add other sections as needed

### Beta Release Process

**For features requiring community testing (experimental features, hardware-specific support):**

Beta releases enable HACS users to opt-in to pre-release testing. The GitHub workflow automatically detects beta versions and marks them as pre-releases.

#### Creating a Beta Release

```bash
# 1. Edit manifest.json manually
# Change version: "1.3.4" → "2.0.0-beta.1"

# 2. Update CHANGELOG.md
# Add new entry: ## [2.0.0-beta.1] - YYYY-MM-DD
# Mark as beta and include HACS instructions:
#   - How to enable beta in HACS
#   - What to test
#   - Where to report issues

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

#### Incrementing Beta Versions

```bash
# Fix bugs reported by beta testers, then:
# 1. Edit manifest.json: "2.0.0-beta.1" → "2.0.0-beta.2"
# 2. Update CHANGELOG.md with fixes
# 3. Commit, merge PR, tag as v2.0.0-beta.2
# 4. Push tags
```

#### Graduating to Stable

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

#### When to Use Beta Releases

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

#### How HACS Users Enable Beta Testing

Include this in beta CHANGELOG entries:

```markdown
**How to test this beta:**
1. Enable beta releases in HACS:
   - HACS → Integrations → MELCloud Home
   - Click menu (⋮) → Repository
   - Enable "Show beta versions" switch
2. Install this beta version
3. Report issues: https://github.com/andrew-blake/melcloudhome/issues
```

### Testing Standards

**⚠️ CRITICAL: Follow Home Assistant testing best practices**

See **[docs/testing-best-practices.md](docs/testing-best-practices.md)** for comprehensive guidelines.

**Integration tests run in Docker:**
- Uses `pytest-homeassistant-custom-component` (can't install locally due to aiohttp conflicts)
- Docker container provides clean test environment with HA fixtures
- Run with: `make test-ha` (builds image and runs tests automatically)
- Tests execute from `tests/integration/` directory to load pytest_plugins correctly

**Quick rules for integration tests:**
- ✅ Test through `hass.states` and `hass.services` ONLY
- ✅ Mock `MELCloudHomeClient` at API boundary
- ✅ Use `hass.config_entries.async_setup()` for setup
- ❌ Never import or test coordinator/entity classes directly
- ❌ Never assert coordinator methods were called
- ❌ Never manipulate `coordinator.data` directly

**Example:**
```python
# ✅ CORRECT: Test through core interfaces
state = hass.states.get("climate.entity_id")
assert state.state == HVACMode.HEAT

await hass.services.async_call(
    "climate", "set_temperature",
    {"entity_id": "climate.entity_id", "temperature": 22},
    blocking=True
)

# ❌ WRONG: Don't test internal implementation
# coordinator.async_set_temperature.assert_called_once()  # DON'T DO THIS
```

**Reference examples:**
- ✅ `tests/integration/test_init.py` - Excellent patterns
- ✅ `tests/integration/test_config_flow.py` - Config flow testing
- ✅ `tests/api/test_auth.py` - API testing with VCR

### Critical API Details

- **User-Agent Required:** Must use Chrome User-Agent or requests blocked
- **String vs Integer Enums:** Control API uses strings, Schedule API uses integers
- **Fan Speeds:** STRINGS ("Auto", "One"-"Five") NOT integers
- **Auto Mode:** "Automatic" NOT "Auto"
- **Rate Limiting:** Minimum 60-second polling interval

See `docs/api/ata-api-reference.md` (ATA) and `docs/api/atw-api-reference.md` (ATW) for complete API details. See `docs/api/device-type-comparison.md` for ATA vs ATW comparison.

### Local Development Environment

**⚠️ PRIMARY WORKFLOW:** Use the local Docker Compose environment for daily development:

```bash
# Start dev environment (Mock API + Home Assistant)
make dev-up

# Access at http://localhost:8123 (username: dev, password: dev)
# Make code changes, then restart HA to reload
make dev-restart

# View logs
make dev-logs

# Reset environment (clear entity registry)
make dev-reset
```

**Features:**
- Mock MELCloud API with 2 ATA + 1 ATW test devices
- Auto-setup with skip onboarding
- Debug logging enabled
- Changes reload with simple restart

**See [DEV-SETUP.md](DEV-SETUP.md) for complete guide.**

### Production Deployment

**⚠️ PRE-RELEASE TESTING ONLY:** Only deploy to production HA for final integration testing before releases.

**Automated Deployment Tool:**

The repository includes an automated deployment tool that handles the complete cycle:

```bash
# Deploy to remote HA instance
make deploy

# Deploy + test via API
make deploy-test

# Deploy + watch logs
make deploy-watch
```

The tool automatically:

- Copies integration to remote server via SSH
- Installs into Docker container
- Restarts Home Assistant
- Monitors logs for errors
- Tests entities via API (with `--test`)

**Configuration:** Set `HA_SSH_HOST`, `HA_CONTAINER`, `HA_URL`, and `HA_TOKEN` in `.env`

**Full documentation:** See [tools/README.md](tools/README.md)

**Manual deployment:**

```bash
# Copy to HA config directory
scp -r custom_components/melcloudhome ha:/tmp/
ssh ha "sudo docker cp /tmp/melcloudhome homeassistant:/config/custom_components/"
ssh ha "sudo docker restart homeassistant"
```

## VSCode Configuration

The repository includes VSCode settings that associate `*.yaml` files with the `home-assistant` file type for proper syntax highlighting and validation.

- NEVER work around pre-commit hooks. They are important code quality checks.
- ALWAYS use `uv run pre-commit` not `pre-commit` directly when running pre-commit manually.
