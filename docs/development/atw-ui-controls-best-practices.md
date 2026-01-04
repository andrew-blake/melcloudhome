# Home Assistant UI Controls for ATW Heat Pump - Best Practices

**Question:** What HA UI controls should be available for our ATW heat pump? What's best practice?

**Status:** Research complete - Architecture already defined in ADR-012

---

## Summary: Recommended Entity Architecture

Based on official MELCloud integration patterns and ADR-012 architectural decisions:

### Per ATW Device, Create 4 Entity Types

1. **`water_heater` entity** (1 per device) - DHW tank control
2. **`climate` entities** (1-2 per device) - Zone heating control
3. **`sensor` entities** (5-7 per device) - Temperature monitoring
4. **`binary_sensor` entities** (2 per device) - Status flags

---

## 1. Water Heater Entity (DHW Tank)

**Entity ID:** `water_heater.{device_name}_tank`

### UI Controls Available

```yaml
Temperature Slider:
  Range: 40-60°C (hardcoded safe defaults)
  Step: 0.5°C or 1.0°C (based on device capability)
  Label: "Target DHW Temperature"

Operation Mode Dropdown:
  Options:
    - eco          # Normal balanced operation (forcedHotWaterMode=False)
    - performance  # DHW priority mode (forcedHotWaterMode=True)
  Label: "DHW Operation Mode"

Power Toggle:
  On/Off: Controls ENTIRE heat pump system (not just DHW)
  Label: "Heat Pump Power"

State Attributes (visible in "more info"):
  - operation_status: "HotWater" | "HeatRoomTemperature" | "Stop"
  - forced_dhw_active: true/false
  - zone_heating_suspended: true/false (when valve on DHW)
```

### Services

- `water_heater.set_temperature` - Set DHW target temp
- `water_heater.set_operation_mode` - Set eco/performance mode
- `water_heater.turn_on` / `turn_off` - System power control

### Key Behavior

⭐ **CRITICAL:** `turn_off()` powers off the **entire heat pump**, not just DHW.

---

## 2. Climate Entity (Zone Heating)

**Entity ID:**

- `climate.{device_name}_zone_1` (always present)
- `climate.{device_name}_zone_2` (if hasZone2=true)

### UI Controls Available

```yaml
Temperature Slider:
  Range: 10-30°C (hardcoded safe defaults for underfloor heating)
  Step: 0.5°C or 1.0°C
  Label: "Target Room Temperature"

HVAC Mode Toggle:
  Options:
    - HEAT  # System on, zone active
    - OFF   # Powers off ENTIRE system (not zone-only)
  Label: "Zone Mode"

Preset Mode Dropdown:
  Options:
    - room_temperature      # Thermostat control (recommended)
    - flow_temperature      # Direct flow temp control (advanced)
    - weather_compensation  # Weather curve mode (advanced)
  Label: "Heating Strategy"

HVAC Action (read-only status):
  Display: "Heating" | "Idle" | "Off"
  Note: Shows "Idle" when 3-way valve is on DHW (even if zone temp below target)

State Attributes (visible in "more info"):
  - operation_mode: Current preset mode API value
  - current_temperature: Room temperature
  - target_temperature: Zone target
```

### Services

- `climate.set_temperature` - Set zone target temp
- `climate.set_hvac_mode` - Set HEAT or OFF
- `climate.set_preset_mode` - Change heating strategy

### Key Behavior

⭐ **CRITICAL:** `set_hvac_mode(OFF)` powers off the **entire heat pump** (matches official MELCloud implementation).

**Rationale from ADR-012:**

- Official MELCloud code does this (proven pattern)
- Physical reality: ONE heat pump with ONE power supply
- User expectations: Climate OFF = turn off heating
- Most systems are single-zone (makes sense)

**Trade-off:** Climate OFF on Zone 1 also powers off Zone 2 and stops DHW heating.

---

## 3. Sensor Entities (Temperature & Status)

**Per device:**

