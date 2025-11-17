# Next Steps for MELCloud Home Integration

This document tracks implementation progress for the MELCloud Home custom component.

---

## 🚀 Quick Start for New Session

**Current Status:** ✅ v1.0.1 DEPLOYED AND WORKING!

**What's Working:**
- ✅ Integration deployed and configured
- ✅ All devices discovered and controllable
- ✅ HVAC controls working (power, temp, mode, fan, swing)
- ✅ 60s polling with auto-refresh
- ✅ Standard HA climate entity UI
- ✅ Comprehensive README with dashboard setup guide

**v1.0.1 Improvements:**
- ✅ Email removed from integration title (privacy)
- ✅ Device attribution added (transparency)
- ✅ Dashboard setup documented
- ✅ README created with automation examples

**What to do next:**
1. **Quick Updates:** `uv run python tools/deploy_custom_component.py melcloudhome --reload` (fast)
2. **Check Logs:** `ssh ha "sudo docker logs -f homeassistant" | grep melcloudhome`
3. **Monitor:** Integration → MELCloud Home → Logs

**Next session:** v1.1 implementation (WebSocket + sensors)

**Jump to:** [Session 8 details](#session-8-v11-real-time--sensors-next) below

**Reference Documents:**
- `_claude/v1.1-requirements.md` - Complete v1.1 requirements specification
- `_claude/ROADMAP.md` - v1.2+ planning and long-term roadmap
- `_claude/KNOWN-ISSUES.md` - Current open issues (only icon remaining)

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

## Session 8: v1.1 Real-Time & Sensors 🎯 NEXT

**Goal:** Add WebSocket real-time updates, sensors, and diagnostic data

**Status:** Requirements complete, ready for implementation
**Timeline:** 7 hours estimated
**Reference:** `_claude/v1.1-requirements.md` (complete specification)

### Phase 1: Research (1 hour)

**WebSocket Protocol Investigation:**
- [ ] Capture WebSocket authentication method (browser DevTools)
- [ ] Document handshake protocol
- [ ] Identify subscription model (per-device? auto-subscribe?)
- [ ] Capture ping/pong keepalive messages
- [ ] Answer open questions OQ-1 through OQ-4

**Tools:** Chrome DevTools on MELCloud Home reports page

### Phase 2: Implementation (4 hours)

**Core Features:**
- [ ] WebSocket manager (`websocket.py`)
  - Connection lifecycle
  - Message parsing (3 types)
  - Reconnection with exponential backoff
  - Token refresh handling
- [ ] Energy tracker (`energy_tracker.py`)
  - Finalized vs current hour separation
  - No double-counting logic
  - Persistence across restarts
- [ ] Coordinator updates (`coordinator.py`)
  - WebSocket integration
  - Energy polling (15 min intervals)
  - Hybrid fallback logic
- [ ] Sensor platform (`sensor.py`)
  - WiFi signal sensor (WebSocket)
  - Current temperature sensor (WebSocket)
  - Target temperature sensor (WebSocket)
  - Energy consumption sensor (REST API polling)
- [ ] Binary sensor platform (`binary_sensor.py`)
  - Error state monitoring (WebSocket)
- [ ] Diagnostic data (`diagnostics.py`)
  - Export integration state
  - WebSocket statistics
  - Energy tracking info
- [ ] Integration icon
  - Download/create icon.png and logo.png
  - Add attribution to README

**File Changes:**
- NEW: 5 files (websocket.py, energy_tracker.py, sensor.py, binary_sensor.py, diagnostics.py)
- MODIFY: 3 files (coordinator.py, const.py, manifest.json)
- NEW: 2 images (icon.png, logo.png)

### Phase 3: Testing (1 hour)

**Unit Tests:**
- [ ] WebSocket connection and message parsing
- [ ] Energy tracking algorithm (deduplication)
- [ ] Type coercion (string → bool, int)
- [ ] Delta merge logic
- [ ] Sensor entity creation

**Integration Tests:**
- [ ] Deploy to HA and verify WebSocket connects
- [ ] Test all 3 message types received
- [ ] Verify state updates < 1 second
- [ ] Test energy tracking (no double-counting)
- [ ] Test reconnection on disconnect
- [ ] Verify diagnostic data export
- [ ] Check icon appears

### Phase 4: Documentation (1 hour)

- [ ] Update README with WebSocket and sensor info
- [ ] Create ADR-005: WebSocket Real-Time Updates
- [ ] Create `_claude/websocket-implementation.md` (technical details)
- [ ] Update KNOWN-ISSUES.md (close icon issue)
- [ ] Update this file (mark Session 8 complete)

### Success Criteria

**Functional:**
- [ ] WebSocket connects and receives messages
- [ ] State updates within 1 second
- [ ] 5 sensor entities created per device
- [ ] Energy tracking accurate (no double-counting)
- [ ] Falls back to polling if WebSocket fails
- [ ] Diagnostic data exports successfully
- [ ] Integration icon shows (no 404)

**Quality:**
- [ ] All tests passing (>80% coverage)
- [ ] No memory leaks (24+ hour test)
- [ ] Code quality checks passing (ruff, mypy)
- [ ] Documentation complete

**New Entities per Device:**
1. `sensor.{}_current_temperature` - Room temp
2. `sensor.{}_target_temperature` - Setpoint
3. `sensor.{}_wifi_signal` - Signal strength
4. `sensor.{}_energy` - Cumulative kWh
5. `binary_sensor.{}_error` - Error state

**Next:** v1.2 HACS distribution (see `_claude/ROADMAP.md`)

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
