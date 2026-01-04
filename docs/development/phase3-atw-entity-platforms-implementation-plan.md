# Phase 3: ATW Entity Platforms Implementation Plan

## Goal
Create Home Assistant entity platforms for ATW (Air-to-Water) heat pump control, enabling UI-based control of zones and DHW.

## Prerequisites ✅
- Phase 2 complete: All ATW control methods implemented in coordinator
- Mock server running with ATW support
- ATA entity patterns established (climate, sensor, binary_sensor)

## Key Architectural Decisions

### 1. Climate Entities: Two Separate Entities
- **Zone 1 climate entity** - Always created
- **Zone 2 climate entity** - Only if `unit.capabilities.has_zone2 == True`
- **Rationale**: Matches official MELCloud pattern, each zone is physically separate hardware

### 2. Water Heater Platform
- **NEW platform**: `water_heater.py` for DHW tank control
- **Operation modes**: `eco` (balanced) and `performance` (DHW priority)
- **Power control**: `turn_on()`/`turn_off()` controls entire system (documented behavior)

### 3. ATW-Specific Sensors (5-7 sensors)
- Zone 1/2 temperatures (conditional on Zone 2)
- Tank temperature
- **Operation status** (critical: shows 3-way valve position)
- WiFi signal

### 4. ATW-Specific Binary Sensors (2-3)
- Error state (problem)
- Connection state (connectivity)
- Forced DHW active (running) - optional

## Implementation Plan

### Step 1: Update Constants (`const.py`)

**Add ATW mappings:**
```python
# ATW Zone Modes → Climate Preset Modes
ATW_TO_HA_PRESET = {
    "HeatRoomTemperature": "room_temperature",
    "HeatFlowTemperature": "flow_temperature",
    "HeatCurve": "weather_compensation",
}

HA_TO_ATW_PRESET = {v: k for k, v in ATW_TO_HA_PRESET.items()}

# Water Heater Operation Modes
WATER_HEATER_MODE_ECO = "eco"
WATER_HEATER_MODE_PERFORMANCE = "performance"

# Operation Status Display
ATW_STATUS_TO_READABLE = {
    "Stop": "idle",
    "HotWater": "heating_dhw",
    "HeatRoomTemperature": "heating_zone",
    "HeatFlowTemperature": "heating_zone",
    "HeatCurve": "heating_zone",
}

# Preset modes list
ATW_PRESET_MODES = ["room_temperature", "flow_temperature", "weather_compensation"]
```

**Lines:** ~40 added

---

### Step 2: Create Water Heater Platform (`water_heater.py` - NEW)

**Pattern:** Follow `climate.py` structure

**Key Features:**
- Temperature control: 40-60°C (use `ATW_TEMP_MIN_DHW`, `ATW_TEMP_MAX_DHW`)
- Operation modes: eco/performance (maps to `forced_hot_water_mode`)
- Power control: entire system on/off
- State attributes: operation_status, forced_dhw_active, zone_heating_suspended

**Service Methods:**
- `async_set_temperature()` → `coordinator.async_set_dhw_temperature()`
- `async_set_operation_mode()` → `coordinator.async_set_forced_hot_water()`
- `async_turn_on()/off()` → `coordinator.async_set_power_atw()`

**Entity Naming:**
- Unique ID: `{unit_id}_tank`
- Entity ID: `water_heater.melcloudhome_0efc_76db_tank`

**Lines:** ~250

**Tests Needed:**
- Entity creation
- Temperature set service
- Operation mode change (eco ↔ performance)
- Power control
- State attributes

---

### Step 3: Update Climate Platform (`climate.py`)

**Add Two New Classes:**

#### Class 1: `ATWClimateZone1`
- HVAC modes: `[OFF, HEAT]` (heat-only system)
- Preset modes: ATW zone strategies (room_temperature, flow_temperature, weather_compensation)
- Temperature range: 10-30°C
- Uses `coordinator.async_set_temperature_zone1()`, `async_set_mode_zone1()`, `async_set_power_atw()`

