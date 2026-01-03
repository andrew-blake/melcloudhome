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

## Decision Drivers

1. **HA Best Practices** - Follow established patterns from MELCloud core integration
2. **Physical Reality** - Reflect actual hardware behavior (3-way valve, single power supply)
3. **User Clarity** - Clear control boundaries, no confusion about power control
4. **MELCloud Precedent** - Official MELCloud integration sets the pattern
5. **Type Safety** - Use appropriate HA entity types for each function
6. **Prevent State Conflicts** - Avoid multiple entities controlling same physical parameter

## Research Findings

### MELCloud Core Integration (Official HA)

From [MELCloud Integration](https://www.home-assistant.io/integrations/melcloud/) documentation:

> "Air-to-Water device provides water_heater, climate and sensor platforms."

> "Up to two climates" for individual radiator zones.

> **"Water heater platform entities allow control of power, which controls the entire system."**

> **"The system cannot be turned on/off through the climate entities."**

From [PR #32078](https://github.com/home-assistant/core/pull/32078) implementing MELCloud ATW support:

- Three entity types: water_heater, climate (per zone), sensor
- System power controlled via water_heater only
- Climate entities handle zone temperature and mode selection
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
  - Zone standby mode (inStandbyMode flag)
  - Zone operation mode via preset_modes
- **Preset modes:**
  - `room_temperature` → HeatRoomTemperature (thermostat control)
  - `flow_temperature` → HeatFlowTemperature (direct flow control)
  - `weather_compensation` → HeatCurve (weather-based)
- **HVAC modes:** HEAT, OFF
  - HEAT = zone active
  - **OFF = zone standby (NOT system power!)**
- **HVAC action:** Reflects 3-way valve status
  - HEATING = valve on this zone and temp below target
  - IDLE = valve on DHW or temp at target
  - OFF = system power off

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

**Decision:** System power controlled EXCLUSIVELY by water_heater entity.

**Implementation:**

```python
# water_heater.py
async def async_turn_on(self):
    """Turn ON entire heat pump system."""
    await self._client.set_atw_power(self._device.id, True)

async def async_turn_off(self):
    """Turn OFF entire heat pump system."""
    await self._client.set_atw_power(self._device.id, False)

# climate.py (Zone entity)
async def async_set_hvac_mode(self, hvac_mode):
    """Set HVAC mode - DOES NOT CONTROL SYSTEM POWER.

    OFF = Zone standby (inStandbyMode flag)
    NOT = System power off
    """
    if hvac_mode == HVACMode.OFF:
        # Zone standby ONLY (not system power!)
        await self._client.set_atw_standby_zone(self._device.id, zone=1, standby=True)
    elif hvac_mode == HVACMode.HEAT:
        await self._client.set_atw_standby_zone(self._device.id, zone=1, standby=False)
```

**Rationale:**

1. **Physical Reality:** Heat pump is ONE device with one power supply
2. **HA MELCloud Precedent:** Official integration uses this pattern
3. **User Clarity:** Single control point for system power
4. **Avoid State Conflicts:** Two entities controlling same parameter = confusion
5. **Standard Pattern:** water_heater typically controls appliance power

### 3. Forced DHW Mode Implementation

**Decision:** Use water_heater operation mode, NOT separate switch entity.

**Operation Modes:**

- `eco` - Normal priority (DHW heats when needed, balances with zones)
- `heat_pump` - Heat pump only (no backup heater if present)
- `performance` - Forced DHW mode (priority DHW, suspends zones)

**Rationale:**

- Standard HA water_heater pattern (eco/performance/etc.)
- No extra entity clutter
- Clear in UI dropdown
- Maps to `forcedHotWaterMode` API parameter

**Alternative Considered:** Separate `switch.forced_dhw` entity

- Rejected: Adds entity count, less standard HA pattern

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
        "operation_status": self._device.operation_mode,  # "HotWater", "HeatRoomTemperature", etc.
        "forced_dhw_active": self._device.forced_hot_water_mode,
        "zone_heating_suspended": self._device.operation_mode == "HotWater",
    }

# Dedicated sensor
class ATWOperationStatusSensor:
    """Human-readable sensor showing current heating target."""
    @property
    def state(self):
        if self._device.operation_mode == "Stop":
            return "idle"
        elif self._device.operation_mode == "HotWater":
            return "heating_dhw"
        elif self._device.operation_mode in ATW_ZONE_MODES:
            return "heating_zone_1"
        return "unknown"
```

**Rationale:**

- Users need to understand why zone isn't heating (valve might be on DHW)
- Helps diagnose forced DHW behavior
- Critical for 3-way valve awareness
- Both attribute (programmatic) and sensor (dashboard) access

### 6. Temperature Range Sources

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

### Alternative C: Climate Controls System Power

**Rejected:** Violates MELCloud precedent, creates confusion about which climate (zone 1 vs zone 2) controls power

### Alternative D: Generic Preset Names (eco/comfort/boost)

**Rejected:** Less clear mapping to technical modes, prefer descriptive names

---

## Implementation Checklist

- [ ] Create `water_heater.py` with power control
- [ ] Update `climate.py` with zone control (NO power)
- [ ] Document in entity docstrings: "System power via water_heater only"
- [ ] Add 3-way valve status to water_heater attributes
- [ ] Implement operation modes for forced DHW
- [ ] Add preset modes for zone control methods
- [ ] Update `docs/architecture.md` with entity responsibility section
- [ ] Integration tests verifying power control boundaries
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

This ADR establishes **non-negotiable boundaries** for entity responsibilities:

1. ⭐ **System power = water_heater ONLY**
2. ⭐ **Climate OFF = zone standby, NOT power**
3. ⭐ **3-way valve status = visible to users**

These decisions are based on:

- Official HA MELCloud integration architecture
- Physical heat pump hardware limitations
- HA entity type best practices
- User experience research

**Do not deviate from these boundaries** without updating this ADR.

---

## Validation Criteria

Implementation correctly follows this ADR when:

✅ `water_heater.turn_off()` turns off entire heat pump
✅ `climate.set_hvac_mode(OFF)` sets zone standby only
✅ `water_heater` attributes show 3-way valve status
✅ `climate.hvac_action` shows IDLE when valve on DHW
✅ Operation mode "performance" enables forced DHW
✅ Climate preset modes control zone heating method
✅ All temperature ranges use safe hardcoded defaults

**Testing:** Verify with mock server that climate.turn_off() does NOT power off system.
