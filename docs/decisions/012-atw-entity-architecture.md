# ADR-012: ATW Entity Architecture and Responsibility Boundaries

**Date:** 2026-01-03
**Status:** Accepted
**Deciders:** @andrew-blake
**Related:** [ADR-011: Multi-Device-Type Architecture](011-multi-device-type-architecture.md)

---

## Context

Air-to-Water (ATW) heat pumps are physically **one device** with **two functional capabilities**:

1. **Zone heating** (underfloor heating/radiators via Zone 1 and optionally Zone 2)
2. **Domestic Hot Water (DHW)** production via tank

The device uses a **3-way valve** and can only perform ONE task at a time (physical hardware limitation documented in `docs/architecture.md:263-332`).

Home Assistant requires mapping ATW devices to appropriate entity types. Key questions:

1. Which entity types to use? (climate, water_heater, switch, sensor, binary_sensor)
2. **Which entity controls system power?** (Critical decision)
3. How to represent forced DHW mode?
4. How to expose zone operation modes?
5. How to show 3-way valve status?

## HAR Analysis Findings (2026-01-03)

**Analyzed:** 137 API calls across 2 HAR files (107 + 30 calls)

**Critical Findings:**

1. ❌ **No Zone Standby Control**
   - `InStandbyMode` appears in settings array (read-only status)
   - NOT found in any PUT control request (0 out of 16)
   - UI toggle likely sets temperature to minimum (10°C) to simulate "off"

2. ❌ **No Water Heater Operation Mode Enum**
   - Only `forcedHotWaterMode` boolean (True/False)
   - No "eco/heat_pump/performance" mode field in API
   - Water heater operation modes must be emulated from boolean

3. ✅ **Control Parameters Found:**
   - `power` (system-wide on/off)
   - `setTemperatureZone1` (zone target)
   - `operationModeZone1` (zone heating method)
   - `setTankWaterTemperature` (DHW target)
   - `forcedHotWaterMode` (DHW priority)

## Decision Drivers

1. **HA Best Practices** - Follow established patterns from MELCloud core integration
2. **Physical Reality** - Reflect actual hardware behavior (3-way valve, single power supply)
3. **User Clarity** - Clear control boundaries, no confusion about power control
4. **MELCloud Precedent** - Official MELCloud integration sets the pattern
5. **Type Safety** - Use appropriate HA entity types for each function
6. **Prevent State Conflicts** - Avoid multiple entities controlling same physical parameter
7. **API Reality** - Design based on actual API capabilities, not assumptions

## Research Findings

### MELCloud Core Integration (Official HA)

