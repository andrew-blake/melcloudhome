# MELCloud Home API Reference - Air-to-Water Units
## Complete Air-to-Water Heat Pump API Specification

**Document Version:** 1.0
**Last Updated:** 2026-01-03
**Device Type:** Air-to-Water Heat Pumps (Ecodan, Hydrobox)
**Source:** 107 captured API calls + community testing

> **Note:** This document covers Air-to-Water heat pump units only.
> For Air-to-Air (A/C) units, see [ata-api-reference.md](ata-api-reference.md).
> For comparison between device types, see [device-type-comparison.md](device-type-comparison.md).

---

## ⚠️ CRITICAL SAFETY NOTICE

**This API controls production HVAC equipment. Safety guidelines:**

1. **ONLY use values observed from the official MELCloud Home UI or documented here**
2. **NEVER send experimental or out-of-range values**
3. **NEVER test edge cases or boundary conditions**
4. **All values in this document were captured from actual API usage**
5. **When in doubt, observe the UI - do not guess or extrapolate**

**Rationale:** This is production heat pump equipment. Invalid commands could:
- Confuse the system or backend
- Trigger unexpected behavior
- Potentially cause equipment issues
- Generate backend errors

---

## Device Architecture Overview

Air-to-Water heat pumps are **ONE physical device** with **TWO functional capabilities**:
- **Zone 1** - Space heating control (underfloor heating/radiators)
- **Hot Water (DHW)** - Domestic hot water tank

**Critical Limitation:** The heat pump uses a **3-way valve** and can only perform ONE task at a time:
- Either heat DHW tank
- OR heat Zone 1
- Cannot do both simultaneously

The system automatically balances between these priorities unless Forced Hot Water mode is enabled.

---

## Quick Reference: All Parameters

### Control Parameters (PUT /api/atwunit/{unitId})

| Parameter | Type | Valid Values | Notes |
|-----------|------|--------------|-------|
| `power` | boolean | `true`, `false`, `null` | null for no change |
| `setTemperatureZone1` | number | 10-30 (0.5° increments) | Zone heating target |
| `setTemperatureZone2` | number | null | Zone 2 support (if hasZone2=true) |
| `operationModeZone1` | string | `"HeatRoomTemperature"`<br/>`"HeatFlowTemperature"`<br/>`"HeatCurve"` | How zone is heated |
| `operationModeZone2` | string | null | Zone 2 mode (if hasZone2=true) |
| `setTankWaterTemperature` | number | 40-60 | DHW tank target |
| `forcedHotWaterMode` | boolean | `true`, `false`, `null` | DHW priority mode |
| `setHeatFlowTemperatureZone1` | number | null | Advanced: Direct flow control |
| `setCoolFlowTemperatureZone1` | number | null | Not used (heat-only systems) |
| `setHeatFlowTemperatureZone2` | number | null | Zone 2 flow control |
| `setCoolFlowTemperatureZone2` | number | null | Not used |

### Status Fields (GET /api/user/context)

| Field | Type | Meaning |
|-------|------|---------|
| `OperationMode` | string | **STATUS ONLY** - Current 3-way valve position<br/>`"Stop"` = idle<br/>`"HotWater"` = heating DHW<br/>Other = heating zone |
| `Power` | boolean | System on/off |
| `InStandbyMode` | boolean | Standby state |
| `OperationModeZone1` | string | Zone 1 heating method |
| `RoomTemperatureZone1` | number | Current room temp |
| `SetTemperatureZone1` | number | Zone 1 target |
| `TankWaterTemperature` | number | Current DHW temp |
| `SetTankWaterTemperature` | number | DHW target |
| `ForcedHotWaterMode` | boolean | DHW priority enabled |
| `HasZone2` | number | Zone 2 support (0/1) |
| `HasCoolingMode` | boolean | Cooling available (usually false) |
| `IsInError` | boolean | Error state |
| `ErrorCode` | string | Error code if any |

---

## API Endpoints

### Base URL
```
https://melcloudhome.com
```

### Authentication
- Uses OAuth 2.0 + AWS Cognito (same as A2A)
- Session cookies managed automatically
- Session expires ~8 hours
- **CRITICAL:** All requests require `x-csrf: 1` header

