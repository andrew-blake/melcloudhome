# Next Steps for MELCloud Home Integration

This document tracks implementation progress for the MELCloud Home custom component.

---

## 🚀 Quick Start for New Session

**Current Status:** Integration complete and ready for deployment

**What to do next:**
1. **Deploy:** `python tools/deploy_custom_component.py melcloudhome --reload`
2. **Configure:** Add integration via HA UI (Configuration → Integrations)
3. **Test:** Manual testing checklist in `ha-integration-requirements.md`
4. **Monitor:** Watch logs and verify all devices appear

**Next session:** Manual testing and v1.1 planning

**Jump to:** [Session 6 details](#session-6-deployment--testing--next) below

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

---

## ~~Session 5: Home Assistant Integration~~ ✅ COMPLETED

**Goal:** Build Home Assistant custom component for MELCloud Home devices

**Status:** Complete - Ready for deployment

See Session 5 in Completed Sessions above for full details.

---

## Session 6: Deployment & Testing 🎯 NEXT

**Goal:** Deploy to Home Assistant and verify all functionality

**Status:** Ready to deploy

### Deployment Steps

1. **Deploy integration:**
   ```bash
   python tools/deploy_custom_component.py melcloudhome
   ```

2. **Add via HA UI:**
   - Configuration → Integrations → Add Integration
   - Search for "MELCloud Home v2"
   - Enter credentials: a.blake01@gmail.com / screech-POPULAR7marissa

3. **Verify devices loaded:**
   - Check all devices appear
   - Verify entity names follow pattern: `climate.home_[room]_heatpump`

4. **Manual testing checklist:**
   - [ ] Power on/off via UI
   - [ ] Temperature adjustment (0.5° increments)
   - [ ] All HVAC modes: Heat, Cool, Auto, Dry, Fan
   - [ ] Fan speeds: Auto, One-Five
   - [ ] Swing modes (vane positions)
   - [ ] Verify 60s polling updates
   - [ ] Test error recovery (disconnect/reconnect)
   - [ ] Check device info shows building names

### Troubleshooting

**View logs:**
```bash
python tools/deploy_custom_component.py melcloudhome --watch
```

**Or directly:**
```bash
ssh ha "sudo docker logs -f homeassistant 2>&1" | grep melcloudhome
```

**Common issues:**
- Integration not appearing: Check logs for Python errors
- Entities not loading: Verify credentials in config entry
- States not updating: Check 60s polling interval

### Success Criteria

- [ ] All devices discovered
- [ ] All controls working (power, temp, mode, fan, swing)
- [ ] State updates after 60s
- [ ] No errors in logs
- [ ] Entity names follow naming convention

**Next:** v1.1 planning based on usage feedback

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

**Complete v1.0 Integration:**
- API Client (Sessions 1-4)
  - Authentication (AWS Cognito OAuth)
  - Read operations (get devices, device state, user context)
  - Write operations (power, temperature, mode, fan speed, vanes)
  - 79 tests passing, 82% code coverage
  - VCR cassette recording/replay for fast tests
- Home Assistant Integration (Session 5)
  - 7 integration files (manifest, config_flow, coordinator, climate, etc.)
  - Modern HA architecture (DataUpdateCoordinator, device registry)
  - Config flow with email/password setup
  - 60s polling with auto re-authentication
  - Full climate control (HVAC, fan, swing, temperature)
- Development Tools
  - Automated deployment with reload support
  - Log monitoring and error detection
  - API testing capability
- Documentation
  - Complete API reference and OpenAPI spec
  - HA integration requirements
  - Best practices review
  - Testing strategy (why NOT to mock HA)
  - 3 ADRs (bundled client, auth refresh, entity naming)

### Next Priority 🎯

**Session 6: Deployment & Testing** 🚀

**Ready to deploy:**
- Integration complete and tested
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
- `../docs/integration-review.md`: Best practices review and quality assessment
- `../docs/testing-strategy.md`: Why not to mock HA and proper testing approaches
- `../tools/README.md`: Deployment tool documentation and workflows