**HVAC Action Logic (3-way valve aware):**
```python
@property
def hvac_action(self) -> HVACAction | None:
    device = self._device
    if not device or not device.power:
        return HVACAction.OFF

    # Check if valve is on THIS zone
    if device.operation_status in ATW zone mode strings:
        # Valve on zone - check temperature
        if current < target - 0.5:  # Hysteresis
            return HVACAction.HEATING
        return HVACAction.IDLE

    # Valve on DHW - zone shows IDLE
    return HVACAction.IDLE
```

**Entity Naming:**
- Unique ID: `{unit_id}_zone_1`
- Entity ID: `climate.melcloudhome_0efc_76db_zone_1`

#### Class 2: `ATWClimateZone2`
- Nearly identical to Zone 1
- Uses Zone 2 fields: `room_temperature_zone2`, `set_temperature_zone2`, `operation_mode_zone2`
- Uses `coordinator.async_set_temperature_zone2()`, `async_set_mode_zone2()`
- Only created if `unit.capabilities.has_zone2 == True`

**Entity Naming:**
- Unique ID: `{unit_id}_zone_2`
- Entity ID: `climate.melcloudhome_0efc_76db_zone_2`

**Update Setup Function:**
```python
async def async_setup_entry(...):
    # Existing ATA climate entities
    for building in coordinator.data.buildings:
        for unit in building.air_to_air_units:
            entities.append(MELCloudHomeClimate(...))  # Unchanged

    # NEW: ATW climate entities
    for building in coordinator.data.buildings:
        for unit in building.air_to_water_units:
            # Zone 1 - always
            entities.append(ATWClimateZone1(coordinator, unit, building, entry))

            # Zone 2 - conditional
            if unit.capabilities.has_zone2:
                entities.append(ATWClimateZone2(coordinator, unit, building, entry))

    async_add_entities(entities)
```

**Lines:** ~350 added

**Tests Needed:**
- Zone 1 always created
- Zone 2 conditional on has_zone2
- Preset mode changes
- Temperature control
- HVAC action respects 3-way valve
- Power off turns off entire system

---

### Step 4: Update Sensor Platform (`sensor.py`)

**Add ATW Sensor Descriptions:**

```python
@dataclass(frozen=True, kw_only=True)
class MELCloudHomeATWSensorEntityDescription(SensorEntityDescription):
    """ATW sensor entity description."""
    value_fn: Callable[[AirToWaterUnit], float | str | None]
    available_fn: Callable[[AirToWaterUnit], bool] = lambda x: True
    should_create_fn: Callable[[AirToWaterUnit], bool] | None = None


ATW_SENSOR_TYPES: tuple[MELCloudHomeATWSensorEntityDescription, ...] = (
    # Zone 1 temperature (always)
    MELCloudHomeATWSensorEntityDescription(
        key="zone_1_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda unit: unit.room_temperature_zone1,
        available_fn=lambda unit: unit.room_temperature_zone1 is not None,
    ),

    # Zone 2 temperature (conditional)
    MELCloudHomeATWSensorEntityDescription(
        key="zone_2_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda unit: unit.room_temperature_zone2,
        should_create_fn=lambda unit: unit.capabilities.has_zone2,
        available_fn=lambda unit: unit.room_temperature_zone2 is not None,
    ),

    # Tank temperature (always)
    MELCloudHomeATWSensorEntityDescription(
        key="tank_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda unit: unit.tank_water_temperature,
        available_fn=lambda unit: unit.tank_water_temperature is not None,
    ),

    # Operation status (CRITICAL for 3-way valve visibility)
    MELCloudHomeATWSensorEntityDescription(
        key="operation_status",
        device_class=None,  # Categorical
        value_fn=lambda unit: ATW_STATUS_TO_READABLE.get(unit.operation_status, "unknown"),
    ),

    # WiFi signal (diagnostic)
    MELCloudHomeATWSensorEntityDescription(
        key="wifi_signal",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda unit: unit.rssi,
        available_fn=lambda unit: unit.rssi is not None,
    ),
)
```

