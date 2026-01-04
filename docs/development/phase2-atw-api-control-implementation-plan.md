# Strategic Recommendation: What to Build Next

## Current State Summary

**Phase 1 (Models + Mock Server): ✅ COMPLETE**
- API models fully implemented (`AirToWaterUnit`, `AirToWaterCapabilities`)
- 31+ unit tests passing
- Mock server with full 3-way valve simulation
- ADR-012 architecture fully defined
- UI controls documentation complete (986 lines, needs cleanup)

**Phase 2 (API Control Methods): ❌ MISSING - BLOCKING**
- No control methods in `MELCloudHomeClient`
- No coordinator methods for ATW control
- Estimated effort: 2-3 hours

**Phase 3 (Entity Platforms): ❌ MISSING - BLOCKED BY PHASE 2**
- No `water_heater.py` platform
- No ATW support in `climate.py`
- No ATW sensors/binary_sensors
- Estimated effort: 5-8 hours (once unblocked)

**Documentation (`atw-ui-controls-best-practices.md`): ⚠️ FUNCTIONAL BUT BLOATED**
- ~986 lines with ~50% redundancy
- Functional enough to guide implementation
- Would benefit from cleanup but not blocking
- Estimated effort: 1-2 hours

---

## Dependency Analysis

```
Phase 2 (API Control)
    ↓ BLOCKS
Phase 3 (Entity Platforms)
    ↓ ENABLES
User-Facing UI Controls

Documentation ← INDEPENDENT (can be done anytime)
```

**Critical Path:** Phase 2 → Phase 3 → Deployment

**Blocker:** Can't build UI entities without coordinator control methods

---

## Recommendation: Build Phase 2 First (API Control Methods)

### Why Phase 2 Should Be Next

#### 1. **Unblocks Everything** 🔓
Phase 3 (UI) cannot be built without Phase 2. The entities need coordinator methods to call:
- `async_set_power_atw()` - Water heater & climate need this
- `async_set_zone_temperature()` - Climate zones need this
- `async_set_dhw_temperature()` - Water heater needs this
- `async_set_forced_hot_water()` - Water heater operation mode needs this

**Attempting Phase 3 first = immediate blockers + throwaway mock code**

#### 2. **Relatively Quick** ⚡
- Estimated: 2-3 hours for Phase 2
- vs 5-8 hours for Phase 3
- Gets you to "unblocked" state quickly

#### 3. **Low Risk** ✅
- Mock server already implements `PUT /api/atwunit/{id}` endpoint
- Payload structure is known and documented
- Can test immediately against mock server
- Pattern already established by existing ATA control methods

#### 4. **Clean Architecture** 🏗️
Maintains proper layering:
```
Entity → Coordinator → API Client → HTTP
```

Building UI first would require either:
- Bypassing coordinator (architectural violation)
- Writing temporary mock coordinator (throwaway code)
- Waiting on Phase 2 anyway (wasted time)

#### 5. **Immediate Testability** 🧪
Once Phase 2 is done:
- Test control methods against mock server
- Validate 3-way valve simulation responds correctly
- Verify state updates propagate
- Build confidence before Phase 3

---

## Alternative: Documentation Cleanup

### Why NOT Documentation First

**Pros:**
- Clean reference for Phase 3 implementation
- Remove redundancy, improve clarity
- Independent work, no blockers

**Cons:**
- Doesn't move implementation forward
- Current doc is functional enough (despite bloat)
- Can be done anytime (not time-sensitive)
- Only saves ~1 hour in Phase 3 (minor benefit)

**Verdict:** Documentation cleanup is a "nice-to-have," not critical path

---

## Recommended Sequence

### Option A: Maximum Momentum (Recommended)

**Goal:** Get to working UI as fast as possible

1. **Phase 2: Build API Control Methods** (2-3 hours)
   - Add 9 methods to `MELCloudHomeClient` (separate Zone 1 and Zone 2 methods)
   - Add corresponding coordinator methods
   - Add ATW unit caching to coordinator
   - Write ~18 control method tests with VCR cassettes
   - Test against mock server for validation

2. **Phase 3: Build Entity Platforms** (5-8 hours)
   - Create `water_heater.py` (~250 lines)
   - Update `climate.py` for ATW zones (~300 lines)
   - Update `sensor.py` for ATW (~150 lines)
   - Update `binary_sensor.py` for ATW (~50 lines)
   - Update `__init__.py` to register water_heater platform
   - Write integration tests
   - Deploy to mock server environment

