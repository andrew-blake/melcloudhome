# Next Steps for MELCloud Home Integration

This document tracks implementation progress for the MELCloud Home custom component.

---

## 🚀 Quick Start for New Session

**Current Status:** API client complete, ready to build Home Assistant integration

**What to do next:**
1. **Read:** `_claude/ha-integration-requirements.md` (complete spec)
2. **Implement:** 7 files in `custom_components/melcloudhome/`
3. **Test:** Write tests alongside (fixtures provided in spec)
4. **Verify:** Run manual testing checklist

**Estimated time:** 3-4 hours

**Jump to:** [Session 5 details](#session-5-home-assistant-integration--next) below

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

---

## ~~Session 5: Home Assistant Integration~~ 🎯 NEXT

**Goal:** Build Home Assistant custom component for MELCloud Home devices

**Status:** Requirements complete, ready for implementation

### Prerequisites ✅
- API client fully functional (Sessions 1-4 complete)
- Requirements documented in `ha-integration-requirements.md`
- All critical design decisions made (entity naming, error handling, testing)

### Implementation Guide

**📖 Read First:** `_claude/ha-integration-requirements.md` - Complete specification with:
- 7 files to create (manifest, config_flow, coordinator, climate, etc.)
- Modern HA best practices (entity naming, device registry, etc.)
- Comprehensive testing strategy (50+ test cases specified)
- Critical notes and common pitfalls

**⚡ Quick Start:**
1. Read requirements doc thoroughly
2. Create files in order: manifest → const → strings → config_flow → coordinator → __init__ → climate
3. Write tests alongside each component (TDD approach)
4. Use existing API client (no changes needed)
5. Follow modern HA patterns (`_attr_has_entity_name`, device info, etc.)

**🎯 Deliverables:**
- 7 core files in `custom_components/melcloudhome/`
- 4 test files with >80% coverage
- All files type-checked (mypy) and formatted (ruff)
- Manual testing completed (15-item checklist in requirements)

**⏱️ Estimated Time:** 3-4 hours for experienced HA developer

**🔗 References:**
- API client: `custom_components/melcloudhome/api/` (complete)
- Requirements: `_claude/ha-integration-requirements.md`
- ADR-002: Authentication refresh strategy
- Test patterns: See requirements doc Testing Strategy section

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

## Session 6: Schedule Operations (Optional - v1.1+)

**Priority:** Low - Defer to v1.1

- `create_schedule(unit_id, schedule)`: POST `/api/cloudschedule/{unit_id}`
- `delete_schedule(unit_id, schedule_id)`: DELETE
- `set_schedules_enabled(unit_id, enabled)`: PUT

**Note:** Schedule API uses integer enums (0, 1, 2) unlike control API strings

---

## Session 7: Telemetry Operations (Optional - v1.1+)

**Priority:** Low - Nice to have for energy monitoring sensors

- `get_temperature_history()`: Temperature data over time
- `get_energy_data()`: Energy consumption metrics
- `get_error_history()`: Device error logs

---

## Current State Summary

### What's Working ✅

**API Client (Complete)**:
- Authentication (AWS Cognito OAuth)
- Read operations (get devices, get device state)
- Write operations (power, temperature, mode, fan speed, vanes)
- Comprehensive testing infrastructure
  - 82 tests total (79 passing, 3 skipped)
  - 82% code coverage
  - Control tests (12) + Read tests (4) + Validation tests (46) + Auth tests (20)
  - VCR cassette recording/replay for fast tests
  - Centralized fixtures following DRY principle
- Type-safe code with all checks passing
- Development workflow tools (make test, make test-cov)

**Documentation (Complete)**:
- API reference with verified values
- OpenAPI 3.0.3 specification
- HA integration requirements (comprehensive)
- ADR-001: Bundled API client architecture
- ADR-002: Authentication refresh strategy

### Next Priority 🎯

**Session 5: Home Assistant Integration** 🚀

**Ready to implement:**
- Complete requirements spec in `_claude/ha-integration-requirements.md`
- 7 files to create (manifest, config_flow, coordinator, climate, etc.)
- 50+ test cases specified
- All design decisions made
- Modern HA best practices documented

**Start here:**
1. Read `_claude/ha-integration-requirements.md`
2. Create files in order: manifest → const → strings → config_flow → coordinator → __init__ → climate
3. Write tests alongside (TDD)
4. Run manual testing checklist

### Future Work 📋

- Schedule management (v1.1 - Optional)
- Telemetry/energy monitoring (v1.1 - Optional)
- Sensor platform (v1.1 - Optional)
- OAuth refresh tokens (v1.1 - See ADR-002)
- Scenes API (v2.0 - Deferred)

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
