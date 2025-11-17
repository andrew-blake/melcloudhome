# Next Steps for MELCloud Home Integration

This document tracks implementation progress for the MELCloud Home custom component.

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

### Session 4: Control APIs (2025-01-17)
- ✅ Implemented all device control methods in `client.py`
  - `set_power()`: Turn device on/off
  - `set_temperature()`: Set target temperature (10-31°C, 0.5° increments)
  - `set_mode()`: Set operation mode (Heat, Cool, Automatic, Dry, Fan)
  - `set_fan_speed()`: Set fan speed (Auto, One-Five)
  - `set_vanes()`: Control vane directions
- ✅ Created comprehensive test suite (`test_client_control.py`)
  - 12 passing control operation tests
  - Tested against real Dining Room device with VCR recording
  - Verified state changes after each control operation
- ✅ Fixed API response handling
  - Empty response handling for control endpoint (returns 200 with no body)
  - Value normalization in models (API returns "0"-"5", client uses "Auto", "One"-"Five")
- ✅ All 16 tests passing (12 control + 4 read)
- ✅ All pre-commit hooks passing
- 📁 **Deliverables:** Control methods, `test_client_control.py`, 12 VCR cassettes

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

## Session 5: Schedule Operations (Optional for v1.0)

**Priority:** Medium - Can defer to v1.1

- `create_schedule(unit_id, schedule)`: POST `/api/cloudschedule/{unit_id}`
- `delete_schedule(unit_id, schedule_id)`: DELETE
- `set_schedules_enabled(unit_id, enabled)`: PUT

**Note:** Schedule API uses integer enums (0, 1, 2) unlike control API strings

---

## Session 6: Telemetry Operations (Optional for v1.0)

**Priority:** Low - Nice to have for energy monitoring

- `get_temperature_history()`: Temperature data over time
- `get_energy_data()`: Energy consumption metrics
- `get_error_history()`: Device error logs

---

## Session 7: Home Assistant Integration

After API client is complete, build the HA custom component:

### Structure
```
custom_components/melcloudhome/
├── manifest.json
├── __init__.py
├── config_flow.py      # OAuth UI flow
├── coordinator.py      # Data update coordinator
├── climate.py          # Climate entity
├── sensor.py           # Energy, error, signal sensors
├── const.py            # HA-specific constants
└── strings.json        # UI translations
```

### Implementation Priority
1. `manifest.json` + `__init__.py`: Integration setup
2. `config_flow.py`: OAuth authentication flow
3. `coordinator.py`: Polling coordinator (60s minimum) with session refresh
4. `climate.py`: Climate entity (power, temp, mode, fan, vanes)
5. `sensor.py`: Optional sensors (energy, errors, Wi-Fi signal)

### Authentication Handling
**Decision:** See [ADR-002](../docs/decisions/002-authentication-refresh-strategy.md)

**v1.0 Implementation:**
- Store username/password (encrypted by HA)
- Coordinator catches `AuthenticationError` on 401
- Automatically re-login and retry operation
- Transparent to user (no manual re-authentication)

**Future (v1.1+):**
- Migrate to OAuth refresh tokens
- Remove password storage requirement
- Enhanced security following OAuth best practices

---

## Current State Summary

### What's Working ✅
- Authentication (AWS Cognito OAuth)
- Read operations (get devices, get device state)
- Write operations (power, temperature, mode, fan speed, vanes)
- Comprehensive testing infrastructure (16 tests, all passing)
- VCR cassette recording/replay for fast tests
- Type-safe code with all checks passing

### Next Priority 🎯
- **Home Assistant Integration** (Session 7)
- Build custom component with climate entity
- Implement coordinator with automatic re-authentication

### Future Work 📋
- Schedule management (v1.1 - Optional)
- Telemetry/energy monitoring (v1.1 - Optional)
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
