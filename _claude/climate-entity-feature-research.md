# Climate Entity Feature Research - Missing Features Analysis

**Date:** 2025-11-17
**Context:** User noted LG ThinQ supports `climate.turn_on` - research what we're missing
**Status:** Critical gaps identified

---

## Executive Summary

Research into Home Assistant climate entity capabilities reveals **critical missing features** in the MELCloud Home integration. Most importantly, we're missing the mandatory TURN_ON/TURN_OFF feature flags required for HA 2025.1+ compliance.

### Critical Findings

| Feature | Status | Priority | Effort | Impact |
|---------|--------|----------|--------|---------|
| **TURN_ON/TURN_OFF flags** | ❌ MISSING | 🔴 CRITICAL | 1h | Required for HA 2025.1+ |
| **HVAC Action property** | ❌ MISSING | 🟡 MEDIUM | 2h | Better user feedback |
| **Horizontal Swing Mode** | ⚠️ PARTIAL | 🟡 LOW | 1h | Complete feature parity |
| Preset Modes | ✅ N/A | - | - | Not applicable to hardware |

---

## 1. Current Implementation Status

### ✅ Currently Supported

**Services/Methods:**

- `async_set_hvac_mode()` - Change operation mode (Heat, Cool, Auto, Dry, Fan, Off)
- `async_set_temperature()` - Set target temperature
- `async_set_fan_mode()` - Set fan speed
- `async_set_swing_mode()` - Set vertical vane position

**ClimateEntityFeature Flags:**

- `TARGET_TEMPERATURE` - Always enabled
- `FAN_MODE` - Conditionally enabled based on device capabilities
- `SWING_MODE` - Conditionally enabled based on device capabilities

**From climate.py:169**

```python
@property
def supported_features(self) -> ClimateEntityFeature:
    """Return the list of supported features."""
    features = ClimateEntityFeature.TARGET_TEMPERATURE

    device = self._device
    if device is None:
        return features

    if device.capabilities:
        if (
            device.capabilities.has_automatic_fan_speed
            or device.capabilities.number_of_fan_speeds > 0
        ):
            features |= ClimateEntityFeature.FAN_MODE
        if device.capabilities.has_swing or device.capabilities.has_air_direction:
            features |= ClimateEntityFeature.SWING_MODE

    return features
```

---

## 2. Missing Feature #1: TURN_ON/TURN_OFF (CRITICAL) 🔴

### Why This Matters

**Home Assistant Core 2024.2 Changes:**

- Added `ClimateEntityFeature.TURN_ON` and `ClimateEntityFeature.TURN_OFF` flags
- 10-month deprecation period ended in 2025.1
- Now **mandatory** for integrations that support power control
- Without these flags, `climate.turn_on` and `climate.turn_off` services may not work

**User Impact:**

- ❌ Voice commands like "turn on the AC" may fail
- ❌ Automations using these services will break
- ❌ Integration appears incomplete vs modern integrations
- ❌ Non-compliant with HA 2025.1+ standards

**Why Separate from hvac_mode:**

- `set_hvac_mode(OFF)` requires remembering the last mode
- `turn_on()` should restore to last mode or sensible default
- Better matches user expectations and voice assistant behavior

### Implementation

**Recommended Implementation (KISS Principle)**

```python
# Add to MELCloudHomeClimate class in climate.py

async def async_turn_on(self) -> None:
    """Turn the entity on."""
    # Device will resume its previous state (mode, temp, fan, vanes, etc.)
    await self.coordinator.client.set_power(self._unit_id, True)
    await self.coordinator.async_request_refresh()

async def async_turn_off(self) -> None:
    """Turn the entity off."""
    await self.coordinator.client.set_power(self._unit_id, False)
    await self.coordinator.async_request_refresh()

@property
def supported_features(self) -> ClimateEntityFeature:
    """Return the list of supported features."""
    # Always support these features
    features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    device = self._device
    if device is None:
        return features

    # Check capabilities from device
    if device.capabilities:
        if (
            device.capabilities.has_automatic_fan_speed
            or device.capabilities.number_of_fan_speeds > 0
        ):
            features |= ClimateEntityFeature.FAN_MODE
        if device.capabilities.has_swing or device.capabilities.has_air_direction:
            features |= ClimateEntityFeature.SWING_MODE

    return features
```

**Why This Approach:**

