# Phase 3: ATW Entity Platforms Implementation Plan

## Goal

Create Home Assistant entity platforms for ATW (Air-to-Water) heat pump control, enabling UI-based control of zones and DHW.

## Prerequisites ✅

- Phase 2 complete: All ATW control methods implemented in coordinator
- Mock server running with ATW support
- ATA entity patterns established (climate, sensor, binary_sensor)

## Critical Review Findings (2026-01-04)

**Review Status:** Plan validated against actual ATA implementation
**Document:** See `phase3-critical-review.md` for full analysis

**Key Corrections Applied:**

- Added missing `get_building_for_atw_unit()` coordinator method
- Refined 3-way valve hvac_action logic (check specific zone, not just "any zone")
- Fixed temperature unit to use `UnitOfTemperature.CELSIUS` constant
- Added type ignore comments documentation
- Added setup logging requirement
- Verified water_heater platform exists in HA with correct features
- Updated water heater operation modes to use HA constants

## Key Architectural Decisions

### 1. Climate Entities: Zone 1 Only (Simplified Scope)

- **Zone 1 climate entity** - Single zone implementation
- **Zone 2 climate entity** - **DEFERRED TO PHASE 4** (no test hardware available)
- **Rationale**: Don't implement what we can't test. Zone 2 support added later when hardware accessible.

### 2. Water Heater Platform

- **NEW platform**: `water_heater.py` for DHW tank control
- **Operation modes**: `eco` (balanced) and `performance` (DHW priority)
- **Power control**: `turn_on()`/`turn_off()` controls entire system (documented behavior)

### 3. ATW-Specific Sensors (3 sensors - Essential Only)

- **Zone 1 temperature** - Current room temp from Zone 1 thermostat
- **Tank temperature** - Current DHW tank temperature
- **Operation status** - Shows 3-way valve position (raw API values: "Stop", "HotWater", "HeatRoomTemperature", etc.)
- WiFi signal - **DEFERRED** (not essential, can add later)

### 4. ATW-Specific Binary Sensors (3)

- **Error state** (problem) - Device error detection
- **Connection state** (connectivity) - Online/offline status
- **Forced DHW active** (running) - Shows when DHW has priority over zones

## Implementation Plan

### Step 0: Add Missing Coordinator Helper (`coordinator.py`)

**REQUIRED FIRST:** Add building lookup helper for ATW units

**Add after `get_atw_unit()` method:**

```python
def get_building_for_atw_unit(self, unit_id: str) -> Building | None:
    """Get the building that contains the specified ATW unit - O(1) lookup.

    Args:
        unit_id: ATW unit ID

    Returns:
        Building containing the unit, or None if not found
    """
    return self._atw_unit_to_building.get(unit_id)
```

**Lines:** ~10 added
**Why needed:** Matches ATA pattern for consistency, enables `_building` property in entities

---

### Step 1: Update Constants (`const.py`)

**Add ATW mappings:**

```python
# ATW Zone Modes → Climate Preset Modes (lowercase for i18n)
# Display names in translations/en.json: "Room", "Flow", "Curve"
ATW_TO_HA_PRESET = {
    "HeatRoomTemperature": "room",  # Display: "Room"
    "HeatFlowTemperature": "flow",  # Display: "Flow"
    "HeatCurve": "curve",            # Display: "Curve"
}

HA_TO_ATW_PRESET = {v: k for k, v in ATW_TO_HA_PRESET.items()}

# Water Heater Operation Modes (map to HA standard modes)
# Use HA constants from homeassistant.components.water_heater
# STATE_ECO, STATE_PERFORMANCE are standard HA modes
WATER_HEATER_FORCED_DHW_TO_HA = {
    False: "eco",        # Maps to STATE_ECO
    True: "performance",  # Maps to STATE_PERFORMANCE
}
WATER_HEATER_HA_TO_FORCED_DHW = {
    "eco": False,
    "performance": True,
}

# Preset modes list (lowercase keys, translated in en.json)
ATW_PRESET_MODES = ["room", "flow", "curve"]
```

**Lines:** ~20 added

---

### Step 2: Add Translations (`translations/en.json`)

**Add ATW translations for preset modes and sensors:**

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

**Lines:** ~15 added (merge with existing translations)

---

### Step 3: Create Water Heater Platform (`water_heater.py` - NEW)

**Imports Required:**

```python
from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
    STATE_ECO,
    STATE_PERFORMANCE,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.device_registry import DeviceInfo
```

**Pattern:** Follow `climate.py` structure with type ignore comments

**Class Definition:**

```python
class ATWWaterHeater(
    CoordinatorEntity[MELCloudHomeCoordinator],  # type: ignore[misc]
    WaterHeaterEntity,  # type: ignore[misc]
):
    """Water heater entity for ATW DHW tank.

    Note: type: ignore[misc] required because HA is not installed in dev environment
    (aiohttp version conflict). Mypy sees HA base classes as 'Any'.
    """

    _attr_has_entity_name = False  # Use explicit naming for stable entity IDs
    _attr_temperature_unit = UnitOfTemperature.CELSIUS  # Use constant
```

**Key Features:**

- Temperature control: 40-60°C (use `ATW_TEMP_MIN_DHW`, `ATW_TEMP_MAX_DHW`)
- Operation modes: `STATE_ECO`/`STATE_PERFORMANCE` (HA standard constants)
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

**Class Definition:**

