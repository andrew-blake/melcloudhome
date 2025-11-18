# Next Steps for MELCloud Home Integration

This document tracks implementation progress for the MELCloud Home custom component.

---

## 🚀 Quick Start for New Session

**Current Status:** ✅ v1.1.2 DEPLOYED | 🔴 v1.1.3 READY TO IMPLEMENT

**What's Working:**
- ✅ Integration deployed and configured
- ✅ All devices discovered and controllable
- ✅ HVAC controls working (power, temp, mode, fan, swing)
- ✅ 60s polling with auto-refresh
- ✅ Standard HA climate entity UI
- ✅ Stable entity IDs based on unit UUIDs
- ✅ Diagnostics export support
- ✅ Custom integration icon
- ✅ Comprehensive documentation

**🔴 CRITICAL: v1.1.3 Hotfix Required**
- ❌ Missing TURN_ON/TURN_OFF feature flags (HA 2025.1+ compliance)
- ❌ Voice commands ("turn on the AC") may be broken
- ⚡ Quick 1-2 hour fix required immediately
- 📋 See Session 10 below

**What to do next:**
1. **IMMEDIATE:** Implement v1.1.3 hotfix (turn_on/turn_off)
2. **Quick Updates:** `uv run python tools/deploy_custom_component.py melcloudhome --reload`
3. **Check Logs:** `ssh ha "sudo docker logs -f homeassistant" | grep melcloudhome`
4. **Monitor:** Integration → MELCloud Home → Logs

**Next session:** v1.1.3 implementation (Session 10)