---

## 1. Heat Pump Control

### Endpoint
```
PUT /api/atwunit/{unitId}
```

Updates device settings. Supports **partial updates** - only send changed fields, set others to `null`.

### Headers
```http
x-csrf: 1
content-type: application/json; charset=utf-8
referer: https://melcloudhome.com/dashboard
user-agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36...
```

### Request Body Structure
```json
{
  "power": null,
  "setTemperatureZone1": 21,
  "setTemperatureZone2": null,
  "operationModeZone1": null,
  "operationModeZone2": null,
  "setTankWaterTemperature": null,
  "forcedHotWaterMode": null,
  "setHeatFlowTemperatureZone1": null,
  "setCoolFlowTemperatureZone1": null,
  "setHeatFlowTemperatureZone2": null,
  "setCoolFlowTemperatureZone2": null
}
```

**Important:** Only set parameters you want to change (others should be `null`).

### Common Operations

#### Power Control
```json
// Power ON
{"power": true, ...all others null...}

// Power OFF
{"power": false, ...all others null...}
```

#### Zone 1 Temperature
```json
// Set zone temperature to 21°C
{"setTemperatureZone1": 21, ...all others null...}

// Valid range: 10.0 - 30.0 (for underfloor heating)
// Increments: 0.5°C or 1°C depending on device
```

#### DHW Temperature
```json
// Set DHW tank to 50°C
{"setTankWaterTemperature": 50, ...all others null...}

// Valid range: 40 - 60°C
```

#### Operation Modes (Zone 1)
```json
// Room Temperature Mode (thermostat control)
{"operationModeZone1": "HeatRoomTemperature", ...all others null...}

// Flow Temperature Mode (direct control)
{"operationModeZone1": "HeatFlowTemperature", ...all others null...}

// Weather Compensation Curve
{"operationModeZone1": "HeatCurve", ...all others null...}
```

**Mode Descriptions:**
- **HeatRoomTemperature:** Thermostat mode - maintains room at target temperature
- **HeatFlowTemperature:** Direct flow control - sets heating water temperature
- **HeatCurve:** Weather compensation - adjusts based on outdoor temperature

#### Forced Hot Water Mode
```json
// Enable DHW priority ("Heat Now" in UI)
{"forcedHotWaterMode": true, ...all others null...}

// Disable DHW priority ("Auto" in UI)
{"forcedHotWaterMode": false, ...all others null...}
```

**UI Label:** "Auto / Heat Now" toggle
- **Auto** (`false`): DHW heats automatically when below target
- **Heat Now** (`true`): Force DHW heating immediately (priority mode)

**Effect:**
- When enabled: Heat pump prioritizes DHW heating
- Zone 1 heating temporarily suspended
- Automatically returns to normal when DHW reaches target temperature

### Response
```
HTTP 200 OK
Content-Length: 0
```
Empty response body indicates success.

---

## 2. Device Status & Discovery

### Endpoint
```
GET /api/user/context
```

Returns complete user context including all buildings, devices, current states, and capabilities.

**Note:** This endpoint is **shared** between A2A and A2W devices.

### Response Structure
```json
{
  "id": "user-uuid",
  "firstname": "John",
  "lastname": "Doe",
  "email": "user@example.com",
  "language": "en",
  "country": "PL",
  "numberOfDevicesAllowed": 10,
  "numberOfBuildingsAllowed": 2,
  "buildings": [
    {
      "id": "building-uuid",
      "name": "Home",
      "timezone": "Europe/Madrid",
      "airToWaterUnits": [
        {
          "id": "unit-uuid",
          "givenDisplayName": "Heat pump",
          "displayIcon": "Lounge",
          "macAddress": "AABBCCDDEEFF",
          "timeZone": "Europe/Madrid",
          "ftcModel": 3,
          "isConnected": true,
          "isInError": false,
          "settings": [...],
          "capabilities": {...},
          "schedule": [...],
          "scheduleEnabled": true,
          "holidayMode": {...},
          "frostProtection": {...}
        }
      ],
      "airToAirUnits": [...]
    }
  ]
}
```