**Add ATWSensor Class:**
- Same pattern as `MELCloudHomeSensor`
- Uses `coordinator.get_atw_unit()` instead of `get_unit()`

**Update Setup Function:**
```python
# After ATA sensors...
for building in coordinator.data.buildings:
    for unit in building.air_to_water_units:
        for description in ATW_SENSOR_TYPES:
            create_check = description.should_create_fn or description.available_fn
            if create_check(unit):
                entities.append(ATWSensor(coordinator, unit, building, entry, description))
```

**Lines:** ~150 added

**Tests Needed:**
- Zone 1 sensors always created
- Zone 2 sensors conditional
- Operation status mapping
- WiFi signal availability

---

### Step 5: Update Binary Sensor Platform (`binary_sensor.py`)

**Add ATW Binary Sensor Descriptions:**

```python
ATW_BINARY_SENSOR_TYPES: tuple[MELCloudHomeBinarySensorEntityDescription, ...] = (
    MELCloudHomeBinarySensorEntityDescription(
        key="error_state",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda unit: unit.is_in_error,
    ),
    MELCloudHomeBinarySensorEntityDescription(
        key="connection_state",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda unit: True,  # Handled by coordinator.last_update_success
    ),
    MELCloudHomeBinarySensorEntityDescription(
        key="forced_dhw_active",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda unit: unit.forced_hot_water_mode,
    ),
)
```

**Add ATWBinarySensor Class** - Same pattern as existing

**Update Setup Function** - Add ATW binary sensor loop

**Lines:** ~100 added

---

### Step 6: Register Water Heater Platform (`__init__.py`)

**Update platforms list:**
```python
platforms: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.WATER_HEATER,  # ADD
]
```

**Lines:** 1 line changed

---

### Step 7: Testing Implementation

**Test Files to Create/Update:**

1. **`tests/integration/test_water_heater.py`** (NEW)
   - ~400 lines
   - 15+ tests covering setup, temperature, modes, power

2. **`tests/integration/test_climate.py`** (UPDATE)
   - Add `TestATWClimate` class
   - ~500 lines added
   - 20+ tests for Zone 1/2, preset modes, 3-way valve behavior

3. **`tests/integration/test_sensor.py`** (UPDATE)
   - Add `TestATWSensors` class
   - ~200 lines added
   - Tests for all ATW sensors

4. **`tests/integration/test_binary_sensor.py`** (UPDATE)
   - Add `TestATWBinarySensors` class
   - ~150 lines added

**Mock Data Utilities:**
```python
# In conftest.py or test files
def create_mock_atw_unit(
    unit_id: str = "test-atw-unit-id",
    power: bool = True,
    zone1_temp: float = 20.0,
    zone1_target: float = 21.0,
    tank_temp: float = 48.5,
    tank_target: float = 50.0,
    forced_dhw: bool = False,
    has_zone2: bool = False,
    operation_status: str = "Stop",
) -> AirToWaterUnit:
    """Create mock ATW unit for testing."""
    # Build complete AirToWaterUnit with AirToWaterCapabilities
```

---

## Implementation Order

### Phase 3A: Foundation (Start Here)
1. Update `const.py` with ATW mappings
2. Create mock data builder for ATW units
3. Verify coordinator methods work in tests

### Phase 3B: Water Heater (Core Feature)
1. Create `water_heater.py` platform
2. Create `test_water_heater.py`
3. Verify DHW control works end-to-end

### Phase 3C: Climate Entities (Main UI)
1. Add `ATWClimateZone1` to `climate.py`
2. Add `ATWClimateZone2` to `climate.py`
3. Update setup function
4. Add tests to `test_climate.py`
5. Verify preset modes and 3-way valve awareness

