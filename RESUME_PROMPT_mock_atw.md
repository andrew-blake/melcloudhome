# Resume Prompt: ATW (Air-to-Water) Home Assistant Integration Implementation

**Created:** 2026-01-03
**Purpose:** Guide next Claude session to implement ATW heat pump HA platform entities
**Branch:** `feature/atw-heat-pump-support`

---

## Current State Summary

### ✅ **Already Implemented (Other Session):**

1. **ATW API Models** (`custom_components/melcloudhome/api/models.py`)
   - `AirToWaterCapabilities` - Device capability flags and safe hardcoded temp ranges
   - `AirToWaterUnit` - Full device model (likely implemented)
   - Safe temperature defaults (40-60°C DHW, 10-30°C zones) to avoid API bugs

2. **ATW Constants** (`custom_components/melcloudhome/api/const.py`)
   - API endpoints: `/api/atwunit/{unit_id}`
   - Operation modes: `HeatRoomTemperature`, `HeatFlowTemperature`, `HeatCurve`
   - Status values: `Stop`, `HotWater`, or zone mode string
   - Temperature ranges and increments
   - **NOT YET COMMITTED** (51 lines unstaged)

3. **ATW Tests** (`tests/api/test_atw_models.py` + fixtures)
   - Model parsing tests with real API fixtures
   - **NOT YET COMMITTED** (untracked files)

4. **Mock Server** (`tools/mock_melcloud_server.py`)
   - ATW device simulation with 3-way valve logic
   - Default device: "House Heat Pump" with Zone 1 + DHW
   - **COMMITTED** in `2aa4f8f`

5. **Debug Mode** (Integration code)
   - Config flow toggle for mock server
   - Simple auth flow for development
   - **COMMITTED** in `150de0d`

### ❌ **NOT Yet Implemented:**

1. **water_heater.py** - Platform for DHW tank control
2. **climate.py updates** - Support for ATW zone entities (currently ATA-only)
3. **sensor.py updates** - ATW-specific sensors (tank temp, zone temps, etc.)
4. **Coordinator updates** - Handle ATW devices in polling/state management
5. **Client API methods** - ATW-specific control methods

---

## Research: HA Best Practices for ATW Heat Pumps

Based on research of existing HA heat pump integrations:

### **Standard Entity Architecture:**

**Air-to-Water devices should provide:**

1. **water_heater entity** (1 per device)
   - Controls: DHW tank temperature, operation mode, system power
   - Properties: Current temp, target temp, operation mode
   - Services: set_temperature, set_operation_mode, turn_on/off

2. **climate entities** (1-2 per device)
   - One per heating zone (Zone 1, optionally Zone 2)
   - Controls: Room temperature target, zone-specific mode
   - **Cannot control system power** (power is water_heater only)
   - HVAC modes: heat, off (heat-only systems)

3. **sensor entities** (multiple)
   - Zone room temperatures
   - Tank water temperature
   - Outdoor temperature
   - Flow/return temperatures (if available)
   - Operation mode status

### **Key Insights from MELCloud Core Integration:**

