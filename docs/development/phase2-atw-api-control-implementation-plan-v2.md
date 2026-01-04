# Phase 2: ATW API Control Methods - Implementation Plan v2

**Goal:** Add ATW (Air-to-Water) heat pump control methods to API client and coordinator

**Status:** Ready for implementation (patterns verified against ATA)

**Estimated effort:** 2-3 hours

---

## Quick Overview

Add **9 control methods** to enable ATW heat pump control:

| Method | Purpose | Endpoint |
|--------|---------|----------|
| `set_power_atw()` | Power entire system on/off | PUT /api/atwunit/{id} |
| `set_temperature_zone1()` | Set Zone 1 target (10-30°C) | PUT /api/atwunit/{id} |
| `set_temperature_zone2()` | Set Zone 2 target (10-30°C) | PUT /api/atwunit/{id} |
| `set_mode_zone1()` | Set Zone 1 heating strategy | PUT /api/atwunit/{id} |
| `set_mode_zone2()` | Set Zone 2 heating strategy | PUT /api/atwunit/{id} |
| `set_dhw_temperature()` | Set DHW tank target (40-60°C) | PUT /api/atwunit/{id} |
| `set_forced_hot_water()` | Enable/disable DHW priority | PUT /api/atwunit/{id} |
| `set_standby_mode()` | Enable/disable standby mode | PUT /api/atwunit/{id} |

**Pattern:** All methods use same endpoint with sparse update payload (only changed field + nulls)

---

## Prerequisites

Before starting, verify these exist:

- ✅ `AirToWaterUnit` model in `api/models.py`
- ✅ `AirToWaterCapabilities` with `has_zone2: bool`
- ✅ `ATW_*` constants in `api/const.py` (temp ranges, mode names)
- ✅ `get_user_context()` returns ATW units in `UserContext`
- ✅ `_api_request()` method in `MELCloudHomeClient`
- ✅ `_execute_with_retry()` method in coordinator
- ✅ VCR configuration in `tests/conftest.py`

**All prerequisites are met** (verified via code analysis)

---

## Implementation Steps

### Step 1: Add Helper Method to API Client

**File:** `custom_components/melcloudhome/api/client.py`

**Location:** Add after existing `set_vanes()` method (last ATA control method)

**Purpose:** DRY - Build sparse update payload in one place (ATW has 12+ control fields)

```python
async def _update_atw_unit(self, unit_id: str, payload: dict[str, Any]) -> None:
    """Send sparse update to ATW unit.

    Args:
        unit_id: ATW unit ID
        payload: Fields to update (others will be set to None)

    Raises:
        AuthenticationError: If not authenticated
        ApiError: If API request fails

    Note:
        API requires ALL control fields present in payload.
        Changed fields have values, unchanged fields are None.
    """
    # Build complete payload with nulls for unchanged fields
    full_payload = {
        "power": None,
        "setTankWaterTemperature": None,
        "forcedHotWaterMode": None,
        "setTemperatureZone1": None,
        "setTemperatureZone2": None,
        "operationModeZone1": None,
        "operationModeZone2": None,
        "inStandbyMode": None,
        "setHeatFlowTemperatureZone1": None,
        "setCoolFlowTemperatureZone1": None,
        "setHeatFlowTemperatureZone2": None,
        "setCoolFlowTemperatureZone2": None,
        **payload,  # Override with actual values
    }

    # Send request (returns None, follows ATA pattern)
    await self._api_request("PUT", f"/api/atwunit/{unit_id}", json=full_payload)
```

**Note:** This is a DRY improvement over ATA (which duplicates payload building in each method). ATA could benefit from same refactoring (see Appendix A).

---

### Step 2: Add Control Methods to API Client

**File:** `custom_components/melcloudhome/api/client.py`

**Location:** Add after `_update_atw_unit()` helper

Add 9 public control methods following ATA pattern:

#### 2.1 Power Control

```python
async def set_power_atw(self, unit_id: str, power: bool) -> None:
    """Power entire ATW heat pump ON/OFF.

    Args:
        unit_id: ATW unit ID
        power: True=ON, False=OFF

    Raises:
        AuthenticationError: If not authenticated
        ApiError: If API request fails

    Note:
        Powers off ENTIRE system (all zones + DHW).
    """
    payload = {"power": power}
    await self._update_atw_unit(unit_id, payload)
```

#### 2.2 Zone 1 Temperature Control

```python
async def set_temperature_zone1(self, unit_id: str, temperature: float) -> None:
    """Set Zone 1 target temperature.

    Args:
        unit_id: ATW unit ID
        temperature: Target temp in Celsius (10-30°C)

    Raises:
        ValueError: If temperature out of safe range
        AuthenticationError: If not authenticated
        ApiError: If API request fails
    """
    # Validate against hardcoded safe defaults (never trust API ranges)
    if not ATW_TEMP_MIN_ZONE <= temperature <= ATW_TEMP_MAX_ZONE:
        raise ValueError(
            f"Zone temperature must be between {ATW_TEMP_MIN_ZONE} and "
            f"{ATW_TEMP_MAX_ZONE}°C, got {temperature}"
        )

    payload = {"setTemperatureZone1": temperature}
    await self._update_atw_unit(unit_id, payload)
```

#### 2.3 Zone 2 Temperature Control

```python
async def set_temperature_zone2(self, unit_id: str, temperature: float) -> None:
    """Set Zone 2 target temperature.

    Args:
        unit_id: ATW unit ID
        temperature: Target temp in Celsius (10-30°C)

    Raises:
        ValueError: If temperature out of safe range
        AuthenticationError: If not authenticated
        ApiError: If API request fails

    Note:
        Does NOT validate has_zone2 capability (coordinator's responsibility).
        API will return error if Zone 2 not available.
    """
    # Validate temperature range only (static validation)
    if not ATW_TEMP_MIN_ZONE <= temperature <= ATW_TEMP_MAX_ZONE:
        raise ValueError(
            f"Zone temperature must be between {ATW_TEMP_MIN_ZONE} and "
            f"{ATW_TEMP_MAX_ZONE}°C, got {temperature}"
        )

    payload = {"setTemperatureZone2": temperature}
    await self._update_atw_unit(unit_id, payload)
```

#### 2.4 Zone 1 Mode Control

```python
async def set_mode_zone1(self, unit_id: str, mode: str) -> None:
    """Set Zone 1 heating strategy.

    Args:
        unit_id: ATW unit ID
        mode: One of ATW_ZONE_MODES:
            - "HeatRoomTemperature" (thermostat control)
            - "HeatFlowTemperature" (direct flow temp)
            - "HeatCurve" (weather compensation)

    Raises:
        ValueError: If mode not in ATW_ZONE_MODES
        AuthenticationError: If not authenticated
        ApiError: If API request fails
    """
    # Validate mode using constants
    if mode not in ATW_ZONE_MODES:
        raise ValueError(
            f"Zone mode must be one of {ATW_ZONE_MODES}, got {mode}"
        )

    payload = {"operationModeZone1": mode}
    await self._update_atw_unit(unit_id, payload)
```

#### 2.5 Zone 2 Mode Control