```yaml
sensor.{device_name}_tank_temperature:
  Unit: °C
  Device Class: temperature
  Purpose: Current DHW tank temperature

sensor.{device_name}_zone_1_temperature:
  Unit: °C
  Device Class: temperature
  Purpose: Current Zone 1 room temperature

sensor.{device_name}_zone_2_temperature:  # If hasZone2
  Unit: °C
  Device Class: temperature
  Purpose: Current Zone 2 room temperature

sensor.{device_name}_outdoor_temperature:
  Unit: °C
  Device Class: temperature
  Purpose: Outside temperature (for weather compensation)

sensor.{device_name}_operation_status:
  Values: "idle" | "heating_dhw" | "heating_zone_1" | "heating_zone_2"
  Purpose: Human-readable 3-way valve status
  Critical: Shows what heat pump is currently doing

sensor.{device_name}_wifi_signal:
  Unit: dBm
  Device Class: signal_strength
  Purpose: WiFi connection quality

Optional (if API provides):
sensor.{device_name}_zone_1_flow_temperature
sensor.{device_name}_zone_1_return_temperature
sensor.{device_name}_error_code  # When IsInError=true
```

---

## 4. Binary Sensor Entities (Status Flags)

```yaml
binary_sensor.{device_name}_error:
  State: on/off
  Device Class: problem
  Purpose: IsInError flag from API

binary_sensor.{device_name}_forced_dhw_active:
  State: on/off
  Device Class: running
  Purpose: Shows when ForcedHotWaterMode is enabled
```

---

## Critical Architectural Decisions (from ADR-012)

### Decision 1: Power Control

**Both water_heater AND climate can control system power.**

```python
# These have the SAME effect - both power off entire heat pump:
await water_heater.turn_off()
await climate.set_hvac_mode(HVACMode.OFF)
```

**Rationale:**

- Matches official MELCloud core integration (actual code, not docs)
- Physical reality: ONE heat pump device
- User expectations: Climate OFF should turn off heating
- Proven pattern in production

**Source:** ADR-012 lines 166-223 (revised 2026-01-03 after code analysis)

### Decision 2: 3-Way Valve Visibility

**Status exposed in 3 places:**

1. Water heater state attribute: `operation_status`
2. Dedicated sensor: `sensor.operation_status` (human-readable)
3. Climate `hvac_action`: Shows IDLE when valve on DHW

**Why:** Users need to understand why zone isn't heating (valve might be on DHW).

### Decision 3: Forced DHW Mode

**Implemented as water_heater operation mode** (NOT separate switch):

```yaml
Operation Modes:
  eco:         Normal balanced operation
  performance: DHW priority (zone heating suspended)

API Mapping:
  eco         → forcedHotWaterMode: false
  performance → forcedHotWaterMode: true
```

**Why:** Standard HA pattern, no extra entity clutter.

### Decision 4: Zone Operation Modes

**Implemented as climate preset modes** (NOT HVAC modes):

```yaml
Preset Modes:
  room_temperature:      Thermostat control (default/recommended)
  flow_temperature:      Direct flow temp control (advanced)
  weather_compensation:  Outdoor temp-based curve (advanced)
```

**Why:** HVAC modes (heat/cool/auto) don't fit heat-only systems. Preset modes are standard pattern for heating strategies.

### Decision 5: Temperature Ranges

**Always use hardcoded safe defaults** (NEVER trust API):

```yaml
DHW Tank:  40-60°C (safe range for all systems)
Zone:      10-30°C (safe for underfloor heating)
Step:      0.5°C or 1.0°C (from hasHalfDegrees capability)
```

**Why:** API ranges have known reliability issues; safety-critical for HVAC equipment.

---

## Best Practice Pattern (Official MELCloud Reference)

**Source:** Official Home Assistant MELCloud integration

- **Documentation:** <https://www.home-assistant.io/integrations/melcloud/>
- **Implementation PR:** #32078
- **Code:** `homeassistant/components/melcloud/`

**Pattern:**

- Water heater for DHW + system power
- Climate per zone for room heating
- Sensors for monitoring
- Both water_heater AND climate can control system power

---

## Implementation Status

**Already Decided:** Full entity architecture documented in ADR-012 (2026-01-03)

**Already Implemented:**

- ✅ API models (AirToWaterUnit, AirToWaterCapabilities)
- ✅ Mock server with 3-way valve simulation
- ✅ Phase 1 validation complete

**Not Yet Implemented:**