**Jump to:** [Session 10 details](#session-10-v113-compliance-hotfix-next) below

**Reference Documents:**
- `_claude/ROADMAP.md` - Complete roadmap with v1.1.3 and v1.2+ planning
- `_claude/climate-entity-feature-research.md` - Missing features analysis (Session 9)
- `_claude/repository-strategy.md` - HACS distribution strategy
- `_claude/session-9-research-findings.md` - Complete Session 9 research
- `_claude/websocket-research-defer.md` - WebSocket investigation (deferred to v1.3)
- `_claude/KNOWN-ISSUES.md` - Current open issues
- `docs/decisions/007-defer-websocket-implementation.md` - WebSocket deferral ADR

---

## ✅ Completed Sessions

### Session 1: API Discovery & Documentation (2025-01-09)
- ✅ Discovered and documented 87% of MELCloud Home API
- ✅ Created OpenAPI 3.0.3 specification
- ✅ Documented control, schedule, and telemetry endpoints
- ✅ Identified critical API details (string enums, rate limits, etc.)
- 📁 **Deliverables:** `openapi.yaml`, `melcloudhome-api-reference.md`

### Session 2: Authentication (2025-01-15)
- ✅ Implemented AWS Cognito OAuth flow in `auth.py`
- ✅ Fixed authentication with correct headers (`x-csrf: 1`, `referer`)
- ✅ Added 3-second wait for Blazor WASM initialization
- ✅ Created project foundation (`const.py`, `models.py`, `exceptions.py`)
- 📁 **Deliverables:** Working authentication module

### Session 3: API Client + Testing (2025-01-16)
- ✅ Implemented `client.py` with read-only operations
  - `get_user_context()`: Fetch complete user context
  - `get_devices()`: Get all devices
  - `get_device(unit_id)`: Get specific device
- ✅ Fixed `models.py` to parse actual API response format
- ✅ Set up comprehensive TDD with VCR testing
  - pytest + pytest-asyncio + vcrpy + pytest-recording
  - VCR records real API, replays for fast tests (12s vs 20s)
  - Comprehensive data scrubbing (emails, names, credentials)
  - 4 passing integration tests
- ✅ All pre-commit hooks passing (ruff, mypy, formatting)
- ✅ Proper type annotations throughout
- 📁 **Deliverables:** `client.py`, `tests/`, VCR cassettes

### Session 4: Control APIs + Comprehensive Testing (2025-01-17)
- ✅ Implemented all device control methods in `client.py`
  - `set_power()`: Turn device on/off
  - `set_temperature()`: Set target temperature (10-31°C, 0.5° increments)
  - `set_mode()`: Set operation mode (Heat, Cool, Automatic, Dry, Fan)
  - `set_fan_speed()`: Set fan speed (Auto, One-Five)
  - `set_vanes()`: Control vane directions
- ✅ Comprehensive test suite (82 tests total)
  - `test_client_control.py`: 12 control operation tests with VCR
  - `test_client_validation.py`: 46 parameter validation tests (fast, no VCR)
  - `test_auth.py`: 20 authentication tests (17 passing, 3 skipped)
  - All tests verified against real Dining Room device
- ✅ Fixed API response handling
  - Empty response handling for control endpoint (200 OK with no body)
  - Value normalization in models (API returns "0"-"5", client uses "Auto", "One"-"Five")
- ✅ Test infrastructure improvements
  - Added pytest-cov for coverage reporting (82% overall)
  - Centralized credentials in conftest.py fixtures (DRY principle)
  - Updated Makefile: `make test`, `make test-cov` commands
  - Updated .gitignore for test artifacts
- ✅ Documentation: ADR-002 (authentication refresh strategy)
- 📁 **Deliverables:** Control methods, 3 test files, 22 VCR cassettes, ADR-002

### Session 5: Home Assistant Integration (2025-11-17)
- ✅ Implemented complete HA custom component (7 core files)
  - `manifest.json`: Integration metadata with issue_tracker and loggers
  - `const.py`: Constants and mode mappings (MELCloud ↔ HA)
  - `strings.json`: UI translations for config flow
  - `config_flow.py`: Email/password configuration wizard
  - `coordinator.py`: 60s polling with auto re-authentication
  - `__init__.py`: Setup/teardown with lazy imports
  - `climate.py`: Full climate entity (HVAC, fan, swing, temperature)
- ✅ Modern HA architecture and best practices
  - DataUpdateCoordinator pattern
  - Modern entity naming (`_attr_has_entity_name = True`)
  - Proper device registry with building context
  - ConfigEntryAuthFailed/NotReady error handling
  - Lazy imports for test compatibility
- ✅ Deployment automation
  - Created `tools/deploy_custom_component.py`
  - SSH-based deployment with Docker integration
  - API reload support (5x faster than restart)
  - Log monitoring and error detection
  - API testing capability
- ✅ Comprehensive documentation
  - Best practices review (docs/integration-review.md)
  - Testing strategy (docs/testing-strategy.md)
  - Deployment tool guide (tools/README.md)
  - Updated CLAUDE.md with workflows
- ✅ All quality checks passing
  - Ruff linting and formatting
  - Mypy type checking
  - API tests: 79 passing, 82% coverage
  - Pre-commit hooks configured
- 📁 **Deliverables:** 7 integration files, deployment tool, 3 docs, .env setup

### Session 6: Integration Refactoring (2025-11-17)
- ✅ Comprehensive code review for DRY/KISS violations
- ✅ Fixed authentication duplication (DRY violation)
  - `config_flow.py` now uses `MELCloudHomeClient` (not `MELCloudHomeAuth`)
  - Single authentication abstraction throughout codebase
- ✅ Removed redundant login in `__init__.py` (KISS violation)
  - Coordinator handles all authentication on first refresh
  - Eliminated extra network call on startup
- ✅ Performance optimization - O(1) device lookups
  - Added cached dictionaries to coordinator
  - `_units` and `_unit_to_building` for instant lookups
  - Changed from O(n*m) loops to O(1) dict access
  - ~10x performance improvement per update cycle
- ✅ Consolidated temperature constants (DRY violation)
  - `client.py` and `climate.py` now import from `api/const.py`
  - Single source of truth for all temperature values
- ✅ Documented lazy imports pattern
  - Explained why HA not in dev dependencies
  - Standard practice due to HA's strict dependency pinning
  - Clear documentation in code and pyproject.toml
- ✅ All quality checks passing
  - Tests: 79 passed, 3 skipped (100% pass rate)
  - Ruff: All checks passed
  - Pre-commit: All hooks passed
  - Coverage: 82% maintained
- 📁 **Deliverables:**
  - 6 files refactored (client, config_flow, __init__, coordinator, climate, pyproject)
  - ADR-004: Integration Refactoring
  - Full backwards compatibility maintained

### Session 7: Deployment & Testing (2025-11-17)
- ✅ Deployed integration to Home Assistant
  - Used deployment tool: `uv run python tools/deploy_custom_component.py melcloudhome`
  - Container restarted successfully
  - Integration files installed
- ✅ Configured via Home Assistant UI
  - Configuration → Integrations → Add Integration
  - Searched for "MELCloud Home v2"
  - Entered credentials and authenticated successfully
  - Unique ID prevents duplicate accounts
- ✅ All devices discovered automatically
  - All climate entities created
  - Entity naming: `climate.home_[room]_heatpump`
  - Device registry populated with building info
- ✅ Manual testing completed
  - Power on/off: ✅ Working
  - Temperature adjustment: ✅ Working (0.5° increments)
  - HVAC modes: ✅ Working (Heat, Cool, Auto, Dry, Fan)
  - Fan speeds: ✅ Working (Auto, One-Five)
  - Swing modes: ✅ Working (vane positions)
  - 60s polling: ✅ Working (state updates)
  - Error handling: ✅ Working (entities become unavailable)
- ✅ Standard HA climate UI confirmed
  - Native thermostat card
  - All controls visible and functional
  - Automation support working
- ✅ Identified known issues for v1.1
  - Integration icon 404 (cosmetic)
  - Dashboard default widget (UX)
  - Email in integration title (privacy/cosmetic)
  - Documented in `_claude/KNOWN-ISSUES.md`
- 📁 **Deliverables:**
  - v1.0.0 deployed and working in production
  - Manual testing completed successfully
  - Known issues documented for v1.1
  - Ready for daily use

### Session 8: v1.1 Polish & Stable Entity IDs (2025-11-17)
- ✅ Researched legacy MELCloud integration for patterns
  - Found icons.json approach (modern HA pattern)
  - Found diagnostics.py implementation reference
  - Identified sensor platform patterns for v1.2
- ✅ Implemented stable entity IDs based on unit UUIDs
  - Format: `climate.melcloud_0efc_76db` (first 4 + last 4 chars)
  - Ensures stability across building/room renames
  - Changed `has_entity_name` from True to False for explicit control
- ✅ Created diagnostics.py with comprehensive export
  - Exports config, entities, coordinator, device info
  - Automatic redaction of email/password
  - Accessible via Integration → ⋮ → Download diagnostics
- ✅ Added integration icon (icons.json)
  - Used Material Design Icon (mdi:heat-pump)
  - Modern JSON approach instead of PNG files
- ✅ Fixed deprecation warning
  - Removed via_device reference
  - Eliminates HA 2025.12.0 warning
- ✅ Polish improvements
  - Renamed from "MELCloud Home v2" to "MELCloud Home"
  - Updated all documentation
  - Updated KNOWN-ISSUES.md and ROADMAP.md
- 📁 **Deliverables:**
  - v1.1.2 deployed and working
  - 2 new files: diagnostics.py, icons.json
  - Updated: climate.py, manifest.json, strings.json, README.md
  - All issues resolved except #7 (missing images, cosmetic)

---

## ~~Session 5: Home Assistant Integration~~ ✅ COMPLETED

**Goal:** Build Home Assistant custom component for MELCloud Home devices

**Status:** Complete - Refactored and ready for deployment

See Session 5 in Completed Sessions above for full details.

---

## ~~Session 6: Integration Refactoring~~ ✅ COMPLETED

**Goal:** Review and fix DRY/KISS violations, optimize performance

**Status:** Complete - All violations fixed, performance optimized

See Session 6 in Completed Sessions above for full details.

---

## ~~Session 7: Deployment & Testing~~ ✅ COMPLETED

**Goal:** Deploy to Home Assistant and verify all functionality

**Status:** Complete - v1.0.0 deployed and working perfectly!

See Session 7 in Completed Sessions above for full details.

---

## ~~Session 8: v1.1 Polish & Diagnostics~~ ✅ COMPLETED

**Goal:** Polish integration with diagnostics, icon, and documentation improvements

**Status:** Complete - v1.1.2 deployed with stable entity IDs!
**Timeline:** 2 hours actual

See Session 8 in Completed Sessions above for full details.

### Session 9: Pre-v1.2 Research & Planning (2025-11-17)
- ✅ Researched legacy MELCloud integration patterns
- ✅ Researched HA climate integration best practices
- ✅ Researched HACS distribution requirements
- ✅ **Critical Discovery:** Missing TURN_ON/TURN_OFF support (v1.1.3 hotfix needed)
- ✅ **Decision:** Defer WebSocket to v1.3 due to reliability issues (ADR-007)
- ✅ **Decision:** Maintain modern architecture (don't copy MELCloud's deprecated patterns) (ADR-005)
- ✅ **Decision:** Adopt entity description pattern for sensors (ADR-006)
- ✅ **Decision:** Create separate HACS repository, keep current as dev environment
- ✅ **Decision:** Keep API bundled (KISS principle, no PyPI package)
- ✅ Identified missing features: HVAC Action, Horizontal Swing Mode
- ✅ Updated ROADMAP.md with v1.1.3 hotfix + v1.2 plan
- 📁 **Deliverables:**
  - `_claude/session-9-research-findings.md` - Comprehensive research report
  - `_claude/climate-entity-feature-research.md` - Missing features analysis
  - `_claude/repository-strategy.md` - HACS distribution strategy
  - `docs/decisions/005-divergence-from-official-melcloud.md` - Architecture ADR
  - `docs/decisions/006-entity-description-pattern.md` - Sensor pattern ADR
  - `docs/decisions/007-defer-websocket-implementation.md` - WebSocket deferral ADR
  - Updated ROADMAP.md with v1.1.3 and v1.2 scope

---

## ~~Session 9: Pre-v1.2 Review & Planning~~ ✅ COMPLETED

**Goal:** Critical review of best practices before v1.2 implementation

**Status:** Complete - Research and planning complete!
**Timeline:** 4 hours actual
**Date:** 2025-11-17

See Session 9 in Completed Sessions above for full details.

---

## Session 10: v1.1.3 Compliance Hotfix 🔴 NEXT

**Goal:** Fix critical HA 2025.1 compliance issue with turn_on/turn_off

**Status:** Ready to implement
**Timeline:** 1-2 hours
**Priority:** CRITICAL
**Reference:** `_claude/climate-entity-feature-research.md`, `_claude/ROADMAP.md`

### Critical Issue

**Missing TURN_ON/TURN_OFF Support:**
- Home Assistant 2025.1 requires `ClimateEntityFeature.TURN_ON` and `TURN_OFF` flags
- Without these, voice commands and automations may fail
- Simple 1-hour fix with high user impact

### Implementation Tasks

**1. Update climate.py (30 minutes)**
- [ ] Add `async_turn_on()` method
- [ ] Add `async_turn_off()` method
- [ ] Add TURN_ON/TURN_OFF feature flags to `supported_features`
- [ ] Test locally with deployment tool

**Code to Add:**
```python
async def async_turn_on(self) -> None:
    """Turn the entity on."""
    await self.coordinator.client.set_power(self._unit_id, True)
    await self.coordinator.async_request_refresh()

async def async_turn_off(self) -> None:
    """Turn the entity off."""
    await self.coordinator.client.set_power(self._unit_id, False)
    await self.coordinator.async_request_refresh()

# Update supported_features
features = (
    ClimateEntityFeature.TARGET_TEMPERATURE
    | ClimateEntityFeature.TURN_ON
    | ClimateEntityFeature.TURN_OFF
)
```

**2. Testing (30 minutes)**
- [ ] Set HEAT mode, turn off, turn on → resumes HEAT
- [ ] Set COOL at 24°C, turn off, turn on → resumes COOL at 24°C
- [ ] Test voice command: "Hey Google, turn on bedroom AC"
- [ ] Test automation using `climate.turn_on` service
- [ ] Verify device resumes previous state (not forced to AUTO)

**3. Deployment (15 minutes)**
- [ ] Deploy to production via deployment tool
- [ ] Monitor logs for errors
- [ ] Test on actual devices
- [ ] Verify voice assistants working

**4. Documentation (15 minutes)**
- [ ] Update session notes
- [ ] Mark v1.1.3 as complete in ROADMAP.md
- [ ] Update NEXT-STEPS.md for Session 11 (v1.2)

### Deliverables

- Updated `custom_components/melcloudhome/climate.py`
- v1.1.3 deployed to production
- No breaking changes
- HA 2025.1+ compliance achieved

### Success Criteria

- [ ] TURN_ON/TURN_OFF methods implemented
- [ ] Feature flags added
- [ ] Voice commands working (Google Home, Alexa)
- [ ] Automations using climate.turn_on working
- [ ] Device resumes previous state correctly
- [ ] Deployed to production
- [ ] No breaking changes or regressions

**Next:** Session 11 - v1.2 Implementation (Sensors + HACS + Enhanced Features)

---

## ~~Session 4: Control APIs (Device Control)~~ ✅ COMPLETED

**Goal:** Add write operations to control devices

### Implementation Steps

1. **Write tests for control operations**
   ```python
   # tests/test_client_control.py
   async def test_set_power(authenticated_client, dining_room_unit_id):
       """Test turning device on/off"""

   async def test_set_temperature(authenticated_client, dining_room_unit_id):
       """Test setting target temperature"""

   async def test_set_mode(authenticated_client, dining_room_unit_id):
       """Test changing operation mode"""
   ```

2. **Implement control methods in `client.py`**
   ```python
   async def set_power(self, unit_id: str, power: bool) -> None:
       """Turn device on/off"""

   async def set_temperature(self, unit_id: str, temp: float) -> None:
       """Set target temperature (10-31°C in 0.5° increments)"""

   async def set_mode(self, unit_id: str, mode: str) -> None:
       """Set operation mode: Heat, Cool, Automatic, Dry, Fan"""

   async def set_fan_speed(self, unit_id: str, speed: str) -> None:
       """Set fan speed: Auto, One, Two, Three, Four, Five"""

   async def set_vanes(
       self, unit_id: str, vertical: str, horizontal: str
   ) -> None:
       """Control vane direction"""
   ```

3. **Test carefully**
   - VCR will record control operations
   - Test against real device
   - Verify state changes after commands
   - Add delays if needed for state propagation

### API Details

**Endpoint:** `PUT /api/units/{unitId}`

**Required Headers:**
- `x-csrf: 1`
- `referer: https://melcloudhome.com/dashboard`
- `Content-Type: application/json`

**Request Body:**
```json
{
  "power": true,
  "setTemperature": 22.0,
  "operationMode": "Heat",
  "setFanSpeed": "Auto",
  "vaneVerticalDirection": "Auto",
  "vaneHorizontalDirection": "Auto"
}
```

**Key Considerations:**
- Use correct string values ("Automatic" not "Auto" for mode)
- Fan speeds are strings not integers
- Temperature range: 10-31°C in 0.5° increments

---

## Session 8: Schedule Operations (Optional - v1.1+)

**Priority:** Low - Defer to v1.1

- `create_schedule(unit_id, schedule)`: POST `/api/cloudschedule/{unit_id}`
- `delete_schedule(unit_id, schedule_id)`: DELETE
- `set_schedules_enabled(unit_id, enabled)`: PUT

**Note:** Schedule API uses integer enums (0, 1, 2) unlike control API strings

---

## Session 9: Telemetry Operations (Optional - v1.1+)

**Priority:** Low - Nice to have for energy monitoring sensors

- `get_temperature_history()`: Temperature data over time
- `get_energy_data()`: Energy consumption metrics
- `get_error_history()`: Device error logs

---

## Current State Summary

### What's Working ✅

**Complete v1.0 Integration:**
- API Client (Sessions 1-4)
  - Authentication (AWS Cognito OAuth)
  - Read operations (get devices, device state, user context)
  - Write operations (power, temperature, mode, fan speed, vanes)
  - 79 tests passing, 82% code coverage
  - VCR cassette recording/replay for fast tests
- Home Assistant Integration (Sessions 5-6)
  - 7 integration files (manifest, config_flow, coordinator, climate, etc.)
  - Modern HA architecture (DataUpdateCoordinator, device registry)
  - Config flow with email/password setup
  - 60s polling with auto re-authentication
  - Full climate control (HVAC, fan, swing, temperature)
  - **Refactored for DRY/KISS/Performance (Session 6)**
    - Single authentication abstraction
    - O(1) device lookups with caching
    - Consolidated constants
    - Documented lazy imports
- Development Tools
  - Automated deployment with reload support
  - Log monitoring and error detection
  - API testing capability
- Documentation
  - Complete API reference and OpenAPI spec
  - HA integration requirements
  - Best practices review
  - Testing strategy (why NOT to mock HA)
  - 4 ADRs (bundled client, auth refresh, entity naming, refactoring)

### Next Priority 🎯

**Session 7: Deployment & Testing** 🚀

**Ready to deploy:**
- Integration complete, refactored, and tested
- All DRY/KISS violations fixed
- Performance optimized (O(1) lookups)
- Deployment tool ready (`tools/deploy_custom_component.py`)
- Manual testing checklist prepared
- .env configured with credentials

**Deploy now:**
```bash
python tools/deploy_custom_component.py melcloudhome --reload
```

### Future Work 📋

**v1.1 (Based on Usage Feedback):**
- Schedule management (optional)
- Sensor platform for energy monitoring (optional)
- Options flow for reconfiguration
- Diagnostic data support
- OAuth refresh tokens (if API adds support)

**v2.0 (Long-term):**
- Scenes API integration
- Advanced automation support
- Multi-language translations

---

## Reference Documentation

### API Documentation
- `melcloudhome-api-reference.md`: Complete API reference with verified values
- `melcloudhome-schedule-api.md`: Schedule management endpoints
- `melcloudhome-telemetry-endpoints.md`: Monitoring and reporting APIs
- `openapi.yaml`: OpenAPI 3.0.3 specification

### Project Documentation
- `CLAUDE.md`: Development workflow and project structure
- `../docs/decisions/001-bundled-api-client.md`: ADR for bundled architecture
- `../docs/decisions/002-authentication-refresh-strategy.md`: ADR for auth handling
- `../docs/decisions/003-entity-naming-strategy.md`: ADR for entity naming and device registry
- `../docs/decisions/004-integration-refactoring.md`: ADR for DRY/KISS/performance fixes (Session 6)
- `../docs/integration-review.md`: Best practices review and quality assessment
- `../docs/testing-strategy.md`: Why not to mock HA and proper testing approaches
- `../tools/README.md`: Deployment tool documentation and workflows