```python
class ATWClimateZone1(
    CoordinatorEntity[MELCloudHomeCoordinator],  # type: ignore[misc]
    ClimateEntity,  # type: ignore[misc]
):
    """Climate entity for ATW Zone 1.

    Note: type: ignore[misc] required because HA is not installed in dev environment
    (aiohttp version conflict). Mypy sees HA base classes as 'Any'.
    """

    _attr_has_entity_name = False
    _attr_temperature_unit = UnitOfTemperature.CELSIUS  # Use constant
    _attr_target_temperature_step = ATW_TEMP_STEP
    _attr_min_temp = ATW_TEMP_MIN_ZONE
    _attr_max_temp = ATW_TEMP_MAX_ZONE
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_preset_modes = ATW_PRESET_MODES  # NEW: Not used in ATA
```

**NEW FEATURE: Preset Modes**

- ⚠️ **This is NEW functionality** not present in ATA climate entities
- Preset modes map ATW zone operation strategies to HA UI
- Requires implementing `ClimateEntityFeature.PRESET_MODE`
- Requires `preset_mode` property and `async_set_preset_mode()` method
- **Research needed:** Custom preset names may need translations in `strings.json`

**Features:**

- HVAC modes: `[OFF, HEAT]` (heat-only system)
- Preset modes: `room_temperature`, `flow_temperature`, `weather_compensation` (zone strategies)
- Temperature range: 10-30°C
- Uses `coordinator.async_set_temperature_zone1()`, `async_set_mode_zone1()`, `async_set_power_atw()`

**Device Info (with suggested_area):**

```python
self._attr_device_info = DeviceInfo(
    identifiers={(DOMAIN, unit.id)},
    name=f"{building.name} {unit.name}",
    manufacturer="Mitsubishi Electric",
    model=f"Air-to-Water Heat Pump (Ecodan FTC{unit.ftc_model})",
    suggested_area=building.name,  # IMPORTANT: for HA area assignment
)
```

**HVAC Action Logic (3-way valve aware - REFINED):**

```python
@property
def hvac_action(self) -> HVACAction | None:
    """Return current HVAC action (3-way valve aware).

    CRITICAL: Must check if valve is serving THIS specific zone.
    operation_status shows what valve is ACTIVELY doing.
    operation_mode_zone1 shows CONFIGURED mode for Zone 1.

    Valve serves Zone 1 only when: operation_status == operation_mode_zone1
    """
    device = self._device
    if device is None or not device.power:
        return HVACAction.OFF

    # Check if 3-way valve is serving THIS zone (Zone 1)
    # Don't just check "is it on a zone" - check if it's on ZONE 1 specifically
    if device.operation_status == device.operation_mode_zone1:
        # Valve is on Zone 1 - check if heating needed
        current = device.room_temperature_zone1
        target = device.set_temperature_zone1

        if current is not None and target is not None:
            if current < target - 0.5:  # Hysteresis threshold
                return HVACAction.HEATING
        return HVACAction.IDLE

    # Valve is elsewhere (DHW or Zone 2) - zone shows IDLE even if below target
    return HVACAction.IDLE
```

**Zone 2 HVAC Action (similar):**

```python
# For Zone 2 entity: if device.operation_status == device.operation_mode_zone2:
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
class MELCloudHomeATWSensorEntityDescription(SensorEntityDescription):  # type: ignore[misc]
    """ATW sensor entity description with value extraction.

    Note: type: ignore[misc] required because HA is not installed in dev environment
    (aiohttp version conflict). Mypy sees SensorEntityDescription as 'Any'.
    """

    value_fn: Callable[[AirToWaterUnit], float | str | None]
    """Function to extract sensor value from unit data."""

    available_fn: Callable[[AirToWaterUnit], bool] = lambda x: True
    """Function to determine if sensor is available."""

    should_create_fn: Callable[[AirToWaterUnit], bool] | None = None
    """Function to determine if sensor should be created. If None, uses available_fn."""


ATW_SENSOR_TYPES: tuple[MELCloudHomeATWSensorEntityDescription, ...] = (
    # Zone 1 temperature
    MELCloudHomeATWSensorEntityDescription(
        key="zone_1_temperature",
        translation_key="zone_1_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda unit: unit.room_temperature_zone1,
        available_fn=lambda unit: unit.room_temperature_zone1 is not None,
    ),

    # Tank temperature
    MELCloudHomeATWSensorEntityDescription(
        key="tank_temperature",
        translation_key="tank_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda unit: unit.tank_water_temperature,
        available_fn=lambda unit: unit.tank_water_temperature is not None,
    ),

    # Operation status (3-way valve position - raw API values)
    MELCloudHomeATWSensorEntityDescription(
        key="operation_status",
        translation_key="operation_status",
        device_class=None,  # Categorical (not numeric)
        value_fn=lambda unit: unit.operation_status,  # Raw: "Stop", "HotWater", "HeatRoomTemperature", etc.
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
        translation_key="error_state",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda unit: unit.is_in_error,
    ),
    MELCloudHomeBinarySensorEntityDescription(
        key="connection_state",
        translation_key="connection_state",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda unit: True,  # Handled by coordinator.last_update_success
    ),
    MELCloudHomeBinarySensorEntityDescription(
        key="forced_dhw_active",
        translation_key="forced_dhw_active",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda unit: unit.forced_hot_water_mode,
    ),
)
```

**Add ATWBinarySensor Class:**

```python
class ATWBinarySensor(
    CoordinatorEntity[MELCloudHomeCoordinator],  # type: ignore[misc]
    BinarySensorEntity,  # type: ignore[misc]
):
    """Representation of a MELCloud Home ATW binary sensor.

    Note: type: ignore[misc] required because HA is not installed in dev environment
    (aiohttp version conflict). Mypy sees HA base classes as 'Any'.
    """

    # Same pattern as MELCloudHomeBinarySensor
    # Special case: connection_state has different availability logic
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