- ❌ `water_heater.py` - DHW tank entity
- ❌ `climate.py` updates - ATW zone support
- ❌ `sensor.py` updates - ATW sensors
- ❌ `binary_sensor.py` updates - ATW binary sensors
- ❌ API control methods (Phase 2)
- ❌ Coordinator updates

---

## Example UI Cards

### Water Heater Card (Lovelace)

```yaml
House Heat Pump Tank
━━━━━━━━━━━━━━━━━━━━
Current: 48.5°C
Target: 50.0°C

Operation: Eco
Status: Heating DHW

[Slider: 40-60°C]
[Mode: Eco ▼]
[Power Toggle: ON]

Attributes:
  operation_status: HotWater
  zone_heating_suspended: true
  forced_dhw_active: false
```

### Climate Card (Zone 1)

```yaml
House Heat Pump Zone 1
━━━━━━━━━━━━━━━━━━━━━━
Current: 20.0°C
Target: 21.0°C

Mode: Heat
Action: Idle  ← Shows Idle because valve is on DHW
Preset: Room Temperature

[Slider: 10-30°C]
[Preset: Room Temp ▼]

Attributes:
  operation_mode: HeatRoomTemperature
```

### Operation Status Sensor Card

```yaml
System Status
━━━━━━━━━━━━━
Currently: Heating DHW
Forced Priority: No
Zone 1 Suspended: Yes
```

---

## User Experience Notes

### When Forced DHW Active

1. Water heater shows: `Operation: Performance`
2. Water heater attribute: `forced_dhw_active: true`
3. Sensor shows: `heating_dhw`
4. Climate Zone 1 shows: `Action: Idle` (even if temp below target)
5. Climate attribute may show: `zone_heating_suspended: true`

**Why:** 3-way valve can only heat ONE thing at a time (physical limitation).

### Power Control UX

**Two ways to power off system:**

1. **Via water_heater:** Toggle switch in water heater card
2. **Via climate:** Set HVAC mode to OFF

**Both have same effect** - entire heat pump powers off (all zones + DHW).

**Why this is OK:**

- Matches official MELCloud implementation
- Most systems are single-zone
- Physical reality: ONE heat pump
- User expectation: Climate OFF = heating stops

---

## Questions Already Answered in ADR-012

### Q1: Should climate control system power?

**A:** YES (both water_heater AND climate can control power)

### Q2: How to represent zone operation modes?

**A:** Climate preset modes (room_temperature/flow_temperature/weather_compensation)

### Q3: How to expose 3-way valve status?

**A:** Water heater attributes + dedicated sensor + climate hvac_action

### Q4: How to handle forced DHW mode?

**A:** Water heater operation mode "performance"

### Q5: Should we support flow temp / curve modes?

**A:** YES, as climate preset modes (advanced features)

---

## Files for Reference

**Architecture & Decisions:**

- `docs/decisions/012-atw-entity-architecture.md` - Complete entity architecture (574 lines)
- `docs/architecture.md` - 3-way valve behavior diagrams
- `docs/api/atw-api-reference.md` - Complete API spec

**Implementation Examples:**

- `custom_components/melcloudhome/climate.py` - Current A2A implementation (pattern reference)
- `custom_components/melcloudhome/sensor.py` - Current sensor implementation
- `tools/mock_melcloud_server.py` - Mock server with 3-way valve simulation

**Testing:**

- `docs/testing-best-practices.md` - HA entity testing patterns
- `tools/test_atw_mock_server.py` - Validation script

---

## Next Steps (If Implementing)

1. **Phase 2:** Implement ATW control methods in API client
2. **Phase 3:** Create `water_heater.py` platform
3. **Phase 4:** Update `climate.py` for ATW zones
4. **Phase 5:** Update `sensor.py` and `binary_sensor.py`
5. **Phase 6:** Test with mock server
6. **Phase 7:** Deploy to real hardware

**Estimated effort:** 7-11 hours total (from RESUME_PROMPT_mock_atw.md)

---

## Implementation Requirements: Making UI Controls Appear

### Question: Do we need to code anything special to make these controls appear?

**Short Answer:** Mostly NO for standard controls, but YES for proper implementation and a few special things.

