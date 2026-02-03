# CLAUDE.md

This file provides quick orientation and navigation for Claude Code when working with this repository.

## What This Repo Is

MELCloud Home integration for Home Assistant, distributed via HACS. Supports Air-to-Air (ATA) air conditioning units and Air-to-Water (ATW) heat pumps with full HVAC control, energy monitoring, and zone management.

**Repository:** <https://github.com/andrew-blake/melcloudhome>

## Project Context

### Distribution & Workflow

- **Distribution:** HACS (Home Assistant Community Store)
- **Branching:** GitHub Flow - always use feature branches, never commit directly to main
- **Pre-commit hooks:** Enforced by git hooks
- **Personal setup:** See `CLAUDE.local.md` (gitignored) for remote HA deployment and diagnostics

## Quick Commands

```bash
# Setup
uv sync                          # Install dependencies
source .venv/bin/activate        # Activate environment

# Local dev environment (Mock API + Home Assistant)
make dev-up                      # Start dev environment
make dev-restart                 # Restart HA after code changes
make dev-logs                    # View logs
make dev-reset                   # Clear entity registry, fresh start
                                 # ⚠️ CRITICAL: Enable Advanced Mode in user profile
                                 # to see "Connect to Mock Server" checkbox during setup
                                 # See DEV-SETUP.md section 2.1 for details

# Code quality
make format                      # Format with ruff
make lint                        # Lint with ruff
make type-check                  # Type check with mypy
make pre-commit                  # Run all pre-commit checks

# Testing
make test-api                    # API unit tests (VCR, no Docker)
make test-integration            # Integration tests (Docker, mocked API)
make test-e2e                    # E2E tests (Docker, mock server)
make test                        # All tests with coverage
```

## Documentation Navigator

### Architecture & Design

- **Architecture overview:** `docs/architecture.md` - System architecture, multi-device patterns, 3-way valve behavior
- **Entity reference:** `docs/entities.md` - All entities, entity ID convention, capabilities
- **Architecture decisions:** `docs/decisions/` - ADRs documenting key technical decisions
- **Code structure:** Browse `custom_components/melcloudhome/` - Multi-device architecture with ATA/ATW separation

**Key patterns:**

- **Bundled API client:** Library in `api/` subfolder - facade pattern composing ATA + ATW clients
- **Multi-device architecture:** Platform routers dispatch to device-specific implementations
- **Entity IDs:** UUID-based for stability - see `docs/entities.md`

### API Documentation

- **ATA (Air-to-Air) API:** `docs/api/ata-api-reference.md`
- **ATW (Air-to-Water) API:** `docs/api/atw-api-reference.md`
- **Device comparison:** `docs/api/device-type-comparison.md`
- **OpenAPI spec:** `openapi.yaml` (root directory)

### Development Guides

- **Local dev setup:** `DEV-SETUP.md` - Mock server, Docker Compose environment, Advanced Mode setup
- **Testing standards:** `docs/testing-best-practices.md` - HA-specific testing patterns, anti-patterns, debugging
- **Testing strategy:** `docs/testing-strategy.md` - Test types, when to use each
- **Deployment tools:** `tools/README.md` - Automated deployment, remote testing
- **Release process:** `docs/release-process.md` - Release + beta workflows

### Research & Tools

- **Reverse engineering:** `docs/research/REVERSE_ENGINEERING.md` - API discovery without hardware
- **RE tools:** `tools/reverse-engineering/` - Chrome overrides, request proxying
- **Research archive:** `docs/archive/research/` - Historical planning docs

## Home Assistant Integration Testing

**Critical anti-patterns (Claude commonly violates these):**

✅ **DO:**

- Test entities through `hass.states` and `hass.services` ONLY
- Mock `MELCloudHomeClient` at API boundary

❌ **NEVER:**

- Import/test coordinator or entity classes directly
- Assert internal method calls (e.g., `coordinator.async_set_temperature.assert_called_once()`)
- Manipulate `coordinator.data` directly

**Study working examples:** `tests/integration/test_climate_ata.py`, `tests/integration/test_climate_atw.py`

## Pre-commit Hooks

**CRITICAL WORKFLOW RULE:**

1. Make all your changes
2. Run `make pre-commit`
3. **DO NOT make ANY edits after this point**
4. Immediately run `git commit`
5. If you need to make more edits, return to step 2

**Why:** Pre-commit hooks only check staged files during commit. If you run `make pre-commit`, then edit files, then commit - the commit hooks will catch unformatted code and fail.

- NEVER work around pre-commit hooks - they are important code quality checks

---

## About This File

**Purpose:** Navigation index and quick command reference for Claude Code.

**Principles:**

- Keep under ~150 lines - this is a guide, not detailed documentation
- NO file trees - they go stale immediately
- NO duplicated content - link to detailed docs instead
- Personal setup (SSH, deployment) goes in `CLAUDE.local.md` (gitignored)
- Only include content that doesn't exist elsewhere: command quick reference, Claude-specific reminders

**When adding content, ask:** "Does this belong in a detailed doc that I should link to instead?"