### Phase 3D: Sensors & Binary Sensors (Observability)
1. Update `sensor.py` with ATW sensor descriptions
2. Update `binary_sensor.py` with ATW binary sensor descriptions
3. Add tests
4. Verify operation status sensor works

### Phase 3E: Platform Registration
1. Update `__init__.py` to register water_heater platform

### Phase 3F: Integration Testing
1. Test all platforms together
2. Verify device grouping (all entities under one device)
3. Test power control from multiple entities
4. End-to-end scenario testing

---

## Critical Files to Modify

**Production Code:**
1. `/Users/ablake/Development/home-automation/home-assistant/melcloudhome/custom_components/melcloudhome/const.py` - Add ATW constants (~40 lines)
2. `/Users/ablake/Development/home-automation/home-assistant/melcloudhome/custom_components/melcloudhome/water_heater.py` - NEW platform (~250 lines)
3. `/Users/ablake/Development/home-automation/home-assistant/melcloudhome/custom_components/melcloudhome/climate.py` - Add ATW classes (~350 lines)
4. `/Users/ablake/Development/home-automation/home-assistant/melcloudhome/custom_components/melcloudhome/sensor.py` - Add ATW sensors (~150 lines)
5. `/Users/ablake/Development/home-automation/home-assistant/melcloudhome/custom_components/melcloudhome/binary_sensor.py` - Add ATW binary sensors (~100 lines)
6. `/Users/ablake/Development/home-automation/home-assistant/melcloudhome/custom_components/melcloudhome/__init__.py` - Register water_heater (1 line)

**Test Code:**
1. `/Users/ablake/Development/home-automation/home-assistant/melcloudhome/tests/integration/test_water_heater.py` - NEW (~400 lines)
2. `/Users/ablake/Development/home-automation/home-assistant/melcloudhome/tests/integration/test_climate.py` - Add ATW tests (~500 lines)
3. `/Users/ablake/Development/home-automation/home-assistant/melcloudhome/tests/integration/test_sensor.py` - Add ATW tests (~200 lines)
4. `/Users/ablake/Development/home-automation/home-assistant/melcloudhome/tests/integration/test_binary_sensor.py` - Add ATW tests (~150 lines)
5. `/Users/ablake/Development/home-automation/home-assistant/melcloudhome/tests/integration/conftest.py` - Add mock ATW builder (~50 lines)

**Total:** ~2,640 lines (890 production + 1,750 tests)

---

## Key Implementation Patterns to Follow

### 1. Entity Base Pattern
```python
class ATWWaterHeater(CoordinatorEntity[MELCloudHomeCoordinator], WaterHeaterEntity):
    def __init__(self, coordinator, unit: AirToWaterUnit, building, entry):
        super().__init__(coordinator)
        self._unit_id = unit.id
        self._attr_unique_id = f"{unit.id}_tank"
        # ... standard device_info, naming ...

    @property
    def _device(self) -> AirToWaterUnit | None:
        return self.coordinator.get_atw_unit(self._unit_id)
```

### 2. Service Call Pattern
```python
async def async_set_temperature(self, **kwargs):
    temperature = kwargs.get("temperature")
    if temperature is None:
        return

    # Validate
    if temperature < self.min_temp or temperature > self.max_temp:
        _LOGGER.warning("Temperature out of range")
        return

    # Execute via coordinator
    await self.coordinator.async_set_dhw_temperature(self._unit_id, temperature)

    # Request debounced refresh (not immediate)
    await self.coordinator.async_request_refresh_debounced()
```

### 3. Testing Pattern
```python
@pytest.mark.asyncio
async def test_water_heater_set_temperature(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Test setting DHW temperature via service."""
    await hass.services.async_call(
        "water_heater",
        "set_temperature",
        {"entity_id": "water_heater.melcloudhome_0efc_76db_tank", "temperature": 55},
        blocking=True,
    )
    # Service succeeded (no exception)
```