### Settings Array Format
Settings are returned as name-value pairs:
```json
"settings": [
  {"name": "Power", "value": "True"},
  {"name": "InStandbyMode", "value": "False"},
  {"name": "OperationMode", "value": "Stop"},
  {"name": "OperationModeZone1", "value": "HeatRoomTemperature"},
  {"name": "RoomTemperatureZone1", "value": "21"},
  {"name": "SetTemperatureZone1", "value": "21"},
  {"name": "TankWaterTemperature", "value": "45"},
  {"name": "SetTankWaterTemperature", "value": "50"},
  {"name": "ForcedHotWaterMode", "value": "False"},
  {"name": "HasZone2", "value": "0"},
  {"name": "HasCoolingMode", "value": "False"},
  {"name": "IsInError", "value": "False"},
  {"name": "ErrorCode", "value": ""}
]
```

### Capabilities Object
```json
"capabilities": {
  "hasHotWater": true,
  "maxSetTankTemperature": 60,
  "minSetTankTemperature": 0,
  "minSetTemperature": 10,
  "maxSetTemperature": 30,
  "hasHalfDegrees": false,
  "hasZone2": false,
  "hasThermostatZone1": true,
  "hasThermostatZone2": true,
  "hasHeatZone1": true,
  "hasHeatZone2": false,
  "hasMeasuredEnergyConsumption": false,
  "hasMeasuredEnergyProduction": false,
  "hasEstimatedEnergyConsumption": true,
  "hasEstimatedEnergyProduction": true,
  "ftcModel": 3,
  "hasDemandSideControl": true
}
```

**⚠️ Temperature Range Warning:**
- API-reported ranges may be incorrect (known bug history)
- Use safe defaults: Zone 1: 10-30°C, DHW: 40-60°C
- Verify against physical FTC controller if possible

---

## 3. OperationMode Status Interpretation

**CRITICAL:** `OperationMode` is a **STATUS field**, not a control parameter.

It indicates what the 3-way valve is currently doing:

| Value | Meaning |
|-------|---------|
| `"Stop"` | Zone 1 not heating (target reached or disabled) |
| `"HotWater"` | Currently heating DHW tank |
| `"HeatRoomTemperature"` | Currently heating Zone 1 (room temp mode) |
| `"HeatFlowTemperature"` | Currently heating Zone 1 (flow temp mode) |
| `"HeatCurve"` | Currently heating Zone 1 (curve mode) |

**Usage:**
- **Read this field** to know what device is doing RIGHT NOW
- **Do NOT set this field** - it's automatically determined by system
- Control zone operation via `operationModeZone1` instead

---

## 4. Schedules

### Create/Update Schedule
```
POST /api/atwcloudschedule/{unitId}
```

**Request Body:**
```json
{
  "id": "uuid-v4",
  "days": [1, 2, 3, 4, 5],
  "time": "06:00:00",
  "power": true,
  "setTemperatureZone1": 21,
  "setTemperatureZone2": null,
  "setTankWaterTemperature": 50,
  "forcedHotWaterMode": false,
  "operationModeZone1": 0,
  "operationModeZone2": null
}
```

**Field Details:**
- `id`: Client-generated UUID
- `days`: Array of day numbers (0=Sunday, 1=Monday, ..., 6=Saturday)
- `time`: Time in HH:MM:SS format (24-hour)
- `operationModeZone1`: **INTEGER** (not string like control API)
  - Mapping unknown: likely 0/1/2 for the three modes
  - Requires testing to confirm

### Enable/Disable Schedules
```
PUT /api/atwcloudschedule/{unitId}/enabled
```

**Request Body:**
```json
{
  "enabled": true
}
```

### Delete Schedule
```
DELETE /api/atwcloudschedule/{unitId}/{scheduleId}
```

---

## 5. Holiday Mode

```
POST /api/holidaymode
```

**Request Body:**
```json
{
  "enabled": true,
  "startDate": "2026-01-10T10:00:00",
  "endDate": "2026-01-20T18:00:00",
  "units": {
    "ATW": [
      "unit-uuid-1",
      "unit-uuid-2"
    ]
  }
}
```

**Features:**
- Can apply to **multiple units** simultaneously
- ISO 8601 datetime format
- Set `enabled: false` to deactivate