### Standard Controls (Auto-Generated by HA)

These appear **automatically** when you implement the entity correctly:

#### Water Heater (Auto-Generated)

✅ Temperature slider → Just implement `target_temperature_step`, `min_temp`, `max_temp`
✅ Current/target temp display → Just implement properties
✅ Power toggle → Just implement `async_turn_on()` / `async_turn_off()`
✅ Operation mode dropdown → Implement `operation_list` property and `async_set_operation_mode()`

#### Climate (Auto-Generated)

✅ Temperature slider → Just implement `target_temperature_step`, `min_temp`, `max_temp`
✅ HVAC mode toggle → Just implement `hvac_modes` property and `async_set_hvac_mode()`
✅ Preset mode dropdown → Just implement `preset_modes` property and `async_set_preset_mode()`
✅ HVAC action display → Just implement `hvac_action` property

#### Sensors (Auto-Generated)

✅ Temperature display → Just implement `native_value` property
✅ State display → Just implement `state` property

### What You MUST Implement

```python
# 1. Water Heater Entity Properties (for UI controls to appear)
@property
def min_temp(self) -> float:
    return 40.0  # DHW min

@property
def max_temp(self) -> float:
    return 60.0  # DHW max

@property
def target_temperature_step(self) -> float:
    return 0.5 if self._device.capabilities.has_half_degrees else 1.0

@property
def operation_list(self) -> list[str]:
    return ["eco", "performance"]  # For dropdown

@property
def current_operation(self) -> str:
    return "performance" if self._device.forced_hot_water_mode else "eco"

@property
def supported_features(self) -> WaterHeaterEntityFeature:
    return (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE |
        WaterHeaterEntityFeature.OPERATION_MODE |
        WaterHeaterEntityFeature.ON_OFF
    )

# 2. Climate Entity Properties (for UI controls to appear)
@property
def hvac_modes(self) -> list[HVACMode]:
    return [HVACMode.OFF, HVACMode.HEAT]  # For toggle

@property
def preset_modes(self) -> list[str]:
    return ["room_temperature", "flow_temperature", "weather_compensation"]  # For dropdown

@property
def supported_features(self) -> ClimateEntityFeature:
    return (
        ClimateEntityFeature.TARGET_TEMPERATURE |
        ClimateEntityFeature.PRESET_MODE
    )
```

### What You DON'T Need to Code

❌ No custom UI components needed
❌ No Lovelace card configuration required
❌ No frontend JavaScript
❌ No CSS styling
❌ No custom panel registration

**Home Assistant automatically generates the appropriate UI based on entity type and properties.**

### Special Implementations Needed

#### 1. State Attributes (Extra Info in "More Info" Dialog)

These DON'T appear automatically - you must implement `extra_state_attributes`:

```python
# Water heater entity
@property
def extra_state_attributes(self) -> dict[str, Any]:
    """Additional attributes shown in more-info dialog."""
    return {
        "operation_status": self._device.operation_status,  # 3-way valve status
        "forced_dhw_active": self._device.forced_hot_water_mode,
        "zone_heating_suspended": self._device.operation_status == "HotWater",
    }

# Climate entity
@property
def extra_state_attributes(self) -> dict[str, Any]:
    """Additional attributes shown in more-info dialog."""
    return {
        "operation_mode": self._device.operation_mode_zone1,  # Current heating strategy
        # Add flow_temperature if available
        # Add return_temperature if available
    }
```

#### 2. Translations (User-Friendly Names)

Create `custom_components/melcloudhome/strings.json` for friendly names:

```json
{
  "entity": {
    "water_heater": {
      "melcloudhome": {
        "state_attributes": {
          "operation_list": {
            "state": {
              "eco": "Eco (Balanced)",
              "performance": "Performance (DHW Priority)"
            }
          }
        }
      }
    },
    "climate": {
      "melcloudhome": {
        "state_attributes": {
          "preset_mode": {
            "state": {
              "room_temperature": "Room Temperature",
              "flow_temperature": "Flow Temperature",
              "weather_compensation": "Weather Compensation"
            }
          }
        }
      }
    }
  }
}
```

#### 3. Device Info (Grouping Entities)

All entities for same device must return same `device_info` to group them:

```python
@property
def device_info(self) -> DeviceInfo:
    """Link all entities to same device."""
    return DeviceInfo(
        identifiers={(DOMAIN, self._device.id)},
        name=self._device.name,
        manufacturer="Mitsubishi Electric",
        model=f"Ecodan ATW (FTC{self._device.ftc_model})",
    )
```

### Implementation Checklist for UI Controls

#### Water Heater Platform (`water_heater.py`)

- [ ] Implement `min_temp`, `max_temp`, `target_temperature_step`
- [ ] Implement `current_temperature`, `target_temperature`
- [ ] Implement `operation_list`, `current_operation`
- [ ] Implement `supported_features` with correct flags
- [ ] Implement `async_set_temperature()`
- [ ] Implement `async_set_operation_mode()`
- [ ] Implement `async_turn_on()` / `async_turn_off()`
- [ ] Implement `extra_state_attributes()` for 3-way valve status
- [ ] Implement `device_info` property

#### Climate Platform (`climate.py` updates)

- [ ] Implement `min_temp`, `max_temp`, `target_temperature_step`
- [ ] Implement `current_temperature`, `target_temperature`
- [ ] Implement `hvac_modes` list
- [ ] Implement `hvac_mode` current state
- [ ] Implement `hvac_action` (heating/idle/off)
- [ ] Implement `preset_modes` list
- [ ] Implement `preset_mode` current state
- [ ] Implement `supported_features` with correct flags
- [ ] Implement `async_set_temperature()`
- [ ] Implement `async_set_hvac_mode()`
- [ ] Implement `async_set_preset_mode()`
- [ ] Implement `extra_state_attributes()` for operation mode
- [ ] Implement `device_info` property

#### Sensor Platform (`sensor.py` updates)

- [ ] Create sensor descriptions with `SensorEntityDescription`
- [ ] Implement `native_value` property
- [ ] Implement `native_unit_of_measurement`
- [ ] Implement `device_class` (temperature, etc.)
- [ ] Implement `device_info` property

#### Binary Sensor Platform (`binary_sensor.py` updates)

- [ ] Create sensor descriptions with `BinarySensorEntityDescription`
- [ ] Implement `is_on` property
- [ ] Implement `device_class` (problem, running, etc.)
- [ ] Implement `device_info` property

### Example: Complete Water Heater Property Set

```python
class ATWWaterHeaterEntity(CoordinatorEntity, WaterHeaterEntity):
    """Water heater entity for ATW DHW tank."""

    # Required for UI temperature slider
    @property
    def min_temp(self) -> float:
        return self._device.capabilities.min_set_tank_temperature  # 40.0

    @property
    def max_temp(self) -> float:
        return self._device.capabilities.max_set_tank_temperature  # 60.0

    @property
    def target_temperature_step(self) -> float:
        return 0.5 if self._device.capabilities.has_half_degrees else 1.0

    # Required for UI temperature display
    @property
    def current_temperature(self) -> float | None:
        return self._device.tank_water_temperature

    @property
    def target_temperature(self) -> float | None:
        return self._device.set_tank_water_temperature

    # Required for UI operation mode dropdown
    @property
    def operation_list(self) -> list[str]:
        return ["eco", "performance"]

    @property
    def current_operation(self) -> str:
        return "performance" if self._device.forced_hot_water_mode else "eco"

    # Required for UI to show controls
    @property
    def supported_features(self) -> WaterHeaterEntityFeature:
        return (
            WaterHeaterEntityFeature.TARGET_TEMPERATURE |
            WaterHeaterEntityFeature.OPERATION_MODE |
            WaterHeaterEntityFeature.ON_OFF
        )

    # Required for UI temperature unit
    @property
    def temperature_unit(self) -> str:
        return UnitOfTemperature.CELSIUS

    # Services (called when user interacts with UI)
    async def async_set_temperature(self, **kwargs) -> None:
        temperature = kwargs.get(ATTR_TEMPERATURE)
        await self.coordinator.async_set_dhw_temperature(
            self._device.id, temperature
        )

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        enabled = operation_mode == "performance"
        await self.coordinator.async_set_forced_dhw(
            self._device.id, enabled
        )

    async def async_turn_on(self) -> None:
        await self.coordinator.async_set_power_atw(self._device.id, True)

    async def async_turn_off(self) -> None:
        await self.coordinator.async_set_power_atw(self._device.id, False)

    # Extra state attributes (in "more info" dialog)
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "operation_status": self._device.operation_status,
            "forced_dhw_active": self._device.forced_hot_water_mode,
            "zone_heating_suspended": self._device.operation_status == "HotWater",
        }

    # Device grouping
    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.id)},
            name=self._device.name,
            manufacturer="Mitsubishi Electric",
            model=f"Ecodan ATW (FTC{self._device.ftc_model})",
        )
```

