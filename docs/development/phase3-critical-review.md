# Phase 3 Plan - Critical Review vs ATA Implementation

## Goal

Validate Phase 3 plan against actual ATA implementation patterns to identify gaps, inconsistencies, or improvements.

---

## ✅ CORRECTLY CAPTURED PATTERNS

### 1. Entity Inheritance Pattern

**Plan says:**

```python
class ATWWaterHeater(CoordinatorEntity[MELCloudHomeCoordinator], WaterHeaterEntity)
```

**Actual ATA pattern:**

```python
class MELCloudHomeClimate(CoordinatorEntity[MELCloudHomeCoordinator], ClimateEntity)
class MELCloudHomeSensor(CoordinatorEntity[MELCloudHomeCoordinator], SensorEntity)
```

✅ **CORRECT** - Plan matches actual pattern

---

### 2. Entity Naming Strategy

**Plan says:**

- Unique ID: `{unit_id}_tank`, `{unit_id}_zone_1`
- Entity name: `"MELCloudHome {uuid_first4} {uuid_last4} Tank"`

**Actual ATA pattern (climate.py:77-81):**

```python
unit_id_clean = unit.id.replace("-", "")
self._attr_name = f"MELCloudHome {unit_id_clean[:4]} {unit_id_clean[-4:]}"
# Result: climate.melcloudhome_0efc_76db
```

**Actual ATA pattern (sensor.py:154-162):**

```python
self._attr_unique_id = f"{unit.id}_{description.key}"
self._attr_name = f"MELCloudHome {unit_id_clean[:4]} {unit_id_clean[-4:]} {key_clean.replace('_', ' ').title()}"
# Result: sensor.melcloudhome_0efc_76db_room_temperature
```

✅ **CORRECT** - Plan follows established naming conventions

---

### 3. Device Info Pattern

**Plan shows:**

```python
self._attr_device_info = DeviceInfo(
    identifiers={(DOMAIN, unit.id)},
    name=f"{building.name} {unit.name}",
    manufacturer="Mitsubishi Electric",
    model=f"Air-to-Water Heat Pump (Ecodan FTC{unit.ftc_model})",
)
```

**Actual ATA pattern (climate.py:83-90):**

```python
self._attr_device_info = DeviceInfo(
    identifiers={(DOMAIN, unit.id)},
    name=f"{building.name} {unit.name}",
    manufacturer="Mitsubishi Electric",
    model="Air-to-Air Heat Pump (via MELCloud Home)",
    suggested_area=building.name,
)
```

⚠️ **MINOR ISSUE** - Plan missing `suggested_area=building.name`

---

### 4. Coordinator Lookup Pattern

**Plan says:**

```python
@property
def _device(self) -> AirToWaterUnit | None:
    return self.coordinator.get_atw_unit(self._unit_id)
```

**Actual ATA pattern (climate.py:109-111):**

```python
@property
def _device(self) -> AirToAirUnit | None:
    return self.coordinator.get_unit(self._unit_id)  # type: ignore[no-any-return]
```

⚠️ **MINOR ISSUE** - Plan missing `# type: ignore[no-any-return]` comment

---

### 5. Service Call Refresh Pattern

**Plan says:**

```python
await self.coordinator.async_set_dhw_temperature(self._unit_id, temperature)
await self.coordinator.async_request_refresh_debounced()
```

**Actual ATA pattern (climate.py:304-307):**

```python
await self.coordinator.async_set_temperature(self._unit_id, temperature)
# Request debounced refresh to avoid race conditions
await self.coordinator.async_request_refresh_debounced()
```

✅ **CORRECT** - Plan matches actual pattern

---

## ⚠️ ISSUES FOUND IN PLAN

### Issue 1: Missing Building Lookup Helper

**Plan doesn't mention:**

Need to add `get_building_for_atw_unit()` method to coordinator, similar to existing:

```python
# coordinator.py:344-346
def get_building_for_unit(self, unit_id: str) -> Building | None:
    """Get the building that contains the specified unit - O(1) lookup."""
    return self._unit_to_building.get(unit_id)
```