---

## 6. Frost Protection

```
POST /api/protection/frost
```

**Request Body:**
```json
{
  "enabled": true,
  "min": 9,
  "max": 11,
  "units": {
    "ATW": [
      "unit-uuid"
    ]
  }
}
```

**Purpose:** Prevents system from freezing in cold weather by maintaining minimum temperatures.

---

## 7. Energy Reporting

```
GET /api/telemetry/energy/{unitId}?from=2026-01-01T00:00&to=2026-01-31T23:59&interval=Day&measure=interval_energy_consumed
```

**Measures:**
- `interval_energy_consumed` - Energy used
- `interval_energy_produced` - Energy generated/saved

**Intervals:** Hour, Day, Month

**Note:** Only available if device has energy metering. Check `hasMeasuredEnergyConsumption` in capabilities.

---

## 8. Error Log

```
GET /api/atwunit/{unitId}/errorlog
```

**Response:**
```json
[
  {
    "timestamp": "2026-01-01T06:02:29Z",
    "errorCode": "E4",
    "errorReason": null,
    "clearedTimestamp": null
  }
]
```

---

## Summer Mode (DHW Only, No Heating)

**Problem:** Cannot independently disable Zone 1 heating.

**Solution:** Set Zone 1 target temperature below current room temperature:

```json
{
  "setTemperatureZone1": 10,
  "power": null,
  ...all others null...
}
```

**Result:**
- Room temperature (e.g., 22°C) > target (10°C)
- Zone 1 status: IDLE (no heating needed)
- `OperationMode` changes to "Stop" or "HotWater"
- Heat pump only heats DHW when needed

---

## Unknown/Undocumented Fields

The following fields appear in API responses but their purpose is unclear. **Do not modify these unless their behavior is understood.**

### ProhibitHotWater
- **Location:** Settings array
- **Type:** Boolean (string "True"/"False")
- **Observed value:** Always "False" in all captures
- **Purpose:** Unknown
- **Recommendation:** Always send `null` in control requests

### Additional Unknown Capabilities
The following capability fields appear but their effect is unclear:
- `maxImportPower`: Always 0 in observations
- `maxHeatOutput`: Always 0 in observations
- `temperatureUnit`: Always empty string
- `immersionHeaterCapacity`: Always 0
- `temperatureIncrement`: Always 0
- `temperatureIncrementOverride`: Always empty string
- `refridgerentAddress`: Always 0 (note: typo in API - "refridgerent")

**Recommendation:** Parse these fields but don't rely on them for logic.

---

## Testing Coverage

This API documentation is based on comprehensive testing:

### Data Sources
- **107 captured API calls** from MELCloud Home web application (Recording 2)
- **30 targeted API calls** from focused testing (Recording 3)
- **Community testing** from @pwa-2025 (EHSCVM2D Hydrokit)
- **GitHub Discussion:** #26

### Hardware Tested
- **Model:** EHSCVM2D Hydrokit
- **FTC:** Model 3
- **Configuration:** Single zone (Zone 2: no), DHW support
- **Heating type:** Underfloor heating
- **Location:** Spain (vacation home)

### Operations Tested

**Power Control:**
- ✅ Power ON/OFF (multiple cycles)
- ✅ Rapid sequential changes (1-2 second intervals)

**Temperature Testing:**
- ✅ Zone 1: 10°C, 21°C, 22°C, 23°C, 24°C, 30°C (full range)
- ✅ DHW: 40°C, 45°C, 49°C, 50°C, 51°C, 60°C (full range)
- ✅ Incremental changes (up/down 1°C)

**Operation Modes:**
- ✅ HeatRoomTemperature (primary mode)
- ✅ HeatFlowTemperature (tested 2x)
- ✅ HeatCurve (tested)
- ✅ Mode switching verified

**DHW Control:**
- ✅ Forced hot water mode (4 toggles ON/OFF)
- ✅ DHW temperature changes
- ✅ Priority behavior confirmed

**Advanced Features:**
- ✅ Schedule creation
- ✅ Schedule enable/disable
- ✅ Holiday mode (2 activations)
- ✅ Frost protection
- ✅ Error log retrieval