### Reference: Existing A2A Climate Implementation

**File:** `custom_components/melcloudhome/climate.py` (lines 53-150)

**What Makes UI Controls Appear (from existing A2A code):**

```python
class MELCloudHomeClimate(CoordinatorEntity, ClimateEntity):
    """A2A climate entity - shows EXACTLY what properties trigger UI controls."""

    # Temperature slider appears because of these:
    _attr_temperature_unit = "°C"                    # Units
    _attr_target_temperature_step = TEMP_STEP        # Step size (0.5°C)
    _attr_max_temp = TEMP_MAX_HEAT                   # Max value (31°C)
    # Also need: min_temp property and current_temperature property

    # HVAC mode controls appear because of these:
    _attr_hvac_modes = [                              # List of available modes
        HVACMode.OFF,
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.AUTO,
        HVACMode.DRY,
        HVACMode.FAN_ONLY,
    ]
    # Also need: hvac_mode property (current state)
    # Also need: async_set_hvac_mode() service

    # Fan speed dropdown appears because of:
    _attr_fan_modes = FAN_SPEEDS                      # ["Auto", "One", "Two", ...]
    # Also need: fan_mode property (current state)
    # Also need: async_set_fan_mode() service

    # Swing mode dropdown appears because of:
    _attr_swing_modes = VANE_POSITIONS                # ["Auto", "Swing", "One", ...]
    # Also need: swing_mode property (current state)
    # Also need: async_set_swing_mode() service

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Determines which features show in UI."""
        return (
            ClimateEntityFeature.TARGET_TEMPERATURE |  # Temperature slider
            ClimateEntityFeature.FAN_MODE |            # Fan dropdown
            ClimateEntityFeature.SWING_MODE            # Swing dropdown
            # For ATW: Add ClimateEntityFeature.PRESET_MODE for zone modes
        )
```

**Key Insight:** Just implement the properties and HA auto-generates the UI!

**Current sensor.py** has sensor patterns:

- File: `custom_components/melcloudhome/sensor.py`
- Shows SensorEntityDescription pattern
- Shows how to use value_fn for sensor values

---

## Summary: Answer to Your Question

**What HA UI controls should be available?**

### Primary Controls (User-Facing)

1. **Water Heater Card:**
   - DHW temperature slider (40-60°C)
   - Operation mode dropdown (eco/performance)
   - System power toggle (ON/OFF)

2. **Climate Card(s) - One Per Zone:**
   - Zone temperature slider (10-30°C)
   - HVAC mode toggle (HEAT/OFF) - also controls system power
   - Preset mode dropdown (room_temperature/flow_temperature/weather_compensation)