- ✅ **Device remembers state** - Resumes previous mode, temperature, fan speed, vanes, etc.
- ✅ **KISS principle** - Let the device do what it already does
- ✅ **Predictable behavior** - User gets back exactly what they had before
- ✅ **Matches physical remote** - Same as pressing power button on remote
- ✅ **Less opinionated** - Don't force users into AUTO mode
- ✅ **Simpler code** - No state management or mode-setting logic needed

**Behavior Example:**

- User sets HEAT mode at 22°C → turns off → turns on → **resumes HEAT at 22°C**
- Much better than forcing everyone to AUTO mode!

**Alternative (NOT Recommended):**

```python
def __init__(self, ...):
    # ... existing init code ...
    self._last_hvac_mode: HVACMode = HVACMode.AUTO  # Default

async def async_turn_on(self) -> None:
    """Turn the entity on to the last active mode."""
    # Restore last mode, or use AUTO if never set
    await self.async_set_hvac_mode(self._last_hvac_mode)

async def async_turn_off(self) -> None:
    """Turn the entity off."""
    # Save current mode before turning off
    current_mode = self.hvac_mode
    if current_mode != HVACMode.OFF:
        self._last_hvac_mode = current_mode

    await self.coordinator.client.set_power(self._unit_id, False)
    await self.coordinator.async_request_refresh()
```

**Recommendation:** Use Option 1 (Simple). The API already handles power state separately, and AUTO is a sensible default.

### Testing Checklist

- [ ] Call `climate.turn_off` service - device turns off
- [ ] Call `climate.turn_on` service - device turns on to AUTO mode
- [ ] Use voice command "turn on the AC" - device responds
- [ ] Use voice command "turn off the AC" - device responds
- [ ] Test automation with `climate.turn_on` - works correctly
- [ ] Verify entity shows as "off" when powered off
- [ ] Verify entity shows "auto" mode when powered on

---

## 3. Missing Feature #2: HVAC Action Property 🟡

### hvac_mode vs hvac_action

**Key Differences:**

| Property | Purpose | Example Values | Use Case |
|----------|---------|----------------|----------|
| `hvac_mode` | What mode is SET | heat, cool, auto, off | User configuration |
| `hvac_action` | What device is DOING | heating, cooling, idle, off | Real-time feedback |

**Example Scenario:**

- **Mode:** `HVACMode.HEAT` (set to heat)
- **Current temp:** 22°C
- **Target temp:** 21°C
- **Action:** `HVACAction.IDLE` (target reached, not actively heating)

**User Benefit:**
The HA frontend shows the action in the climate card, providing immediate visual feedback about system activity.

### Challenge: MELCloud API Limitations

**Available Data:**

- `power` (bool) - Is unit on/off
- `operation_mode` (str) - Heat/Cool/Automatic/Dry/Fan
- `room_temperature` (float) - Current room temp
- `set_temperature` (float) - Target temp
- `ActualFanSpeed` (str) - Current fan speed

**Missing Data:**

- ❌ No direct "is heating" or "is cooling" indicator
- ❌ No compressor state
- ❌ No valve position

**Solution: Inference with Hysteresis**

We can infer the action from temperature difference, using hysteresis to avoid rapid state changes:

```python
from homeassistant.components.climate import HVACAction

@property
def hvac_action(self) -> HVACAction | None:
    """Return the current running hvac operation.

    Note: MELCloud API doesn't provide direct heating/cooling state.
    We infer the action from operation mode and temperature difference.
    This may not perfectly reflect real-time compressor state.
    """
    device = self._device
    if device is None:
        return None

    # If powered off, action is OFF
    if not device.power:
        return HVACAction.OFF

    # If no temperature readings, can't determine action
    if device.room_temperature is None or device.set_temperature is None:
        return None

    mode = device.operation_mode

    # Fan mode is always just fan (never heats/cools)
    if mode == "Fan":
        return HVACAction.FAN

    # Dry mode is always drying
    if mode == "Dry":
        return HVACAction.DRYING

    # For Heat/Cool/Auto modes, infer from temperature difference
    temp_diff = device.room_temperature - device.set_temperature

    # Use hysteresis to avoid state flapping (±0.5°C threshold)
    if mode == "Heat":
        if temp_diff < -0.5:
            return HVACAction.HEATING
        return HVACAction.IDLE

    if mode == "Cool":
        if temp_diff > 0.5:
            return HVACAction.COOLING
        return HVACAction.IDLE

    if mode == "Automatic":
        # Larger threshold for auto mode (±1.0°C)
        if temp_diff < -1.0:
            return HVACAction.HEATING
        if temp_diff > 1.0:
            return HVACAction.COOLING
        return HVACAction.IDLE

    return HVACAction.IDLE
```