```python
async def set_mode_zone2(self, unit_id: str, mode: str) -> None:
    """Set Zone 2 heating strategy.

    Args:
        unit_id: ATW unit ID
        mode: One of ATW_ZONE_MODES

    Raises:
        ValueError: If mode not in ATW_ZONE_MODES
        AuthenticationError: If not authenticated
        ApiError: If API request fails

    Note:
        Does NOT validate has_zone2 capability (coordinator's responsibility).
    """
    if mode not in ATW_ZONE_MODES:
        raise ValueError(
            f"Zone mode must be one of {ATW_ZONE_MODES}, got {mode}"
        )

    payload = {"operationModeZone2": mode}
    await self._update_atw_unit(unit_id, payload)
```

#### 2.6 DHW Temperature Control

```python
async def set_dhw_temperature(self, unit_id: str, temperature: float) -> None:
    """Set DHW tank target temperature.

    Args:
        unit_id: ATW unit ID
        temperature: Target temp in Celsius (40-60°C)

    Raises:
        ValueError: If temperature out of safe range
        AuthenticationError: If not authenticated
        ApiError: If API request fails
    """
    # Validate against hardcoded safe DHW range
    if not ATW_TEMP_MIN_TANK <= temperature <= ATW_TEMP_MAX_TANK:
        raise ValueError(
            f"DHW temperature must be between {ATW_TEMP_MIN_TANK} and "
            f"{ATW_TEMP_MAX_TANK}°C, got {temperature}"
        )

    payload = {"setTankWaterTemperature": temperature}
    await self._update_atw_unit(unit_id, payload)
```

#### 2.7 Forced DHW Mode Control

```python
async def set_forced_hot_water(self, unit_id: str, enabled: bool) -> None:
    """Enable/disable forced DHW priority mode.

    Args:
        unit_id: ATW unit ID
        enabled: True=DHW priority (suspends zone heating)
                False=Normal balanced operation

    Raises:
        AuthenticationError: If not authenticated
        ApiError: If API request fails

    Note:
        When enabled, 3-way valve prioritizes DHW tank heating.
        Zone heating is suspended until DHW reaches target.
    """
    payload = {"forcedHotWaterMode": enabled}
    await self._update_atw_unit(unit_id, payload)
```

#### 2.8 Standby Mode Control

```python
async def set_standby_mode(self, unit_id: str, standby: bool) -> None:
    """Enable/disable standby mode.

    Args:
        unit_id: ATW unit ID
        standby: True=standby (frost protection only)
                False=normal operation

    Raises:
        AuthenticationError: If not authenticated
        ApiError: If API request fails
    """
    payload = {"inStandbyMode": standby}
    await self._update_atw_unit(unit_id, payload)
```

**Required Imports (add to top of client.py):**
```python
from typing import Any  # For dict[str, Any] in helper

# Constants already imported:
from .const import (
    ATW_TEMP_MIN_ZONE,
    ATW_TEMP_MAX_ZONE,
    ATW_TEMP_MIN_TANK,
    ATW_TEMP_MAX_TANK,
    ATW_ZONE_MODES,
)
```

---

### Step 3: Add ATW Unit Caching to Coordinator

**File:** `custom_components/melcloudhome/coordinator.py`

#### 3.1 Add Cache Dictionaries

**Location:** Add after existing `self._units` declaration in `__init__()`

```python
# Existing A2A cache
self._unit_to_building: dict[str, Building] = {}
self._units: dict[str, AirToAirUnit] = {}

# ADD: A2W cache (same pattern)
self._atw_unit_to_building: dict[str, Building] = {}
self._atw_units: dict[str, AirToWaterUnit] = {}
```

#### 3.2 Update Cache Rebuild Logic

**Location:** Find `_async_rebuild_cache_from_user_context()` method

**Current code (for A2A only):**
```python
def _async_rebuild_cache_from_user_context(
    self, user_context: UserContext
) -> None:
    """Rebuild internal cache from user context."""
    # Clear existing cache
    self._units.clear()
    self._unit_to_building.clear()

    # Populate from user context
    for building in user_context.buildings:
        for unit in building.air_to_air_units:
            self._units[unit.id] = unit
            self._unit_to_building[unit.id] = building
```

**Add ATW caching (same pattern):**
```python
def _async_rebuild_cache_from_user_context(
    self, user_context: UserContext
) -> None:
    """Rebuild internal cache from user context."""
    # Clear existing cache
    self._units.clear()
    self._unit_to_building.clear()
    self._atw_units.clear()  # ADD
    self._atw_unit_to_building.clear()  # ADD

    # Populate from user context
    for building in user_context.buildings:
        # Cache A2A units (existing)
        for unit in building.air_to_air_units:
            self._units[unit.id] = unit
            self._unit_to_building[unit.id] = building

        # Cache A2W units (ADD)
        for atw_unit in building.air_to_water_units:
            self._atw_units[atw_unit.id] = atw_unit
            self._atw_unit_to_building[atw_unit.id] = building
```

#### 3.3 Add Lookup Method

**Location:** Add after existing `get_unit()` method

```python
def get_atw_unit(self, unit_id: str) -> AirToWaterUnit | None:
    """Get ATW unit by ID from cache.

    Args:
        unit_id: ATW unit ID

    Returns:
        Cached AirToWaterUnit if found, None otherwise
    """
    return self._atw_units.get(unit_id)
```

**Required Import:**
```python
from .api.models import AirToWaterUnit  # Add to imports at top
```

---

### Step 4: Add Coordinator Control Methods

**File:** `custom_components/melcloudhome/coordinator.py`

**Location:** Add after existing `async_set_vanes()` method (last ATA control method)

**Pattern:** All methods follow same template:
1. Get cached unit
2. Check if already in desired state (skip API call if so)
3. Log the operation
4. Execute with retry wrapper (handles session expiry)
5. **NO refresh call** (waits for next scheduled poll)

#### 4.1 Power Control

```python
async def async_set_power_atw(self, unit_id: str, power: bool) -> None:
    """Set ATW heat pump power with automatic session recovery.

    Args:
        unit_id: ATW unit ID
        power: True=ON, False=OFF
    """
    # Check cache - skip if already in desired state
    atw_unit = self.get_atw_unit(unit_id)
    if atw_unit and atw_unit.power == power:
        _LOGGER.debug(
            "Power already %s for ATW unit %s, skipping API call",
            "ON" if power else "OFF",
            unit_id[-8:],
        )
        return

    # Log the operation
    _LOGGER.info(
        "Setting power for ATW unit %s to %s",
        unit_id[-8:],
        "ON" if power else "OFF",
    )

    # Execute with automatic retry on session expiry
    await self._execute_with_retry(
        lambda: self.client.set_power_atw(unit_id, power),
        f"set_power_atw({unit_id}, {power})",
    )
```

#### 4.2 Zone 1 Temperature Control