3. **Documentation Cleanup** (1-2 hours) - OPTIONAL
   - Do if time permits
   - Or defer until after real hardware validation

**Total Time to Working UI:** 7-11 hours

---

### Option B: Documentation-First Approach (Not Recommended)

**Goal:** Clean reference before implementation

1. **Documentation Cleanup** (1-2 hours)
   - Reduce redundancy from 986 → ~400 lines
   - Fix technical inconsistencies
   - Clarify optional vs required sections

2. **Phase 2: Build API Control Methods** (2-3 hours)
   - Same as Option A

3. **Phase 3: Build Entity Platforms** (5-8 hours)
   - Same as Option A

**Total Time to Working UI:** 8-13 hours (1-2 hours slower)

**Why slower?** Documentation cleanup doesn't reduce Phase 3 effort significantly.

---

## What About Documentation Issues?

### Critical Issues from Review

Your review identified real problems:
- 50% redundant content
- Technical inconsistencies (hardcoded vs API values)
- Missing critical details (coordinator integration)
- Poor organization

### My Take: Not Blocking

**The doc is good enough to implement from:**
- Property checklists are clear
- Code examples show patterns
- ADR-012 has all architectural decisions
- Existing A2A code provides reference patterns

**What's missing can be figured out during implementation:**
- Coordinator integration patterns (look at existing `climate.py`)
- Platform registration (look at existing `__init__.py`)
- Error handling (use existing patterns)

**When to clean up the doc:**
1. **After Phase 2** - API design fresh in mind, can add coordinator details
2. **After Phase 3** - Learned from implementation, can add real patterns
3. **Never** - If it's functional enough, maybe it's fine

---

## Phase 3 Dependencies (FYI)

Once Phase 2 is done, Phase 3 needs:

**File: `custom_components/melcloudhome/__init__.py`**
- Add `Platform.WATER_HEATER` to PLATFORMS list

**File: `custom_components/melcloudhome/water_heater.py` (NEW)**
- Create `ATWWaterHeaterEntity` class
- ~250 lines, ~20 properties, 3 service methods

**File: `custom_components/melcloudhome/climate.py`**
- Add `ATWClimateEntity` class (~300 lines)
- Update `async_setup_entry()` to create ATW climate entities

**Files: `sensor.py`, `binary_sensor.py`**
- Add ATW sensor descriptions (~150 lines total)

---

## Bottom Line

### Do Phase 2 Next (API Control Methods)

**Rationale:**
1. **Unblocks UI work** - Phase 3 requires Phase 2
2. **Fast** - 2-3 hours to unblocked state
3. **Low risk** - Mock server ready, pattern established
4. **Testable** - Immediate validation against mock
5. **Momentum** - Gets you to working UI in 7-11 hours total

**Don't do documentation first:**
- Not blocking
- Saves minimal time in Phase 3
- Can be done later (or never)
- Current doc is functional enough

### Sequence

```
NOW  → Phase 2: API Control (2-3 hrs)
NEXT → Phase 3: Entity Platforms (5-8 hrs)
THEN → Deploy to real hardware
OPTIONAL → Clean up documentation (1-2 hrs)
```

**Result:** Working ATW UI in 7-11 hours, testable against mock server throughout

---

## User Decisions (Confirmed)

✅ **Sequence:** Phase 2 (API control) → Phase 3 (UI entities) → Documentation cleanup
✅ **Documentation:** Clean up after Phase 2 (while API design is fresh)
✅ **Zone 2 support:** Yes - include Zone 2 control methods
✅ **Testing approach:** Use HAR fixtures for VCR cassettes (existing pattern)

**HAR Files Available:**
- `docs/research/ATW/melcloudhome_com_recording2_anonymized.har` (17 PUT requests)
- `docs/research/ATW/melcloudhome_com_recording3_anonymized.har` (26 PUT requests)

**Fixtures Already Exist:**
- `tests/api/fixtures/atw_fixtures.py` (6 scenarios: heating DHW, heating zone, idle, Zone 2, error, half-degrees)

---

## Phase 2 Implementation Plan: ATW API Control Methods

### Overview

