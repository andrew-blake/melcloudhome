# Phase 3: Final Scope - Simplified for Single Zone

**Date:** 2026-01-04
**Status:** Scope finalized based on hardware availability and user decisions

---

## Key User Decisions

### 1. Preset Mode Naming ✅
**Decision:** Lowercase keys with translations
- **Code:** `ATW_PRESET_MODES = ["room", "flow", "curve"]`
- **UI Display:** "Room", "Flow", "Curve" (via translations/en.json)
- **Default preset:** `"room"` (HeatRoomTemperature - safest, most common)
- **Rationale:** Matches official MELCloud UI terminology, proper i18n pattern

### 2. Operation Status Display ✅
**Decision:** Show raw API values (no mapping)
- **Sensor values:** "Stop", "HotWater", "HeatRoomTemperature", "HeatFlowTemperature", "HeatCurve"
- **Rationale:** Technical accuracy, no information loss, simplifies implementation

### 3. Forced DHW Visibility ✅
**Decision:** Separate binary sensor
- **Entity:** `binary_sensor.melcloudhome_*_forced_dhw_active`
- **Rationale:** Enables automation triggers, shows in entity list

### 4. Power Control ✅
**Decision:** Both water_heater and climate can power off entire system
- **Behavior:** Matches official MELCloud app
- **Documentation:** Clearly documented in code comments and ADR

### 5. Zone 2 Support ✅
**Decision:** SKIP ENTIRELY - Defer to Phase 4
- **Rationale:** No Zone 2 test hardware available
- **Impact:** Significantly simplified scope

### 6. Sensor Coverage ✅
**Decision:** Essential sensors only (3)
- Zone 1 temperature ✅
- Tank temperature ✅
- Operation status ✅
- WiFi signal ❌ DEFERRED

### 7. Entity Naming ✅
**Decision:** Include zone suffix even though only Zone 1
- **Climate entity:** `climate.melcloudhome_0efc_76db_zone_1` (with suffix)
- **Rationale:** Future-proof for Phase 4, clear which zone, consistent with multi-zone systems

### 8. Default Operation Modes ✅
**Decision:** Use safe defaults
- **Climate preset:** `"room"` (thermostat control)
- **Water heater mode:** `"eco"` (balanced operation)
- **Rationale:** Safest modes for residential use, match common patterns

### 9. Implementation Order ✅
**Decision:** Water heater first
- **Order:** Water heater → Climate → Sensors → Binary Sensors
- **Rationale:** Water heater simpler (no preset complexity), builds confidence before tackling climate presets

---

## Simplified Phase 3 Scope

### Entities to Implement (8 total per ATW device):

**Climate (1):**
- `climate.melcloudhome_{id}_zone_1` - Zone 1 room temperature control
  - Preset modes: "room", "flow", "curve" (default: "room")
  - HVAC modes: OFF, HEAT
  - Temperature range: 10-30°C

**Water Heater (1):**
- `water_heater.melcloudhome_{id}_tank` - DHW tank control
  - Operation modes: "eco", "performance" (default: "eco")
  - Temperature range: 40-60°C
  - Powers entire system

**Sensors (3):**
- `sensor.melcloudhome_{id}_zone_1_temperature` - Zone 1 room temp (°C)
- `sensor.melcloudhome_{id}_tank_temperature` - DHW tank temp (°C)
- `sensor.melcloudhome_{id}_operation_status` - 3-way valve position (raw: "Stop", "HotWater", etc.)

**Binary Sensors (3):**
- `binary_sensor.melcloudhome_{id}_error_state` - Device errors (problem class)
- `binary_sensor.melcloudhome_{id}_connection_state` - Online/offline (connectivity class)
- `binary_sensor.melcloudhome_{id}_forced_dhw_active` - DHW priority mode (running class)

---

## Deferred to Phase 4:

**Zone 2 Support:**
- Zone 2 climate entity
- Zone 2 temperature sensor
- Zone 2-specific logic

**Additional Sensors:**
- WiFi signal sensor
- Outdoor temperature sensor (if available)
- Zone 2 target temperature sensor

---

## Updated Implementation Estimates

### Time Estimate: 8-12 hours (down from 12-17)
- Constants & coordinator helper: 30 minutes
- Translations: 30 minutes
- Water heater platform: 3-4 hours
- Climate Zone 1: 2-3 hours
- Sensors (3 only): 1 hour
- Binary sensors: 1 hour
- Integration testing: 2-3 hours

### Code Estimate: ~1,476 lines (down from ~2,640)

**Production Code:** ~676 lines
- coordinator.py: +10
- const.py: +20
- translations/en.json: +15
- water_heater.py: +250 (NEW)
- climate.py: +200 (Zone 1 only)
- sensor.py: +80 (3 sensors)
- binary_sensor.py: +100 (3 binary sensors)
- __init__.py: +1

