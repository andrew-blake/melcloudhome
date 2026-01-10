# MelCloud Air-to-Water Heat Pump - API Documentation

## Device Architecture

The Air-to-Water (ATW) heat pump is **ONE physical device** with **TWO functional views** in the UI:
- **ZONE 1** - Space heating control (underfloor heating/radiators)
- **HOT WATER (DHW)** - Domestic hot water control

These are **NOT separate devices** - they are different views of the same heat pump unit.

### Shared vs. Independent Functions

**SHARED (affect entire device):**
- Power ON/OFF
- Holiday mode
- Frost protection
- Schedules (can control both Zone 1 and DHW)

**INDEPENDENT (per function):**
- Zone 1: target temperature, operation mode
- DHW: tank temperature, forced hot water mode

### Physical Limitation
The heat pump uses a **3-way valve** and can only perform ONE task at a time:
- Either heat DHW tank
- OR heat Zone 1
- Cannot do both simultaneously

The system automatically balances between these priorities unless Forced Hot Water mode is enabled.

---

## Base URL
```
https://melcloudhome.com
```

---

## API Endpoints

### 1. Device Control
```
PUT /api/atwunit/{unitId}
```

**Headers:**
```
Content-Type: application/json; charset=utf-8
x-csrf: 1
```

**Request Body:**
```json
{
  "power": true/false/null,
  "setTankWaterTemperature": 50/null,
  "forcedHotWaterMode": true/false/null,
  "setTemperatureZone1": 21/null,
  "setTemperatureZone2": null,
  "operationModeZone1": "HeatRoomTemperature"/"HeatFlowTemperature"/"HeatCurve"/null,
  "operationModeZone2": null,
  "setHeatFlowTemperatureZone1": null,
  "setCoolFlowTemperatureZone1": null,
  "setHeatFlowTemperatureZone2": null,
  "setCoolFlowTemperatureZone2": null
}
```

**Note:** Set only parameters you want to change. All others must be `null`.

**Response:** `HTTP 200 OK` (empty body)

---

### 2. Get Device Status
```
GET /api/user/context
```

**Response includes:**
```json
{
  "buildings": [{
    "airToWaterUnits": [{
      "id": "UNIT_ID",
      "givenDisplayName": "Heat pump",
      "settings": [
        {"name": "Power", "value": "True"},
        {"name": "OperationMode", "value": "HotWater"},
        {"name": "OperationModeZone1", "value": "HeatCurve"},
        {"name": "SetTemperatureZone1", "value": "21"},
        {"name": "RoomTemperatureZone1", "value": "20.5"},
        {"name": "SetTankWaterTemperature", "value": "50"},
        {"name": "TankWaterTemperature", "value": "45"},
        {"name": "ForcedHotWaterMode", "value": "False"},
        {"name": "ProhibitHotWater", "value": "False"}
      ],
      "capabilities": {
        "hasHotWater": true,
        "minSetTemperature": 10,
        "maxSetTemperature": 30,
        "minSetTankTemperature": 40,
        "maxSetTankTemperature": 60
      },
      "holidayMode": {...},
      "frostProtection": {...}
    }]
  }]
}
```

**Key Status Values:**

| Setting | Meaning |
|---------|---------|
| `OperationMode: "Stop"` | Zone 1 not heating (temp reached or disabled) |
| `OperationMode: "HotWater"` | Currently heating DHW |
| `OperationMode: other` | Currently heating Zone 1 |

---

### 3. Schedules

#### Create/Update Schedule
```
POST /api/atwcloudschedule/{unitId}
```

**Request Body:**
```json
{
  "days": [0],                    // 0=Sunday, 1=Monday, ..., 6=Saturday
  "time": "06:00:00",
  "id": "UUID",
  "power": true,

  // DHW settings (can be null)
  "setTankWaterTemperature": 50,
  "forcedHotWaterMode": false,

  // Zone 1 settings (can be null)
  "setTemperatureZone1": 21,
  "setTemperatureZone2": null,
  "operationModeZone1": 2,        // Number! 0/1/2 (not string)
  "operationModeZone2": null
}
```

**Important:**
- ONE schedule event can control both DHW and Zone 1
- `operationModeZone1` uses **numbers** in schedules (not strings like in PUT)
- Set unused parameters to `null`

#### Enable/Disable Schedule
```
PUT /api/atwcloudschedule/{unitId}/enabled
```

**Request Body:**
```json
{
  "enabled": true
}
```

---