**Monitoring:**
- ✅ Real-time telemetry (9 measure types)
- ✅ Energy reporting endpoints
- ✅ Multiple time ranges (hourly, daily, monthly)

### Known Limitations
- **Zone 2:** Not tested (test system has hasZone2=false)
- **Cooling mode:** Not tested (heat-only system)
- **Measured energy:** Not tested (system has estimated only)
- **Schedule integer mapping:** Unknown (requires additional testing)

### Temperature Range Bug Investigation
- **Initial bug:** API reported 30-50°C for Zone 1 (incorrect for underfloor)
- **User reported to Mitsubishi:** Bug acknowledged
- **Bug fixed:** Now correctly reports 10-30°C
- **Lesson learned:** API-reported ranges may be unreliable

---

## Polling Best Practices

Based on analysis of 110 API calls over testing session:

### Observed Web App Behavior

**High-frequency polling (telemetry):**
- `/api/telemetry/actual/{unitId}`: Polled every few seconds
- Purpose: Real-time UI updates for graphs
- 51 calls in session (~46% of traffic)

**Medium-frequency polling (state):**
- `/api/user/context`: Polled periodically
- 12 calls in session (~11% of traffic)
- Returns complete state for all devices

**Low-frequency polling (system):**
- `/api/user/systeminvites`: Same frequency as context
- 12 calls in session (~11% of traffic)

**On-demand only:**
- `/api/atwunit/{unitId}/errorlog`: 2 calls (manual refresh)
- `/api/telemetry/energy/{unitId}`: 8 calls (view changes)

### Recommendations for Home Assistant Integration

**Primary state updates:**
```
Interval: 60 seconds minimum
Endpoint: GET /api/user/context
Purpose: Device discovery and state
```

**Error monitoring:**
```
Interval: Periodic (5-15 minutes) or on state change
Endpoint: GET /api/atwunit/{unitId}/errorlog
Purpose: Error detection and notifications
```

### Rate Limiting Considerations
- **Minimum interval:** 60 seconds for UserContext (per A2A experience)
- **Keep it simple:** UserContext provides all essential state (temperatures, operation status)
- **Error logs:** Poll periodically for proactive error detection

---

## Important Notes

### Temperature Ranges
- **Zone 1:** 10-30°C (for underfloor heating systems)
- **DHW:** 40-60°C
- **API bug history:** Initial reports showed 30-50°C for Zone 1 (incorrect)
- **Recommendation:** Use safe hardcoded defaults, don't trust API capabilities blindly

### String vs Integer Enums
- **Control API (PUT /api/atwunit):** Uses STRINGS
  - `"HeatRoomTemperature"`, `"HeatFlowTemperature"`, `"HeatCurve"`
- **Schedule API (POST /api/atwcloudschedule):** Uses INTEGERS
  - `0` = `"HeatRoomTemperature"` (Thermostat mode)
  - `1` = `"HeatFlowTemperature"` (Flow temperature mode)
  - `2` = `"HeatCurve"` (Weather compensation)

### Multi-Unit Operations
- Holiday mode: Supports multiple units in single call
- Frost protection: Supports multiple units in single call
- Regular control: One unit at a time

### Error Codes
Based on observed error logs:

**E4:**
- **Observed in:** Multiple error log entries
- **Typical cause:** Outdoor temperature sensor issues or high pressure
- **Frequency:** Most common error in test system
- **Resolution:** Usually self-clearing after conditions normalize

**Note:** This is a preliminary error code list. Additional codes may exist but were not observed during testing.

---

## Device Information

**Tested with:**
- Model: FTC4 (FTC Model 3)
- Configuration: Single zone (no Zone 2), DHW support
- System type: Underfloor heating + domestic hot water

**API Version:** Current as of January 2026

**Data Source:** 107 API calls captured from MELCloud Home web application + community testing

---

## References

- HAR file analysis: `docs/research/ATW/melcloudhome_com_recording2_anonymized.har`
- Research documentation: `docs/research/ATW/MelCloud_ATW_API_Reference.md`
- For A2A devices: [ata-api-reference.md](ata-api-reference.md)
- Device comparison: [device-type-comparison.md](device-type-comparison.md)
