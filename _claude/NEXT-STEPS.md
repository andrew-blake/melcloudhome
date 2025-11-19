# Next Steps for MELCloud Home Integration

This document tracks current and upcoming work for the MELCloud Home custom component.

**For completed sessions (1-9), see [SESSION-HISTORY.md](SESSION-HISTORY.md)**

---

## 🚀 Quick Start for New Session

**Current Status:** ✅ v1.2.1 COMPLETE (WiFi signal monitoring added) | 🎯 Ready for Energy Monitoring (v1.3) or HACS

### What's Working

- ✅ Integration deployed and configured
- ✅ All devices discovered and controllable
- ✅ HVAC controls working (power, temp, mode, fan, swing)
- ✅ TURN_ON/TURN_OFF support (HA 2025.1+ compliant)
- ✅ Voice assistant commands working
- ✅ Sensor platform with room temperature sensors (2 entities)
- ✅ **NEW: WiFi signal strength sensors (2 entities) - Session 12**
- ✅ Binary sensor platform (error state + connection monitoring)
- ✅ HVAC action property (heating/cooling/idle/off feedback)
- ✅ Horizontal swing mode support (independent vane control)
- ✅ 60s polling with auto-refresh
- ✅ Standard HA climate entity UI
- ✅ Stable entity IDs based on unit UUIDs
- ✅ Diagnostics export support
- ✅ Custom integration icon
- ✅ Comprehensive documentation

### ✅ v1.2.1 Progress (Session 12)

- ✅ WiFi signal strength sensor implemented
- ✅ Updated `api/models.py` to parse `rssi` field
- ✅ Added WiFi signal sensor to `sensor.py`
- ✅ Device class: `SIGNAL_STRENGTH` with dBm unit
- ✅ Entity category: `DIAGNOSTIC`
- ✅ 2 WiFi signal sensors deployed and working
- ✅ Energy monitoring requirements documented for v1.3

### What to do next

1. **v1.2.1 Complete!** WiFi signal monitoring deployed
2. **Choose path:**
   - **Option A:** Energy monitoring implementation (v1.3) - 4-5 hours - See `_claude/energy-monitoring-requirements.md`
   - **Option B:** HACS distribution (requires separate repository) - 7-9 hours - See ROADMAP.md
3. **Quick Updates:** `uv run python tools/deploy_custom_component.py melcloudhome --reload`
4. **Check Logs:** `ssh ha "sudo docker logs -f homeassistant" | grep melcloudhome`

### Next session options

**Option A - Session 13:** Energy Monitoring (v1.3) - 4-5 hours
- Implement telemetry API polling (30-minute intervals)
- Add energy consumption sensors
- Integrate with HA Energy Dashboard
- **Entity ID format:** Use `sensor.melcloud_*_energy` (shorter, cleaner than `energy_consumed`)
- **See:** `_claude/energy-monitoring-requirements.md` for complete implementation plan