3. **Status Display:**
   - Current temperatures (DHW, zones, outdoor)
   - Operation status (what's currently heating)
   - 3-way valve position
   - Error state
   - WiFi signal

### Best Practice

✅ Follow official MELCloud pattern: `water_heater` + `climate` (per zone) + sensors
✅ Both water_heater and climate can control system power
✅ Use preset modes for zone heating strategies
✅ Use operation modes for DHW priority
✅ Make 3-way valve status visible (critical for UX)
✅ Use hardcoded safe temperature ranges

**All decisions documented in ADR-012 (already accepted).**

---

## Answer: Do We Need to Code Anything Special?

### NO - Standard Controls

**These appear automatically** when you implement the base entity properties:

✅ **Temperature sliders** - Just set `min_temp`, `max_temp`, `target_temperature_step`
✅ **Mode dropdowns** - Just set `hvac_modes` / `operation_list` / `preset_modes`
✅ **Power toggles** - Just implement `async_turn_on()` / `async_turn_off()`
✅ **Current values** - Just implement `current_temperature`, `hvac_action`, etc.

**No custom UI code needed.** Home Assistant's frontend automatically renders controls based on:

- Entity type (water_heater vs climate)
- `supported_features` flags
- Available properties

### YES - A Few Special Things

#### 1. Supported Features Flags (Required)

Must explicitly declare which features to enable:

```python
# Water heater
WaterHeaterEntityFeature.TARGET_TEMPERATURE |  # Enables slider
WaterHeaterEntityFeature.OPERATION_MODE |      # Enables mode dropdown
WaterHeaterEntityFeature.ON_OFF                # Enables power toggle

# Climate
ClimateEntityFeature.TARGET_TEMPERATURE |      # Enables slider
ClimateEntityFeature.PRESET_MODE               # Enables preset dropdown
```

#### 2. State Attributes (Optional but Recommended)

Must implement `extra_state_attributes()` to show 3-way valve status:

```python
@property
def extra_state_attributes(self) -> dict[str, Any]:
    return {
        "operation_status": self._device.operation_status,     # Critical for UX
        "zone_heating_suspended": ...,                         # Helpful diagnostic
    }
```

#### 3. Translations (Optional but Professional)

Create `strings.json` for friendly names in dropdowns:

```json
{
  "state_attributes": {
    "operation_list": {
      "state": {
        "eco": "Eco (Balanced)",
        "performance": "Performance (DHW Priority)"
      }
    }
  }
}
```

Otherwise dropdowns show raw values: "eco", "performance" (still works, just less polished).

#### 4. HVAC Action Logic (Climate-Specific)

Must implement logic that respects 3-way valve:

```python
@property
def hvac_action(self) -> HVACAction:
    if not self._device.power:
        return HVACAction.OFF

    # Check if 3-way valve is on THIS zone
    if self._device.operation_status in ["HeatRoomTemperature", "HeatFlowTemperature", "HeatCurve"]:
        if self._device.room_temperature_zone1 < self._device.set_temperature_zone1:
            return HVACAction.HEATING
        return HVACAction.IDLE

    # Valve is on DHW - show IDLE even if zone needs heating
    return HVACAction.IDLE
```

**Critical:** Zone shows "Idle" when valve on DHW (user needs to understand why zone not heating).

---

## Bottom Line

### What You Code

1. Entity class extending `WaterHeaterEntity` or `ClimateEntity`
2. Properties returning device state (`current_temperature`, `hvac_mode`, etc.)
3. Service methods (`async_set_temperature`, etc.) calling coordinator
4. `supported_features` flags to enable controls
5. Optional: `extra_state_attributes()` for 3-way valve visibility
6. Optional: `strings.json` for polished dropdown labels

### What HA Auto-Generates

- Temperature sliders with proper ranges
- Mode/preset dropdowns with your options
- Power toggles
- State displays
- Lovelace cards
- All frontend UI components

**Pattern:** Implement the entity, HA builds the UI. No special coding needed beyond standard entity implementation.

---

## Files to Implement

### Priority 1: Water Heater Platform

**New file:** `custom_components/melcloudhome/water_heater.py`

- Extend `WaterHeaterEntity`
- Implement ~15 properties
- Implement 3 service methods
- Reference: A2A `climate.py` for patterns

### Priority 2: Climate Updates

**Update file:** `custom_components/melcloudhome/climate.py`

- Add `ATWClimateEntity` class
- Implement preset_modes (new for ATW)
- Implement 3-way valve aware hvac_action
- Reference: Existing `MELCloudHomeClimate` class

### Priority 3: Sensors

**Update file:** `custom_components/melcloudhome/sensor.py`

- Add ATW sensor descriptions
- Reference: Existing ATA sensor descriptions

### Priority 4: Binary Sensors

**Update file:** `custom_components/melcloudhome/binary_sensor.py`

- Add ATW binary sensor descriptions
- Reference: Existing ATA binary sensor descriptions

### Supporting: Translations (Optional)

**New file:** `custom_components/melcloudhome/strings.json`

- Add friendly names for modes
- Standard HA translation format