Add 9 control methods to API client and coordinator to enable ATW heat pump control (separate methods for Zone 1 and Zone 2). Use VCR cassettes with HAR-extracted fixtures for testing (matches existing ATA pattern).

**Estimated effort:** 2-3 hours

---

### Step 1: Add Control Methods to API Client

**File:** `custom_components/melcloudhome/api/client.py`

Add 9 public control methods + 1 get method + 1 internal helper:

**Prerequisites:** Add `get_atw_unit()` method for Zone 2 capability validation:

```python
async def get_atw_unit(self, unit_id: str) -> AirToWaterUnit | None:
    """Get ATW unit by ID.

    Args:
        unit_id: ATW unit ID

    Returns:
        AirToWaterUnit if found, None otherwise
    """
    context = await self.get_user_context()
    for building in context.buildings:
        for unit in building.air_to_water_units:
            if unit.id == unit_id:
                return unit
    return None
```

**Location:** Add after existing `get_device()` method (for A2A units).

---

#### 1.1 Power Control
```python
async def set_power_atw(self, unit_id: str, power: bool) -> AirToWaterUnit:
    """Power entire ATW heat pump ON/OFF.

    Args:
        unit_id: ATW unit ID
        power: True=ON, False=OFF

    Returns:
        Updated AirToWaterUnit with new state

    Note:
        Powers off ENTIRE system (all zones + DHW)
    """
    payload = {"power": power}
    return await self._update_atw_unit(unit_id, payload)
```

#### 1.2 Zone 1 Temperature Control
```python
async def set_temperature_zone1(
    self, unit_id: str, temperature: float
) -> AirToWaterUnit:
    """Set Zone 1 target temperature (10-30°C).

    Args:
        unit_id: ATW unit ID
        temperature: Target temp in Celsius (10-30°C)

    Returns:
        Updated AirToWaterUnit with new state

    Raises:
        ValueError: If temp out of range
    """
    if not 10 <= temperature <= 30:
        raise ValueError(f"Zone temperature must be 10-30°C, got {temperature}")

    payload = {"setTemperatureZone1": temperature}
    return await self._update_atw_unit(unit_id, payload)
```

#### 1.3 Zone 2 Temperature Control
```python
async def set_temperature_zone2(
    self, unit_id: str, temperature: float
) -> AirToWaterUnit:
    """Set Zone 2 target temperature (10-30°C).

    Args:
        unit_id: ATW unit ID
        temperature: Target temp in Celsius (10-30°C)

    Returns:
        Updated AirToWaterUnit with new state

    Raises:
        ValueError: If temp out of range or device doesn't have Zone 2

    Note:
        Validates device has Zone 2 capability before sending request.
    """
    if not 10 <= temperature <= 30:
        raise ValueError(f"Zone temperature must be 10-30°C, got {temperature}")

    # Validate device has Zone 2
    device = await self.get_atw_unit(unit_id)
    if device and not device.capabilities.has_zone2:
        raise ValueError(f"Device {unit_id} does not have Zone 2")

    payload = {"setTemperatureZone2": temperature}
    return await self._update_atw_unit(unit_id, payload)
```

#### 1.4 Zone 1 Operation Mode Control
```python
async def set_mode_zone1(
    self, unit_id: str, mode: str
) -> AirToWaterUnit:
    """Set Zone 1 heating strategy.

    Args:
        unit_id: ATW unit ID
        mode: One of:
            - "HeatRoomTemperature" (thermostat control)
            - "HeatFlowTemperature" (direct flow temp)
            - "HeatCurve" (weather compensation)

    Returns:
        Updated AirToWaterUnit with new state

    Raises:
        ValueError: If mode unknown
    """
    valid_modes = {"HeatRoomTemperature", "HeatFlowTemperature", "HeatCurve"}
    if mode not in valid_modes:
        raise ValueError(f"Mode must be one of {valid_modes}, got {mode}")

    payload = {"operationModeZone1": mode}
    return await self._update_atw_unit(unit_id, payload)
```