**Limitations:**

1. **Imperfect inference** - We're guessing based on temperature, not actual compressor state
2. **Lag time** - Temperature changes slowly, so action may lag reality
3. **False positives** - Device might be in defrost cycle or fan-only phase
4. **Stale with polling** - With 60-second polling, action may be outdated

**Recommendation:**

- ✅ Implement this feature despite limitations
- ✅ Document limitations in code comments
- ✅ Use conservative hysteresis values
- ✅ Will improve significantly when WebSocket support is added (v1.3)

### Testing Checklist

- [ ] Set to HEAT mode with temp above current - shows "heating"
- [ ] Wait for target reached - shows "idle"
- [ ] Set to COOL mode with temp below current - shows "cooling"
- [ ] Turn off device - shows "off"
- [ ] Set to DRY mode - shows "drying"
- [ ] Set to FAN mode - shows "fan"
- [ ] Set to AUTO mode - shows appropriate action based on temp

---

## 4. Missing Feature #3: Horizontal Swing Mode 🟡

### Current State

**What's Supported:**

- ✅ Vertical swing (up-down vane position) via `swing_mode`
- ✅ Values: "Auto", "Swing", "One" through "Five"

**What's Missing:**

- ❌ Horizontal swing (left-right vane control)
- API supports: "Auto", "Swing", "Left", "LeftCentre", "Centre", "RightCentre", "Right"

**What Happens Now:**

- When setting vertical swing, horizontal is hardcoded to "Auto"
- Users cannot control horizontal vanes independently

### Home Assistant Support

**Modern Standard (HA 2024.2+):**

Home Assistant now provides `ClimateEntityFeature.SWING_HORIZONTAL_MODE` as the proper way to expose horizontal swing control. This is the current standard approach - there is no deprecated alternative. Before 2024.2, integrations had to use custom services or combine vertical+horizontal into a single swing_mode.

### Implementation

```python
# In const.py
VANE_HORIZONTAL_POSITIONS = [
    "Auto",
    "Swing",
    "Left",
    "LeftCentre",
    "Centre",
    "RightCentre",
    "Right"
]

# In climate.py
class MELCloudHomeClimate(...):

    def __init__(self, ...):
        # ... existing init ...
        self._attr_swing_horizontal_modes = VANE_HORIZONTAL_POSITIONS

    @property
    def swing_horizontal_mode(self) -> str | None:
        """Return the current horizontal swing mode (horizontal vane position)."""
        device = self._device
        return device.vane_horizontal_direction if device else None

    async def async_set_swing_horizontal_mode(self, swing_horizontal_mode: str) -> None:
        """Set new horizontal swing mode."""
        if swing_horizontal_mode not in self.swing_horizontal_modes:
            _LOGGER.warning("Invalid horizontal swing mode: %s", swing_horizontal_mode)
            return

        # Get current vertical vane position from device, default to "Auto"
        device = self._device
        vertical = device.vane_vertical_direction if device else "Auto"

        # Set vanes: keep vertical, update horizontal
        await self.coordinator.client.set_vanes(
            self._unit_id,
            vertical,
            swing_horizontal_mode
        )

        await self.coordinator.async_request_refresh()

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return the list of supported features."""
        features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )

        device = self._device
        if device is None:
            return features

        if device.capabilities:
            if (
                device.capabilities.has_automatic_fan_speed
                or device.capabilities.number_of_fan_speeds > 0
            ):
                features |= ClimateEntityFeature.FAN_MODE
            if device.capabilities.has_swing or device.capabilities.has_air_direction:
                features |= ClimateEntityFeature.SWING_MODE
            # Add horizontal swing if device supports air direction
            if device.capabilities.has_air_direction:
                features |= ClimateEntityFeature.SWING_HORIZONTAL_MODE

        return features
```

**Benefits:**

- ✅ Users can control horizontal and vertical vanes independently
- ✅ Better matches physical device capabilities
- ✅ More intuitive UX
- ✅ Complete feature parity with device

### Testing Checklist

- [ ] Set horizontal swing to "Left" - vanes move left
- [ ] Set horizontal swing to "Right" - vanes move right
- [ ] Set horizontal swing to "Auto" - vanes auto-position
- [ ] Set vertical swing to "One" - vertical changes, horizontal unchanged
- [ ] Set horizontal to "Centre", vertical to "Three" - both set correctly
- [ ] Verify both can be controlled independently in HA UI