```python
async def async_set_temperature_zone1(
    self, unit_id: str, temperature: float
) -> None:
    """Set Zone 1 target temperature.

    Args:
        unit_id: ATW unit ID
        temperature: Target temp in Celsius (10-30°C)
    """
    # Check cache - skip if already at target
    atw_unit = self.get_atw_unit(unit_id)
    if atw_unit and atw_unit.set_temperature_zone1 == temperature:
        _LOGGER.debug(
            "Zone 1 temperature already %s°C for ATW unit %s, skipping API call",
            temperature,
            unit_id[-8:],
        )
        return

    _LOGGER.info(
        "Setting Zone 1 temperature for ATW unit %s to %s°C",
        unit_id[-8:],
        temperature,
    )

    await self._execute_with_retry(
        lambda: self.client.set_temperature_zone1(unit_id, temperature),
        f"set_temperature_zone1({unit_id}, {temperature})",
    )
```

#### 4.3 Zone 2 Temperature Control (with capability check)

```python
async def async_set_temperature_zone2(
    self, unit_id: str, temperature: float
) -> None:
    """Set Zone 2 target temperature.

    Args:
        unit_id: ATW unit ID
        temperature: Target temp in Celsius (10-30°C)

    Raises:
        HomeAssistantError: If device doesn't have Zone 2
    """
    # Get cached unit
    atw_unit = self.get_atw_unit(unit_id)

    # Validate Zone 2 capability (using cached data - no extra API call)
    if atw_unit and not atw_unit.capabilities.has_zone2:
        raise HomeAssistantError(
            f"Device '{atw_unit.name}' does not have Zone 2"
        )

    # Check if already at target
    if atw_unit and atw_unit.set_temperature_zone2 == temperature:
        _LOGGER.debug(
            "Zone 2 temperature already %s°C for ATW unit %s, skipping API call",
            temperature,
            unit_id[-8:],
        )
        return

    _LOGGER.info(
        "Setting Zone 2 temperature for ATW unit %s to %s°C",
        unit_id[-8:],
        temperature,
    )

    await self._execute_with_retry(
        lambda: self.client.set_temperature_zone2(unit_id, temperature),
        f"set_temperature_zone2({unit_id}, {temperature})",
    )
```

#### 4.4 Zone 1 Mode Control

```python
async def async_set_mode_zone1(self, unit_id: str, mode: str) -> None:
    """Set Zone 1 heating strategy.

    Args:
        unit_id: ATW unit ID
        mode: One of ATW_ZONE_MODES
    """
    # Check cache - skip if already in desired mode
    atw_unit = self.get_atw_unit(unit_id)
    if atw_unit and atw_unit.operation_mode_zone1 == mode:
        _LOGGER.debug(
            "Zone 1 mode already %s for ATW unit %s, skipping API call",
            mode,
            unit_id[-8:],
        )
        return

    _LOGGER.info(
        "Setting Zone 1 mode for ATW unit %s to %s",
        unit_id[-8:],
        mode,
    )

    await self._execute_with_retry(
        lambda: self.client.set_mode_zone1(unit_id, mode),
        f"set_mode_zone1({unit_id}, {mode})",
    )
```

#### 4.5 Zone 2 Mode Control (with capability check)

```python
async def async_set_mode_zone2(self, unit_id: str, mode: str) -> None:
    """Set Zone 2 heating strategy.

    Args:
        unit_id: ATW unit ID
        mode: One of ATW_ZONE_MODES

    Raises:
        HomeAssistantError: If device doesn't have Zone 2
    """
    # Get cached unit and validate Zone 2
    atw_unit = self.get_atw_unit(unit_id)
    if atw_unit and not atw_unit.capabilities.has_zone2:
        raise HomeAssistantError(
            f"Device '{atw_unit.name}' does not have Zone 2"
        )

    # Check if already in desired mode
    if atw_unit and atw_unit.operation_mode_zone2 == mode:
        _LOGGER.debug(
            "Zone 2 mode already %s for ATW unit %s, skipping API call",
            mode,
            unit_id[-8:],
        )
        return

    _LOGGER.info(
        "Setting Zone 2 mode for ATW unit %s to %s",
        unit_id[-8:],
        mode,
    )

    await self._execute_with_retry(
        lambda: self.client.set_mode_zone2(unit_id, mode),
        f"set_mode_zone2({unit_id}, {mode})",
    )
```

#### 4.6 DHW Temperature Control

```python
async def async_set_dhw_temperature(
    self, unit_id: str, temperature: float
) -> None:
    """Set DHW tank target temperature.

    Args:
        unit_id: ATW unit ID
        temperature: Target temp in Celsius (40-60°C)
    """
    # Check cache - skip if already at target
    atw_unit = self.get_atw_unit(unit_id)
    if atw_unit and atw_unit.set_tank_water_temperature == temperature:
        _LOGGER.debug(
            "DHW temperature already %s°C for ATW unit %s, skipping API call",
            temperature,
            unit_id[-8:],
        )
        return

    _LOGGER.info(
        "Setting DHW temperature for ATW unit %s to %s°C",
        unit_id[-8:],
        temperature,
    )

    await self._execute_with_retry(
        lambda: self.client.set_dhw_temperature(unit_id, temperature),
        f"set_dhw_temperature({unit_id}, {temperature})",
    )
```

#### 4.7 Forced DHW Mode Control

```python
async def async_set_forced_hot_water(self, unit_id: str, enabled: bool) -> None:
    """Enable/disable forced DHW priority mode.

    Args:
        unit_id: ATW unit ID
        enabled: True=DHW priority, False=normal
    """
    # Check cache - skip if already in desired state
    atw_unit = self.get_atw_unit(unit_id)
    if atw_unit and atw_unit.forced_hot_water_mode == enabled:
        _LOGGER.debug(
            "Forced DHW already %s for ATW unit %s, skipping API call",
            enabled,
            unit_id[-8:],
        )
        return

    _LOGGER.info(
        "Setting forced DHW for ATW unit %s to %s",
        unit_id[-8:],
        enabled,
    )

    await self._execute_with_retry(
        lambda: self.client.set_forced_hot_water(unit_id, enabled),
        f"set_forced_hot_water({unit_id}, {enabled})",
    )
```

#### 4.8 Standby Mode Control

```python
async def async_set_standby_mode(self, unit_id: str, standby: bool) -> None:
    """Enable/disable standby mode.

    Args:
        unit_id: ATW unit ID
        standby: True=standby, False=normal
    """
    # Check cache - skip if already in desired state
    atw_unit = self.get_atw_unit(unit_id)
    if atw_unit and atw_unit.in_standby_mode == standby:
        _LOGGER.debug(
            "Standby mode already %s for ATW unit %s, skipping API call",
            standby,
            unit_id[-8:],
        )
        return

    _LOGGER.info(
        "Setting standby mode for ATW unit %s to %s",
        unit_id[-8:],
        standby,
    )

    await self._execute_with_retry(
        lambda: self.client.set_standby_mode(unit_id, standby),
        f"set_standby_mode({unit_id}, {standby})",
    )
```

**Required Imports:**
```python
from homeassistant.exceptions import HomeAssistantError  # Add to imports
```

---

### Step 5: Add Test Fixtures for ATW Unit IDs

**File:** `tests/conftest.py`

**Location:** Add after existing `living_room_unit_id` fixture