#### 1.5 Zone 2 Operation Mode Control
```python
async def set_mode_zone2(
    self, unit_id: str, mode: str
) -> AirToWaterUnit:
    """Set Zone 2 heating strategy.

    Args:
        unit_id: ATW unit ID
        mode: One of:
            - "HeatRoomTemperature" (thermostat control)
            - "HeatFlowTemperature" (direct flow temp)
            - "HeatCurve" (weather compensation)

    Returns:
        Updated AirToWaterUnit with new state

    Raises:
        ValueError: If mode unknown or device doesn't have Zone 2

    Note:
        Validates device has Zone 2 capability before sending request.
    """
    valid_modes = {"HeatRoomTemperature", "HeatFlowTemperature", "HeatCurve"}
    if mode not in valid_modes:
        raise ValueError(f"Mode must be one of {valid_modes}, got {mode}")

    # Validate device has Zone 2
    device = await self.get_atw_unit(unit_id)
    if device and not device.capabilities.has_zone2:
        raise ValueError(f"Device {unit_id} does not have Zone 2")

    payload = {"operationModeZone2": mode}
    return await self._update_atw_unit(unit_id, payload)
```

#### 1.6 DHW Temperature Control
```python
async def set_dhw_temperature(
    self, unit_id: str, temperature: float
) -> AirToWaterUnit:
    """Set DHW tank target temperature (40-60°C).

    Args:
        unit_id: ATW unit ID
        temperature: Target temp in Celsius (40-60°C)

    Returns:
        Updated AirToWaterUnit with new state

    Raises:
        ValueError: If temp out of range
    """
    if not 40 <= temperature <= 60:
        raise ValueError(f"DHW temperature must be 40-60°C, got {temperature}")

    payload = {"setTankWaterTemperature": temperature}
    return await self._update_atw_unit(unit_id, payload)
```

#### 1.7 Forced DHW Mode Control
```python
async def set_forced_hot_water(
    self, unit_id: str, enabled: bool
) -> AirToWaterUnit:
    """Enable/disable forced DHW priority mode.

    Args:
        unit_id: ATW unit ID
        enabled: True=DHW priority (suspends zone heating)
                False=Normal balanced operation

    Returns:
        Updated AirToWaterUnit with new state

    Note:
        When enabled, 3-way valve prioritizes DHW tank heating
        and zone heating is suspended until DHW reaches target.
    """
    payload = {"forcedHotWaterMode": enabled}
    return await self._update_atw_unit(unit_id, payload)
```

#### 1.8 Standby Mode Control (Optional but Recommended)
```python
async def set_standby_mode(
    self, unit_id: str, standby: bool
) -> AirToWaterUnit:
    """Enable/disable standby mode.

    Args:
        unit_id: ATW unit ID
        standby: True=standby (frost protection only)
                False=normal operation

    Returns:
        Updated AirToWaterUnit with new state
    """
    payload = {"inStandbyMode": standby}
    return await self._update_atw_unit(unit_id, payload)
```

#### 1.9 Internal Update Helper
```python
async def _update_atw_unit(
    self, unit_id: str, payload: dict
) -> AirToWaterUnit:
    """Internal: Send PUT request to /api/atwunit/{id}.

    Args:
        unit_id: ATW unit ID
        payload: Sparse update payload (only changed fields + nulls)

    Returns:
        Updated AirToWaterUnit parsed from response

    Raises:
        APIError: If request fails

    Note:
        Uses sparse update pattern - only send changed fields.
        API expects ALL control fields present (unchanged = null).
    """
    # Sparse update: Include all control fields, null for unchanged
    full_payload = {
        "power": None,
        "setTankWaterTemperature": None,
        "forcedHotWaterMode": None,
        "setTemperatureZone1": None,
        "setTemperatureZone2": None,
        "operationModeZone1": None,
        "operationModeZone2": None,
        "inStandbyMode": None,
        "setHeatFlowTemperatureZone1": None,  # Future: Flow temp control
        "setCoolFlowTemperatureZone1": None,
        "setHeatFlowTemperatureZone2": None,
        "setCoolFlowTemperatureZone2": None,
        **payload,  # Override with actual values
    }

    response = await self._session.put(
        f"{self._base_url}/api/atwunit/{unit_id}",
        json=full_payload,
    )
    response.raise_for_status()

    data = response.json()
    return AirToWaterUnit.from_dict(data)
```

**Location in file:** Add after existing `set_vane_position()` method (for A2A control)

---

### Step 2: Add Coordinator Methods

**File:** `custom_components/melcloudhome/coordinator.py`

#### 2.1 Add ATW Unit Caching