**Option B - Session 13:** HACS Distribution Setup - 8-11 hours
- **IMPORTANT:** Fix mypy type errors first (1-2 hours)
- Create separate repository
- Prepare for HACS submission
- **See:** [HACS details in ROADMAP.md](#)

### Reference Documents

- `_claude/ROADMAP.md` - Complete roadmap with v1.1.3 and v1.2+ planning
- `_claude/SESSION-HISTORY.md` - Archive of completed sessions 1-9
- `_claude/climate-entity-feature-research.md` - Missing features analysis (Session 9)
- `_claude/repository-strategy.md` - HACS distribution strategy
- `_claude/session-9-research-findings.md` - Complete Session 9 research
- `_claude/websocket-research-defer.md` - WebSocket investigation (deferred to v1.3)
- `_claude/KNOWN-ISSUES.md` - Current open issues
- `docs/decisions/007-defer-websocket-implementation.md` - WebSocket deferral ADR

---

## Session 10: v1.1.3 Compliance Hotfix ✅ COMPLETE

**Goal:** Fix critical HA 2025.1 compliance issue with turn_on/turn_off

**Status:** Complete (2025-11-18)
**Timeline:** 1.5 hours
**Priority:** CRITICAL
**Reference:** `_claude/climate-entity-feature-research.md`, `_claude/ROADMAP.md`, `_claude/SESSION-HISTORY.md`

### Critical Issue

**Missing TURN_ON/TURN_OFF Support:**
- Home Assistant 2025.1 requires `ClimateEntityFeature.TURN_ON` and `TURN_OFF` flags
- Without these, voice commands and automations may fail
- Simple 1-hour fix with high user impact

### Implementation Tasks

#### 1. Update climate.py ✅ Complete

- ✅ Add `async_turn_on()` method
- ✅ Add `async_turn_off()` method
- ✅ Add TURN_ON/TURN_OFF feature flags to `supported_features`
- ✅ Test locally with deployment tool

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

#### 2. Testing ✅ Complete

- ✅ Feature flags verified (425 = 256 + 128 + 32 + 8 + 1)
- ✅ Turn off functionality tested and working
- ✅ No breaking changes or regressions
- 🔜 Voice command testing (user to verify)
- 🔜 Automation testing (user to verify)

#### 3. Deployment ✅ Complete

- ✅ Deploy to production via deployment tool
- ✅ Monitor logs for errors (no errors found)
- ✅ Feature flags verified via API
- ✅ Integration loaded successfully

#### 4. Documentation ✅ Complete

- ✅ Update session notes in SESSION-HISTORY.md
- ✅ Mark v1.1.3 as complete in ROADMAP.md
- ✅ Update NEXT-STEPS.md for Session 11 (v1.2)

### Deliverables

- Updated `custom_components/melcloudhome/climate.py`
- v1.1.3 deployed to production
- No breaking changes
- HA 2025.1+ compliance achieved

### Success Criteria

- ✅ TURN_ON/TURN_OFF methods implemented
- ✅ Feature flags added (verified: 425 = 256 + 128 + 32 + 8 + 1)
- 🔜 Voice commands working (Google Home, Alexa) - User to verify
- 🔜 Automations using climate.turn_on working - User to verify
- ✅ Device resumes previous state correctly (inherent in device behavior)
- ✅ Deployed to production
- ✅ No breaking changes or regressions

**Completed:** Session 10 v1.1.3 (2025-11-18)

**Next:** Session 11 - v1.2 Implementation (Sensors + HACS + Enhanced Features)

---

## Session 11a: Sensor Platform ✅ COMPLETE

**Goal:** Implement sensor platform with entity description pattern

**Status:** Complete (2025-11-18)
**Timeline:** 4 hours
**Priority:** HIGH

### Implementation Complete

- ✅ Created `sensor.py` with modern entity description pattern (ADR-006)
- ✅ Implemented room temperature sensor (2 entities created)
- ✅ Added energy consumption placeholder (future-ready)
- ✅ Updated `__init__.py` to register sensor platform
- ✅ Updated manifest.json to v1.2.0
- ✅ Deployed to production
- ✅ No errors, properly linked to devices

### Deliverables

- New file: `custom_components/melcloudhome/sensor.py` (5.5KB)
- Updated: `__init__.py`, `manifest.json`
- 2 sensor entities: `sensor.melcloud_0efc_76db_room_temperature`, `sensor.melcloud_bf8d_5119_room_temperature`

---

## Session 11b: Binary Sensor Platform ✅ COMPLETE

**Goal:** Add binary sensors for error states and connection monitoring

**Status:** Complete (2025-11-18)
**Timeline:** 2 hours
**Priority:** MEDIUM

### Implemented Features

- ✅ Error state binary sensor (device_class: PROBLEM)
- ✅ Connection state binary sensor (device_class: CONNECTIVITY)
- ✅ Entity description pattern (same as sensor.py)
- ✅ 4 binary sensor entities deployed (2 per unit)

### Implementation Complete

1. ✅ Created `binary_sensor.py` with entity descriptions
2. ✅ Implemented error state sensor (`unit.is_in_error`)
3. ✅ Implemented connection state sensor (coordinator status)
4. ✅ Updated `__init__.py` to add Platform.BINARY_SENSOR
5. ✅ Updated `strings.json` with entity translations
6. ✅ Deployed and tested successfully

### Deliverables

- New file: `custom_components/melcloudhome/binary_sensor.py` (4.4KB)
- Updated: `__init__.py`, `strings.json`
- 4 binary sensor entities created:
  - `binary_sensor.melcloud_0efc_76db_error_state`
  - `binary_sensor.melcloud_0efc_76db_connection_state`
  - `binary_sensor.melcloud_bf8d_5119_error_state`
  - `binary_sensor.melcloud_bf8d_5119_connection_state`

### Success Criteria

- ✅ Binary sensors created and linked to devices
- ✅ Error state sensors showing "off" (no errors)
- ✅ Connection state sensors showing "on" (connected)
- ✅ No errors in Home Assistant logs
- ✅ Code quality checks passed (ruff, mypy)

**Completed:** Session 11b Binary Sensor Platform (2025-11-18)

**Next:** Session 11c - Enhanced Climate Features (HVAC action, horizontal swing)

---

## Session 11c: Enhanced Climate Features ✅ COMPLETE

**Goal:** Add HVAC action and horizontal swing mode support

**Status:** Complete (2025-11-18)
**Timeline:** 3 hours (actual)
**Priority:** MEDIUM

### Implemented Features

- ✅ HVAC action property (heating/cooling/idle/off/drying/fan)
- ✅ Horizontal swing mode support (independent from vertical)
- ✅ Temperature-based action inference with 0.5°C hysteresis
- ✅ HA 2024.12+ SWING_HORIZONTAL_MODE feature support

### Implementation Complete

1. ✅ Added `hvac_action` property with intelligent inference
2. ✅ Implemented horizontal swing properties (`swing_horizontal_mode`, `swing_horizontal_modes`)
3. ✅ Added `async_set_swing_horizontal_mode()` method
4. ✅ Added `ClimateEntityFeature.SWING_HORIZONTAL_MODE` flag
5. ✅ Updated `const.py` with horizontal vane positions
6. ✅ Deployed and tested successfully

### Deliverables

- Updated: `custom_components/melcloudhome/climate.py` (+90 lines)
- Updated: `custom_components/melcloudhome/const.py` (added horizontal positions)
- HVAC action shows real-time heating/cooling/idle status
- Horizontal swing independently controllable from vertical

### Success Criteria

- ✅ HVAC action property works correctly
- ✅ Temperature-based inference with hysteresis prevents flapping
- ✅ Horizontal swing modes available (7 positions)
- ✅ No errors in Home Assistant logs
- ✅ Code quality checks passed (ruff)
- ✅ Integration loaded and entities active

**Completed:** Session 11c Enhanced Climate Features (2025-11-18)

**Next:** Session 12 - WiFi Signal Monitoring

---

## Session 12: WiFi Signal Monitoring ✅ COMPLETE

**Goal:** Add WiFi signal strength sensors for diagnostic troubleshooting

**Status:** Complete (2025-11-19)
**Timeline:** 1.5 hours
**Priority:** HIGH
**Reference:** `_claude/energy-monitoring-requirements.md` for v1.3 planning

### Implemented Features

- ✅ WiFi signal strength sensor (device_class: SIGNAL_STRENGTH)
- ✅ Shows RSSI in dBm (typical range: -30 excellent to -90 poor)
- ✅ Entity category: DIAGNOSTIC
- ✅ 2 WiFi signal sensors deployed

### Implementation Complete

1. ✅ Updated `api/models.py` to parse `rssi` field from API response (`api/models.py:125,247`)
2. ✅ Added WiFi signal sensor entity description to `sensor.py`
3. ✅ Added translation key to `strings.json`
4. ✅ Deployed and verified sensors registered successfully
5. ✅ Code quality checks passed (ruff, mypy)

### Deliverables

- Updated: `custom_components/melcloudhome/api/models.py` (added rssi field)
- Updated: `custom_components/melcloudhome/sensor.py` (added WiFi signal sensor)
- Updated: `custom_components/melcloudhome/strings.json` (added translation)
- 2 WiFi signal sensor entities created:
  - `sensor.melcloud_0efc_76db_wifi_signal`
  - `sensor.melcloud_bf8d_5119_wifi_signal`

### Success Criteria

- ✅ WiFi signal sensors created and linked to devices
- ✅ Correct device_class (signal_strength) and unit (dBm)
- ✅ Entity category set to DIAGNOSTIC
- ✅ No errors in Home Assistant logs
- ✅ Code quality checks passed (ruff, mypy)
- ✅ Integration loaded and entities registered

### Research & Documentation

- ✅ Researched Home Assistant WiFi signal patterns
- ✅ Confirmed API provides `rssi` field in `/api/user/context` response
- ✅ Documented energy monitoring requirements for v1.3
- ✅ Created comprehensive `_claude/energy-monitoring-requirements.md`

**Completed:** Session 12 WiFi Signal Monitoring (2025-11-19)

**Next:** Session 13 - Energy Monitoring (v1.3) OR HACS Distribution

---

## 🎯 Session 13 Quick Start: Energy Monitoring (v1.3)

**Decision Made:** Implement energy monitoring (Option A)

### Key Decisions Already Made:
- ✅ Entity ID: `sensor.melcloud_*_energy` (not `energy_consumed` - keep it short)
- ✅ Polling interval: 30 minutes
- ✅ Architecture: Extend coordinator (Option A from requirements doc)
- ✅ Time range: Last hour
- ✅ Device class: `SensorDeviceClass.ENERGY`
- ✅ State class: `SensorStateClass.TOTAL_INCREASING`
- ✅ Unit: `UnitOfEnergy.KILO_WATT_HOUR`

### Implementation Steps:

**Phase 1: Architecture & Testing (1 hour)**
1. Read `_claude/energy-monitoring-requirements.md` for complete plan
2. Test telemetry API endpoint with real device:
   ```bash
   # Check if energy data is available
   curl "https://melcloudhome.com/api/telemetry/energy/0efce33f-5847-4042-88eb-aaf3ff6a76db?from=2025-11-19%2000:00&to=2025-11-19%2023:59&interval=Hour&measure=cumulative_energy_consumed_since_last_upload"
   ```
3. Determine unit conversion (Wh vs kWh)
4. Create ADR-008: Energy Monitoring Architecture

**Phase 2: Implementation (3 hours)**
1. Add telemetry methods to `api/client.py`
2. Extend coordinator with energy polling
3. Update `api/models.py` - add `energy_consumed` property
4. Update `sensor.py` - change key from `"energy_consumed"` to `"energy"` ⚠️
5. Test and deploy

**Files to Modify:**
- `custom_components/melcloudhome/api/client.py` - Add `get_energy_data()` and `_parse_energy_response()`
- `custom_components/melcloudhome/coordinator.py` - Add energy polling
- `custom_components/melcloudhome/api/models.py` - Add energy property
- `custom_components/melcloudhome/sensor.py` - Update energy sensor key to `"energy"`
- `custom_components/melcloudhome/strings.json` - Change translation key to `"energy"`
- `docs/decisions/008-energy-monitoring-architecture.md` - New ADR

**Expected Result:**
- 2 new sensors: `sensor.melcloud_0efc_76db_energy` and `sensor.melcloud_bf8d_5119_energy`
- Integration with HA Energy Dashboard
- 30-minute polling for energy data

---

## Reference Documentation

### Development Workflow

- `CLAUDE.md`: Development workflow and project structure
- `tools/README.md`: Deployment tool documentation and workflows
- `_claude/SESSION-HISTORY.md`: Archive of completed sessions

### Architecture & Decisions

- `docs/decisions/001-bundled-api-client.md`: ADR for bundled architecture
- `docs/decisions/002-authentication-refresh-strategy.md`: ADR for auth handling
- `docs/decisions/003-entity-naming-strategy.md`: ADR for entity naming and device registry
- `docs/decisions/004-integration-refactoring.md`: ADR for DRY/KISS/performance fixes
- `docs/decisions/005-divergence-from-official-melcloud.md`: Architecture ADR
- `docs/decisions/006-entity-description-pattern.md`: Sensor pattern ADR
- `docs/decisions/007-defer-websocket-implementation.md`: WebSocket deferral ADR

### API Documentation

- `_claude/melcloudhome-api-reference.md`: Complete API reference with verified values
- `_claude/melcloudhome-schedule-api.md`: Schedule management endpoints
- `_claude/melcloudhome-telemetry-endpoints.md`: Monitoring and reporting APIs
- `_claude/energy-monitoring-requirements.md`: Energy monitoring requirements and implementation plan (v1.3)
- `_claude/openapi.yaml`: OpenAPI 3.0.3 specification

### Quality & Testing

- `docs/integration-review.md`: Best practices review and quality assessment
- `docs/testing-strategy.md`: Why not to mock HA and proper testing approaches