```python
@pytest.fixture
def atw_unit_id_zone1() -> str:
    """ID of ATW unit with single zone for testing.

    Note: Replace with actual ATW unit ID from your MELCloud account.
    """
    return "REPLACE-WITH-ACTUAL-ATW-UNIT-ID"


@pytest.fixture
def atw_unit_id_zone2() -> str:
    """ID of ATW unit with two zones for testing.

    Note: Replace with actual 2-zone ATW unit ID from your account.
    """
    return "REPLACE-WITH-ACTUAL-2ZONE-ATW-UNIT-ID"
```

---

### Step 6: Write Control Method Tests

**File:** `tests/api/test_atw_control.py` (NEW)

**Pattern:** Follows ATA test pattern (Set → Wait → Fetch → Verify)

```python
"""Tests for ATW API control methods.

Uses pytest-vcr to record/replay live API interactions.
First run records to cassettes, subsequent runs replay.
"""

import asyncio

import pytest

from custom_components.melcloudhome.api.client import MELCloudHomeClient


# =============================================================================
# Power Control Tests
# =============================================================================


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_set_power_atw_on(
    authenticated_client: MELCloudHomeClient,
    atw_unit_id_zone1: str,
) -> None:
    """Test turning ATW heat pump on."""
    # Set power on
    await authenticated_client.set_power_atw(atw_unit_id_zone1, True)

    # Wait for state propagation
    await asyncio.sleep(2)

    # Fetch fresh state
    ctx = await authenticated_client.get_user_context()
    unit = ctx.get_air_to_water_unit_by_id(atw_unit_id_zone1)

    # Verify
    assert unit is not None
    assert unit.power is True


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_set_power_atw_off(
    authenticated_client: MELCloudHomeClient,
    atw_unit_id_zone1: str,
) -> None:
    """Test turning ATW heat pump off."""
    await authenticated_client.set_power_atw(atw_unit_id_zone1, False)
    await asyncio.sleep(2)

    ctx = await authenticated_client.get_user_context()
    unit = ctx.get_air_to_water_unit_by_id(atw_unit_id_zone1)

    assert unit is not None
    assert unit.power is False


# =============================================================================
# Zone 1 Temperature Tests
# =============================================================================


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_set_temperature_zone1(
    authenticated_client: MELCloudHomeClient,
    atw_unit_id_zone1: str,
) -> None:
    """Test setting Zone 1 target temperature."""
    target_temp = 22.0

    await authenticated_client.set_temperature_zone1(atw_unit_id_zone1, target_temp)
    await asyncio.sleep(2)

    ctx = await authenticated_client.get_user_context()
    unit = ctx.get_air_to_water_unit_by_id(atw_unit_id_zone1)

    assert unit is not None
    assert unit.set_temperature_zone1 == target_temp


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_set_temperature_zone1_half_degree(
    authenticated_client: MELCloudHomeClient,
    atw_unit_id_zone1: str,
) -> None:
    """Test setting Zone 1 temperature with 0.5° increment."""
    target_temp = 21.5

    await authenticated_client.set_temperature_zone1(atw_unit_id_zone1, target_temp)
    await asyncio.sleep(2)

    ctx = await authenticated_client.get_user_context()
    unit = ctx.get_air_to_water_unit_by_id(atw_unit_id_zone1)

    assert unit is not None
    assert unit.set_temperature_zone1 == target_temp


# =============================================================================
# Zone 2 Temperature Tests
# =============================================================================


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_set_temperature_zone2(
    authenticated_client: MELCloudHomeClient,
    atw_unit_id_zone2: str,
) -> None:
    """Test setting Zone 2 target temperature."""
    target_temp = 20.0

    await authenticated_client.set_temperature_zone2(atw_unit_id_zone2, target_temp)
    await asyncio.sleep(2)

    ctx = await authenticated_client.get_user_context()
    unit = ctx.get_air_to_water_unit_by_id(atw_unit_id_zone2)

    assert unit is not None
    assert unit.set_temperature_zone2 == target_temp


# =============================================================================
# Zone Mode Tests
# =============================================================================


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_set_mode_zone1_room_temperature(
    authenticated_client: MELCloudHomeClient,
    atw_unit_id_zone1: str,
) -> None:
    """Test setting Zone 1 to thermostat control mode."""
    mode = "HeatRoomTemperature"

    await authenticated_client.set_mode_zone1(atw_unit_id_zone1, mode)
    await asyncio.sleep(2)

    ctx = await authenticated_client.get_user_context()
    unit = ctx.get_air_to_water_unit_by_id(atw_unit_id_zone1)

    assert unit is not None
    assert unit.operation_mode_zone1 == mode


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_set_mode_zone1_heat_curve(
    authenticated_client: MELCloudHomeClient,
    atw_unit_id_zone1: str,
) -> None:
    """Test setting Zone 1 to weather compensation mode."""
    mode = "HeatCurve"

    await authenticated_client.set_mode_zone1(atw_unit_id_zone1, mode)
    await asyncio.sleep(2)

    ctx = await authenticated_client.get_user_context()
    unit = ctx.get_air_to_water_unit_by_id(atw_unit_id_zone1)

    assert unit is not None
    assert unit.operation_mode_zone1 == mode


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_set_mode_zone2_room_temperature(
    authenticated_client: MELCloudHomeClient,
    atw_unit_id_zone2: str,
) -> None:
    """Test setting Zone 2 to thermostat control mode."""
    mode = "HeatRoomTemperature"

    await authenticated_client.set_mode_zone2(atw_unit_id_zone2, mode)
    await asyncio.sleep(2)

    ctx = await authenticated_client.get_user_context()
    unit = ctx.get_air_to_water_unit_by_id(atw_unit_id_zone2)

    assert unit is not None
    assert unit.operation_mode_zone2 == mode


# =============================================================================
# DHW Control Tests
# =============================================================================


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_set_dhw_temperature(
    authenticated_client: MELCloudHomeClient,
    atw_unit_id_zone1: str,
) -> None:
    """Test setting DHW tank target temperature."""
    target_temp = 50.0

    await authenticated_client.set_dhw_temperature(atw_unit_id_zone1, target_temp)
    await asyncio.sleep(2)

    ctx = await authenticated_client.get_user_context()
    unit = ctx.get_air_to_water_unit_by_id(atw_unit_id_zone1)

    assert unit is not None
    assert unit.set_tank_water_temperature == target_temp


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_set_forced_hot_water_enable(
    authenticated_client: MELCloudHomeClient,
    atw_unit_id_zone1: str,
) -> None:
    """Test enabling forced DHW priority mode."""
    await authenticated_client.set_forced_hot_water(atw_unit_id_zone1, True)
    await asyncio.sleep(2)

    ctx = await authenticated_client.get_user_context()
    unit = ctx.get_air_to_water_unit_by_id(atw_unit_id_zone1)

    assert unit is not None
    assert unit.forced_hot_water_mode is True


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_set_forced_hot_water_disable(
    authenticated_client: MELCloudHomeClient,
    atw_unit_id_zone1: str,
) -> None:
    """Test disabling forced DHW mode."""
    await authenticated_client.set_forced_hot_water(atw_unit_id_zone1, False)
    await asyncio.sleep(2)

    ctx = await authenticated_client.get_user_context()
    unit = ctx.get_air_to_water_unit_by_id(atw_unit_id_zone1)

    assert unit is not None
    assert unit.forced_hot_water_mode is False


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_set_standby_mode(
    authenticated_client: MELCloudHomeClient,
    atw_unit_id_zone1: str,
) -> None:
    """Test enabling standby mode."""
    await authenticated_client.set_standby_mode(atw_unit_id_zone1, True)
    await asyncio.sleep(2)

    ctx = await authenticated_client.get_user_context()
    unit = ctx.get_air_to_water_unit_by_id(atw_unit_id_zone1)

    assert unit is not None
    assert unit.in_standby_mode is True


# =============================================================================
# Validation Tests (No VCR - Fast Unit Tests)
# =============================================================================


@pytest.mark.asyncio
async def test_set_temperature_zone1_below_minimum() -> None:
    """Zone 1 temperature below 10°C should raise ValueError."""
    client = MELCloudHomeClient()

    with pytest.raises(ValueError, match="must be between 10"):
        await client.set_temperature_zone1("unit-id", 9.5)


@pytest.mark.asyncio
async def test_set_temperature_zone1_above_maximum() -> None:
    """Zone 1 temperature above 30°C should raise ValueError."""
    client = MELCloudHomeClient()

    with pytest.raises(ValueError, match="must be between"):
        await client.set_temperature_zone1("unit-id", 35.0)


@pytest.mark.asyncio
async def test_set_temperature_zone2_out_of_range() -> None:
    """Zone 2 temperature out of range should raise ValueError."""
    client = MELCloudHomeClient()

    with pytest.raises(ValueError, match="must be between"):
        await client.set_temperature_zone2("unit-id", 5.0)


@pytest.mark.asyncio
async def test_set_dhw_temperature_below_minimum() -> None:
    """DHW temperature below 40°C should raise ValueError."""
    client = MELCloudHomeClient()

    with pytest.raises(ValueError, match="must be between 40"):
        await client.set_dhw_temperature("unit-id", 35.0)


@pytest.mark.asyncio
async def test_set_dhw_temperature_above_maximum() -> None:
    """DHW temperature above 60°C should raise ValueError."""
    client = MELCloudHomeClient()

    with pytest.raises(ValueError, match="must be between"):
        await client.set_dhw_temperature("unit-id", 70.0)


@pytest.mark.asyncio
async def test_set_mode_zone1_invalid() -> None:
    """Invalid Zone 1 mode should raise ValueError."""
    client = MELCloudHomeClient()

    with pytest.raises(ValueError, match="must be one of"):
        await client.set_mode_zone1("unit-id", "InvalidMode")


@pytest.mark.asyncio
async def test_set_mode_zone2_invalid() -> None:
    """Invalid Zone 2 mode should raise ValueError."""
    client = MELCloudHomeClient()

    with pytest.raises(ValueError, match="must be one of"):
        await client.set_mode_zone2("unit-id", "InvalidMode")
```