Update `_async_rebuild_cache_from_user_context()` method:

```python
def _async_rebuild_cache_from_user_context(
    self, user_context: UserContext
) -> None:
    """Rebuild internal cache from user context."""
    # Clear existing cache
    self._units.clear()
    self._atw_units.clear()  # ADD THIS
    self._unit_to_building.clear()
    self._atw_unit_to_building.clear()  # ADD THIS

    # Populate from user context
    for building in user_context.buildings:
        # Cache A2A units (existing)
        for unit in building.air_to_air_units:
            self._units[unit.id] = unit
            self._unit_to_building[unit.id] = building

        # Cache A2W units (ADD THIS)
        for atw_unit in building.air_to_water_units:
            self._atw_units[atw_unit.id] = atw_unit
            self._atw_unit_to_building[atw_unit.id] = building
```

Add cache dictionaries to `__init__()` after existing A2A cache dictionaries:

```python
self._unit_to_building: dict[str, Building] = {}
self._units: dict[str, AirToAirUnit] = {}
self._atw_units: dict[str, AirToWaterUnit] = {}  # ADD THIS
self._atw_unit_to_building: dict[str, Building] = {}  # ADD THIS
```

Add lookup method after existing `get_unit()` method:

```python
def get_atw_unit(self, unit_id: str) -> AirToWaterUnit | None:
    """Get ATW unit by ID from cache."""
    return self._atw_units.get(unit_id)
```

#### 2.2 Add Control Methods

Add after existing `async_set_vane_position()` method (for A2A control):

```python
async def async_set_power_atw(self, unit_id: str, power: bool) -> None:
    """Set ATW heat pump power."""
    await self.client.set_power_atw(unit_id, power)
    await self.async_request_refresh()

async def async_set_temperature_zone1(
    self, unit_id: str, temperature: float
) -> None:
    """Set Zone 1 target temperature."""
    await self.client.set_temperature_zone1(unit_id, temperature)
    await self.async_request_refresh()

async def async_set_temperature_zone2(
    self, unit_id: str, temperature: float
) -> None:
    """Set Zone 2 target temperature."""
    await self.client.set_temperature_zone2(unit_id, temperature)
    await self.async_request_refresh()

async def async_set_mode_zone1(
    self, unit_id: str, mode: str
) -> None:
    """Set Zone 1 heating strategy."""
    await self.client.set_mode_zone1(unit_id, mode)
    await self.async_request_refresh()

async def async_set_mode_zone2(
    self, unit_id: str, mode: str
) -> None:
    """Set Zone 2 heating strategy."""
    await self.client.set_mode_zone2(unit_id, mode)
    await self.async_request_refresh()

async def async_set_dhw_temperature(
    self, unit_id: str, temperature: float
) -> None:
    """Set DHW tank target temperature."""
    await self.client.set_dhw_temperature(unit_id, temperature)
    await self.async_request_refresh()

async def async_set_forced_hot_water(
    self, unit_id: str, enabled: bool
) -> None:
    """Enable/disable forced DHW priority mode."""
    await self.client.set_forced_hot_water(unit_id, enabled)
    await self.async_request_refresh()

async def async_set_standby_mode(
    self, unit_id: str, standby: bool
) -> None:
    """Enable/disable standby mode."""
    await self.client.set_standby_mode(unit_id, standby)
    await self.async_request_refresh()
```

---

### Step 3: Create Control Test Fixtures

**File:** `tests/api/fixtures/atw_control_fixtures.py` (NEW)

Extract PUT request/response pairs from HAR files:

```python
"""Control operation fixtures for ATW API testing.

Extracted from HAR files:
- docs/research/ATW/melcloudhome_com_recording2_anonymized.har
- docs/research/ATW/melcloudhome_com_recording3_anonymized.har

De-anonymized field names: "Doeter" → "Water"
"""

# Power control
ATW_CONTROL_POWER_ON_REQUEST = {
    "power": True,
    "setTankWaterTemperature": None,
    "forcedHotWaterMode": None,
    "setTemperatureZone1": None,
    "setTemperatureZone2": None,
    "operationModeZone1": None,
    "operationModeZone2": None,
    # ... all other fields
}

ATW_CONTROL_POWER_ON_RESPONSE = {
    # Full device state after power on
    # (copy from atw_fixtures.py and modify power=True)
}

# Repeat for:
# - POWER_OFF
# - FORCED_DHW_ENABLE / DISABLE
# - ZONE_TEMP_22
# - ZONE_MODE_HEAT_ROOM_TEMP
# - DHW_TEMP_50
# - STANDBY_ENABLE
```