From [MELCloud Integration](https://www.home-assistant.io/integrations/melcloud/) documentation:

> "Air-to-Water device provides water_heater, climate and sensor platforms."

> "Up to two climates" for individual radiator zones.

> **"Water heater platform entities allow control of power, which controls the entire system."**

> **"The system cannot be turned on/off through the climate entities."**

**⚠️ DISCREPANCY FOUND (2026-01-03):**

**Actual code implementation** ([climate.py](https://github.com/home-assistant/core/blob/dev/homeassistant/components/melcloud/climate.py)):

```python
async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
    if hvac_mode == HVACMode.OFF:
        await self._device.set({"power": False})  # ⚠️ Powers off ENTIRE system
        return
```

**Reality:** Climate entity **DOES** control system power via HVAC_MODE.OFF

**Conclusion:** Documentation is incorrect or outdated. Actual implementation allows **BOTH** water_heater and climate to control power.

From [PR #32078](https://github.com/home-assistant/core/pull/32078) implementing MELCloud ATW support:

- Three entity types: water_heater, climate (per zone), sensor
- Climate entities handle zone temperature, mode selection, AND power
- Radiators must be in "room temperature control mode"

### Other Heat Pump Integrations

**Mastertherm** ([GitHub](https://github.com/sHedC/homeassistant-mastertherm)):

- Uses climate entities for zones
- Uses water_heater for DHW tank
- Separate entities for different heating circuits

**Pattern:** All ATW integrations use **water_heater + climate** combination.

---

## Decision

### 1. Entity Architecture

**Per ATW device, create:**

#### **water_heater Entity** (DHW Tank)

- **Entity ID:** `water_heater.{device_name}_tank`
- **Controls:**
  - DHW tank target temperature (40-60°C)
  - Operation mode (eco, heat_pump, performance)
  - **SYSTEM POWER** (turn_on/turn_off controls entire heat pump)
- **State attributes:**
  - `operation_status` - 3-way valve position (OperationMode STATUS field)
  - `forced_dhw_active` - Boolean (ForcedHotWaterMode)
  - `zone_heating_suspended` - Boolean (true when valve on DHW)

#### **climate Entity** (Zone 1)

- **Entity ID:** `climate.{device_name}_zone_1`
- **Controls:**
  - Zone 1 target temperature (10-30°C)
  - Zone operation mode via preset_modes
- **Preset modes:**
  - `room_temperature` → HeatRoomTemperature (thermostat control)
  - `flow_temperature` → HeatFlowTemperature (direct flow control) *Phase 2+*
  - `weather_compensation` → HeatCurve (weather-based)
- **HVAC modes:** HEAT, OFF
  - HEAT = system on, zone heating
  - **OFF = powers off ENTIRE system** (all zones + DHW)
    - **Implementation:** Sets `power: false` (system-wide)
    - **Rationale:** Matches official MELCloud implementation
    - **Effect:** Entire heat pump powers off (not zone-specific)
    - **Trade-off:** Climate OFF also stops other zones and DHW
- **HVAC action:** Reflects 3-way valve status
  - HEATING = valve on this zone and temp below target
  - IDLE = valve on DHW or temp at target
  - OFF = system power off

**HAR Analysis:** No zone-level enable/disable control found in 137 API calls. Official MELCloud uses system power for climate OFF.

#### **climate Entity** (Zone 2 - if hasZone2=true)

Same as Zone 1 but for Zone 2 parameters

#### **sensor Entities**

- `sensor.{device_name}_tank_temperature` - DHW current temp
- `sensor.{device_name}_zone_1_temperature` - Zone 1 room temp
- `sensor.{device_name}_outdoor_temperature` - Outside temp
- `sensor.{device_name}_operation_status` - Human-readable valve status
- `sensor.{device_name}_wifi_signal` - RSSI

#### **binary_sensor Entities**

- `binary_sensor.{device_name}_error` - IsInError flag
- `binary_sensor.{device_name}_forced_dhw_active` - ForcedHotWaterMode

### 2. Power Control Architecture ⭐ **CRITICAL**

**Decision:** System power controlled by BOTH water_heater and climate entities (matches official MELCloud).

**Decision Rationale:** Official MELCloud code analysis shows **both entities** control power. Following official pattern for consistency and user expectations.

**Implementation:**

```python
# water_heater.py
async def async_turn_on(self):
    """Turn ON entire heat pump system."""
    await self._client.set_power_atw(self._device.id, True)

async def async_turn_off(self):
    """Turn OFF entire heat pump system."""
    await self._client.set_power_atw(self._device.id, False)

# climate.py (Zone entity)
async def async_set_hvac_mode(self, hvac_mode):
    """Set HVAC mode - CAN control system power (matches official MELCloud).

    OFF = Powers off ENTIRE system (all zones + DHW)
    HEAT = Powers on system (if off) and sets zone to heat mode
    """
    if hvac_mode == HVACMode.OFF:
        # Power off entire heat pump system
        # Matches official MELCloud implementation
        # Note: Also turns off other zones and DHW
        await self._client.set_power_atw(self._device.id, False)
    elif hvac_mode == HVACMode.HEAT:
        # Power on system if currently off
        # Then ensure zone is not in standby
        if not self._device.power:
            await self._client.set_power_atw(self._device.id, True)
        # Zone temperature and mode are separate controls
```

**Note:** HAR analysis found no zone-specific standby control. `InStandbyMode` is read-only status.

**Implementation matches official MELCloud:** Climate OFF powers off entire system (not zone-specific).

**Rationale:**

1. **Official Implementation Precedent:** Actual MELCloud code allows both entities to control power
2. **User Expectations:** Users expect climate OFF to turn off heating (standard HA UX)
3. **Physical Reality:** Heat pump is ONE device with one power supply
4. **Simplicity:** Direct power control, no workarounds needed
5. **Single-Zone Systems:** Most common use case - climate OFF makes sense

**Trade-offs Accepted:**

- ⚠️ Climate OFF on Zone 1 also powers off Zone 2 (multi-zone systems)
- ⚠️ Climate OFF stops DHW heating also
- ⚠️ Two entities can control same parameter (power)
- ✅ Matches official implementation (proven pattern)
- ✅ Simpler than alternatives (minimum temp workaround)

### 3. Forced DHW Mode Implementation

**Decision:** Use water_heater operation mode, NOT separate switch entity.

**Operation Modes (Simplified based on API reality):**

- `eco` - Normal balanced operation (forcedHotWaterMode=False)
  - DHW heats when needed, balanced with zone heating
  - System automatically manages priorities
- `performance` - DHW priority mode (forcedHotWaterMode=True)
  - Prioritizes DHW heating over zones
  - Temporarily suspends zone heating
  - Automatically returns to normal when DHW reaches target

**API Mapping:**
```python
eco         → forcedHotWaterMode: False
performance → forcedHotWaterMode: True
```

**Note:** API only provides boolean `forcedHotWaterMode` parameter (no mode enum).

**Rationale:**

- Standard HA water_heater pattern (eco/performance)
- Maps cleanly to API boolean
- No extra entity clutter
- Clear in UI dropdown

**Alternative Considered:** Separate `switch.forced_dhw` entity

- Rejected: Adds entity count, less standard HA pattern

**Note:** Three-mode approach (eco/heat_pump/performance) was considered but HAR analysis showed only boolean `forcedHotWaterMode` in API.

### 4. Zone Operation Modes

**Decision:** Use climate preset modes, NOT HVAC modes.

**Preset Modes:**

- `room_temperature` - Thermostat control (recommended)
- `flow_temperature` - Direct flow temperature control (advanced)
- `weather_compensation` - Weather-based curve (advanced)

**Maps to API:**

- `room_temperature` → `"HeatRoomTemperature"`
- `flow_temperature` → `"HeatFlowTemperature"`
- `weather_compensation` → `"HeatCurve"`

**Rationale:**

- Preset modes are standard HA pattern for heating strategies
- HVAC modes (heat/cool/auto) don't fit (heat-only system)
- Clear user experience
- Matches thermostat conventions

### 5. 3-Way Valve Status Visibility

**Decision:** Expose via water_heater state attributes AND dedicated sensor.

**Implementation:**

```python
# water_heater entity
@property
def extra_state_attributes(self):
    return {
        "operation_status": self._device.operation_status,  # "HotWater", "Stop", "HeatRoomTemperature", etc.
        "forced_dhw_active": self._device.forced_hot_water_mode,
        "zone_heating_suspended": self._device.operation_status == "HotWater",
    }

# Dedicated sensor
class ATWOperationStatusSensor:
    """Human-readable sensor showing current heating target."""
    @property
    def state(self):
        if self._device.operation_status == "Stop":
            return "idle"
        elif self._device.operation_status == "HotWater":
            return "heating_dhw"
        elif self._device.operation_status in ATW_ZONE_MODES:
            return "heating_zone_1"
        return "unknown"
```

**Field Naming:** API field `OperationMode` renamed to `operation_status` in model to avoid confusion with `operation_mode_zone1` (control field).

**Rationale:**

- Users need to understand why zone isn't heating (valve might be on DHW)
- Helps diagnose forced DHW behavior
- Critical for 3-way valve awareness
- Both attribute (programmatic) and sensor (dashboard) access

### 6. API Method Naming Convention

**Decision:** Follow A2A pattern - descriptive names without device type prefix.

**A2A Pattern (existing):**
```python
set_power(unit_id, power)           # Generic descriptive name
set_temperature(unit_id, temp)      # Not set_ata_temperature()
set_mode(unit_id, mode)             # Not set_ata_mode()
set_fan_speed(unit_id, speed)       # Not set_ata_fan_speed()
```

**A2W Pattern (new):**
```python
set_zone_temperature(unit_id, temp)    # Descriptive (zone-specific)
set_dhw_temperature(unit_id, temp)     # Descriptive (DHW-specific)
set_zone_mode(unit_id, mode)           # Descriptive
set_forced_hot_water(unit_id, enabled) # Descriptive

# Exception: Power needs suffix to distinguish from A2A set_power()
set_power_atw(unit_id, power)          # Suffix for clarity (avoid conflict)
```

**Rationale:**
- Consistency with existing A2A methods
- Function name describes what it controls, not device type
- `_atw` suffix only where needed (power) to avoid naming collision
- Clear, readable, follows Python naming conventions

### 7. Temperature Range Sources

**Decision:** ALWAYS use hardcoded safe defaults, NEVER trust API-reported ranges.

**Safe Defaults:**

- DHW tank: 40-60°C
- Zone heating: 10-30°C
- Temperature step: 0.5°C or 1.0°C (from hasHalfDegrees capability)

**Rationale:**

- API temperature ranges have known reliability issues
- Safety-critical: Heat pump equipment
- Better to be conservative than risk out-of-range values
- Precedent from ATA implementation

---

## Consequences

### Positive

✅ **Clear Responsibility Boundaries**

- No confusion about which entity controls what
- Single source of truth for system power

✅ **Matches HA Precedent**

- Follows MELCloud core integration pattern
- Uses standard entity types appropriately

✅ **User-Friendly**

- Intuitive: Water heater controls water heating + system
- Intuitive: Climate controls room heating
- Clear dashboard cards

✅ **Prevents Common Errors**

- Can't accidentally create power control conflicts
- 3-way valve behavior visible to users
- Safe temperature ranges

✅ **Testable**

- Mock server simulates 3-way valve
- Clear expected behaviors
- Integration tests can verify boundaries

### Negative

⚠️ **Initial User Learning Curve**

- Users might expect climate.turn_off() to turn off system
- Need documentation explaining power control location
- Mitigated by: Standard HA pattern, clear entity naming

⚠️ **More Complex Than Single Climate Entity**

- Requires two entity types instead of one
- More code to maintain
- Mitigated by: Clear separation of concerns, better UX

⚠️ **Forced DHW via Operation Mode**

- Less discoverable than dedicated switch
- Operation mode dropdown might not be obvious
- Mitigated by: Standard water_heater pattern, tooltips

---

## Alternatives Considered

### Alternative A: Climate-Only Architecture

**Rejected:** Doesn't fit HA water_heater pattern, loses DHW-specific features

### Alternative B: Switch for Forced DHW

**Rejected:** Extra entity clutter, less standard than operation mode

### Alternative C: Climate-Exclusive Power Control

**Rejected:** Only climate entities control power (water_heater has no power control)

**Rationale for rejection:**
- Violates MELCloud precedent (official integration provides power in water_heater)
- Creates confusion in multi-zone systems about which climate controls power
- Water heater is natural location for "whole system" power control

**Accepted Solution:** Dual power control - BOTH water_heater AND climate can control system power (matches official MELCloud implementation)

### Alternative D: Generic Preset Names (eco/comfort/boost)

**Rejected:** Less clear mapping to technical modes, prefer descriptive names

---

## Implementation Checklist

### Phase 1: API Layer
- [ ] Add ATW constants to `api/const.py`
- [ ] Add ATW models to `api/models.py`
- [ ] Rename `OperationMode` → `operation_status` to avoid confusion
- [ ] Update `Building` and `UserContext` for ATW support
- [ ] Create comprehensive unit tests (31+ tests)
- [ ] Validate safe temperature defaults with HAR data

### Phase 2: API Control Methods (Next)
- [ ] Add `set_power_atw(unit_id, power)` method
- [ ] Add `set_zone_temperature(unit_id, temp)` method with 10-30°C validation
- [ ] Add `set_dhw_temperature(unit_id, temp)` method with 40-60°C validation
- [ ] Add `set_zone_mode(unit_id, mode)` method
- [ ] Add `set_forced_hot_water(unit_id, enabled)` method
- [ ] Add `set_holiday_mode(unit_ids, ...)` multi-unit method
- [ ] Add `set_frost_protection(unit_ids, ...)` multi-unit method
- [ ] Create control method tests in `test_atw_client.py`

### Phase 3: Entity Layer (Future)
- [ ] Create `water_heater.py` with power control
- [ ] Update `climate.py` with zone control (NO power, minimum temp for OFF)
- [ ] Document in entity docstrings: "System power via water_heater only"
- [ ] Add 3-way valve status to water_heater attributes (`operation_status` field)
- [ ] Implement eco/performance operation modes (map to forcedHotWaterMode boolean)
- [ ] Add preset modes for zone control methods (room_temperature/weather_compensation)
- [ ] Update `docs/architecture.md` with entity responsibility section
- [ ] Integration tests verifying power control boundaries
- [ ] Integration tests verifying climate OFF doesn't power off system
- [ ] User documentation explaining entity responsibilities

---

## References

### Home Assistant Documentation

- [Water Heater Entity](https://developers.home-assistant.io/docs/core/entity/water-heater/)
- [Climate Entity](https://developers.home-assistant.io/docs/core/entity/climate/)
- [MELCloud Integration](https://www.home-assistant.io/integrations/melcloud/)

### Implementation References

- [MELCloud ATW PR #32078](https://github.com/home-assistant/core/pull/32078)
- [Mastertherm Integration](https://github.com/sHedC/homeassistant-mastertherm)

### Internal Documentation

- `docs/architecture.md` - 3-way valve behavior (lines 263-332)
- `docs/api/atw-api-reference.md` - Complete API specification
- `RESUME_PROMPT_mock_atw.md` - Implementation guide

---

## Notes

This ADR establishes **architectural boundaries** for entity responsibilities (revised 2026-01-03):

1. ⭐ **System power = BOTH water_heater AND climate** (matches official MELCloud)
2. ⭐ **Climate OFF = system power off** (NOT zone-specific standby - API doesn't support that)
3. ⭐ **3-way valve status = visible to users** via `operation_status` field
4. ⭐ **Water heater operation modes = eco/performance** (maps to forcedHotWaterMode boolean)

**Key Findings from Analysis:**

- Official MELCloud implementation uses dual power control (climate + water_heater)
- Official MELCloud documentation differs from actual code regarding climate power control
- No zone-specific standby control exists in API (verified via 137 API calls)
- Water heater operation modes are emulated from `forcedHotWaterMode` boolean

These decisions are based on:

- ✅ Actual official HA MELCloud implementation code
- ✅ HAR file analysis (137 API calls)
- ✅ Physical heat pump hardware limitations
- ✅ HA entity type best practices
- ⚠️ Documentation (found to be incorrect in some areas)

**Do not deviate from these boundaries** without updating this ADR.

---

## Implementation Approach

### Phase 1: API Client Layer (Read-Only)

**Scope:** Models and parsing logic for ATW device state

**Implementation includes:**
- `AirToWaterUnit` model with `operation_status` field
- `AirToWaterCapabilities` with hardcoded safe temperature defaults (40-60°C DHW, 10-30°C Zone)
- Settings array parsing with type conversions (string→bool, string→float)
- Building and UserContext updated to support ATW units
- Comprehensive unit tests using HAR file fixtures

**Design validated by HAR analysis:**
- API temperature ranges are unreliable (inverted range bug observed)
- Safe hardcoded defaults are necessary
- `operation_status` distinct from `operation_mode_zone1` prevents confusion

**Phase progression:** Phase 1 (read-only) validates models, Phase 2 adds control methods, Phase 3 adds entity layer.

---

## Validation Criteria

Implementation correctly follows this ADR when:

✅ `water_heater.turn_off()` turns off entire heat pump
✅ `climate.set_hvac_mode(OFF)` ALSO turns off entire heat pump (matches official MELCloud)
✅ Both entities can control system power (proven pattern from official integration)
✅ `water_heater` attributes show 3-way valve status via `operation_status` field
✅ `climate.hvac_action` shows IDLE when valve on DHW
✅ Water heater operation mode "performance" enables forced DHW (forcedHotWaterMode=True)
✅ Water heater operation mode "eco" disables forced DHW (forcedHotWaterMode=False)
✅ Climate preset modes control zone heating method (room_temperature/weather_compensation)
✅ All temperature ranges use safe hardcoded defaults (10-30°C Zone, 40-60°C DHW)
✅ API methods follow naming convention: descriptive names, `set_power_atw()` for power

**Testing:**
- ✅ Verify climate.set_hvac_mode(OFF) powers off system (power=false API call)
- ✅ Verify water_heater.turn_off() also powers off system
- ✅ Both methods have same effect (dual control is acceptable)