**Test Count:** 18 tests
- **11 VCR tests:** Test actual API control operations with live recording
- **7 validation tests:** Fast unit tests for input validation

---

### Step 7: Generate VCR Cassettes (Live Recording)

**First-Time Setup:**

```bash
# 1. Set credentials for live API access
export MELCLOUD_USER="your.email@example.com"
export MELCLOUD_PASSWORD="your_password"

# 2. Run tests - VCR will record live API calls
pytest tests/api/test_atw_control.py -v

# 3. Check cassettes were created
ls tests/api/cassettes/test_*atw*.yaml
```

**What Happens:**
- VCR intercepts HTTP calls
- Records to `tests/api/cassettes/test_set_power_atw_on.yaml`, etc.
- Scrubs sensitive data (emails, passwords, device names)
- Each test gets its own cassette file

**Subsequent Runs:**
```bash
# No credentials needed - VCR replays from cassettes
pytest tests/api/test_atw_control.py -v
```

**If Tests Fail:**
- Check that ATW unit IDs in fixtures are correct
- Verify account has ATW devices
- Check cassettes for errors (`status: 4xx` or `5xx`)

---

### Step 8: Run Quality Checks

```bash
# Run ATW control tests
pytest tests/api/test_atw_control.py -v

# Run all API tests (verify no regressions)
pytest tests/api/ -v

# Type check
make type-check

# Lint
make lint

# All checks together
make all
```

**Expected results:**
- ✅ 18 new tests pass
- ✅ All existing tests still pass
- ✅ No type errors
- ✅ No lint errors

---

### Step 9: Manual Validation (Optional)

Create validation script for manual testing against mock server:

**File:** `tools/validate_atw_control.py` (NEW)

```python
"""Manual validation script for ATW control methods.

Tests against mock server to validate 3-way valve simulation.
"""

import asyncio
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from custom_components.melcloudhome.api.client import MELCloudHomeClient


async def main() -> None:
    """Test ATW control methods against mock server."""
    # Connect to mock server
    client = MELCloudHomeClient("http://localhost:8080")

    try:
        # Login
        print("Logging in...")
        await client.login("test@example.com", "password")

        # Get initial state
        print("\n=== Initial State ===")
        ctx = await client.get_user_context()
        unit = ctx.buildings[0].air_to_water_units[0]
        print(f"Power: {unit.power}")
        print(f"Zone 1 target: {unit.set_temperature_zone1}°C")
        print(f"DHW target: {unit.set_tank_water_temperature}°C")
        print(f"Forced DHW: {unit.forced_hot_water_mode}")
        print(f"Operation status: {unit.operation_status}")

        # Test power control
        print("\n=== Testing Power Control ===")
        await client.set_power_atw(unit.id, False)
        await asyncio.sleep(1)

        ctx = await client.get_user_context()
        unit = ctx.get_air_to_water_unit_by_id(unit.id)
        print(f"After power off: {unit.power}")
        assert unit.power is False, "Power should be OFF"

        await client.set_power_atw(unit.id, True)
        await asyncio.sleep(1)

        ctx = await client.get_user_context()
        unit = ctx.get_air_to_water_unit_by_id(unit.id)
        print(f"After power on: {unit.power}")
        assert unit.power is True, "Power should be ON"

        # Test zone temperature
        print("\n=== Testing Zone 1 Temperature ===")
        await client.set_temperature_zone1(unit.id, 23.0)
        await asyncio.sleep(1)

        ctx = await client.get_user_context()
        unit = ctx.get_air_to_water_unit_by_id(unit.id)
        print(f"After set 23°C: {unit.set_temperature_zone1}°C")
        assert unit.set_temperature_zone1 == 23.0

        # Test DHW temperature
        print("\n=== Testing DHW Temperature ===")
        await client.set_dhw_temperature(unit.id, 55.0)
        await asyncio.sleep(1)

        ctx = await client.get_user_context()
        unit = ctx.get_air_to_water_unit_by_id(unit.id)
        print(f"After set 55°C: {unit.set_tank_water_temperature}°C")
        assert unit.set_tank_water_temperature == 55.0

        # Test forced DHW mode
        print("\n=== Testing Forced DHW Mode ===")
        await client.set_forced_hot_water(unit.id, True)
        await asyncio.sleep(1)

        ctx = await client.get_user_context()
        unit = ctx.get_air_to_water_unit_by_id(unit.id)
        print(f"After enable: forced={unit.forced_hot_water_mode}, status={unit.operation_status}")
        assert unit.forced_hot_water_mode is True

        # Test zone mode
        print("\n=== Testing Zone 1 Mode ===")
        await client.set_mode_zone1(unit.id, "HeatRoomTemperature")
        await asyncio.sleep(1)

        ctx = await client.get_user_context()
        unit = ctx.get_air_to_water_unit_by_id(unit.id)
        print(f"After set mode: {unit.operation_mode_zone1}")
        assert unit.operation_mode_zone1 == "HeatRoomTemperature"

        print("\n✅ All validations passed!")

    finally:
        await client.close()


if __name__ == "__main__":
    print("Starting mock server validation...")
    print("Ensure mock server is running: python tools/mock_melcloud_server.py\n")
    asyncio.run(main())
```

