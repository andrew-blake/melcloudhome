# ADR-012: ATW Entity Architecture and Power Control

**Date:** 2026-01-03 (Updated: 2026-01-09)
**Status:** Accepted
**Deciders:** @andrew-blake
**Related:** [ADR-011: Multi-Device-Type Architecture](011-multi-device-type-architecture.md)

## Context

Air-to-Water (ATW) heat pumps are physically **one device** with **two capabilities**:

1. Zone heating (Zone 1, optionally Zone 2)
2. Domestic Hot Water (DHW) via tank

**Physical constraint:** 3-way valve can only heat ONE target at a time (zones OR DHW tank). See [architecture documentation](../architecture.md#atw-3-way-valve-behavior) for detailed behavior.

**Key question:** Which Home Assistant entity controls system power?

## Decision

### Entity Architecture

**Per ATW device:**

| Entity Type | Entity ID | Controls | Does NOT Control |
|-------------|-----------|----------|------------------|
| **switch** | `{device}_system_power` | System power ON/OFF (primary) | Zone temps, DHW |
| **climate** | `{device}_zone_1` | Zone temp, preset modes, HVAC mode | System power (delegates) |
| **water_heater** | `{device}_tank` | DHW temp, operation mode | **System power** (read-only) |
| **sensor** | Various | Temperature readings, status | N/A |
| **binary_sensor** | `{device}_error`, `{device}_forced_dhw` | Status monitoring | N/A |

### Power Control Architecture

**Critical decision:** Switch is primary, climate delegates, water heater is read-only.

```python
# switch.py - PRIMARY power control
class ATWSystemPowerSwitch:
    async def async_turn_on(self, **kwargs):
        await self.coordinator.async_set_power_atw(self._unit_id, True)

    async def async_turn_off(self, **kwargs):
        await self.coordinator.async_set_power_atw(self._unit_id, False)

# climate.py - DELEGATES to same method
class ATWClimateZone1:
    async def async_set_hvac_mode(self, hvac_mode):
        if hvac_mode == HVACMode.HEAT:
            await self.coordinator.async_set_power_atw(self._unit_id, True)
        elif hvac_mode == HVACMode.OFF:
            await self.coordinator.async_set_power_atw(self._unit_id, False)

# water_heater.py - NO power control
class ATWWaterHeater:
    # No turn_on/turn_off methods
    @property
    def state(self):
        if not device.power:
            return STATE_OFF
        # DHW logic only...
```

### Other Key Decisions

**Forced DHW:** Water heater operation modes (Eco/High demand), using HA standard states

- `Eco` (STATE_ECO) → `forcedHotWaterMode=False` - Energy efficient, balanced operation
- `High demand` (STATE_HIGH_DEMAND) → `forcedHotWaterMode=True` - Priority mode, faster heating

Note: These map to HA's standard water heater operation modes following industry patterns (Rheem: ENERGY_SAVING → STATE_ECO, AO Smith: HYBRID → STATE_ECO)

**Zone modes:** Climate preset modes (room_temperature, flow_temperature, weather_compensation)

**3-way valve:** Visible via `operation_status` sensor and water_heater attributes

**Temperature ranges:** Hardcoded safe defaults (Zone: 10-30°C, DHW: 40-60°C) - API ranges unreliable

## Rationale

**Why switch as primary?**

- Clearer UX than official MELCloud (which allows both water_heater AND climate to control power)
- Standard HA pattern: switches control binary states
- Prevents ambiguity about "source of truth"

**Why climate delegates?**

- Users expect `climate.turn_off()` to work (standard HA behavior)
- No duplicate logic - both call same coordinator method
- Maintains Single Responsibility Principle

**Why water heater has NO power control?**

- Deliberate divergence from official MELCloud
- Avoids confusion in multi-zone systems
- Water heater traditionally controls DHW-specific settings only

**HAR analysis findings:**

- No zone-level standby control exists (137 API calls analyzed)
- Climate OFF must power off entire system (API limitation)
- Water heater modes are boolean `forcedHotWaterMode` only

## Consequences

**Positive:**

- Clear responsibility boundaries
- Single source of truth for power
- Standard HA UX maintained

**Negative:**

- Climate OFF powers off entire system (not zone-specific) - API limitation
- Diverges from official MELCloud - deliberate choice for better architecture

## Validation Criteria

Implementation is correct when:

- ✅ `switch.turn_off()` powers off entire system
- ✅ `climate.set_hvac_mode(OFF)` powers off entire system (delegates to same method)
- ✅ `water_heater` has NO `turn_on/turn_off` methods
- ✅ Both switch and climate call `coordinator.async_set_power_atw()`
- ✅ Water heater `state` reflects power but cannot control it

## References

- HAR analysis: 137 API calls across 2 files
- MELCloud core integration: [climate.py](https://github.com/home-assistant/core/blob/dev/homeassistant/components/melcloud/climate.py)
- `docs/architecture.md`: 3-way valve behavior (lines 263-332)
- `docs/api/atw-api-reference.md`: Complete API specification