### 4. Mock Client for Tests
```python
with patch("custom_components.melcloudhome.MELCloudHomeClient") as mock_client_class:
    client = mock_client_class.return_value
    client.get_user_context = AsyncMock(return_value=create_mock_user_context())

    # Mock ATW control methods
    client.set_power_atw = AsyncMock()
    client.set_temperature_zone1 = AsyncMock()
    client.set_dhw_temperature = AsyncMock()
    client.set_forced_hot_water = AsyncMock()
    # ... etc
```

---

## Testing Strategy

**Integration Tests (Test through HA core):**
- ✅ Mock at API boundary (`MELCloudHomeClient`)
- ✅ Setup via `hass.config_entries.async_setup()`
- ✅ Assert through `hass.states` and `hass.services`
- ❌ Never test coordinator internals directly

**Mock Server Tests (Already Working):**
- API layer tests in `tests/api/test_atw_control.py` (18 tests passing)
- No additional mock server tests needed for entity platforms

---

## Success Criteria

### Functionality
- [ ] Water heater entity created for each ATW device
- [ ] Zone 1 climate entity always created
- [ ] Zone 2 climate entity created only when `has_zone2 == True`
- [ ] All sensors created appropriately
- [ ] All binary sensors created
- [ ] All entities grouped under same device
- [ ] Temperature controls work (DHW, Zone 1, Zone 2)
- [ ] Operation mode controls work (water heater, climate presets)
- [ ] Power control works from both water_heater and climate entities
- [ ] 3-way valve status visible in operation_status sensor
- [ ] Climate `hvac_action` shows IDLE when valve on DHW

### Testing
- [ ] All entity creation tests pass
- [ ] All service call tests pass
- [ ] All state reflection tests pass
- [ ] Conditional Zone 2 tests pass
- [ ] No regressions in existing ATA tests
- [ ] Mock data builders work for both single-zone and dual-zone configs

### Code Quality
- [ ] No type errors (mypy)
- [ ] No lint errors (ruff)
- [ ] Follows ATA patterns exactly
- [ ] Entity IDs stable and predictable
- [ ] Device info consistent across entities

---

## Risk Mitigation

**3-Way Valve UX:**
- Operation status sensor shows clearly what's heating
- Climate hvac_action respects valve position
- Water heater attributes show zone_heating_suspended

**Power Control Confusion:**
- Both entities can power off system (matches official MELCloud)
- Clear in ADR-012 documentation
- Entity names make device relationship clear

**Zone 2 Testing:**
- Mock server supports Zone 2
- Test both has_zone2=True and False scenarios
- Use should_create_fn pattern (proven in ATA sensors)

---

## Estimated Effort

**Total Time:** 12-17 hours

**Breakdown:**
- Constants & foundation: 1 hour
- Water heater platform: 3-4 hours
- Climate updates: 4-5 hours
- Sensor updates: 2-3 hours
- Binary sensor updates: 1-2 hours
- Integration testing: 2-3 hours

**Can be parallelized:** Water heater and climate can be built concurrently if needed.

---

## Next Steps After Phase 3

1. Deploy to real HA instance (use `tools/deploy_custom_component.py`)
2. Manual testing with mock server
3. Document in ADR-012 or new ADR
4. Create PR for review
5. Release when validated

---

## Key Takeaways

✅ **Follow ATA patterns exactly** - consistency is critical
✅ **Use Phase 2 coordinator methods** - all control already implemented
✅ **Two separate climate entities** - best UX for dual-zone systems
✅ **Water heater platform** - proper HA pattern for DHW control
✅ **Operation status sensor** - essential 3-way valve visibility
✅ **Test through HA core** - no internal coordinator testing
✅ **Mock server ready** - full testing without real device
