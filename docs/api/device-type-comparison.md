# Device Type Comparison: Air-to-Air vs Air-to-Water

Quick reference guide comparing Air-to-Air (A/C) and Air-to-Water (Heat Pump) devices in the MELCloud Home API.

> **Implementation Note:** This document provides a complete API comparison. Control endpoints for both device types are implemented in the integration. Telemetry endpoints (section 6) are mostly reference-only - see [melcloudhome-telemetry-endpoints.md](melcloudhome-telemetry-endpoints.md) for implementation status.

**Last Updated:** 2026-01-03

---

## Quick Navigation

- [Endpoint Comparison](#endpoint-comparison)
- [Control Parameters](#control-parameters)
- [Device Architecture](#device-architecture)
- [Operation Mode Semantics](#operation-mode-semantics)
- [Capabilities Structure](#capabilities-structure)
- [Telemetry Measures](#telemetry-measures)
- [Code Examples](#code-examples)

---

## Endpoint Comparison

| Feature | Air-to-Air (A/C) | Air-to-Water (Heat Pump) | Shared? |
|---------|------------------|--------------------------|---------|
| **Control** | `PUT /api/ataunit/{id}` | `PUT /api/atwunit/{id}` | ❌ Different prefix |
| **User Context** | `GET /api/user/context` | `GET /api/user/context` | ✅ **Same endpoint** |
| **Context Structure** | `buildings[].airToAirUnits[]` | `buildings[].airToWaterUnits[]` | ⚠️ Parallel arrays |
| **Schedule Create** | `POST /api/cloudschedule/{id}` | `POST /api/atwcloudschedule/{id}` | ❌ Different prefix |
| **Schedule Delete** | `DELETE /api/cloudschedule/{id}/{scheduleId}` | `DELETE /api/atwcloudschedule/{id}/{scheduleId}` | ❌ Different prefix |
| **Schedule Enable** | `PUT /api/cloudschedule/{id}/enabled` | `PUT /api/atwcloudschedule/{id}/enabled` | ❌ Different prefix |
| **Telemetry** | `GET /api/telemetry/actual`<br/>(unitId as query param) | `GET /api/telemetry/actual/{id}`<br/>(unitId in path) | ⚠️ **Different structure** |
| **Energy** | `GET /api/telemetry/energy/{id}` | `GET /api/telemetry/energy/{id}` | ✅ **Identical** |
| **Error Log** | `GET /api/ataunit/{id}/errorlog` | `GET /api/atwunit/{id}/errorlog` | ⚠️ Same pattern, different prefix |
| **Holiday Mode** | N/A (unit-level only) | `POST /api/holidaymode` | ❌ **A2W exclusive** |
| **Frost Protection** | N/A | `POST /api/protection/frost` | ❌ **A2W exclusive** |

### Key Observations

- **Shared authentication:** 100% identical (AWS Cognito OAuth)
- **Shared UserContext:** Single endpoint returns both device types
- **Parallel structure:** Endpoints follow same pattern with different prefixes
- **Multi-unit operations:** A2W supports batch operations (holiday mode, frost protection)

---

## Control Parameters

### Side-by-Side Comparison

| Category | Air-to-Air | Air-to-Water | Notes |
|----------|------------|--------------|-------|
| **Power** | `power` (boolean) | `power` (boolean) | ✅ Identical |
| **Temperature** | `setTemperature`<br/>(single target) | `setTemperatureZone1`<br/>`setTankWaterTemperature`<br/>(dual targets) | ❗ A2W has 2 temps |
| **Temp Range** | 10-31°C<br/>(mode-specific) | Zone 1: 10-30°C<br/>DHW: 40-60°C | ❗ Different semantics |
| **Operation Mode** | `operationMode`<br/>(5 modes) | `operationModeZone1`<br/>(3 modes) | ❗ Different modes |
| **Mode Values** | Heat, Cool, Automatic,<br/>Dry, Fan | HeatRoomTemperature,<br/>HeatFlowTemperature,<br/>HeatCurve | ❗ Different names |
| **Fan Control** | `setFanSpeed`<br/>(Auto, One-Five) | N/A | ❌ A2A exclusive |
| **Vane Control** | `vaneVerticalDirection`<br/>`vaneHorizontalDirection` | N/A | ❌ A2A exclusive |
| **Zone Control** | Single zone (implicit) | `Zone1`, `Zone2` (optional) | ❗ A2W multi-zone |
| **DHW Control** | N/A | `forcedHotWaterMode` | ❌ A2W exclusive |
| **Standby** | `inStandbyMode` | `InStandbyMode` | ✅ Similar (status) |
| **Null Pattern** | Unset fields = null | Unset fields = null | ✅ Identical |

### A2A Request Example
```json
{
  "power": null,
  "operationMode": "Heat",
  "setTemperature": 22.0,
  "setFanSpeed": "Auto",
  "vaneVerticalDirection": "Swing",
  "vaneHorizontalDirection": "Auto",
  "inStandbyMode": null,
  "temperatureIncrementOverride": null
}
```

### A2W Request Example
```json
{
  "power": null,
  "setTemperatureZone1": 21,
  "setTemperatureZone2": null,
  "operationModeZone1": "HeatRoomTemperature",
  "operationModeZone2": null,
  "setTankWaterTemperature": 50,
  "forcedHotWaterMode": false,
  "setHeatFlowTemperatureZone1": null,
  "setCoolFlowTemperatureZone1": null,
  "setHeatFlowTemperatureZone2": null,
  "setCoolFlowTemperatureZone2": null
}
```

---

## Device Architecture

### Air-to-Air (A/C)

**Function:** Single-purpose climate control
- Cool or heat a space
- One temperature target
- One operation mode at a time
- Direct control of all functions

**Typical Use:**
- Room air conditioning
- Single-zone heating/cooling
- Immediate response

**Control Flow:**
```
User → Set Mode/Temp → A/C responds immediately
```

### Air-to-Water (Heat Pump)

**Function:** Dual-purpose with 3-way valve (see [architecture](../architecture.md#atw-3-way-valve-behavior))
- Zone 1 heating (underfloor/radiators)
- DHW tank heating

**Typical Use:**
- Whole-home heating
- Domestic hot water
- Slower response (thermal mass)

**Control Flow:**
```
User → Set Targets → System prioritizes → 3-way valve → One task at a time
```

See [architecture documentation](../architecture.md#atw-3-way-valve-behavior) for detailed 3-way valve behavior and state diagram.

---

## Operation Mode Semantics

### Air-to-Air Modes

**5 operation modes (strings):**
- `"Heat"` - Heat the room
- `"Cool"` - Cool the room
- `"Automatic"` - Auto heat/cool (⚠️ NOT "Auto"!)
- `"Dry"` - Dehumidify
- `"Fan"` - Fan only

**Mode determines:**
- What the A/C does
- Temperature range constraints
- Available fan speeds

**Direct control:** User sets mode, A/C does it immediately.

### Air-to-Water Modes

**3 operation modes for Zone 1 (strings):**
- `"HeatRoomTemperature"` - Thermostat mode (maintain room temp)
- `"HeatFlowTemperature"` - Flow temp mode (direct water temp control)
- `"HeatCurve"` - Weather compensation (outdoor temp-based)

**Two types of "mode":**

1. **Control mode** (`operationModeZone1`): HOW to heat
   - User sets this
   - Determines heating strategy

2. **Status mode** (`OperationMode`): WHAT is heating NOW
   - `"Stop"` - Zone 1 idle (target reached)
   - `"HotWater"` - Currently heating DHW
   - *(zone mode)* - Currently heating Zone 1

**Critical distinction:**
- A2A: `operationMode` is both control AND status
- A2W: `operationModeZone1` = control, `OperationMode` = status

---

## Capabilities Structure

### Comparison Table

| Capability | Air-to-Air | Air-to-Water | Notes |
|------------|------------|--------------|-------|
| **Temperature Ranges** | Mode-specific<br/>(heat/cool/auto/dry) | Function-specific<br/>(zone/DHW) | Different semantics |
| **Operation Modes** | Boolean flags<br/>(hasCool, hasHeat, hasAuto, hasDry, hasFan) | Implicit<br/>(always heat-only) | A2W simpler |
| **Fan Capabilities** | `numberOfFanSpeeds`<br/>`hasAutomaticFanSpeed`<br/>`hasSwing`<br/>`hasAirDirection` | N/A | A2A exclusive |
| **Vane Capabilities** | `supportsWideVane` | N/A | A2A exclusive |
| **Zone Support** | N/A | `hasZone2` | A2W exclusive |
| **DHW Support** | N/A | `hasHotWater`<br/>`minSetTankTemperature`<br/>`maxSetTankTemperature` | A2W exclusive |
| **FTC Model** | N/A | `ftcModel` (integer) | A2W exclusive |
| **Energy Metering** | `hasEnergyConsumedMeter` | `hasMeasuredEnergyConsumption`<br/>`hasMeasuredEnergyProduction`<br/>`hasEstimatedEnergyConsumption`<br/>`hasEstimatedEnergyProduction` | A2W more granular |
| **Standby** | `hasStandby` | N/A (always present) | A2A capability flag |
| **Demand Control** | `hasDemandSideControl` | `hasDemandSideControl` | ✅ Both |

### Temperature Range Details

**Air-to-Air:**
```
Heat mode:     10-31°C
Cool/Dry mode: 16-31°C
Auto mode:     16-31°C
Increments:    0.5°C (if hasHalfDegreeIncrements)
```

**Air-to-Water:**
```
Zone 1:        10-30°C (underfloor heating)
Zone 2:        10-30°C (if hasZone2)
DHW:           40-60°C
Increments:    0.5°C or 1°C (if hasHalfDegrees)

⚠️ API-reported ranges may be incorrect - use safe defaults
```

---

## Telemetry Measures

### Air-to-Air Measures

**3 primary measures:**
- `roomTemperature` - Current room temp
- `setTemperature` - Target temp
- `rssi` - WiFi signal strength

**Energy (if available):**
- `energyConsumed` - Cumulative kWh

### Air-to-Water Measures

**9 telemetry types:**

**Temperature:**
- `roomTemperatureZone1` - Room temp
- `setTemperatureZone1` - Zone target
- `tankWaterTemperature` - Current DHW temp
- `setTankWaterTemperature` - DHW target

**Flow (hydraulic):**
- `flow_temperature` - System output
- `flow_temperature_zone1` - Zone-specific
- `flow_temperature_boiler` - Boiler output

**Return (hydraulic):**
- `return_temperature` - System return
- `return_temperature_zone1` - Zone-specific
- `return_temperature_boiler` - Boiler return

**Connection:**
- `rssi` - WiFi signal

**Energy (if available):**
- `interval_energy_consumed` - Energy used (intervals)
- `interval_energy_produced` - Energy generated (intervals)

### Query Pattern Difference

**Air-to-Air:**
```
GET /api/telemetry/actual?unitId={id}&from=...&to=...
```
(unitId as query parameter)

**Air-to-Water:**
```
GET /api/telemetry/actual/{id}?from=...&to=...&measure=tank_water_temperature
```
(unitId in path, measure specified)

---

## Key Differences Summary

### Shared (100%)
- ✅ Authentication (AWS Cognito OAuth)
- ✅ Session management
- ✅ UserContext endpoint
- ✅ Sparse update pattern (nulls ignored)
- ✅ Empty 200 response for control
- ✅ Settings as name-value array
- ✅ Schedule structure (string/int enum split)

### Similar (~90%)
- ⚠️ Endpoint patterns (same structure, different prefix)
- ⚠️ Control flow (PUT with JSON, nulls for unchanged)
- ⚠️ Capabilities object (different fields, same concept)
- ⚠️ Telemetry structure (different measures, same format)

### Different
- ❌ Device architecture (single vs dual-function)
- ❌ Temperature semantics (one target vs two targets)
- ❌ Operation modes (5 vs 3, different meanings)
- ❌ A2A has fan/vane control, A2W doesn't
- ❌ A2W has DHW control, A2A doesn't
- ❌ A2W has multi-unit operations, A2A doesn't
- ❌ A2W has 3-way valve limitation, A2A doesn't

---

## Related Documentation

- **A2A API Reference:** [ata-api-reference.md](ata-api-reference.md)
- **A2W API Reference:** [atw-api-reference.md](atw-api-reference.md)
- **OpenAPI Specification:** [../../openapi.yaml](../../openapi.yaml)
- **Architecture Decision:** [../decisions/011-multi-device-type-architecture.md](../decisions/011-multi-device-type-architecture.md)