From [MELCloud HA Integration](https://www.home-assistant.io/integrations/melcloud/) and [PR #32078](https://github.com/home-assistant/core/pull/32078):

- ✅ "Air-to-Water device provides water_heater, climate and sensor platforms"
- ✅ "Up to two climates" for individual radiator zones
- ✅ "Water heater platform entities allow control of power, which controls the entire system"
- ⚠️ "The system cannot be turned on/off through the climate entities"
- ⚠️ "Radiators need to be configured in room temperature control mode"
- ⚠️ "Flow temperature and curve modes are not supported" (by MELCloud core)
- ⚠️ "Air-to-water devices do not report energy consumption in an easily accessible manner"

**Important architectural decision:** System power control is **ONLY** via water_heater entity, not climate entities. This reflects that the heat pump is fundamentally one physical device.

### **Reference Implementations:**

- **MELCloud (HA Core):** [MELCloud Integration](https://www.home-assistant.io/integrations/melcloud/)
- **Mastertherm:** [GitHub](https://github.com/sHedC/homeassistant-mastertherm)
- **Daikin Altherma:** Multiple custom integrations available

---

## Recommended Entity Architecture for MELCloudHome ATW

Based on research and the 3-way valve architecture:

### **Per ATW Device, Create:**

#### 1. **Water Heater Entity** (`water_heater.{device_name}_tank`)

**Purpose:** DHW (Domestic Hot Water) tank control

**Properties:**

- `current_temperature` - Tank water temperature (TankWaterTemperature)
- `target_temperature` - Target tank temp (SetTankWaterTemperature)
- `min_temp` - 40°C (hardcoded safe default)
- `max_temp` - 60°C (hardcoded safe default)
- `operation_list` - ["off", "eco", "heat_pump", "performance"]
- `current_operation` - Current mode

**Services:**

- `set_temperature(temperature)` - Set DHW target
- `set_operation_mode(operation_mode)` - Set DHW mode
- `turn_on()` / `turn_off()` - **System-wide power** (not just DHW!)

**State Attributes:**

- `forced_hot_water_mode` - Boolean (DHW priority)
- `operation_mode_status` - What 3-way valve is doing ("HotWater", "HeatRoomTemperature", etc.)
- `zone_heating_suspended` - Boolean (true when valve is on DHW)

**CRITICAL:** `turn_on()`/`turn_off()` controls **entire heat pump**, not just DHW!

#### 2. **Climate Entity** - Zone 1 (`climate.{device_name}_zone_1`)

**Purpose:** Space heating control for Zone 1

**Properties:**

- `current_temperature` - Room temperature (RoomTemperatureZone1)
- `target_temperature` - Target room temp (SetTemperatureZone1)
- `min_temp` - 10°C
- `max_temp` - 30°C
- `hvac_modes` - [HEAT, OFF]
- `hvac_action` - heating, idle, off
- `preset_modes` - Map to OperationModeZone1 values

**Services:**

- `set_temperature(temperature)` - Set zone target
- `set_hvac_mode(mode)` - HEAT or OFF (standby mode)
- `set_preset_mode(preset)` - Zone operation mode

**State Attributes:**

- `operation_mode` - "HeatRoomTemperature" / "HeatFlowTemperature" / "HeatCurve"
- `flow_temperature` - If available
- `return_temperature` - If available

**CRITICAL:**

- **NO system power control** (that's water_heater only)
- `hvac_mode=OFF` should set `inStandbyMode`, NOT system power!
- Preset modes for different heating strategies

#### 3. **Climate Entity** - Zone 2 (if `has_zone2=true`)

Same as Zone 1 but for Zone 2 parameters

#### 4. **Sensor Entities:**

**Per ATW Device:**

- `sensor.{device_name}_tank_temperature` - DHW tank temp
- `sensor.{device_name}_zone_1_temperature` - Zone 1 room temp
- `sensor.{device_name}_outdoor_temperature` - Outside temp
- `sensor.{device_name}_operation_status` - What's heating now (OperationMode STATUS)
- `sensor.{device_name}_wifi_signal` - RSSI

**Optional (if API provides):**

- `sensor.{device_name}_zone_1_flow_temperature`
- `sensor.{device_name}_zone_1_return_temperature`
- `sensor.{device_name}_error_code` (if IsInError=true)

#### 5. **Binary Sensors:**

- `binary_sensor.{device_name}_error` - IsInError flag
- `binary_sensor.{device_name}_forced_dhw_active` - ForcedHotWaterMode

---

## Implementation Guidance

### **File Structure:**

```
custom_components/melcloudhome/
├── water_heater.py          # NEW - DHW tank entity
├── climate.py               # UPDATE - Add ATW zone support (currently ATA-only)
├── sensor.py                # UPDATE - Add ATW sensors
├── binary_sensor.py         # UPDATE - Add ATW binary sensors
├── coordinator.py           # UPDATE - Handle ATW in polling
└── const.py                 # UPDATE - Add water_heater platform
```

### **Critical Implementation Details:**

#### **1. 3-Way Valve Awareness**

The heat pump can ONLY do ONE thing at a time (physical limitation):

- Either heat DHW tank
- OR heat Zone 1
- Cannot do both

**Status field** (`OperationMode`) shows current activity:

- `"HotWater"` - Valve on DHW (zone heating suspended)
- `"HeatRoomTemperature"` - Valve on Zone 1
- `"Stop"` - Idle (both targets reached)

**Implementation:**

```python
# water_heater entity
@property
def extra_state_attributes(self):
    return {
        "operation_status": self._device.operation_mode,  # STATUS field
        "zone_heating_suspended": self._device.operation_mode == "HotWater",
        "forced_dhw_active": self._device.forced_hot_water_mode,
    }

# climate entity (Zone 1)
@property
def hvac_action(self):
    if not self._device.power:
        return HVACAction.OFF
    # Check if 3-way valve is on this zone
    if self._device.operation_mode in ["HeatRoomTemperature", "HeatFlowTemperature", "HeatCurve"]:
        if self._device.room_temperature_zone1 < self._device.set_temperature_zone1:
            return HVACAction.HEATING
        return HVACAction.IDLE
    # Valve is on DHW
    return HVACAction.IDLE
```

#### **2. Power Control Architecture**

**ONLY water_heater entity controls system power:**

```python
# water_heater.py
async def async_turn_on(self):
    """Turn ON entire heat pump system."""
    await self._client.set_power_atw(self._device.id, True)

async def async_turn_off(self):
    """Turn OFF entire heat pump system."""
    await self._client.set_power_atw(self._device.id, False)

# climate.py (Zone)
async def async_set_hvac_mode(self, hvac_mode):
    """Set HVAC mode (HEAT or OFF).

    OFF = Standby mode (not system power!)
    """
    if hvac_mode == HVACMode.OFF:
        # Set zone to standby (NOT system power)
        await self._client.set_standby_zone(self._device.id, True)
    elif hvac_mode == HVACMode.HEAT:
        # Exit standby
        await self._client.set_standby_zone(self._device.id, False)
```

#### **3. Preset Modes Mapping**

**Climate Entity Preset Modes:**

```python
PRESET_ROOM_TEMP = "room_temperature"      # HeatRoomTemperature (thermostat)
PRESET_FLOW_TEMP = "flow_temperature"      # HeatFlowTemperature (direct)
PRESET_WEATHER_COMP = "weather_compensation"  # HeatCurve

# Map to OperationModeZone1
PRESET_TO_ATW_MODE = {
    PRESET_ROOM_TEMP: "HeatRoomTemperature",
    PRESET_FLOW_TEMP: "HeatFlowTemperature",
    PRESET_WEATHER_COMP: "HeatCurve",
}
```

**Water Heater Operation Modes:**

```python
# Based on ForcedHotWaterMode + other settings
OPERATION_MODE_ECO = "eco"              # Normal priority
OPERATION_MODE_HEAT_PUMP = "heat_pump"  # Heat pump only (no backup)
OPERATION_MODE_PERFORMANCE = "performance"  # Forced DHW mode
# Note: Exact modes depend on device capabilities
```

#### **4. Temperature Step**

```python
# Both climate and water_heater
@property
def target_temperature_step(self):
    return 0.5 if self._device.capabilities.has_half_degrees else 1.0
```

---

## Implementation Checklist

### **Phase 1: Water Heater Platform** (Priority 1)

- [ ] Create `water_heater.py`
- [ ] `ATWWaterHeaterEntity` class extending `WaterHeaterEntity`
- [ ] Map device to entity (one water_heater per ATW device)
- [ ] Implement required properties:
  - [ ] `current_temperature` (tank)
  - [ ] `target_temperature` (tank)
  - [ ] `min_temp` / `max_temp` (40-60°C)
  - [ ] `supported_features` (TARGET_TEMPERATURE, OPERATION_MODE, ON_OFF)
  - [ ] `operation_list`
  - [ ] `current_operation`
- [ ] Implement services:
  - [ ] `async_set_temperature()`
  - [ ] `async_set_operation_mode()`
  - [ ] `async_turn_on()` / `async_turn_off()` (system power!)
- [ ] Add state attributes:
  - [ ] `operation_status` (3-way valve position)
  - [ ] `forced_dhw_active`
  - [ ] `zone_heating_suspended`
- [ ] Add to `const.py` PLATFORMS list
- [ ] Register in coordinator

### **Phase 2: Climate Platform Updates** (Priority 2)

- [ ] Update `climate.py` to support both ATA and ATW devices
- [ ] `ATWClimateEntity` class for zone control
- [ ] Map zones to entities (one climate per zone)
- [ ] Implement required properties:
  - [ ] `current_temperature` (room)
  - [ ] `target_temperature` (room)
  - [ ] `min_temp` / `max_temp` (10-30°C)
  - [ ] `hvac_modes` [HEAT, OFF]
  - [ ] `hvac_action` (heating, idle, off)
  - [ ] `preset_modes` (room_temp, flow_temp, weather_comp)
  - [ ] `supported_features`
- [ ] Implement services:
  - [ ] `async_set_temperature()`
  - [ ] `async_set_hvac_mode()` (standby, NOT power!)
  - [ ] `async_set_preset_mode()` (zone operation mode)
- [ ] Add state attributes:
  - [ ] `operation_mode` (zone control method)
  - [ ] `flow_temperature` (if available)
  - [ ] `3way_valve_status` (for debugging)
- [ ] **CRITICAL:** No system power control (redirect to water_heater)

### **Phase 3: Sensor Platform Updates** (Priority 3)

- [ ] Update `sensor.py` to add ATW sensors
- [ ] Tank temperature sensor
- [ ] Zone 1 room temperature sensor
- [ ] Zone 2 room temperature sensor (if has_zone2)
- [ ] Outdoor temperature sensor
- [ ] Operation status sensor (3-way valve position)
- [ ] Flow/return temperature sensors (if API provides)

### **Phase 4: Binary Sensor Updates** (Priority 3)

- [ ] Update `binary_sensor.py` for ATW
- [ ] Error sensor (IsInError)
- [ ] Forced DHW active sensor
- [ ] Connection status (if needed)

### **Phase 5: Testing** (Priority 4)

- [ ] Integration tests for water_heater platform
- [ ] Integration tests for ATW climate entities
- [ ] Test with mock server in docker-compose.dev.yml
- [ ] Verify 3-way valve status updates correctly
- [ ] Test power control (system-wide via water_heater)
- [ ] Test zone control (temperature, presets)
- [ ] Test forced DHW mode behavior

---

## Key Design Decisions

### **Q1: Should climate entities control system power?**

**A: NO** ✋

**Reasoning:**

- MELCloud core integration: "system cannot be turned on/off through climate entities"
- Physical reality: Heat pump is ONE device, not separate per zone
- HA best practice: water_heater controls the whole system
- Climate OFF = zone standby, NOT system power

**Implementation:**

- `climate.turn_off()` → Set zone to standby mode
- `water_heater.turn_off()` → Turn off entire heat pump

### **Q2: How to represent zone operation modes?**

**A: Use climate preset modes**

**Reasoning:**

- Preset modes are standard HA pattern for heating strategies
- Clear user experience (Eco, Comfort, etc. OR Room Temp, Flow Temp, Weather Comp)
- Maps cleanly to `operationModeZone1` parameter

**Options:**

1. **Descriptive names:** "Room Temperature", "Flow Temperature", "Weather Compensation"
2. **Generic names:** "comfort", "eco", "boost" (less clear mapping)
3. **Technical names:** "thermostat", "direct_flow", "curve" (clearer for HVAC users)

**Recommendation:** Use descriptive names matching API (Option 1)

### **Q3: How to expose 3-way valve status?**

**A: Via water_heater state attributes + sensor**

**Reasoning:**

- Users need visibility into what the heat pump is currently doing
- Helps debug why zone isn't heating (valve might be on DHW)
- Not a controllable parameter, just status info

**Implementation:**

```python
# water_heater entity
@property
def extra_state_attributes(self):
    return {
        "operation_status": self._device.operation_mode,  # "HotWater", "HeatRoomTemperature", etc.
        "zone_heating_suspended": self._device.operation_mode == "HotWater",
    }

# Plus a dedicated sensor for visibility
class ATWOperationStatusSensor:
    """Sensor showing what the heat pump is currently heating."""
    @property
    def state(self):
        mode = self._device.operation_mode
        if mode == "Stop":
            return "idle"
        elif mode == "HotWater":
            return "heating_dhw"
        elif mode in ["HeatRoomTemperature", "HeatFlowTemperature", "HeatCurve"]:
            return "heating_zone_1"
        return mode.lower()
```

### **Q4: How to handle forced hot water mode?**

**A: Via water_heater operation mode + service call**

**Options:**

1. **Separate switch entity** - `switch.force_dhw`
2. **Water heater operation mode** - "performance" mode
3. **Service call** - Custom service

**Recommendation:** Use operation mode "performance" (Option 2)

- Standard HA pattern
- Doesn't require extra entity
- Clear in UI ("Performance" mode = priority DHW heating)

### **Q5: Should we support flow temperature / curve modes?**

**A: YES, but as presets (not primary control)**

**Reasoning:**

- MELCloud core doesn't support these (limitation)
- We have API documentation for them
- Power users want these features
- Use climate preset modes for selection

**Implementation Strategy:**

- Default: "Room Temperature" mode (thermostat control)
- Advanced: "Flow Temperature" and "Weather Compensation" as presets
- Document that room temp mode is recommended

---

## Technical Implementation Notes

### **Client API Methods Needed:**

Add to `MELCloudHomeClient`:

```python
async def set_atw_temperature_zone1(self, unit_id: str, temperature: float):
    """Set Zone 1 target temperature."""
    await self._api_request("PUT", f"/api/atwunit/{unit_id}", json={
        "setTemperatureZone1": temperature,
        # All others null
    })

async def set_atw_tank_temperature(self, unit_id: str, temperature: float):
    """Set DHW tank target temperature."""
    await self._api_request("PUT", f"/api/atwunit/{unit_id}", json={
        "setTankWaterTemperature": temperature,
        # All others null
    })

async def set_atw_forced_dhw(self, unit_id: str, enabled: bool):
    """Enable/disable forced hot water mode."""
    await self._api_request("PUT", f"/api/atwunit/{unit_id}", json={
        "forcedHotWaterMode": enabled,
        # All others null
    })

async def set_atw_zone_mode(self, unit_id: str, mode: str):
    """Set zone operation mode."""
    await self._api_request("PUT", f"/api/atwunit/{unit_id}", json={
        "operationModeZone1": mode,
        # All others null
    })

async def set_atw_power(self, unit_id: str, power: bool):
    """Control system power."""
    await self._api_request("PUT", f"/api/atwunit/{unit_id}", json={
        "power": power,
        # All others null
    })
```

### **Coordinator Updates:**

```python
# coordinator.py
async def _async_update_data(self):
    """Fetch data from API."""
    context = await self._client.get_user_context()

    # Store both ATA and ATW devices
    self._ata_units = context.buildings[0].air_to_air_units
    self._atw_units = context.buildings[0].air_to_water_units  # NEW

    return context

# Add ATW control methods
async def async_set_atw_temperature_zone1(self, unit_id: str, temperature: float):
    """Set zone 1 temperature with debouncing."""
    await self._client.set_atw_temperature_zone1(unit_id, temperature)
    self._debounce_refresh()
```

### **Entity Registration:**

```python
# __init__.py
async def async_setup_entry(hass, entry):
    platforms = [
        Platform.BINARY_SENSOR,
        Platform.CLIMATE,
        Platform.SENSOR,
        Platform.WATER_HEATER,  # NEW
    ]
```

---

## Testing Strategy

### **With Mock Server:**

1. **Start dev environment:**

   ```bash
   docker compose -f docker-compose.dev.yml up -d
   ```

2. **Configure with debug mode:**
   - Add integration in HA UI
   - ✅ Check "Development Mode"
   - Connects to mock server automatically

3. **Expected entities created:**
   - `water_heater.house_heat_pump_tank`
   - `climate.house_heat_pump_zone_1`
   - `sensor.house_heat_pump_tank_temperature`
   - `sensor.house_heat_pump_zone_1_temperature`
   - `sensor.house_heat_pump_operation_status`
   - `binary_sensor.house_heat_pump_error`

4. **Test scenarios:**
   - [ ] Set DHW temperature via water_heater
   - [ ] Enable forced DHW mode (watch 3-way valve status)
   - [ ] Set zone temperature via climate
   - [ ] Verify zone heating suspends when DHW active
   - [ ] Turn off system via water_heater (not climate!)
   - [ ] Change zone preset mode

### **Mock Server Behavior:**

Mock server simulates 3-way valve logic:

- If `forcedHotWaterMode=true` → `operationMode="HotWater"`
- Else if DHW < target → `operationMode="HotWater"`
- Else if Zone < target → `operationMode=operationModeZone1`
- Else → `operationMode="Stop"`

---

## Common Pitfalls to Avoid

1. ❌ **Don't allow climate entity to control system power**
   - Climate OFF = standby mode
   - System power = water_heater only

2. ❌ **Don't use API-reported temperature ranges**
   - Always use hardcoded safe defaults
   - API ranges are unreliable (known bug history)

3. ❌ **Don't ignore 3-way valve status**
   - Critical for user understanding
   - Show in water_heater attributes
   - Affects hvac_action for climate

4. ❌ **Don't create separate entities for flow/return temps**
   - These are attributes of climate/water_heater
   - Only create sensors if truly independent

5. ❌ **Don't confuse OperationMode (STATUS) with OperationModeZone1 (CONTROL)**
   - `OperationMode` = read-only status (what's heating NOW)
   - `OperationModeZone1` = control parameter (HOW to heat zone)

---

## Reference Documentation

### **In This Repo:**

- Architecture: `docs/architecture.md` (3-way valve diagrams)
- ATW API: `docs/api/atw-api-reference.md` (complete spec)
- Mock Server: `tools/mock_melcloud_server.py` (working example)
- Implementation Plan: `docs/development/mock-server-implementation-plan.md`

### **Home Assistant Documentation:**

- [Water Heater Entity](https://developers.home-assistant.io/docs/core/entity/water-heater/)
- [Climate Entity](https://developers.home-assistant.io/docs/core/entity/climate/)
- [MELCloud Integration](https://www.home-assistant.io/integrations/melcloud/)

### **Reference Implementations:**

- [MELCloud ATW PR #32078](https://github.com/home-assistant/core/pull/32078) - Official MELCloud ATW support
- [Mastertherm Integration](https://github.com/sHedC/homeassistant-mastertherm) - Another ATW implementation
- [Daikin Altherma Resources](https://www.speaktothegeek.co.uk/2024/03/daikin-altherma-3-heat-pump-and-home-assistant/)

---

## Recommended Implementation Order

### **Session 1: Water Heater Platform** (2-3 hours)

1. Create `water_heater.py` with `ATWWaterHeaterEntity`
2. Implement basic properties and services
3. Add 3-way valve status attributes
4. Test with mock server

### **Session 2: Climate Updates** (2-3 hours)

1. Refactor `climate.py` to support both ATA and ATW
2. Create `ATWClimateEntity` for zones
3. Implement preset modes for zone operation
4. Handle 3-way valve in hvac_action
5. Test zone control with mock server

### **Session 3: Sensors** (1-2 hours)

1. Update `sensor.py` for ATW
2. Add temperature sensors
3. Add operation status sensor
4. Test sensor updates

### **Session 4: Integration & Polish** (1-2 hours)

1. Update coordinator for ATW device handling
2. Add binary sensors
3. Integration tests
4. End-to-end testing with mock server
5. Documentation updates

---

## Quick Start Commands for Next Session

```bash
# Check what's been done (ATW models/tests)
git diff custom_components/melcloudhome/api/models.py
git diff custom_components/melcloudhome/api/const.py
cat tests/api/test_atw_models.py

# Start dev environment
docker compose -f docker-compose.dev.yml up -d

# View logs while testing
docker compose -f docker-compose.dev.yml logs -f

# After code changes
docker compose -f docker-compose.dev.yml restart homeassistant

# Test API directly
curl http://localhost:8080/api/user/context | jq '.buildings[0].airToWaterUnits'
```

---

## Critical Success Criteria

✅ **water_heater entity controls system power** (turn_on/turn_off)
✅ **climate entities control zone temperatures** (NOT system power)
✅ **3-way valve status visible** in water_heater attributes
✅ **Forced DHW mode works** via water_heater operation mode
✅ **Zone preset modes work** (room temp, flow temp, weather comp)
✅ **All temperature ranges use safe hardcoded defaults** (not API)
✅ **hvac_action reflects 3-way valve** (idle when valve on DHW)
✅ **Mock server testing works** in docker-compose.dev.yml

---

## Notes for Implementation

### **Entity Naming:**

```
water_heater.{device_slug}_tank         # DHW tank
climate.{device_slug}_zone_1            # Zone 1 heating
climate.{device_slug}_zone_2            # Zone 2 (if exists)
sensor.{device_slug}_tank_temperature   # DHW tank temp
sensor.{device_slug}_zone_1_temperature # Zone 1 room temp
sensor.{device_slug}_operation_status   # What's heating now
```

### **Device Info:**

All ATW entities for same device should share device_info:

```python
@property
def device_info(self):
    return {
        "identifiers": {(DOMAIN, self._device.id)},
        "name": self._device.name,
        "manufacturer": "Mitsubishi Electric",
        "model": f"Ecodan ATW (FTC{self._device.ftc_model})",
    }
```

### **Unique IDs:**

```python
f"{self._device.id}_tank"        # water_heater
f"{self._device.id}_zone_1"      # climate zone 1
f"{self._device.id}_zone_2"      # climate zone 2
f"{self._device.id}_tank_temp"   # sensor
```

---

## Questions to Resolve Before Starting

1. **Operation mode mapping:** Should water_heater use generic modes (eco/performance) or ATW-specific modes?
2. **Standby mode:** How should climate entity OFF mode be represented? (InStandbyMode flag exists in API)
3. **Zone 2 support:** Implement from the start or defer? (Mock server doesn't have Zone 2 yet)
4. **Flow temperature control:** Expose as advanced feature or defer to Phase 2?
5. **Energy sensors:** ATW doesn't report energy easily - should we add placeholder entities or skip entirely?

**Recommendation:** Start with Phase 1 (water_heater) as it's the most critical and well-defined.

---

## Success Validation

### **In HA UI, you should see:**

**Water Heater Card:**

```
House Heat Pump Tank
━━━━━━━━━━━━━━━━━━━━
Current: 48.5°C
Target: 50.0°C

Operation: Eco
Status: Heating DHW

[Slider: 40-60°C]
[Mode: Eco ▼]
[On/Off Toggle]
```

**Climate Card (Zone 1):**

```
House Heat Pump Zone 1
━━━━━━━━━━━━━━━━━━━━━━
Current: 20.0°C
Target: 21.0°C

Mode: Heat
Action: Heating
Preset: Room Temperature

[Slider: 10-30°C]
[Preset: Room Temp ▼]
```

**With Forced DHW Active:**

- Water heater: "Status: Heating DHW (Forced)"
- Climate Zone 1: "Action: Idle" (even if below target - valve on DHW!)

---

## Implementation Timeline Estimate

- **Water Heater Platform:** 2-3 hours
- **Climate Updates:** 2-3 hours
- **Sensor Updates:** 1-2 hours
- **Integration & Testing:** 1-2 hours
- **Documentation:** 1 hour

**Total:** ~7-11 hours for complete ATW support

---

## Final Notes

- The mock server is **fully functional** and ready for testing
- Debug mode is **working** - integration connects to mock automatically
- ATW models are **implemented** - just need platform entities
- Architecture is **well-documented** - follow the 3-way valve principles
- Reference the MELCloud core integration for HA best practices
- **Test continuously** with docker-compose.dev.yml setup

**You've got everything you need to implement ATW support!** 🚀

---

## Quick Reference: File Locations

```
custom_components/melcloudhome/
├── water_heater.py                  # CREATE THIS (Priority 1)
├── climate.py                       # UPDATE (add ATW support)
├── sensor.py                        # UPDATE (add ATW sensors)
├── binary_sensor.py                 # UPDATE (add ATW binary sensors)
├── coordinator.py                   # UPDATE (handle ATW in polling)
├── const.py                         # UPDATE (add water_heater platform)
├── api/
│   ├── client.py                    # UPDATE (add ATW control methods)
│   ├── models.py                    # ✅ DONE (AirToWaterUnit, etc.)
│   └── const.py                     # ✅ DONE (ATW constants - unstaged)
└── tests/
    └── api/
        └── test_atw_models.py       # ✅ DONE (model tests - untracked)
```

**Good luck with the implementation!** 🎯