**Action:** Use script or manual extraction from HAR files (search for PUT requests to `/api/atwunit/`)

---

### Step 4: Write Control Method Tests

**File:** `tests/api/test_atw_control.py` (NEW)

Pattern matches `tests/api/test_client_control.py`:

**Note:** Add ATW unit ID fixtures to `tests/conftest.py` (similar to existing `dining_room_unit_id` fixture):
```python
@pytest.fixture
def atw_unit_id_zone1() -> str:
    """ID of ATW unit with single zone for testing."""
    return "ACTUAL-ATW-UNIT-ID-FROM-YOUR-ACCOUNT"

@pytest.fixture
def atw_unit_id_zone2() -> str:
    """ID of ATW unit with two zones for testing."""
    return "ACTUAL-ATW-UNIT-ID-WITH-ZONE2"
```

Replace `"unit-001"` and `"unit-004"` in tests with fixture parameters.

---

```python
"""Tests for ATW API control methods.

Uses VCR cassettes recorded from live API interactions.
"""

import pytest
from custom_components.melcloudhome.api.client import MELCloudHomeClient


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_set_power_atw_on(
    authenticated_client: MELCloudHomeClient,
    atw_unit_id_zone1: str,
) -> None:
    """Test turning ATW heat pump on."""
    # Turn on
    unit = await authenticated_client.set_power_atw(atw_unit_id_zone1, True)

    # Verify
    assert unit is not None
    assert unit.power is True


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_set_power_atw_off(
    authenticated_client: MELCloudHomeClient,
) -> None:
    """Test turning ATW heat pump off."""
    unit_id = "unit-001"

    unit = await authenticated_client.set_power_atw(unit_id, False)

    assert unit is not None
    assert unit.power is False


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_set_temperature_zone1(
    authenticated_client: MELCloudHomeClient,
) -> None:
    """Test setting Zone 1 target temperature."""
    unit_id = "unit-001"
    target_temp = 22.0

    unit = await authenticated_client.set_temperature_zone1(unit_id, target_temp)

    assert unit is not None
    assert unit.set_temperature_zone1 == target_temp


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_set_temperature_zone2(
    authenticated_client: MELCloudHomeClient,
) -> None:
    """Test setting Zone 2 target temperature."""
    unit_id = "unit-004"  # Has Zone 2
    target_temp = 20.0

    unit = await authenticated_client.set_temperature_zone2(unit_id, target_temp)

    assert unit is not None
    assert unit.set_temperature_zone2 == target_temp


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_set_mode_zone1_room_temperature(
    authenticated_client: MELCloudHomeClient,
) -> None:
    """Test setting Zone 1 to thermostat control mode."""
    unit_id = "unit-001"
    mode = "HeatRoomTemperature"

    unit = await authenticated_client.set_mode_zone1(unit_id, mode)

    assert unit is not None
    assert unit.operation_mode_zone1 == mode


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_set_mode_zone1_heat_curve(
    authenticated_client: MELCloudHomeClient,
) -> None:
    """Test setting Zone 1 to weather compensation mode."""
    unit_id = "unit-001"
    mode = "HeatCurve"

    unit = await authenticated_client.set_mode_zone1(unit_id, mode)

    assert unit is not None
    assert unit.operation_mode_zone1 == mode


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_set_mode_zone2_room_temperature(
    authenticated_client: MELCloudHomeClient,
) -> None:
    """Test setting Zone 2 to thermostat control mode."""
    unit_id = "unit-004"  # Has Zone 2
    mode = "HeatRoomTemperature"

    unit = await authenticated_client.set_mode_zone2(unit_id, mode)

    assert unit is not None
    assert unit.operation_mode_zone2 == mode


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_set_dhw_temperature(
    authenticated_client: MELCloudHomeClient,
) -> None:
    """Test setting DHW tank target temperature."""
    unit_id = "unit-001"
    target_temp = 50.0

    unit = await authenticated_client.set_dhw_temperature(unit_id, target_temp)

    assert unit is not None
    assert unit.set_tank_water_temperature == target_temp


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_set_forced_hot_water_enable(
    authenticated_client: MELCloudHomeClient,
) -> None:
    """Test enabling forced DHW priority mode."""
    unit_id = "unit-001"

    unit = await authenticated_client.set_forced_hot_water(unit_id, True)

    assert unit is not None
    assert unit.forced_hot_water_mode is True


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_set_forced_hot_water_disable(
    authenticated_client: MELCloudHomeClient,
) -> None:
    """Test disabling forced DHW mode."""
    unit_id = "unit-001"

    unit = await authenticated_client.set_forced_hot_water(unit_id, False)

    assert unit is not None
    assert unit.forced_hot_water_mode is False


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_set_standby_mode(
    authenticated_client: MELCloudHomeClient,
) -> None:
    """Test enabling standby mode."""
    unit_id = "unit-001"

    unit = await authenticated_client.set_standby_mode(unit_id, True)

    assert unit is not None
    assert unit.in_standby_mode is True


# Validation tests
@pytest.mark.asyncio
async def test_set_temperature_zone1_out_of_range(
    authenticated_client: MELCloudHomeClient,
) -> None:
    """Test Zone 1 temperature out of safe range."""
    with pytest.raises(ValueError, match="must be 10-30"):
        await authenticated_client.set_temperature_zone1("unit-001", 35.0)


@pytest.mark.asyncio
async def test_set_temperature_zone2_out_of_range(
    authenticated_client: MELCloudHomeClient,
) -> None:
    """Test Zone 2 temperature out of safe range."""
    with pytest.raises(ValueError, match="must be 10-30"):
        await authenticated_client.set_temperature_zone2("unit-004", 5.0)


@pytest.mark.asyncio
async def test_set_dhw_temperature_out_of_range(
    authenticated_client: MELCloudHomeClient,
) -> None:
    """Test DHW temperature out of safe range."""
    with pytest.raises(ValueError, match="must be 40-60"):
        await authenticated_client.set_dhw_temperature("unit-001", 70.0)


@pytest.mark.asyncio
async def test_set_mode_zone1_invalid(
    authenticated_client: MELCloudHomeClient,
) -> None:
    """Test Zone 1 mode with invalid mode string."""
    with pytest.raises(ValueError, match="Mode must be one of"):
        await authenticated_client.set_mode_zone1("unit-001", "InvalidMode")


@pytest.mark.asyncio
async def test_set_mode_zone2_invalid(
    authenticated_client: MELCloudHomeClient,
) -> None:
    """Test Zone 2 mode with invalid mode string."""
    with pytest.raises(ValueError, match="Mode must be one of"):
        await authenticated_client.set_mode_zone2("unit-004", "InvalidMode")
```