**Fix needed:**

```python
def get_building_for_atw_unit(self, unit_id: str) -> Building | None:
    """Get the building that contains the specified ATW unit - O(1) lookup."""
    return self._atw_unit_to_building.get(unit_id)
```

**Impact:** Minor - entities don't currently use `_building` property, but should follow pattern for consistency.

---

### Issue 2: Temperature Unit Attribute

**Plan says:**

```python
_attr_temperature_unit = UnitOfTemperature.CELSIUS
```

**Actual ATA pattern (climate.py:57):**

```python
_attr_temperature_unit = "°C"
```

⚠️ **INCONSISTENCY** - Plan uses enum, actual uses string. Should match actual pattern.

**Fix:** Use `"°C"` string, not `UnitOfTemperature.CELSIUS`

---

### Issue 3: Sensor Availability Logic

**Plan says:**

```python
# Sensors check device.is_in_error in available property
```

**Actual ATA pattern (sensor.py:178-191):**

```python
@property
def available(self) -> bool:
    """Return if entity is available."""
    if not self.coordinator.last_update_success:
        return False

    unit = self.coordinator.get_unit(self._unit_id)
    if unit is None:
        return False

    # Check if device is in error state
    if unit.is_in_error:
        return False

    return self.entity_description.available_fn(unit)
```

✅ **CORRECT** - Plan should include `is_in_error` check in sensor availability

---

### Issue 4: Binary Sensor Special Cases

**Plan doesn't explicitly mention:**

Connection state binary sensor has special availability logic (binary_sensor.py:154-156):

```python
@property
def available(self) -> bool:
    """Return if entity is available."""
    # Connection sensor is always available (it reports connection status)
    if self.entity_description.key == "connection_state":
        return True
```

**Fix needed:** Plan should document this special case for ATW connection sensor.

---

### Issue 5: Entity Description Type Annotations

**Plan shows:**

```python
@dataclass(frozen=True, kw_only=True)
class MELCloudHomeATWSensorEntityDescription(SensorEntityDescription):
    value_fn: Callable[[AirToWaterUnit], float | str | None]
```

**Actual ATA pattern (sensor.py:34):**

```python
class MELCloudHomeSensorEntityDescription(SensorEntityDescription):  # type: ignore[misc]
    """..."""
```

⚠️ **MISSING** - Plan should include `# type: ignore[misc]` comment with explanation about HA dev environment

---

### Issue 6: Setup Function Logging

**Plan doesn't show:**

Actual ATA pattern includes debug logging (sensor.py:119-124):

```python
if entities:
    _LOGGER.debug(
        "Setting up %d sensor entities for %d units",
        len(entities),
        len([u for b in coordinator.data.buildings for u in b.air_to_air_units]),
    )
```

**Fix:** ATW setup functions should include similar logging for diagnostics.

---

### Issue 7: Climate Entity Doesn't Use Preset Modes Correctly

**Plan proposes:**

```python
_attr_preset_modes = ATW_PRESET_MODES
```

**CRITICAL FINDING:**

Looking at actual climate.py:

- ❌ ATA climate does NOT use preset modes at all
- ❌ No `_attr_preset_modes` attribute
- ❌ No `async_set_preset_mode()` method
- ❌ No `preset_mode` property

**ATW zone operation modes are fundamentally different:**

- ATA modes: Heat/Cool/Auto/Dry/Fan (HVAC modes)
- ATW zone modes: HeatRoomTemperature/HeatFlowTemperature/HeatCurve (heating strategies)

**Question:** Should ATW zone modes be:

1. **Preset modes** (plan's approach) - makes sense conceptually
2. **Custom service** - more complex but explicit
3. **Not exposed** - just use default mode (HeatRoomTemperature)

**Recommendation:** Preset modes ARE the correct HA pattern for this, but plan should note this is a NEW pattern not used by ATA.

---

### Issue 8: Water Heater Platform - No Existing Reference

**Plan proposes:** `water_heater.py` platform

**Finding:** No existing water_heater implementation to reference in codebase.

**Implication:**

- Can't copy-paste from ATA pattern (different platform type)
- Need to research Home Assistant `WaterHeaterEntity` base class
- Need to understand water_heater-specific features and methods

**Action needed:** Check HA water_heater component documentation or reference implementations.

---

### Issue 9: Entity Description Callable Signatures

**Plan shows:**

```python
value_fn: Callable[[AirToWaterUnit], float | str | None]
should_create_fn: Callable[[AirToWaterUnit], bool] | None = None
```

**Actual ATA pattern (sensor.py:41-48):**

```python
value_fn: Callable[[AirToAirUnit], float | str | None]
"""Function to extract sensor value from unit data."""

available_fn: Callable[[AirToAirUnit], bool] = lambda x: True
"""Function to determine if sensor is available."""

should_create_fn: Callable[[AirToAirUnit], bool] | None = None
"""Function to determine if sensor should be created. If None, uses available_fn."""
```

✅ **CORRECT** - Plan matches signatures, but should include docstrings

---

### Issue 10: Sensor Device Info Format

**Plan doesn't specify:**

Sensor and binary_sensor use dict format for device_info, not DeviceInfo object (sensor.py:165-167):

```python
# Link to device (same device as climate entity)
self._attr_device_info = {
    "identifiers": {(DOMAIN, unit.id)},
}
```

**Not:**

```python
self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, unit.id)})
```

⚠️ **INCONSISTENCY** - Climate uses `DeviceInfo` object, sensors use dict. Plan should clarify which to use for ATW sensors.

---

## 🔍 MISSING DETAILS IN PLAN

### Missing Detail 1: turn_on/turn_off Implementation

**Climate entity has these (climate.py:358-366):**

```python
async def async_turn_on(self) -> None:
    """Turn the entity on."""
    await self.coordinator.async_set_power(self._unit_id, True)
    await self.coordinator.async_request_refresh_debounced()

async def async_turn_off(self) -> None:
    """Turn the entity off."""
    await self.coordinator.async_set_power(self._unit_id, False)
    await self.coordinator.async_request_refresh_debounced()
```

✅ Plan includes these for water_heater, but should also include for ATW climate entities.

---

### Missing Detail 2: Type Ignore Comments

**Actual code has these throughout:**

- `# type: ignore[misc]` on class definitions (sensor.py:34, 96, 129)
- `# type: ignore[no-any-return]` on coordinator lookups (climate.py:111)

**Reason (from comments):**

```
Note: type: ignore[misc] required because HA is not installed in dev environment
(aiohttp version conflict). Mypy sees HA base classes as 'Any'.
```

**Plan should document:** All ATW entity classes will need same type ignore comments.

---

### Missing Detail 3: Translation Keys

**Actual pattern uses `translation_key` in entity descriptions:**

```python
MELCloudHomeSensorEntityDescription(
    key="room_temperature",
    translation_key="room_temperature",  # ← Used for i18n
    # ...
)
```

**Plan should specify:** Translation keys for all ATW sensors/binary_sensors.

**Files to check/create:**

- `translations/en.json` - English translations
- May need to add ATW-specific translation entries

---

### Missing Detail 4: Entity Category for Diagnostic Sensors

**WiFi signal sensor uses (sensor.py:72):**

```python
entity_category=EntityCategory.DIAGNOSTIC,
```

**Plan should specify:** Which ATW sensors are diagnostic vs regular.

**Recommendations:**

- `operation_status` - Regular sensor (primary UX)
- `wifi_signal` - Diagnostic
- `zone_*_temperature` - Regular (user-facing)
- `tank_temperature` - Regular (user-facing)

---

### Missing Detail 5: Initial Data Handling

**Actual pattern handles None gracefully:**

```python
@property
def native_value(self) -> float | str | None:
    """Return the sensor value."""
    unit = self.coordinator.get_unit(self._unit_id)
    if unit is None:
        return None
    return self.entity_description.value_fn(unit)
```

✅ Plan assumes this pattern but should explicitly document it.

---

## ❌ POTENTIAL PROBLEMS

### Problem 1: Water Heater Platform Complexity

**Plan estimates:** 250 lines for water_heater.py

**Reality check:**

- Climate.py (single entity type): 367 lines
- Water heater will need: properties + service methods + availability
- Likely closer to 200-220 lines (reasonable estimate)

✅ **ACCEPTABLE** - Estimate is in right ballpark

---

### Problem 2: Preset Modes Are New Territory

**Plan proposes:** ATW climate entities use preset modes

**Finding:** ATA climate does NOT use preset modes at all

**Implications:**

- No existing pattern to copy
- Need to research Home Assistant `ClimateEntityFeature.PRESET_MODE`
- Need to implement `async_set_preset_mode()` method
- Need to add `preset_mode` property

**Recommendation:** This is correct approach for ATW zone modes, but plan should note this is NEW functionality not present in ATA.

**Research needed:**

- How to properly implement preset modes
- Whether to use standard presets or custom ones
- UI behavior for preset selection

---

### Problem 3: 3-Way Valve HVAC Action Logic Incomplete

**Plan shows simplified logic:**

```python
if device.operation_status in ATW zone mode strings:
    if current < target - 0.5:
        return HVACAction.HEATING
    return HVACAction.IDLE
return HVACAction.IDLE
```

**Missing consideration:**

- What if `operation_status = "HeatRoomTemperature"` but it's Zone 2 mode, not Zone 1?
- Zone 1 climate entity should check if valve is on Zone 1 SPECIFICALLY

**Better logic:**

```python
# For Zone 1 entity
if device.operation_status == device.operation_mode_zone1:
    # Valve is on THIS zone
    if current < target - 0.5:
        return HVACAction.HEATING
    return HVACAction.IDLE

# Valve elsewhere (DHW or Zone 2)
return HVACAction.IDLE
```

⚠️ **NEEDS REFINEMENT** - Plan's hvac_action logic needs to differentiate which zone the valve is serving.

---

### Problem 4: Missing coordinator.get_building_for_atw_unit()

**Plan assumes this exists but coordinator only has:**

- `get_building_for_unit()` - for ATA units
- NOT `get_building_for_atw_unit()` - missing for ATW

**Fix required:** Add to coordinator.py:

```python
def get_building_for_atw_unit(self, unit_id: str) -> Building | None:
    """Get the building that contains the specified ATW unit - O(1) lookup."""
    return self._atw_unit_to_building.get(unit_id)
```

⚠️ **MISSING** - Plan should include this in Step 1 or coordinator updates

---

### Problem 5: Sensor Entity Description Typing

**Plan proposes new dataclass but doesn't address:**

Should it be a separate class (`MELCloudHomeATWSensorEntityDescription`) or reuse existing class with generic type?

**Actual pattern uses separate class per unit type:**

- `MELCloudHomeSensorEntityDescription` - uses `Callable[[AirToAirUnit], ...]`

**For ATW:**

- Need `MELCloudHomeATWSensorEntityDescription` - uses `Callable[[AirToWaterUnit], ...]`

✅ **CORRECT** - Plan's approach is right (separate class)

---

### Problem 6: Entity Description Shouldn't Have should_create_fn

**Looking at actual usage (sensor.py:106-117):**

```python
for description in SENSOR_TYPES:
    # Use should_create_fn if defined, otherwise use available_fn
    create_check = (
        description.should_create_fn
        if description.should_create_fn
        else description.available_fn
    )
    if create_check(unit):
        entities.append(MELCloudHomeSensor(...))
```

✅ **CORRECT** - Plan's use of `should_create_fn` matches actual pattern (used for energy sensor capability check)

---

## 🎯 CRITICAL FINDINGS SUMMARY

### HIGH PRIORITY FIXES

1. **Add `get_building_for_atw_unit()` to coordinator** - Missing but needed for pattern consistency

2. **Refine 3-way valve hvac_action logic** - Need to check which specific zone valve is serving, not just "is it on a zone"

3. **Add `suggested_area` to DeviceInfo** - Missing from plan's device_info examples

4. **Document preset mode implementation** - This is NEW functionality not in ATA, needs research

### MEDIUM PRIORITY FIXES

1. **Add type ignore comments** - All entity classes need `# type: ignore[misc]` with explanation

2. **Add setup logging** - Debug logs for entity count (matches ATA pattern)

3. **Clarify device_info format** - Dict for sensors vs DeviceInfo object for climate/water_heater

4. **Add translation_key documentation** - All entity descriptions need them

### LOW PRIORITY (NICE TO HAVE)

1. **Document diagnostic entity categories** - Which sensors are diagnostic vs regular

2. **Add entity description docstrings** - Match ATA pattern with inline documentation

---

## 📋 RECOMMENDED PLAN UPDATES

### Update 1: Add Missing Coordinator Method

**Add to Step 1 (Foundation):**

```python
# coordinator.py - Add after get_atw_unit()
def get_building_for_atw_unit(self, unit_id: str) -> Building | None:
    """Get the building that contains the specified ATW unit - O(1) lookup."""
    return self._atw_unit_to_building.get(unit_id)
```

---

### Update 2: Refine HVAC Action Logic

**For Zone 1 Climate:**

```python
@property
def hvac_action(self) -> HVACAction | None:
    """Return current HVAC action (3-way valve aware)."""
    device = self._device
    if device is None or not device.power:
        return HVACAction.OFF

    # Check if 3-way valve is serving THIS zone (Zone 1)
    # operation_status shows which mode is ACTIVE (what valve is doing)
    # operation_mode_zone1 shows CONFIGURED mode for Zone 1

    # If status matches Zone 1's mode, valve is on Zone 1
    if device.operation_status == device.operation_mode_zone1:
        current = device.room_temperature_zone1
        target = device.set_temperature_zone1

        if current is not None and target is not None:
            if current < target - 0.5:  # Hysteresis
                return HVACAction.HEATING
        return HVACAction.IDLE

    # Valve is elsewhere (DHW or Zone 2)
    return HVACAction.IDLE
```

**For Zone 2 Climate:**

```python
# Similar but checks: device.operation_status == device.operation_mode_zone2
```

---

### Update 3: Water Heater Platform Research

**Before implementing water_heater.py, research:**

1. Home Assistant `WaterHeaterEntity` base class methods
2. Required properties: `current_temperature`, `target_temperature`, etc.
3. Service methods: `async_set_temperature()`, `async_set_operation_mode()`
4. Feature flags: What features are available?
5. Example implementations from other integrations

**OR:** Check if HA has water_heater component at all (it may be deprecated/renamed).

---

### Update 4: Add Type Annotations Documentation

**Standard pattern to add to all ATW entity classes:**

```python
class ATWWaterHeater(
    CoordinatorEntity[MELCloudHomeCoordinator],  # type: ignore[misc]
    WaterHeaterEntity,  # type: ignore[misc]
):
    """Water heater entity for ATW DHW tank.

    Note: type: ignore[misc] required because HA is not installed in dev environment
    (aiohttp version conflict). Mypy sees HA base classes as 'Any'.
    """
```

---

### Update 5: Explicit Setup Logging

**Add to all setup functions:**

```python
async def async_setup_entry(...):
    # ... create entities ...

    if entities:
        _LOGGER.debug(
            "Setting up %d ATW sensor entities for %d units",
            len(entities),
            len([u for b in coordinator.data.buildings for u in b.air_to_water_units]),
        )

    async_add_entities(entities)
```

---

## 🚨 BLOCKERS THAT NEED RESOLUTION

### Blocker 1: Water Heater Platform May Not Exist in HA

**Investigation needed:** Does Home Assistant have `water_heater` platform?

**Check:**

- HA core repository for `homeassistant.components.water_heater`
- Official integrations using water_heater
- Alternative: Use `climate` entity with custom features?

**If water_heater doesn't exist:**

- Alternative 1: Create DHW as second climate entity (less intuitive but works)
- Alternative 2: Use `switch` + `number` entities (crude but functional)
- Alternative 3: Use custom component domain

---

### Blocker 2: Preset Modes Pattern Not Established

**Research needed:**

- How to properly implement `ClimateEntityFeature.PRESET_MODE`
- Whether custom presets are allowed or must use standard ones
- UI behavior in HA frontend
- Example implementations from other climate integrations

**Standard HA presets:**

- `away`, `boost`, `comfort`, `eco`, `home`, `sleep`, `activity`

**ATW needs:**

- `room_temperature` - ❌ Not standard
- `flow_temperature` - ❌ Not standard
- `weather_compensation` - ❌ Not standard

**Options:**

1. Use custom presets (if HA supports)
2. Map to standard presets (confusing for users)
3. Don't expose modes via climate entity (use separate service)

---

## ✅ STRENGTHS OF PLAN

1. **Comprehensive scope** - Covers all entity types needed
2. **Follows ATA patterns** - Consistency with existing code
3. **Testing strategy sound** - Mock at API boundary, test through HA core
4. **Conditional creation logic** - Handles Zone 2 properly
5. **Device grouping** - All entities under same device
6. **Coordinator reuse** - Leverages Phase 2 control methods
7. **3-way valve awareness** - Recognizes physical limitation
8. **Realistic estimates** - Time and line count estimates reasonable

---

## 📊 FINAL VERDICT

### Plan Quality: **B+ (Good but needs refinement)**

**Strengths:**

- ✅ Solid architectural decisions
- ✅ Follows most ATA patterns correctly
- ✅ Comprehensive coverage
- ✅ Realistic scope

**Weaknesses:**

- ⚠️ Missing some implementation details (type ignores, logging, building lookup)
- ⚠️ 3-way valve hvac_action logic needs refinement
- ⚠️ Assumes water_heater platform exists (needs verification)
- ⚠️ Preset modes are uncharted territory (no ATA reference)

---

## 🔧 RECOMMENDED ACTIONS

### Before Starting Implementation

1. **Verify water_heater platform exists in HA** - Critical blocker
   - Check HA documentation
   - Find reference implementations
   - Alternative plans if it doesn't exist

2. **Research preset mode implementation** - New pattern
   - Find examples in other integrations
   - Understand custom vs standard presets
   - Validate UI behavior

3. **Add missing coordinator method** - `get_building_for_atw_unit()`

4. **Refine plan with findings** - Update Phase 3 plan with:
   - Type ignore comments
   - Setup logging
   - Refined hvac_action logic
   - DeviceInfo vs dict clarification

### During Implementation

1. **Follow ATA patterns exactly** - Copy working code, adapt for ATW
2. **Test incrementally** - Don't wait until all platforms done
3. **Reference actual files** - climate.py:109, sensor.py:165, etc.

---

## 📝 QUICK REFERENCE CHECKLIST

When implementing ATW entities, ensure:

- [ ] Class has `# type: ignore[misc]` comment
- [ ] Device info includes `suggested_area=building.name`
- [ ] Temperature unit is string `"°C"` not enum
- [ ] `_device` property has `# type: ignore[no-any-return]`
- [ ] Sensors check `is_in_error` in availability
- [ ] Connection sensor has special availability (always True)
- [ ] Setup function includes debug logging
- [ ] Entity descriptions have docstrings
- [ ] Sensors use dict for device_info, climate uses DeviceInfo object
- [ ] All service calls end with `async_request_refresh_debounced()`
- [ ] HVAC action checks WHICH zone valve is serving (not just "is on a zone")

---

## 🎓 LESSONS FOR FUTURE PHASES

1. **Critical review before implementation** - Saves rework
2. **Verify assumptions early** - Water heater platform existence
3. **Research new patterns** - Preset modes not in ATA
4. **Copy exact patterns** - Type ignores, logging, comments matter
5. **Test incrementally** - Don't build everything then test

---

## CONCLUSION

**The Phase 3 plan is solid and implementable**, but needs refinement in several areas:

1. Add missing coordinator helper
2. Verify water_heater platform exists
3. Research preset mode implementation
4. Refine 3-way valve logic
5. Document type ignores and other boilerplate

**Recommendation:** Update plan with these findings, then proceed with implementation starting with water_heater platform research/verification.