**Usage:**
```bash
# Terminal 1: Start mock server
python tools/mock_melcloud_server.py

# Terminal 2: Run validation
python tools/validate_atw_control.py
```

**Watch mock server logs** for:
- PUT requests to `/api/atwunit/{id}`
- Payload structure (correct fields)
- 3-way valve status updates

---

## Success Criteria

### Code Quality

- [ ] 1 helper method added to `MELCloudHomeClient` (`_update_atw_unit`)
- [ ] 9 control methods added to `MELCloudHomeClient`
- [ ] All client methods return `None` (not `AirToWaterUnit`)
- [ ] All client methods use constants from `const.py`
- [ ] All client methods validate inputs before API calls
- [ ] 2 cache dictionaries added to coordinator (`_atw_units`, `_atw_unit_to_building`)
- [ ] 1 lookup method added to coordinator (`get_atw_unit`)
- [ ] 8 coordinator methods added with correct pattern:
  - [ ] Check cache first (skip if already in desired state)
  - [ ] Log the operation (debug for skip, info for execution)
  - [ ] Use `_execute_with_retry()` wrapper (session recovery)
  - [ ] **NO** `async_request_refresh()` call (waits for scheduled poll)
- [ ] Zone 2 methods validate `has_zone2` capability in coordinator (not client)
- [ ] All methods have docstrings with type annotations
- [ ] No type errors (mypy passes)
- [ ] No lint errors (ruff passes)

### Tests

- [ ] 18 control method tests created (11 VCR + 7 validation)
- [ ] All tests follow pattern: Set → Wait → Fetch → Verify
- [ ] VCR cassettes generated for all control operations
- [ ] Validation tests for error cases (out of range, invalid modes)
- [ ] All existing tests still pass
- [ ] 2 ATW unit ID fixtures added to `conftest.py`

### Manual Validation (Optional)

- [ ] Validation script created (`tools/validate_atw_control.py`)
- [ ] Power control verified against mock server
- [ ] Zone temperature control verified (Zone 1 & 2)
- [ ] Zone mode control verified (all 3 modes)
- [ ] DHW temperature control verified
- [ ] Forced DHW mode verified (3-way valve status updates correctly)
- [ ] Standby mode verified
- [ ] Mock server logs show correct PUT request payloads

---

## Files Modified

| File | Changes | Lines Added |
|------|---------|-------------|
| `custom_components/melcloudhome/api/client.py` | Add 1 helper + 9 control methods | ~180 |
| `custom_components/melcloudhome/coordinator.py` | Add caching + 8 control methods | ~200 |
| `tests/conftest.py` | Add 2 ATW unit ID fixtures | ~15 |
| `tests/api/test_atw_control.py` (NEW) | Create 18 tests | ~350 |
| `tools/validate_atw_control.py` (NEW) | Manual validation script | ~120 |
| `tests/api/cassettes/*.yaml` (AUTO) | 11 VCR cassettes | Auto-generated |

**Total:** ~865 lines of production code + tests

---

## Key Design Decisions

### 1. Return Type: `None` (Matches ATA)

**Decision:** Client methods return `None`, not `AirToWaterUnit`

**Rationale:**
- Matches established ATA pattern
- Avoids race conditions (returned state might be stale)
- Clear separation: control methods don't fetch state
- Coordinator polling handles state updates

### 2. Helper Method: `_update_atw_unit()` (DRY Improvement)

**Decision:** Use helper to build sparse payloads (differs from ATA)