**Test count:** ~18 tests (13 VCR + 5 validation)

---

### Step 5: Generate VCR Cassettes (Live Recording)

**VCR Pattern (Same as Phase 1):**

Tests use `@pytest.mark.vcr()` decorator to automatically record/replay HTTP interactions:

1. **First run (recording):**
   ```bash
   # Set credentials for live API access
   export MELCLOUD_USER="your.email@example.com"
   export MELCLOUD_PASSWORD="your_password"

   # Run tests - VCR will record live API calls
   pytest tests/api/test_atw_control.py -v
   ```

   VCR automatically:
   - Makes real API calls to `https://melcloudhome.com`
   - Records requests + responses to `tests/api/cassettes/test_atw_control_*.yaml`
   - Scrubs sensitive data (emails, passwords, cookies) per `conftest.py` config

2. **Subsequent runs (replay):**
   ```bash
   # No credentials needed - VCR replays from cassettes
   pytest tests/api/test_atw_control.py -v
   ```

   VCR automatically:
   - Matches requests to cassettes
   - Returns cached responses
   - No actual API calls made

**Configuration:** Already set up in `tests/conftest.py`:
- Cassette directory: `tests/api/cassettes/`
- Sensitive data scrubbing (emails, passwords, device names)
- Match on: method, scheme, host, port, path, query
- Record mode: `once` (record if missing, else replay)

**HAR Files:** Used for research/reference only, not for cassette generation.

**Cassette location:** `tests/api/cassettes/test_atw_control_*.yaml`

---

### Step 6: Run Tests