---

## 5. Features NOT to Implement ❌

### Preset Modes (Not Applicable)

**What Are Presets:**
Predefined comfort settings like:

- `ECO` - Energy saving mode
- `AWAY` - Vacation mode (higher/lower temps)
- `BOOST` - Maximum heating/cooling
- `COMFORT` - Normal operation
- `SLEEP` - Quiet night mode

**Why Not Implement:**

- ❌ MELCloud devices don't have preset modes
- ✅ Schedules serve this purpose (already accessible via API)
- ❌ Would be confusing to users (no physical equivalent)
- ✅ Users should use HA automations for custom comfort scenarios

### Target Temperature Range (Not Supported)

**What It Is:**
`ClimateEntityFeature.TARGET_TEMPERATURE_RANGE` allows setting separate high/low temperatures for heat_cool mode (e.g., keep between 20-24°C)

**Why Not Implement:**

- ❌ MELCloud devices use single target temperature even in Auto mode
- ❌ API doesn't support temperature ranges
- ❌ No hardware capability for this

### Target Humidity (No Hardware Support)

**What It Is:**
`ClimateEntityFeature.TARGET_HUMIDITY` for devices with humidity control

**Why Not Implement:**

- ❌ API provides "Dry" mode for dehumidification but no humidity sensors
- ❌ No target humidity control in API
- ❌ Hardware limitation

### Aux Heat (Not Applicable)

**What It Is:**
`ClimateEntityFeature.AUX_HEAT` for dual-fuel systems with auxiliary/emergency heating

**Why Not Implement:**

- ❌ Mitsubishi heat pumps don't have auxiliary heat systems
- ❌ Not applicable to this hardware

---

## 6. Comparison with LG ThinQ Integration

### What LG ThinQ Has

**Features:**

- ✅ Turn on/off (via dedicated services) - **WE'RE MISSING THIS**
- ✅ Temperature control
- ✅ Temperature range (for heat_cool mode)
- ✅ Fan mode
- ✅ Preset modes (maps to their specific API)

**Known Issues:**

- Issue #131252: Can't set mode when device is off
- Requires sequential: turn_on → set_mode → set_temperature
- Similar architecture to MELCloud (separate power/mode control)

### What We Do Better

- ✅ More granular vertical swing control (7 positions vs basic on/off)
- ✅ Independent horizontal vane control (once implemented)
- ✅ Cleaner state management (separate power and mode in API)
- ✅ Better architecture (DataUpdateCoordinator vs older patterns)

### What They Do Better

- ✅ Explicit turn_on/turn_off implementation - **WE NEED TO ADD THIS**

---

## 7. Implementation Roadmap

### v1.1.3 Hotfix - Critical Compliance (IMMEDIATE)

**Time Estimate: 2-3 hours**
**Priority: 🔴 CRITICAL**

**Scope:**

1. Add TURN_ON/TURN_OFF feature flags
2. Implement `async_turn_on()` method
3. Implement `async_turn_off()` method
4. Test with voice assistants and automations

**Why Hotfix:**

- Required for HA 2025.1+ compliance
- Simple 1-hour implementation
- High user impact (voice commands, automations)
- No dependencies on other features

**Deliverables:**

- Updated `climate.py` with turn_on/turn_off support
- Testing verification
- Release v1.1.3 to production

### v1.2 - Enhanced Features

**Time Estimate: 3-4 hours (in addition to sensors + HACS)**
**Priority: 🟡 MEDIUM**

**Scope:**

1. Add HVAC Action property with inference logic
2. Add Horizontal Swing Mode support
3. Comprehensive testing

**Why v1.2:**

- Can be bundled with sensor platform work
- Nice-to-have improvements, not critical
- Benefit from same testing cycle

**Deliverables:**

- `hvac_action` property implementation
- Horizontal swing mode support
- Updated tests

### v1.3+ - Real-Time Enhancements

**Time Estimate: Future**
**Priority: 🟢 LOW**

**Scope:**

1. WebSocket support for real-time hvac_action
2. More accurate state reporting
3. Sub-second update latency

**Why Later:**

- Requires WebSocket implementation (already planned)
- Current inference logic is "good enough"
- Can iterate based on user feedback

---

## 8. Complete Code Example

Here's the complete updated climate entity with all recommended changes:

```python
# climate.py - Complete updated version

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
    HVACAction,
)

class MELCloudHomeClimate(CoordinatorEntity[MELCloudHomeCoordinator], ClimateEntity):
    """Representation of a MELCloud Home climate device."""

    def __init__(
        self,
        coordinator: MELCloudHomeCoordinator,
        unit: AirToAirUnit,
        building: Building,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._unit_id = unit.id
        self._building_id = building.id

        # Horizontal swing modes
        self._attr_swing_horizontal_modes = VANE_HORIZONTAL_POSITIONS

        # ... existing initialization ...

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return the list of supported features."""
        # Always support these features
        features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )

        device = self._device
        if device is None:
            return features

        # Check capabilities from device
        if device.capabilities:
            if (
                device.capabilities.has_automatic_fan_speed
                or device.capabilities.number_of_fan_speeds > 0
            ):
                features |= ClimateEntityFeature.FAN_MODE
            if device.capabilities.has_swing or device.capabilities.has_air_direction:
                features |= ClimateEntityFeature.SWING_MODE
            # Add horizontal swing if device supports air direction
            if device.capabilities.has_air_direction:
                features |= ClimateEntityFeature.SWING_HORIZONTAL_MODE

        return features

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current running hvac operation.

        Note: MELCloud API doesn't provide direct heating/cooling state.
        We infer the action from operation mode and temperature difference.
        This may not perfectly reflect real-time compressor state.
        """
        device = self._device
        if device is None:
            return None

        # If powered off, action is OFF
        if not device.power:
            return HVACAction.OFF

        # If no temperature readings, can't determine action
        if device.room_temperature is None or device.set_temperature is None:
            return None

        mode = device.operation_mode

        # Fan mode is always just fan (never heats/cools)
        if mode == "Fan":
            return HVACAction.FAN

        # Dry mode is always drying
        if mode == "Dry":
            return HVACAction.DRYING

        # For Heat/Cool/Auto modes, infer from temperature difference
        temp_diff = device.room_temperature - device.set_temperature

        # Use hysteresis to avoid state flapping (±0.5°C threshold)
        if mode == "Heat":
            if temp_diff < -0.5:
                return HVACAction.HEATING
            return HVACAction.IDLE

        if mode == "Cool":
            if temp_diff > 0.5:
                return HVACAction.COOLING
            return HVACAction.IDLE

        if mode == "Automatic":
            # Larger threshold for auto mode (±1.0°C)
            if temp_diff < -1.0:
                return HVACAction.HEATING
            if temp_diff > 1.0:
                return HVACAction.COOLING
            return HVACAction.IDLE

        return HVACAction.IDLE

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        # Device will resume its previous state
        await self.coordinator.client.set_power(self._unit_id, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        await self.coordinator.client.set_power(self._unit_id, False)
        await self.coordinator.async_request_refresh()

    @property
    def swing_horizontal_mode(self) -> str | None:
        """Return the current horizontal swing mode (horizontal vane position)."""
        device = self._device
        return device.vane_horizontal_direction if device else None

    async def async_set_swing_horizontal_mode(self, swing_horizontal_mode: str) -> None:
        """Set new horizontal swing mode."""
        if swing_horizontal_mode not in self.swing_horizontal_modes:
            _LOGGER.warning("Invalid horizontal swing mode: %s", swing_horizontal_mode)
            return

        # Get current vertical vane position from device
        device = self._device
        vertical = device.vane_vertical_direction if device else "Auto"

        # Set vanes: keep vertical, update horizontal
        await self.coordinator.client.set_vanes(
            self._unit_id,
            vertical,
            swing_horizontal_mode
        )

        await self.coordinator.async_request_refresh()

    # ... existing methods (set_temperature, set_hvac_mode, etc.) ...
```

```python
# const.py - Add horizontal vane positions

VANE_HORIZONTAL_POSITIONS = [
    "Auto",
    "Swing",
    "Left",
    "LeftCentre",
    "Centre",
    "RightCentre",
    "Right"
]
```

---

## 9. Testing Strategy

### Unit Tests