### 4. Holiday Mode (SHARED)
```
POST /api/holidaymode
```

**Request Body:**
```json
{
  "enabled": true,
  "startDate": "2025-12-20T10:00:00",
  "endDate": "2025-12-27T18:00:00",
  "units": {
    "ATW": ["UNIT_ID_1", "UNIT_ID_2"]
  }
}
```

**Note:** Holiday mode affects the **entire device** (both Zone 1 and DHW). Can apply to multiple units.

---

### 5. Frost Protection (SHARED)
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
    "ATW": ["UNIT_ID"]
  }
}
```

---

### 6. Telemetry (Real-time Data)
```
GET /api/telemetry/actual/{unitId}
```

**Response:**
```json
{
  "measureData": [
    {
      "deviceId": "UNIT_ID",
      "type": "setTankWaterTemperature",
      "values": [
        {"time": "2025-12-20 10:15:30", "value": "50.0"},
        {"time": "2025-12-20 10:20:30", "value": "51.0"}
      ]
    }
  ]
}
```

**Note:** Polled frequently by web app (every few seconds).

---

### 7. Error Log
```
GET /api/atwunit/{unitId}/errorlog
```

**Response:**
```json
[
  {
    "timestamp": "2025-11-01T06:02:29Z",
    "errorCode": "E4",
    "errorReason": null,
    "clearedTimestamp": null
  }
]
```

---

## Common Operations

### Power Control

**Turn ON:**
```json
PUT /api/atwunit/{unitId}
{"power": true, ...all others null...}
```

**Turn OFF:**
```json
PUT /api/atwunit/{unitId}
{"power": false, ...all others null...}
```

---

### Zone 1 Temperature

**Set to 21°C:**
```json
PUT /api/atwunit/{unitId}
{"setTemperatureZone1": 21, ...all others null...}
```

**Valid range:** 10-30°C (confirmed fixed from previous 30-50°C bug)

---

### DHW Temperature

**Set to 50°C:**
```json
PUT /api/atwunit/{unitId}
{"setTankWaterTemperature": 50, ...all others null...}
```

**Valid range:** 40-60°C

---

### Operation Modes (Zone 1)

**Room Temperature Mode:**
```json
PUT /api/atwunit/{unitId}
{"operationModeZone1": "HeatRoomTemperature", ...all others null...}
```

**Flow Temperature Mode:**
```json
PUT /api/atwunit/{unitId}
{"operationModeZone1": "HeatFlowTemperature", ...all others null...}
```

**Weather Compensation Curve:**
```json
PUT /api/atwunit/{unitId}
{"operationModeZone1": "HeatCurve", ...all others null...}
```

---

### Forced Hot Water Mode

**Enable (priority to DHW):**
```json
PUT /api/atwunit/{unitId}
{"forcedHotWaterMode": true, ...all others null...}
```

**Effect:**
- Heat pump prioritizes DHW heating
- Zone 1 heating temporarily suspended
- Automatically returns to normal when DHW reaches target temperature

**Disable:**
```json
PUT /api/atwunit/{unitId}
{"forcedHotWaterMode": false, ...all others null...}
```

---

## Use Case: Summer Mode (DHW Only, No Heating)

**Problem:** Cannot disable Zone 1 heating independently.

**Solution:** Set Zone 1 target temperature below current room temperature:

```json
PUT /api/atwunit/{unitId}
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

## Important Notes

### Temperature Ranges
- **Zone 1:** 10-30°C (for underfloor heating)
- **DHW:** 40-60°C
- Web app now correctly enforces these ranges (bug fixed)

### API vs. UI Naming
- **API:** `forcedHotWaterMode`
- **Web UI:** "HOT WATER" toggle
- **Mobile UI:** "AUTO / HEAT NOW"
- All refer to the same function

### Operation Mode Formats
- **In PUT requests:** Use strings (`"HeatRoomTemperature"`, `"HeatFlowTemperature"`, `"HeatCurve"`)
- **In schedules:** Use numbers (`0`, `1`, `2`)
- Exact number-to-mode mapping requires testing

### Schedule Behavior
- One schedule can affect both Zone 1 AND DHW
- Not separate schedules per function
- All non-null values in schedule request will be applied

### Holiday Mode
- Single setting affects entire device
- Both UI views (Zone 1 and DHW) show same holiday mode status
- One API call to enable/disable

---

## Device Information

**Tested with:**
- Configuration: Single zone (no Zone 2), DHW support
- System type: Underfloor heating + domestic hot water

**API Version:** Current as of December 2025
