# MelCloud Air-to-Water Heat Pump - Complete API Documentation

## Overview

This documentation is based on **107 API calls** captured from the MelCloudHome web application during comprehensive testing of a Mitsubishi Air-to-Water heat pump system.

**Test Coverage:**

- ✅ Basic power control
- ✅ All operation modes
- ✅ Temperature settings (Zone 1 and DHW)
- ✅ Forced hot water mode
- ✅ Schedules (create, enable/disable)
- ✅ Holiday mode
- ✅ Frost protection
- ✅ Real-time telemetry
- ✅ Error logs
- ✅ Energy reporting

---

## Base URL

```
https://melcloudhome.com
```

---

## API Endpoints Summary

| Endpoint | Method | Purpose | Calls |
|----------|--------|---------|-------|
| `/api/atwunit/{unitId}` | PUT | Control heat pump | 16 |
| `/api/user/context` | GET | Get user & devices data | 12 |
| `/api/telemetry/actual/{unitId}` | GET | Real-time telemetry | 51 |
| `/api/telemetry/energy/{unitId}` | GET | Energy consumption | 8 |
| `/api/atwcloudschedule/{unitId}` | POST | Create schedule | 1 |
| `/api/atwcloudschedule/{unitId}/enabled` | PUT | Enable/disable schedule | 1 |
| `/api/holidaymode` | POST | Configure holiday mode | 2 |
| `/api/protection/frost` | POST | Configure frost protection | 2 |
| `/api/atwunit/{unitId}/errorlog` | GET | Get error history | 2 |
| `/api/user/systeminvites` | GET | Get system invites | 12 |

---

## 1. Heat Pump Control

### Endpoint

```
PUT /api/atwunit/{unitId}
```

### Headers

```
Content-Type: application/json; charset=utf-8
x-csrf: 1
Origin: https://melcloudhome.com
```

### Request Body Structure

```json
{
  "power": true/false/null,
  "setTankWaterTemperature": 50/null,
  "forcedHotWaterMode": true/false/null,
  "setTemperatureZone1": 30/null,
  "setTemperatureZone2": null,
  "operationModeZone1": "HeatRoomTemperature"/"HeatFlowTemperature"/"HeatCurve"/null,
  "operationModeZone2": null,
  "setHeatFlowTemperatureZone1": null,
  "setCoolFlowTemperatureZone1": null,
  "setHeatFlowTemperatureZone2": null,
  "setCoolFlowTemperatureZone2": null
}
```

**Important:** Only set parameters you want to change (others should be `null`).

### Captured Operations

#### Power Control

```json
// Power ON
{"power": true, ...all others null...}

// Power OFF
{"power": false, ...all others null...}
```

#### Operation Modes (Zone 1)

```json
// Heat based on room temperature (thermostat mode)
{"operationModeZone1": "HeatRoomTemperature", ...}

// Heat based on flow temperature (direct control)
{"operationModeZone1": "HeatFlowTemperature", ...}

// Heat based on weather compensation curve
{"operationModeZone1": "HeatCurve", ...}
```

#### Temperature Settings

```json
// Zone 1 temperature (tested range: 30-50°C)
{"setTemperatureZone1": 31, ...}
{"setTemperatureZone1": 39, ...}
{"setTemperatureZone1": 50, ...}

// DHW temperature
{"setTankWaterTemperature": 50, ...}
```

#### Forced Hot Water Mode

```json
// Enable forced DHW heating
{"forcedHotWaterMode": true, ...}

// Disable forced DHW heating
{"forcedHotWaterMode": false, ...}
```

### Response

```
HTTP 200 OK
Content-Length: 0
```

---

## 2. User Context & Device Data

### Endpoint

```
GET /api/user/context
```

### Response Structure