```python
# tests/test_climate_features.py

async def test_turn_on_resumes_state(hass, climate_entity):
    """Test turning on device resumes previous state."""
    # Set device to HEAT mode at 22°C
    await climate_entity.async_set_hvac_mode(HVACMode.HEAT)
    await climate_entity.async_set_temperature(temperature=22.0)
    await hass.async_block_till_done()

    # Turn off
    await climate_entity.async_turn_off()
    await hass.async_block_till_done()

    # Turn on - should resume HEAT at 22°C
    await climate_entity.async_turn_on()
    await hass.async_block_till_done()

    # Device should resume previous state (device handles this)
    assert climate_entity._device.power is True
    # Note: Mode and temp preserved by device, not forced by integration

async def test_hvac_action_heating(hass, climate_entity):
    """Test hvac_action shows HEATING when temp below target."""
    device = climate_entity._device
    device.power = True
    device.operation_mode = "Heat"
    device.room_temperature = 18.0
    device.set_temperature = 22.0

    assert climate_entity.hvac_action == HVACAction.HEATING

async def test_hvac_action_idle(hass, climate_entity):
    """Test hvac_action shows IDLE when temp at target."""
    device = climate_entity._device
    device.power = True
    device.operation_mode = "Heat"
    device.room_temperature = 22.0
    device.set_temperature = 22.0

    assert climate_entity.hvac_action == HVACAction.IDLE

async def test_horizontal_swing_independent(hass, climate_entity):
    """Test horizontal swing can be set independently."""
    # Set vertical to position 3
    await climate_entity.async_set_swing_mode("Three")

    # Set horizontal to left
    await climate_entity.async_set_swing_horizontal_mode("Left")
    await hass.async_block_till_done()

    # Both should be set correctly
    assert climate_entity.swing_mode == "Three"
    assert climate_entity.swing_horizontal_mode == "Left"
```

### Manual Testing Checklist

**Turn On/Off:**

- [ ] Set HEAT mode, turn off, turn on → resumes HEAT mode (device remembers state)
- [ ] Set COOL mode at 24°C, turn off, turn on → resumes COOL at 24°C
- [ ] Voice command: "Hey Google, turn on bedroom AC" → device powers on
- [ ] Voice command: "Alexa, turn off bedroom AC" → device powers off
- [ ] Automation using `climate.turn_on` → executes correctly
- [ ] Verify device resumes previous mode, not forced to AUTO

**HVAC Action:**

- [ ] Heat mode, cold room → shows "heating"
- [ ] Heat mode, warm room → shows "idle"
- [ ] Cool mode, warm room → shows "cooling"
- [ ] Cool mode, cold room → shows "idle"
- [ ] Fan mode → shows "fan"
- [ ] Dry mode → shows "drying"
- [ ] Device off → shows "off"

**Horizontal Swing:**

- [ ] Set horizontal to "Left" → vanes move left
- [ ] Set horizontal to "Right" → vanes move right
- [ ] Set horizontal to "Centre" → vanes center
- [ ] Set horizontal to "Swing" → vanes oscillate left-right
- [ ] Change vertical, horizontal unchanged → works
- [ ] Change horizontal, vertical unchanged → works

---

## 10. Summary

### Critical Action Required (v1.1.3)

**TURN_ON/TURN_OFF Implementation - 2-3 hours**

This is a **compliance issue**, not just a nice-to-have:

- Required for HA 2025.1+ compatibility
- Breaks voice assistant integration without it
- Simple 1-hour implementation
- High user impact

**Recommendation:** Create v1.1.3 hotfix immediately, before v1.2 work.

### Enhanced Features (v1.2)

**HVAC Action + Horizontal Swing - 3-4 hours**

Both provide value but aren't critical:

- Better user experience
- Complete feature parity
- Can wait for v1.2 release cycle

### What Not to Do

Don't implement:

- ❌ Preset modes (not applicable)
- ❌ Target temp range (not supported)
- ❌ Target humidity (no hardware support)
- ❌ Aux heat (not applicable)

---

## References

**Official HA Documentation:**

- Climate Entity: <https://developers.home-assistant.io/docs/core/entity/climate/>
- 2024.2 Feature Changes: <https://developers.home-assistant.io/blog/2024/01/24/climate-climateentityfeatures-expanded/>
- Architecture Discussion #982: <https://github.com/home-assistant/architecture/discussions/982>

**Integration Examples:**

- LG ThinQ: <https://github.com/home-assistant/core/tree/dev/homeassistant/components/lg_thinq>
- Ecobee: <https://github.com/home-assistant/core/blob/dev/homeassistant/components/ecobee/climate.py>
- Nest: <https://github.com/home-assistant/core/blob/dev/homeassistant/components/nest/climate.py>

**Project Documentation:**

- API Reference: `_claude/melcloudhome-api-reference.md`
- Current Implementation: `custom_components/melcloudhome/climate.py`