**Test Code:** ~800 lines
- test_water_heater.py: +300 (NEW)
- test_climate.py: +250 (Zone 1 only)
- test_sensor.py: +100 (3 sensors)
- test_binary_sensor.py: +100 (3 binary sensors)
- conftest.py: +50 (mock builder)

---

## Constants Updates (const.py)

```python
# ATW Zone Modes → Climate Preset Modes (lowercase for i18n)
ATW_TO_HA_PRESET = {
    "HeatRoomTemperature": "room",  # Display: "Room" (in en.json)
    "HeatFlowTemperature": "flow",  # Display: "Flow"
    "HeatCurve": "curve",            # Display: "Curve"
}

HA_TO_ATW_PRESET = {
    "room": "HeatRoomTemperature",
    "flow": "HeatFlowTemperature",
    "curve": "HeatCurve",
}

# Preset modes list
ATW_PRESET_MODES = ["room", "flow", "curve"]

# Water Heater Operation Modes (use HA standard modes)
# Import from homeassistant.components.water_heater: STATE_ECO, STATE_PERFORMANCE
WATER_HEATER_FORCED_DHW_TO_HA = {
    False: "eco",        # Maps to STATE_ECO
    True: "performance",  # Maps to STATE_PERFORMANCE
}
WATER_HEATER_HA_TO_FORCED_DHW = {
    "eco": False,
    "performance": True,
}
```

---

## Translations Updates (translations/en.json)

**Add to existing JSON structure:**

```json
{
  "entity": {
    "climate": {
      "melcloudhome": {
        "preset_mode": {
          "room": "Room",
          "flow": "Flow",
          "curve": "Curve"
        }
      }
    },
    "sensor": {
      "zone_1_temperature": {
        "name": "Zone 1 temperature"
      },
      "tank_temperature": {
        "name": "Tank temperature"
      },
      "operation_status": {
        "name": "Operation status"
      }
    },
    "binary_sensor": {
      "forced_dhw_active": {
        "name": "Forced DHW active"
      }
    }
  }
}
```

---

## Implementation Priority Order

### 1. Foundation (30 min)
- Add `get_building_for_atw_unit()` to coordinator
- Update const.py with simplified constants
- Update translations/en.json

### 2. Water Heater (3-4 hours)
- Create water_heater.py
- Create test_water_heater.py
- Verify DHW control works

### 3. Climate Zone 1 (2-3 hours)
- Add ATWClimateZone1 to climate.py
- Implement preset modes (NEW functionality)
- Add tests
- Verify 3-way valve awareness

### 4. Sensors (1 hour)
- Add 3 sensor descriptions to sensor.py
- Add ATWSensor class
- Add tests

### 5. Binary Sensors (1 hour)
- Add 3 binary sensor descriptions to binary_sensor.py
- Add ATWBinarySensor class
- Add tests

### 6. Integration (2-3 hours)
- Platform registration in __init__.py
- End-to-end testing
- Device grouping verification

---

## Success Criteria (Simplified)

### Functionality
- [ ] Water heater entity created
- [ ] Zone 1 climate entity created (Zone 2 skipped)
- [ ] 3 sensors created (zone temp, tank temp, operation status)
- [ ] 3 binary sensors created (error, connection, forced DHW)
- [ ] All entities grouped under same device
- [ ] Temperature controls work (DHW, Zone 1)
- [ ] Operation modes work (water heater eco/performance, climate presets)
- [ ] Power control works from both entities
- [ ] 3-way valve status visible in operation_status sensor
- [ ] Climate hvac_action shows IDLE when valve on DHW

### Testing
- [ ] All entity creation tests pass
- [ ] All service call tests pass
- [ ] Preset mode tests pass (NEW)
- [ ] No regressions in ATA tests

### Code Quality
- [ ] No type errors
- [ ] No lint errors
- [ ] All type: ignore comments documented
- [ ] Setup functions have debug logging
- [ ] DeviceInfo has suggested_area

---

## Phase 4 Scope (Future)

When Zone 2 hardware becomes available:
- Add ATWClimateZone2 class
- Add zone_2_temperature sensor
- Add conditional creation logic (`if unit.capabilities.has_zone2`)
- Add WiFi signal sensor
- Test dual-zone scenarios

**Estimated Phase 4 effort:** 4-6 hours
**Estimated Phase 4 code:** ~1,000 lines

---

## Key Takeaways

✅ **Simplified scope is achievable** - 8-12 hours vs 12-17
✅ **Focus on testable features** - Only single zone that can be verified
✅ **Proper i18n from start** - Lowercase keys + translations
✅ **No information loss** - Operation status shows raw API values
✅ **Clean separation** - Zone 2 cleanly deferred, not half-implemented