```json
{
  "id": "AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA",
  "firstname": "John",
  "lastname": "Doe",
  "email": "user@example.com",
  "language": "en",
  "country": "PL",
  "numberOfDevicesAllowed": 10,
  "numberOfBuildingsAllowed": 2,
  "buildings": [
    {
      "id": "DDDDDDDD-DDDD-DDDD-DDDD-DDDDDDDDDDDD",
      "name": "MyHome",
      "timezone": "Europe/Madrid",
      "airToWaterUnits": [
        {
          "id": "BBBBBBBB-BBBB-BBBB-BBBB-BBBBBBBBBBBB",
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

### Device Settings (Current State)

```json
"settings": [
  {"name": "Power", "value": "True"},
  {"name": "InStandbyMode", "value": "False"},
  {"name": "OperationMode", "value": "Stop"},
  {"name": "HasZone2", "value": "0"},
  {"name": "OperationModeZone1", "value": "HeatCurve"},
  {"name": "RoomTemperatureZone1", "value": "20.5"},
  {"name": "SetTemperatureZone1", "value": "31"},
  {"name": "ProhibitHotWater", "value": "False"},
  {"name": "TankWaterTemperature", "value": "29"},
  {"name": "SetTankWaterTemperature", "value": "50"},
  {"name": "HasCoolingMode", "value": "False"},
  {"name": "ForcedHotWaterMode", "value": "False"},
  {"name": "IsInError", "value": "False"},
  {"name": "ErrorCode", "value": ""}
]
```

### Device Capabilities

```json
"capabilities": {
  "hasHotWater": true,
  "maxSetTankTemperature": 60,
  "minSetTankTemperature": 0,
  "minSetTemperature": 30,
  "maxSetTemperature": 50,
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

### ⚠️ CRITICAL ISSUE: Temperature Range for Underfloor Heating

**Problem:** The API reports **incorrect temperature ranges** for underfloor heating systems.

**API returns:**

```json
"minSetTemperature": 30,
"maxSetTemperature": 50
```

**Actual valid range (from wall controller):** ~15°C to ~30°C

**Impact:**

- ❌ Web application cannot set realistic temperatures for underfloor heating (typically 20-25°C)
- ❌ Minimum of 30°C is too high for floor heating systems
- ✅ Wall-mounted FTC controller works correctly with proper range

**Recommendation:** HomeAssistant integration should allow users to manually configure correct temperature ranges or ignore API limits and use safe defaults (e.g., 15-35°C).

---

## 3. Real-Time Telemetry

### Endpoint

```
GET /api/telemetry/actual/{unitId}
```

### Purpose

Returns historical values of various parameters. The web application polls this endpoint frequently (every few seconds) to update the UI.

### Response Example

```json
{
  "measureData": [
    {
      "deviceId": "BBBBBBBB-BBBB-BBBB-BBBB-BBBBBBBBBBBB",
      "type": "setTankWaterTemperature",
      "values": [
        {
          "time": "2025-12-14 09:52:39.845000000",
          "value": "60.0"
        },
        {
          "time": "2025-12-14 10:18:40.384000000",
          "value": "50.0"
        }
      ]
    }
  ]
}
```

### Available Data Types

Based on captured data:

- `setTankWaterTemperature` - DHW target temperature history
- Potentially: `roomTemperatureZone1`, `tankWaterTemperature`, `flowTemperature`, `returnTemperature`, etc.

### Usage Pattern

- Called **51 times** during testing session
- Provides time-series data for UI graphs and monitoring
- Essential for real-time status updates

---

## 4. Energy Reporting

### Endpoint

```
GET /api/telemetry/energy/{unitId}
```

### Response Example

```json
{
  "measureData": []
}
```

**Note:** This unit has `hasMeasuredEnergyConsumption: false` and `hasMeasuredEnergyProduction: false`, so energy data is empty. Units with energy meters will return consumption/production data here.

---

## 5. Schedules

### Create/Update Schedule

#### Endpoint

```
POST /api/atwcloudschedule/{unitId}
```

#### Request Body

```json
{
  "days": [0],
  "time": "11:17:00",
  "id": "FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF",
  "power": true,
  "setTankWaterTemperature": 50,
  "forcedHotWaterMode": true,
  "setTemperatureZone1": 31,
  "setTemperatureZone2": null,
  "operationModeZone1": 2,
  "operationModeZone2": null
}
```

#### Field Details

- `days`: Array of day numbers (0=Sunday, 1=Monday, ..., 6=Saturday)
- `time`: Time in HH:MM:SS format (24-hour)
- `id`: UUID for the schedule entry
- `power`: Power state to set
- `setTankWaterTemperature`: DHW temperature
- `forcedHotWaterMode`: Forced DHW mode state
- `setTemperatureZone1`: Zone 1 temperature
- **`operationModeZone1`**: **IMPORTANT - This is a NUMBER, not a string**
  - Likely mapping: `0` = HeatRoomTemperature, `1` = HeatFlowTemperature, `2` = HeatCurve

### Enable/Disable Schedule

#### Endpoint

```
PUT /api/atwcloudschedule/{unitId}/enabled
```

#### Request Body

```json
{
  "enabled": true
}
```

or

```json
{
  "enabled": false
}
```

---

## 6. Holiday Mode

### Endpoint

```
POST /api/holidaymode
```

### Request Body

```json
{
  "enabled": true,
  "startDate": "2025-12-14T11:18:28.435",
  "endDate": "2025-12-17T12:00:00",
  "units": {
    "ATW": [
      "BBBBBBBB-BBBB-BBBB-BBBB-BBBBBBBBBBBB"
    ]
  }
}
```

### Field Details

- `enabled`: `true` to activate, `false` to deactivate
- `startDate`: ISO 8601 datetime (can be in the past or future)
- `endDate`: ISO 8601 datetime
- `units.ATW`: Array of Air-to-Water unit IDs to apply holiday mode to

### Multiple Units

You can include multiple unit IDs:

```json
"units": {
  "ATW": [
    "BBBBBBBB-BBBB-BBBB-BBBB-BBBBBBBBBBBB",
    "CCCCCCCC-CCCC-CCCC-CCCC-CCCCCCCCCCCC"
  ]
}
```

---

## 7. Frost Protection

### Endpoint

```
POST /api/protection/frost
```

### Request Body

```json
{
  "enabled": true,
  "min": 9,
  "max": 11,
  "units": {
    "ATW": [
      "BBBBBBBB-BBBB-BBBB-BBBB-BBBBBBBBBBBB"
    ]
  }
}
```

### Field Details

- `enabled`: Enable/disable frost protection
- `min`: Minimum temperature threshold (°C)
- `max`: Maximum temperature threshold (°C)
- `units.ATW`: Array of unit IDs

### Purpose

Frost protection prevents the system from freezing in cold weather by maintaining minimum temperatures.

---

## 8. Error Log

### Endpoint

```
GET /api/atwunit/{unitId}/errorlog
```

### Response Example

```json
[
  {
    "timestamp": "2025-11-01T06:02:29.6394784Z",
    "errorCode": "E4",
    "errorReason": null,
    "clearedTimestamp": null
  },
  {
    "timestamp": "2025-10-30T13:30:35.6696372Z",
    "errorCode": "E4",
    "errorReason": null,
    "clearedTimestamp": null
  }
]
```

### Field Details

- `timestamp`: When the error occurred (ISO 8601 UTC)
- `errorCode`: Error code (e.g., "E4", "E1", etc.)
- `errorReason`: Additional error information (may be null)
- `clearedTimestamp`: When the error was cleared (null if still active)

### Common Error Codes

- **E4**: Typically related to outdoor temperature sensor issues or high pressure

### Use Cases

- Display error history in HomeAssistant
- Send notifications when new errors occur
- Track system reliability

---

## 9. System Invites

### Endpoint

```
GET /api/user/systeminvites
```

### Response Example

```json
[]
```

### Purpose

Returns pending invitations for guest access to systems. Empty array if no pending invites.

---

## Authentication

The HAR files don't contain direct authentication tokens as cookies were cleared by Chrome. The application uses **session-based authentication**.

### Typical Auth Flow

1. User logs in via web interface
2. Session cookie is set
3. All subsequent API calls include session cookie
4. `x-csrf: 1` header is required for POST/PUT requests

---

## Testing Coverage

### Temperature Tests

| Parameter | Tested Values | Notes |
|-----------|---------------|-------|
| Zone 1 | 30°C, 31°C, 39°C, 50°C | Max tested: 50°C |
| DHW | 50°C | API max: 60°C |

### Operation Modes

- ✅ HeatRoomTemperature
- ✅ HeatFlowTemperature (tested 2x)
- ✅ HeatCurve

### Features Tested

- ✅ Power control (multiple on/off cycles)
- ✅ Forced hot water mode (4 toggles)
- ✅ Schedule creation
- ✅ Schedule enable/disable
- ✅ Holiday mode (2 activations)
- ✅ Frost protection
- ✅ Real-time telemetry monitoring
- ✅ Error log retrieval

---

## Important Notes for HomeAssistant Integration

### 1. Operation Mode Enumeration

**In PUT requests (control):**

- Use **strings**: `"HeatRoomTemperature"`, `"HeatFlowTemperature"`, `"HeatCurve"`

**In schedules:**

- Use **numbers**: `0`, `1`, `2` (mapping unclear, requires testing)

### 2. Temperature Ranges

- **Ignore API-reported ranges** for underfloor heating systems
- Allow user configuration of valid temperature ranges
- Safe defaults: 15-35°C for Zone 1, 40-60°C for DHW

### 3. Polling Strategy

- The web app polls `/api/telemetry/actual/{unitId}` very frequently
- Consider implementing efficient polling with configurable intervals
- Use `/api/user/context` for less frequent full state updates

### 4. Error Handling

- Monitor `/api/atwunit/{unitId}/errorlog` for system errors
- Implement notifications for new error codes
- Display error history in UI

### 5. Schedule Management

- Schedule IDs must be UUIDs
- `operationModeZone1` uses different format (number vs string)
- Multiple schedules per day are supported

### 6. Multi-Unit Support

- Holiday mode and frost protection support multiple units
- Use `units.ATW` array for bulk operations

---

## Known Issues

### 1. Temperature Range Bug

- API reports 30-50°C for Zone 1
- Actual range should be ~15-30°C for underfloor heating
- **Mitsubishi has been notified separately**

### 2. Energy Data

- Not all units support measured energy consumption
- Check `capabilities.hasMeasuredEnergyConsumption` before expecting data

---

## Additional Resources

For questions or additional test scenarios, please create an issue on the HomeAssistant integration repository.

**Test data provided by:** Community user with Mitsubishi Air-to-Water heat pump (FTC Model 3)
**Test date:** 2025-12-14
**Total API calls captured:** 107
**Web application:** <https://melcloudhome.com>