**Rationale:**
- ATW has 12+ control fields (vs ATA's 8)
- Prevents copy-paste errors in payload building
- Single source of truth for payload structure
- ATA could benefit from same pattern (see Appendix A)

**Trade-off:** Slight deviation from ATA, but improves maintainability

### 3. Zone 2 Validation: Coordinator Only (No Client Fetch)

**Decision:** Client doesn't validate `has_zone2`; coordinator checks cached capability

**Rationale:**
- Client methods are fast (no pre-fetch)
- Coordinator already has cached device data (no extra API call)
- Matches ATA pattern (client doesn't fetch before control)
- Better error message (can include device name from cache)

### 4. No Refresh After Control (Matches ATA)

**Decision:** Coordinator methods don't call `async_request_refresh()`

**Rationale:**
- Avoids race conditions (server may not have updated yet)
- Next scheduled poll (60s) gets fresh state
- Prevents duplicate API calls
- HVAC systems don't need instant state updates

### 5. Cache Check & Deduplication (Matches ATA)

**Decision:** All coordinator methods check cache and skip if value already set

**Rationale:**
- Prevents redundant API calls
- Reduces network traffic
- Faster response when value already correct
- Critical for UI sliders (many intermediate values)

---

## Testing Strategy

### VCR Cassette Recording (Automatic)

**First Run (Recording):**
1. Provide credentials via environment variables
2. Run tests with `@pytest.mark.vcr()` decorator
3. VCR makes live API calls
4. VCR records requests/responses to cassette files
5. VCR scrubs sensitive data automatically

**Subsequent Runs (Replay):**
1. No credentials needed
2. VCR replays from cassettes (instant, no network)
3. Tests verify same behavior

**Cassette Format:** YAML files in `tests/api/cassettes/`

### Test Coverage

**VCR Tests (11):**
- Power on/off (2 tests)
- Zone 1 temperature (2 tests - normal + half-degree)
- Zone 2 temperature (1 test)
- Zone modes (3 tests - Zone 1 room/curve, Zone 2 room)
- DHW temperature (1 test)
- Forced DHW enable/disable (2 tests)
- Standby mode (1 test)

**Validation Tests (7):**
- Zone 1/2 temperature out of range (3 tests)
- DHW temperature out of range (2 tests)
- Invalid zone modes (2 tests)

**Total:** 18 tests covering all control paths

---

## Implementation Checklist

### Phase 2.1: Client Methods (API Layer)

- [ ] Add `from typing import Any` import
- [ ] Add ATW constants imports from `const.py`
- [ ] Add `_update_atw_unit()` helper method
- [ ] Add `set_power_atw()` method
- [ ] Add `set_temperature_zone1()` method
- [ ] Add `set_temperature_zone2()` method
- [ ] Add `set_mode_zone1()` method
- [ ] Add `set_mode_zone2()` method
- [ ] Add `set_dhw_temperature()` method
- [ ] Add `set_forced_hot_water()` method
- [ ] Add `set_standby_mode()` method
- [ ] Verify all methods return `None`
- [ ] Verify all methods use constants (not hardcoded strings)
- [ ] Verify all validations raise `ValueError`

### Phase 2.2: Coordinator Methods (Integration Layer)

- [ ] Add `from homeassistant.exceptions import HomeAssistantError` import
- [ ] Add `from .api.models import AirToWaterUnit` import
- [ ] Add `_atw_units` cache dictionary to `__init__()`
- [ ] Add `_atw_unit_to_building` cache dictionary to `__init__()`
- [ ] Update `_async_rebuild_cache_from_user_context()` to cache ATW units
- [ ] Add `get_atw_unit()` lookup method
- [ ] Add `async_set_power_atw()` with cache check + retry wrapper
- [ ] Add `async_set_temperature_zone1()` with cache check + retry wrapper
- [ ] Add `async_set_temperature_zone2()` with Zone 2 validation + cache check
- [ ] Add `async_set_mode_zone1()` with cache check + retry wrapper
- [ ] Add `async_set_mode_zone2()` with Zone 2 validation + cache check
- [ ] Add `async_set_dhw_temperature()` with cache check + retry wrapper
- [ ] Add `async_set_forced_hot_water()` with cache check + retry wrapper
- [ ] Add `async_set_standby_mode()` with cache check + retry wrapper
- [ ] Verify NO methods call `async_request_refresh()`
- [ ] Verify ALL methods use `_execute_with_retry()`
- [ ] Verify ALL methods check cache first

### Phase 2.3: Tests

- [ ] Add 2 ATW unit ID fixtures to `tests/conftest.py`
- [ ] Create `tests/api/test_atw_control.py`
- [ ] Add 11 VCR control tests
- [ ] Add 7 validation tests
- [ ] Verify all VCR tests follow: Set → Wait → Fetch → Verify
- [ ] Verify validation tests raise `ValueError`
- [ ] Run tests to generate VCR cassettes
- [ ] Commit cassettes to git

### Phase 2.4: Validation (Optional)

- [ ] Create `tools/validate_atw_control.py` script
- [ ] Test against mock server
- [ ] Verify 3-way valve simulation works
- [ ] Verify all control operations succeed

---

## Common Pitfalls

### ❌ Don't Return Values from Client Methods

```python
# WRONG
async def set_power_atw(...) -> AirToWaterUnit:
    return await self._update_atw_unit(...)

# RIGHT
async def set_power_atw(...) -> None:
    await self._update_atw_unit(...)
```

### ❌ Don't Call Refresh in Coordinator

```python
# WRONG
async def async_set_power_atw(...):
    await self.client.set_power_atw(...)
    await self.async_request_refresh()  # NO!

# RIGHT
async def async_set_power_atw(...):
    # ... cache check ...
    await self._execute_with_retry(...)
    # NO refresh - next scheduled poll handles it
```

### ❌ Don't Validate Device Exists in Client

```python
# WRONG (extra API call)
async def set_temperature_zone2(...):
    device = await self.get_atw_unit(unit_id)  # NO!
    if not device.capabilities.has_zone2:
        raise ValueError(...)

# RIGHT (client just validates input, coordinator validates capability)
async def set_temperature_zone2(...):
    if not 10 <= temperature <= 30:
        raise ValueError(...)
    await self._update_atw_unit(...)
```

### ❌ Don't Skip Cache Check in Coordinator

```python
# WRONG (redundant API calls)
async def async_set_temperature_zone1(...):
    await self._execute_with_retry(...)  # Always calls API

# RIGHT (skip if already set)
async def async_set_temperature_zone1(...):
    atw_unit = self.get_atw_unit(unit_id)
    if atw_unit and atw_unit.set_temperature_zone1 == temperature:
        return  # Skip API call
    await self._execute_with_retry(...)
```

### ❌ Don't Forget Wait in Tests

```python
# WRONG (state not propagated yet)
await client.set_power_atw(unit_id, True)
unit = await client.get_user_context()  # Too fast!

# RIGHT (wait for propagation)
await client.set_power_atw(unit_id, True)
await asyncio.sleep(2)  # Wait
ctx = await client.get_user_context()
```

---

## Quick Reference: Method Signatures

### Client Methods (api/client.py)

```python
# Helper
async def _update_atw_unit(self, unit_id: str, payload: dict[str, Any]) -> None

# Control
async def set_power_atw(self, unit_id: str, power: bool) -> None
async def set_temperature_zone1(self, unit_id: str, temperature: float) -> None
async def set_temperature_zone2(self, unit_id: str, temperature: float) -> None
async def set_mode_zone1(self, unit_id: str, mode: str) -> None
async def set_mode_zone2(self, unit_id: str, mode: str) -> None
async def set_dhw_temperature(self, unit_id: str, temperature: float) -> None
async def set_forced_hot_water(self, unit_id: str, enabled: bool) -> None
async def set_standby_mode(self, unit_id: str, standby: bool) -> None
```

### Coordinator Methods (coordinator.py)

```python
# Lookup
def get_atw_unit(self, unit_id: str) -> AirToWaterUnit | None

# Control (all follow same pattern)
async def async_set_power_atw(self, unit_id: str, power: bool) -> None
async def async_set_temperature_zone1(self, unit_id: str, temperature: float) -> None
async def async_set_temperature_zone2(self, unit_id: str, temperature: float) -> None
async def async_set_mode_zone1(self, unit_id: str, mode: str) -> None
async def async_set_mode_zone2(self, unit_id: str, mode: str) -> None
async def async_set_dhw_temperature(self, unit_id: str, temperature: float) -> None
async def async_set_forced_hot_water(self, unit_id: str, enabled: bool) -> None
async def async_set_standby_mode(self, unit_id: str, standby: bool) -> None
```

---

## Next Steps After Phase 2

Once Phase 2 is complete and all tests pass:

1. **Optional: Clean up UI controls doc** (1-2 hours)
   - Reduce `atw-ui-controls-best-practices.md` from 986 → ~400 lines
   - Remove redundancy
   - Add coordinator integration examples

2. **Phase 3: Entity Platforms** (5-8 hours)
   - Create `water_heater.py` platform
   - Update `climate.py` for ATW zones
   - Update `sensor.py` and `binary_sensor.py` for ATW
   - Update `__init__.py` to register water_heater platform
   - Write integration tests
   - Deploy and test

3. **Phase 4: Production Deployment**
   - Test with real ATW hardware
   - Create PR with changelog
   - Merge and release

**Total time to working UI:** 7-11 hours

---

## Appendix A: ATA Refactoring Opportunities

**Note:** These are identified for consistency but NOT required for Phase 2.

### Opportunity 1: Extract Payload Builder Helper

**Current ATA Pattern:** Each method builds payload inline (duplicate code):

```python
# set_temperature (lines 209-246)
payload = {
    "power": None,
    "operationMode": None,
    "setFanSpeed": None,
    "vaneHorizontalDirection": None,
    "vaneVerticalDirection": None,
    "setTemperature": temperature,
    "temperatureIncrementOverride": None,
    "inStandbyMode": None,
}

# set_mode (lines 248-281)
payload = {
    "power": None,
    "operationMode": mode,
    "setFanSpeed": None,
    "vaneHorizontalDirection": None,
    "vaneVerticalDirection": None,
    "setTemperature": None,
    "temperatureIncrementOverride": None,
    "inStandbyMode": None,
}
```

**Potential Refactor:** Add `_update_unit()` helper (same as ATW's `_update_atw_unit()`)

```python
async def _update_unit(self, unit_id: str, payload: dict[str, Any]) -> None:
    """Send sparse update to ATA unit."""
    full_payload = {
        "power": None,
        "operationMode": None,
        "setFanSpeed": None,
        "vaneHorizontalDirection": None,
        "vaneVerticalDirection": None,
        "setTemperature": None,
        "temperatureIncrementOverride": None,
        "inStandbyMode": None,
        **payload,
    }
    await self._api_request("PUT", f"/api/ataunit/{unit_id}", json=full_payload)
```

**Then methods become:**
```python
async def set_temperature(self, unit_id: str, temperature: float) -> None:
    # ... validation ...
    await self._update_unit(unit_id, {"setTemperature": temperature})
```

**Benefits:**
- DRY - payload structure in one place
- Easier to add new fields
- Reduces chance of typos/omissions

**Impact:** Would update 6 ATA control methods

---

### Opportunity 2: Extract Common Validation Pattern

**Current ATA Pattern:** Temperature validation duplicated:

```python
# In set_temperature
if not TEMP_MIN_HEAT <= temperature <= TEMP_MAX_HEAT:
    raise ValueError(...)

if (temperature / TEMP_STEP) % 1 != 0:
    raise ValueError(...)
```

**Potential Refactor:** Extract validation helpers:

```python
def _validate_temperature(
    value: float,
    min_temp: float,
    max_temp: float,
    step: float,
    name: str = "Temperature"
) -> None:
    """Validate temperature is in range and valid increment."""
    if not min_temp <= value <= max_temp:
        raise ValueError(f"{name} must be between {min_temp} and {max_temp}°C")

    if (value / step) % 1 != 0:
        raise ValueError(f"{name} must be in {step}° increments")

def _validate_enum(value: str, valid_values: set[str], name: str) -> None:
    """Validate value is in allowed set."""
    if value not in valid_values:
        raise ValueError(f"{name} must be one of {valid_values}, got {value}")
```

**Then:**
```python
async def set_temperature(self, unit_id: str, temperature: float) -> None:
    _validate_temperature(temperature, TEMP_MIN_HEAT, TEMP_MAX_HEAT, TEMP_STEP)
    await self._update_unit(unit_id, {"setTemperature": temperature})
```

**Benefits:**
- Consistent error messages
- Easier to add validation rules
- Reusable across ATA and ATW

**Impact:** Would update validation in 8+ methods

---

### Opportunity 3: Unify Constants Naming

**Current Inconsistency:**

```python
# ATA constants (const.py)
TEMP_MIN_HEAT = 10.0
TEMP_MAX_HEAT = 31.0

# ATW constants (const.py)
ATW_TEMP_MIN_ZONE = 10.0
ATW_TEMP_MAX_ZONE = 30.0
```

**Potential Refactor:** Unified naming scheme:

```python
# ATA
ATA_TEMP_MIN = 10.0
ATA_TEMP_MAX_HEAT = 31.0
ATA_TEMP_MAX_COOL = 31.0

# ATW
ATW_TEMP_MIN_ZONE = 10.0
ATW_TEMP_MAX_ZONE = 30.0
ATW_TEMP_MIN_TANK = 40.0
ATW_TEMP_MAX_TANK = 60.0
```

**Benefits:**
- Clearer which constants belong to which system
- Easier to grep/search
- Reduces confusion

**Impact:** Would update constant names across codebase

---

### Summary: Refactoring Opportunities

**All three opportunities improve DRY and consistency** but are NOT required for Phase 2:

1. **Payload builder helper** - High value, low risk
2. **Validation helpers** - Medium value, medium risk (changes error messages)
3. **Constants renaming** - Low value, high churn (many files affected)

**Recommendation:** Consider #1 (payload helper) for ATA in future refactor. Skip #2 and #3 unless broader refactoring planned.

**For Phase 2:** ATW uses these patterns (helper, validation). If ATA is refactored later to match, even better.

---

## Appendix B: Strategic Rationale

### Why Phase 2 Before Phase 3?

**Phase 3 (UI entities) is blocked** without Phase 2 (API control methods):
- Water heater entity needs `async_set_dhw_temperature()`, `async_set_forced_hot_water()`, etc.
- Climate entity needs `async_set_temperature_zone1()`, `async_set_mode_zone1()`, etc.
- Attempting Phase 3 first = immediate blockers

**Critical path:**
```
Phase 2 (API Control) → Phase 3 (Entities) → Working UI
```

**Time to working UI:** 7-11 hours (2-3 Phase 2 + 5-8 Phase 3)

### Why Not Documentation First?

Current `atw-ui-controls-best-practices.md` has issues (986 lines, 50% redundancy) but:
- Functional enough to guide Phase 3 implementation
- Not blocking
- Can be improved anytime (or never)
- Cleaning it first saves minimal time

**Verdict:** Focus on implementation momentum, clean docs later if needed

---

## Appendix C: Pattern Comparison

### Client Method Pattern

| Aspect | ATA Pattern | ATW Plan v2 | Match? |
|--------|-------------|-------------|--------|
| Return type | `None` | `None` | ✅ |
| Validation | Input validation only | Same | ✅ |
| Device fetch | No pre-fetch | No pre-fetch | ✅ |
| Payload building | Inline (duplicated) | Helper (DRY) | ⚠️ Improved |
| Constants usage | Yes | Yes | ✅ |
| Error handling | ValueError for validation | Same | ✅ |

### Coordinator Method Pattern

| Aspect | ATA Pattern | ATW Plan v2 | Match? |
|--------|-------------|-------------|--------|
| Cache check | Yes (skip if already set) | Yes | ✅ |
| Logging | Debug skip, info execution | Same | ✅ |
| Retry wrapper | `_execute_with_retry()` | Same | ✅ |
| Refresh call | **No** refresh | **No** refresh | ✅ |
| Return type | `None` | `None` | ✅ |
| Zone 2 validation | N/A (A2A single zone) | In coordinator (cached) | ✅ |

### Test Pattern

| Aspect | ATA Pattern | ATW Plan v2 | Match? |
|--------|-------------|-------------|--------|
| VCR decorator | `@pytest.mark.vcr()` | Same | ✅ |
| Test flow | Set → Wait → Fetch → Verify | Same | ✅ |
| Wait time | 2 seconds | 2 seconds | ✅ |
| Validation tests | Separate (no VCR) | Same | ✅ |
| Fixture usage | Unit ID fixtures | Same | ✅ |

**Conclusion:** Plan v2 matches ATA patterns with only one intentional improvement (helper method for DRY).

---

## End of Plan

**Ready for implementation:** All patterns verified, prerequisites met, success criteria defined.

**Estimated effort:** 2-3 hours

**Next:** Begin Step 1 (add helper to client.py) when ready.