```bash
# Run ATW control tests
pytest tests/api/test_atw_control.py -v

# Run all API tests (verify no regressions)
pytest tests/api/ -v

# Type check
make type-check

# Lint
make lint
```

**Expected results:**
- ~15 new tests pass
- All existing tests still pass
- No type errors
- No lint errors

---

### Step 7: Manual Validation Against Mock Server

```bash
# Start mock server
python tools/mock_melcloud_server.py

# In another terminal, test control methods
python -c "
import asyncio
from custom_components.melcloudhome.api.client import MELCloudHomeClient

async def test():
    client = MELCloudHomeClient('http://localhost:8080')
    await client.login('test@example.com', 'password')

    # Get initial state
    ctx = await client.get_user_context()
    unit = ctx.buildings[0].air_to_water_units[0]
    print(f'Initial: power={unit.power}, zone1_temp={unit.set_temperature_zone1}')

    # Test power control
    unit = await client.set_power_atw(unit.id, False)
    print(f'After power off: power={unit.power}')

    unit = await client.set_power_atw(unit.id, True)
    print(f'After power on: power={unit.power}')

    # Test zone temperature
    unit = await client.set_temperature_zone1(unit.id, 23.0)
    print(f'After set temp: zone1_temp={unit.set_temperature_zone1}')

    # Test forced DHW
    unit = await client.set_forced_hot_water(unit.id, True)
    print(f'After force DHW: forced={unit.forced_hot_water_mode}, status={unit.operation_status}')

    await client.close()

asyncio.run(test())
"
```

**Watch mock server logs** to verify:
- PUT requests sent with correct payloads
- 3-way valve simulation updates operation_status
- Responses include updated state

---

## Success Criteria

✅ **Code Quality:**
- [ ] 9 control methods added to `MELCloudHomeClient`
- [ ] 8 coordinator methods added to `MELCloudHomeCoordinator`
- [ ] ATW unit caching implemented
- [ ] All methods have docstrings with types
- [ ] Input validation for temperature ranges and modes
- [ ] No type errors (mypy passes)
- [ ] No lint errors (ruff passes)

✅ **Tests:**
- [ ] ~18 control method tests pass
- [ ] VCR cassettes generated for all operations
- [ ] Validation tests for error cases
- [ ] All existing tests still pass

✅ **Manual Validation:**
- [ ] Power control works (on/off)
- [ ] Zone temperature control works (Zone 1 & 2)
- [ ] Zone mode control works (all 3 modes)
- [ ] DHW temperature control works
- [ ] Forced DHW mode works (3-way valve status updates)
- [ ] Standby mode works
- [ ] Mock server logs show correct PUT requests

---

## Files Modified

1. **`custom_components/melcloudhome/api/client.py`**
   - Add 9 public control methods (separate Zone 1 and Zone 2 methods)
   - Add `_update_atw_unit()` helper
   - ~170 lines added

2. **`custom_components/melcloudhome/coordinator.py`**
   - Add ATW unit caching (2 dictionaries)
   - Add `get_atw_unit()` lookup method
   - Add 8 coordinator control methods
   - ~100 lines added

3. **`tests/api/fixtures/atw_control_fixtures.py`** (NEW)
   - Control request/response fixtures
   - ~200 lines

4. **`tests/api/test_atw_control.py`** (NEW)
   - ~18 control method tests
   - ~300 lines

5. **`tests/api/cassettes/test_atw_control_*.yaml`** (NEW)
   - ~18 VCR cassette files
   - Auto-generated

**Total:** ~770 new lines of code + tests

---

## Next Steps After Phase 2

Once Phase 2 is complete and tests pass:

1. **Optional: Documentation cleanup** (1-2 hours)
   - Reduce `atw-ui-controls-best-practices.md` from 986 → ~400 lines
   - Add coordinator integration examples
   - Fix technical inconsistencies

2. **Phase 3: Entity Platforms** (5-8 hours)
   - Create `water_heater.py` platform
   - Update `climate.py` for ATW zones
   - Update `sensor.py` and `binary_sensor.py` for ATW
   - Write integration tests
   - Deploy to mock server
   - Test with real hardware (when available)

3. **Phase 4: Production Deployment**
   - Create feature branch
   - Test with real ATW hardware
   - Create PR with changelog
   - Merge and release
