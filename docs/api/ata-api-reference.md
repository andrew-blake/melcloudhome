# MELCloud Home API Reference - Air-to-Air Units
## Complete Air-to-Air (ATA) API Specification

> **Note:** This document covers Air-to-Air (ATA) units only.
> - For Air-to-Water heat pumps, see [atw-api-reference.md](atw-api-reference.md)
> - For device type comparison, see [device-type-comparison.md](device-type-comparison.md)

**Document Version:** 1.3
**Last Updated:** 2026-07-20
**Device Type:** Air-to-Air Air Conditioning Units
**Method:** Passive UI observation only

---

## About This Document

This is a **complete API reference** documenting all endpoints for Air-to-Air (ATA) devices.

**Implementation Status:** The control endpoints documented here are **fully implemented** in the Home Assistant integration. This documentation serves as both a user reference and contributor guide.

For current integration features, see [README.md](../../README.md).

---

## ⚠️ CRITICAL SAFETY NOTICE

**This API controls production HVAC equipment. Safety guidelines:**

1. **ONLY use values observed from the official MELCloud Home UI**
2. **NEVER send experimental or out-of-range values**
3. **NEVER test edge cases or boundary conditions**
4. **All values in this document were captured by observing the official UI**
5. **When in doubt, observe the UI - do not guess or extrapolate**

**Rationale:** This is production HVAC equipment. Invalid commands could:
- Confuse the system or backend
- Trigger unexpected behavior
- Potentially cause equipment issues
- Generate backend errors

---

## Quick Reference: All Parameters

| Parameter | Type | UI-Observed Values | Notes |
|-----------|------|-------------------|-------|
| `power` | boolean | `true`, `false` | null for no change |
| `operationMode` | string | `"Heat"`, `"Cool"`, `"Automatic"`, `"Dry"`, `"Fan"` | ⚠️ "Automatic" NOT "Auto" |
| `setFanSpeed` | string | `"Auto"`, `"One"`, `"Two"`, `"Three"`, `"Four"`, `"Five"` | ⚠️ Strings, NOT integers |
| `setTemperature` | number | 10.0 - 31.0 (0.5° increments) | Mode-specific ranges apply |
| `vaneVerticalDirection` | string | `"Auto"`, `"Swing"`, `"One"`, `"Two"`, `"Three"`, `"Four"`, `"Five"` | Positions 1-5 observed in docs |
| `vaneHorizontalDirection` | string | `"Auto"`, `"Swing"` (+positions per docs) | Additional positions in earlier docs |
| `temperatureIncrementOverride` | null | Always `null` | Purpose unknown, always null |
| `inStandbyMode` | boolean | `true`, `false` | null for no change |

---

## API Endpoints

### Base URL
```
https://mobile.bff.melcloudhome.com
```

### Hosts

This integration talks to the **mobile BFF** (`mobile.bff.melcloudhome.com`), the host behind the Base URL above. A separate **web host** (`melcloudhome.com`, the Blazor web app used by [docs/research/web-bff-websocket-capture/README.md](../research/web-bff-websocket-capture/README.md)) exposes an equivalent but not always identical `/api/...` surface — same auth server and data model, different path conventions (e.g. mobile's `/monitor/{resource}/{unitId}` vs web's `/api/{resource}`). Where an endpoint below was only observed on one host, its evidence note says which; treat the other host's path as inferred-by-analogy unless stated otherwise.

### Authentication
- Uses OAuth 2.0 PKCE + AWS Cognito (see [../architecture.md](../architecture.md) for details)
- Bearer token authentication
- User-Agent: `MonitorAndControl.App.Mobile/52 CFNetwork/3860.400.51 Darwin/25.3.0`

### Control Endpoint

**PUT** `/monitor/ataunit/{unit_id}`

Updates device settings. Supports **partial updates** - only send changed fields, set others to `null`.

**Headers:**
```http
authorization: Bearer {access_token}
content-type: application/json; charset=utf-8
user-agent: MonitorAndControl.App.Mobile/52 CFNetwork/3860.400.51 Darwin/25.3.0
```

**Request Body:**
```json
{
  "power": null,
  "operationMode": "Heat",
  "setFanSpeed": null,
  "vaneHorizontalDirection": null,
  "vaneVerticalDirection": null,
  "setTemperature": null,
  "temperatureIncrementOverride": null,
  "inStandbyMode": null
}
```

**Response:**
- Status: `200 OK`
- Body: Empty (Content-Length: 0)

### Device Status Endpoint

**GET** `/context`

Returns complete device list with current states and capabilities.

---

## Parameter Details (UI-Verified)

### 1. Operation Mode (`operationMode`)

**Type:** `string`
**UI-Observed Values:**

| UI Display | API Value | Verified |
|------------|-----------|----------|
| HEAT | `"Heat"` | ✅ Observed |
| COOL | `"Cool"` | ✅ Observed |
| AUTO | `"Automatic"` | ✅ Observed |
| DRY | `"Dry"` | ✅ Observed |
| FAN | `"Fan"` | ✅ Observed |

**⚠️ Important Discovery:** AUTO mode in UI maps to `"Automatic"` in API (NOT `"Auto"`).

**Example Request:**
```json
{
  "power": null,
  "operationMode": "Cool",
  "setFanSpeed": null,
  "vaneHorizontalDirection": null,
  "vaneVerticalDirection": null,
  "setTemperature": null,
  "temperatureIncrementOverride": null,
  "inStandbyMode": null
}
```

**HA Integration Mapping:**
```python
OPERATION_MODE_MAP = {
    "Heat": "heat",
    "Cool": "cool",
    "Automatic": "auto",
    "Dry": "dry",
    "Fan": "fan_only"
}
```

---

### 2. Fan Speed (`setFanSpeed`)

**Type:** `string` (⚠️ NOT integer!)
**UI-Observed Values:**

| UI Display | API Value | Verified |
|------------|-----------|----------|
| AUTO | `"Auto"` | ✅ Observed |
| 1 FAN SPEED | `"One"` | ✅ Observed |
| 2 FAN SPEED | `"Two"` | 📝 Inferred (consistent pattern) |
| 3 FAN SPEED | `"Three"` | ✅ Observed |
| 4 FAN SPEED | `"Four"` | 📝 Inferred (consistent pattern) |
| 5 FAN SPEED | `"Five"` | ✅ Observed |

**⚠️ Critical Correction:** Earlier documentation incorrectly stated fan speeds were integers (0-5).
The actual API uses **string values**: `"Auto"`, `"One"`, `"Two"`, `"Three"`, `"Four"`, `"Five"`.

**Example Request:**
```json
{
  "power": null,
  "operationMode": null,
  "setFanSpeed": "Three",
  "vaneHorizontalDirection": null,
  "vaneVerticalDirection": null,
  "setTemperature": null,
  "temperatureIncrementOverride": null,
  "inStandbyMode": null
}
```

**HA Integration (✅ IMPLEMENTED as of v2.0.0-beta.2):**

The integration normalizes API capitalized values to lowercase for Home Assistant:
```python
# API Layer (matches MELCloud API exactly)
API values: "Auto", "One", "Two", "Three", "Four", "Five"

# Integration Layer (normalized to lowercase per HA standards)
HA values: "auto", "one", "two", "three", "four", "five"

# Normalization mapping (const_ata.py::normalize_to_api)
"auto" → "Auto"
"one" → "One"
"two" → "Two"
"three" → "Three"
"four" → "Four"
"five" → "Five"
```

**Architecture:** The climate entity returns lowercase values to Home Assistant. When sending control commands, values are converted back to capitalized form for the API.

**Note:** Uses lowercase words (e.g., "one", "two") rather than numbers ("1", "2") for consistency with other climate attributes and Home Assistant conventions.

---

### 3. Temperature (`setTemperature`)

**Type:** `number` (float)
**UI-Observed Range:** 10.0 - 31.0°C in 0.5° increments

**Mode-Specific Ranges** (from device capabilities):

| Mode | Minimum | Maximum |
|------|---------|---------|
| Heat | 10°C | 31°C |
| Cool/Dry | 16°C | 31°C |
| Automatic | 16°C | 31°C |

**Device Capabilities:**
- `hasHalfDegreeIncrements`: `true`
- `hasExtendedTemperatureRange`: `true`
- Ranges returned in GET `/context` response

**Example Request:**
```json
{
  "power": null,
  "operationMode": null,
  "setFanSpeed": null,
  "vaneHorizontalDirection": null,
  "vaneVerticalDirection": null,
  "setTemperature": 20.5,
  "temperatureIncrementOverride": null,
  "inStandbyMode": null
}
```

**HA Integration:**
- Maps directly to HA climate `target_temperature`
- Use device capability ranges for min/max
- Support 0.5° precision

---

### 4. Vertical Vane Direction (`vaneVerticalDirection`)

**Type:** `string`
**UI-Observed Values:**

| UI Display | API Value | Verified |
|------------|-----------|----------|
| AUTO | `"Auto"` | ✅ Observed |
| SWING | `"Swing"` | ✅ Observed |
| Position 1 | `"One"` | 📝 From earlier docs |
| Position 2 | `"Two"` | 📝 From earlier docs |
| Position 3 | `"Three"` | 📝 From earlier docs |
| Position 4 | `"Four"` | 📝 From earlier docs |
| Position 5 | `"Five"` | 📝 From earlier docs |

**Note:** Positions 1-5 follow the same naming pattern as fan speeds, documented in earlier API discovery.

**Example Request:**
```json
{
  "power": null,
  "operationMode": null,
  "setFanSpeed": null,
  "vaneHorizontalDirection": null,
  "vaneVerticalDirection": "Swing",
  "setTemperature": null,
  "temperatureIncrementOverride": null,
  "inStandbyMode": null
}
```

**HA Integration (✅ IMPLEMENTED as of v2.0.0-beta.2):**

The integration normalizes API capitalized values to lowercase for Home Assistant:
```python
# API Layer (matches MELCloud API exactly)
API values: "Auto", "Swing", "One", "Two", "Three", "Four", "Five"

# Integration Layer (normalized to lowercase per HA standards)
HA values: "auto", "swing", "one", "two", "three", "four", "five"

# Normalization mapping (const_ata.py::normalize_to_api)
"auto" → "Auto"
"swing" → "Swing"
"one" → "One"
"two" → "Two"
"three" → "Three"
"four" → "Four"
"five" → "Five"
```

**Architecture:** The climate entity returns lowercase values to Home Assistant. When sending control commands, values are converted back to capitalized form for the API.

---

### 5. Horizontal Vane Direction (`vaneHorizontalDirection`)

**Type:** `string`
**UI-Observed Values:**

| UI Display | API Value | Verified |
|------------|-----------|----------|
| AUTO | `"Auto"` | ✅ Observed |
| SWING | `"Swing"` | ✅ Observed |
| LEFT | `"Left"` | 📝 From earlier docs |
| CENTER LEFT | `"LeftCentre"` | 📝 From earlier docs |
| CENTER | `"Centre"` | 📝 From earlier docs |
| CENTER RIGHT | `"RightCentre"` | 📝 From earlier docs |
| RIGHT | `"Right"` | 📝 From earlier docs |

**Note:** Positional values documented in earlier API discovery. Auto and Swing confirmed through UI observation.

**Example Request:**
```json
{
  "power": null,
  "operationMode": null,
  "setFanSpeed": null,
  "vaneHorizontalDirection": "Auto",
  "vaneVerticalDirection": null,
  "setTemperature": null,
  "temperatureIncrementOverride": null,
  "inStandbyMode": null
}
```

**HA Integration (✅ IMPLEMENTED as of v2.0.0-beta.2):**

The integration normalizes API capitalized values to lowercase for Home Assistant:
```python
# API Layer (matches MELCloud API exactly, British spelling)
API values: "Auto", "Swing", "Left", "LeftCentre", "Centre", "RightCentre", "Right"

# Integration Layer (normalized to lowercase per HA standards)
HA values: "auto", "swing", "left", "leftcentre", "centre", "rightcentre", "right"

# Normalization mapping (const_ata.py::normalize_to_api)
"auto" → "Auto"
"swing" → "Swing"
"left" → "Left"
"leftcentre" → "LeftCentre"
"centre" → "Centre"
"rightcentre" → "RightCentre"
"right" → "Right"
```

**Architecture:** The climate entity returns lowercase values to Home Assistant. When sending control commands, values are converted back to capitalized form for the API.

**Note:** Uses lowercase words without underscores (e.g., "leftcentre" not "center_left") for consistency with other climate attributes.

---

### 6. Power (`power`)

**Type:** `boolean`
**Values:** `true` (on), `false` (off), `null` (no change)

Observed in earlier testing. Not re-tested in this session to avoid unnecessary equipment cycling.

---

### 7. Standby Mode (`inStandbyMode`)

**Type:** `boolean`
**Values:** `true`, `false`, `null` (no change)

Documented in device capabilities. Not tested in this session.

---

### 8. Temperature Increment Override (`temperatureIncrementOverride`)

**Type:** Unknown (always `null` in observations)
**Observed Value:** Always `null` in every request

**Status:** Purpose unknown. Always included in payload but always set to `null`.

---

## Complete Request Examples

### Change Mode to Cool
```json
{
  "power": null,
  "operationMode": "Cool",
  "setFanSpeed": null,
  "vaneHorizontalDirection": null,
  "vaneVerticalDirection": null,
  "setTemperature": null,
  "temperatureIncrementOverride": null,
  "inStandbyMode": null
}
```

### Set Fan Speed to 3
```json
{
  "power": null,
  "operationMode": null,
  "setFanSpeed": "Three",
  "vaneHorizontalDirection": null,
  "vaneVerticalDirection": null,
  "setTemperature": null,
  "temperatureIncrementOverride": null,
  "inStandbyMode": null
}
```

### Set Temperature to 22.5°C
```json
{
  "power": null,
  "operationMode": null,
  "setFanSpeed": null,
  "vaneHorizontalDirection": null,
  "vaneVerticalDirection": null,
  "setTemperature": 22.5,
  "temperatureIncrementOverride": null,
  "inStandbyMode": null
}
```

### Multiple Changes at Once
```json
{
  "power": true,
  "operationMode": "Heat",
  "setFanSpeed": "Auto",
  "vaneHorizontalDirection": "Swing",
  "vaneVerticalDirection": "Auto",
  "setTemperature": 21.0,
  "temperatureIncrementOverride": null,
  "inStandbyMode": false
}
```

---

## Home Assistant Integration Mapping

### Climate Entity Attributes

| HA Attribute | API Parameter | Notes |
|--------------|---------------|-------|
| `hvac_mode` | `operationMode` | See OPERATION_MODE_MAP |
| `target_temperature` | `setTemperature` | Direct number mapping |
| `fan_mode` | `setFanSpeed` | See FAN_SPEED_MAP |
| `swing_mode` | `vaneVerticalDirection` / `vaneHorizontalDirection` | May need to combine or choose primary |
| `current_temperature` | From GET response `RoomTemperature` | Read-only |

### Implementation Notes

1. **HVAC Modes:** Map `"Automatic"` to `auto`, others are straightforward
2. **Fan Modes:** Convert string values to display-friendly names
3. **Temperature Precision:** Support 0.5° steps
4. **Swing Modes:** Decision needed on how to expose both horizontal and vertical vanes
5. **Capabilities:** Use device capabilities from GET response for min/max temps

---

## Key Discoveries & Corrections

### 🔴 Critical Corrections to Earlier Documentation

1. **Fan Speeds are STRINGS, not integers**
   - ❌ Old: `0, 1, 2, 3, 4, 5` (integers)
   - ✅ New: `"Auto", "One", "Two", "Three", "Four", "Five"` (strings)

2. **AUTO operation mode is "Automatic"**
   - ❌ Old assumption: `"Auto"`
   - ✅ Actual: `"Automatic"`

### 📝 Confirmed Documentation

3. **Temperature ranges are mode-specific**
   - Retrieved from device capabilities
   - Heat mode allows lower temps (10°C minimum)

4. **Partial updates work correctly**
   - Only changed fields need non-null values
   - Confirmed across all parameter types

5. **Response is always empty**
   - Status 200 with Content-Length: 0
   - No response body returned

---

## Testing Methodology

**All values verified through:**
1. Opening MELCloud Home UI in browser with DevTools
2. Making changes through official UI controls
3. Capturing PUT requests in Network tab
4. Recording exact JSON payloads sent by UI

**No experimental values were sent to the API.**
**No out-of-range values were tested.**
**Safety-first approach maintained throughout.**

---

## Device Capabilities

Device capabilities are returned in GET `/context` response. Key capabilities:

```json
{
  "capabilities": {
    "numberOfFanSpeeds": 5,
    "minTempHeat": 10,
    "maxTempHeat": 31,
    "minTempCoolDry": 16,
    "maxTempCoolDry": 31,
    "minTempAutomatic": 16,
    "maxTempAutomatic": 31,
    "hasHalfDegreeIncrements": true,
    "hasExtendedTemperatureRange": true,
    "hasAutomaticFanSpeed": true,
    "hasSwing": true,
    "hasAirDirection": true,
    "hasCoolOperationMode": true,
    "hasHeatOperationMode": true,
    "hasAutoOperationMode": true,
    "hasDryOperationMode": true,
    "hasStandby": true
  }
}
```

Use these capabilities to:
- Set temperature min/max in HA
- Enable/disable HVAC modes based on device support
- Determine available fan speeds
- Check for vane/swing support

---

## Telemetry Endpoints

### Trend Summary (Temperature Reports)

**GET** `/report/v1/trendsummary`

Returns historical temperature data for chart display. Used by integration to fetch outdoor temperature.

**Query Parameters:**
- `unitId` - Device UUID
- `period` - Report period: `Hourly` or `Daily`
- `from` - Start datetime (ISO 8601: `YYYY-MM-DDTHH:MM:SS.0000000`)
- `to` - End datetime (ISO 8601: `YYYY-MM-DDTHH:MM:SS.0000000`)

**Note:** With `period=Daily` the API ignores `from`/`to` and returns all available historical data (observed: 200+ datapoints spanning several weeks). With `period=Hourly` the API only includes data for the requested window, so idle units that haven't run recently return an empty dataset.

**Example Request:**

```
GET /report/v1/trendsummary?unitId=0efce33f-5847-4042-88eb-aaf3ff6a76db&period=Daily&from=2026-02-02T12:30:00.0000000&to=2026-02-03T12:30:00.0000000
```

**Response:**

```json
{
  "datasets": [
    {
      "label": "REPORT.TREND_SUMMARY_REPORT.DATASET.LABELS.ROOM_TEMPERATURE",
      "data": [{"x": "2026-02-03T12:00:00", "y": 17.0}],
      "backgroundColor": "#F1995D",
      "borderColor": "#F1995D",
      "yAxisId": "yTemp",
      "pointRadius": 0,
      "lineTension": 0,
      "borderWidth": 2,
      "stepped": true,
      "spanGaps": false,
      "isNonInteractive": false
    },
    {
      "label": "REPORT.TREND_SUMMARY_REPORT.DATASET.LABELS.SET_TEMPERATURE",
      "data": [{"x": "2026-02-03T12:00:00", "y": 19.0}]
    },
    {
      "label": "REPORT.TREND_SUMMARY_REPORT.DATASET.LABELS.OUTDOOR_TEMPERATURE",
      "data": [{"x": "2026-02-03T12:00:00", "y": 11.0}]
    }
  ],
  "annotations": []
}
```

**Integration Usage:**

- Polled every 30 minutes (initial probe on startup, then periodic updates)
- Uses `period=Daily` — returns all available historical data regardless of `from`/`to`
- Extracts latest outdoor temperature value from OUTDOOR_TEMPERATURE dataset (last array element)
- Not all devices have outdoor sensors (capability auto-detected at runtime)
- Dataset absent for devices without outdoor sensor; `Hourly` period also returns empty dataset for idle units

**Notes:**

- Response includes chart styling metadata (colors, borders, etc.)
- Multiple temperature datasets returned in single call
- Used by MELCloud web UI for temperature graphs
- Integration sends a 24-hour `from`/`to` window but Daily period ignores it and returns all historical data

### Trend Summary — Legacy Web Host Variant (not integrated)

A second `trendsummary` endpoint exists on the **legacy web host** (`melcloudhome.com`), captured via a browser HAR review of the web app on 2026-07-11 (a separate, broader pass than the [Web BFF & WebSocket capture](../research/web-bff-websocket-capture/README.md), which doesn't include this endpoint). It is **not** the endpoint the integration uses — that's the mobile BFF one documented above — but it differs enough to be worth recording separately rather than assuming it's identical:

```
GET /api/v1/report/trendsummary?unitId=<uuid>&period=Hourly|Daily|Weekly|Monthly&from=<iso>&to=<iso>
```
*(web host: `melcloudhome.com` — the mobile-BFF equivalent above is a different endpoint, not a host variant of this one; see [Hosts](#hosts))*

- Two extra `period` values observed that the mobile BFF endpoint above wasn't seen to support: `Weekly`, `Monthly`.
- `Hourly` period returned data at roughly **3-minute resolution** in a live driven re-capture (2026-07-23: 211 datapoints over an 11h13m window) — finer-grained than anything the mobile BFF variant was observed to return, and a candidate source for HA long-term statistics import if this endpoint is ever integrated. (Corrects an earlier "~2-minute" estimate from the original passive review — the actual interval may vary with how recently the unit was reporting.)
- Top-level response shape is an **array** of report objects, rather than the single flat `{datasets, annotations}` object the mobile BFF endpoint returns above. Each report object: `{reportPeriod, timeUnit, stepSize, from, to, datasets: [...], annotations, previousTriggers}`. `datasets[].id` values observed: `room_temperature`, `set_temperature`, `outside_temperature`. `reportPeriod` is a confirmed int enum: `0`=Hourly, `2`=Weekly, `3`=Monthly (`1`=Daily is inferred by position, not directly observed — Daily's own request wasn't re-captured with this session's tooling, only the pre-existing passive-review evidence). `previousTriggers` is present here too (empty array in every capture) — related to, but distinct from, the dedicated endpoint below.
- **Resolved 2026-07-23** (was previously unconfirmed — the original capture's requests were browser-aborted before completing): `POST /api/v1/report/trendsummary/previous` returns `200` with a genuinely different response shape from the main endpoint — `{data: [{id, data: [{x, y}, ...]}], reportTimeAnnotations: [], previousTriggers: []}` (flat `data` array keyed by dataset `id`, no `label`/`reportPeriod` wrapper). Confirmed request body:

  ```json
  {
    "unitId": "<unit UUID>",
    "triggers": [
      { "trigger": "<iso datetime>", "measure": "room_temperature", "value": 25.5 },
      { "trigger": "9999-12-31T23:59:59.9999999", "measure": "set_temperature", "value": null },
      { "trigger": "<iso datetime>", "measure": "outside_temperature", "value": 29 }
    ],
    "before": "<iso datetime>",
    "currentPeriod": "<iso datetime>",
    "period": 0
  }
  ```

  `triggers` appears to carry, per measure, the timestamp/value of the last-seen datapoint the client already has (with a sentinel far-future date for a measure with no value yet) — consistent with an incremental "give me anything since my last known point per series" contract, though the exact selection logic on the server side wasn't reverse-engineered. `period: 0` matches the `reportPeriod` enum above (this call was triggered from the Hourly tab).

⚠️ Neither endpoint has been re-verified against the mobile BFF host, and both were captured on an ATA-only account (no ATW units to confirm behavior there).

**Evidence Level:** Two sources: a passive browser HAR review, 2026-07-11 (dev account; original raw capture file no longer on disk), and a live Claude-in-Chrome-driven re-capture, 2026-07-23 (real account, read-only GET/POST calls against the actual `/trendsummary` chart UI — no settings were changed on any unit). The 2026-07-23 session resolved the `/previous` endpoint's response shape and added the `reportPeriod`/`timeUnit`/`stepSize`/`from`/`to` fields, which the 2026-07-11 pass hadn't captured. The 2026-07-11 raw capture file is no longer available; the 2026-07-23 session's capture is committed as [docs/research/scenes-trendsummary-capture/](../research/scenes-trendsummary-capture/README.md) — a JSON log of the intercepted requests (not a native HAR export; see that folder's README for the technique and its limitations), anonymized before commit.

---

## Scenes

**Implementation Status:** Not integrated in the Home Assistant integration — documented for reference only. Home Assistant has its own scene/scripting system; whether to surface MELCloud Home's cloud scenes as HA entities is an open question, similar to the Schedules discussion at [#174](https://github.com/andrew-blake/melcloudhome/issues/174).

All endpoints below were directly observed on the **legacy web host** (`melcloudhome.com`, see [Hosts](#hosts)) via the 2026-07-11 browser HAR review, supplemented by a live Claude-in-Chrome-driven re-capture on 2026-07-23 (full round trip: created a real test scene on a live ATA unit, enabled it, disabled it, edited it, deleted it — cleaned up immediately after; enabling briefly and deliberately powered the unit on at a safe, UI-observed setting, restored to its original off state afterward). Not re-verified against the mobile BFF host; captured on an ATA-only account, so cross-device-type (ATW) support is unconfirmed for the request/response shapes below, but see the confirmed `atwSceneSettings` note under Create Scene.

**Behavioral note (2026-07-23):** Enabling a scene applies its settings to the target unit(s) **immediately** — confirmed by watching the physical unit power on, switch to Cool, and set 25°C in real time upon enabling a test scene, matching the scene's configured settings exactly. This is not a passive "favorite" flag; enabling a scene is equivalent to sending its settings directly to the control endpoint. In the web UI, clicking a scene's tile in the Scenarios list toggles it enabled/disabled directly (no confirmation step) — the same action that hits the Enable/Disable endpoints below.

### List Scenes

```
GET /api/user/scenes
```
*(web host: `melcloudhome.com`)*

Returns an array of scene objects for the authenticated user.

### Create Scene

```
POST /api/scene
```
*(web host: `melcloudhome.com`)*

**Request Body (fields observed):**

```json
{
  "id": "00000000-0000-0000-0000-000000000000",
  "userId": "",
  "name": "<scene name>",
  "enabled": true,
  "icon": "HomeIcon",
  "ataSceneSettings": [
    {
      "unitId": "<unit UUID>",
      "ataSettings": {
        "power": true,
        "operationMode": 3,
        "setFanSpeed": 5,
        "vaneHorizontalDirection": 3,
        "vaneVerticalDirection": 0,
        "setTemperature": 21.0,
        "temperatureIncrementOverride": null,
        "inStandbyMode": null
      },
      "previousSettings": null
    }
  ]
}
```

**Response** (from `GET /api/user/scenes` after creating, 2026-07-23): a freshly server-assigned UUID, not the all-zero placeholder — confirming the server does assign its own ID rather than persisting whatever the client sent. **Still not confirmed which**: the exact Create request body couldn't be re-captured in the 2026-07-23 session (see Evidence Level note below on this specific gap), so whether the client actually sends the all-zero GUID (as originally observed 2026-07-11) and the server replaces it, or sends something else, remains only 2026-07-11-sourced evidence.

**Response also confirmed to include `atwSceneSettings` (2026-07-23):** present as `[]` on this ATA-only account — resolving the naming-symmetry guess below from "not observed" to "confirmed key exists, empty when unused." Whether it's ever populated (i.e. whether a scene can mix ATA and ATW units) is still unconfirmed.

**Field Details:**

- `id`: sent as the all-zero GUID `00000000-0000-0000-0000-000000000000` on create per the 2026-07-11 capture — the 2026-07-23 re-capture confirms the *response* gets a real server-assigned ID either way, but couldn't re-confirm what the client actually sends (see above).
- `ataSceneSettings`: array, one entry per ATA unit included in the scene, keyed by `unitId`.
- `ataSettings`: same field set as the control endpoint (`PUT /monitor/ataunit/{id}`, documented above) — `power`, `operationMode`, `setFanSpeed`, `vaneHorizontalDirection`, `vaneVerticalDirection`, `setTemperature`, `temperatureIncrementOverride`, `inStandbyMode` — **but int-encoded**, not the strings the control endpoint uses (see mapping below).
- `previousSettings`: observed as `null` in every capture; plausibly a rollback/undo slot, not confirmed.

**Enum mapping — POST sends ints, GET returns strings (confirmed both directions on this endpoint):**

| Field | POST value (int) | GET value (string) |
|-------|-------------------|---------------------|
| `operationMode` | `3` | `"cool"` |
| `setFanSpeed` | `5` | `"five"` |
| `vaneHorizontalDirection` | `3` | `"centre"` |
| `vaneVerticalDirection` | `0` | `"auto"` |

This same int/string duality is also confirmed directly on the Schedules endpoint — see [#195](https://github.com/andrew-blake/melcloudhome/pull/195). Here it's observed on both the request and response side of this endpoint, so the mapping pairs above can be treated as confirmed (for these specific values; other positions/modes weren't exercised in the capture).

### Get Scene

```
GET /api/scene/{sceneId}
```
*(web host: `melcloudhome.com`)*

**New endpoint, confirmed 2026-07-23** — fetches a single scene by ID; the web UI calls this when opening a scene for editing. Confirmed via browser network monitoring (method, URL, and `200` status all observed directly); the response body itself couldn't be captured in this session (see Evidence Level note below) but is presumably shaped like one entry of the `GET /api/user/scenes` array.

### Update Scene

```
PUT /api/scene/{sceneId}
```
*(web host: `melcloudhome.com`)*

**Corrects earlier documentation** — this section previously assumed Update reused `POST /api/scene` (same as Create). **Confirmed 2026-07-23 via browser network monitoring: Update is actually `PUT` to the scene's own ID-scoped URL**, not a re-POST to the collection endpoint. The request/response bodies couldn't be captured in this session (see Evidence Level note below), so the exact shape (flat vs. nested, whether `id` is repeated in the body) is unconfirmed — unlike Schedules' Update, don't assume the two share a shape.

### Enable Scene

```
PUT /api/scene/{sceneId}/enable
```
*(web host: `melcloudhome.com`)*

Empty body, confirmed `200` with an empty response. Sets `enabled: true`. **Confirmed 2026-07-23: this immediately applies the scene's settings to the target unit(s)** — verified by watching a real unit power on and change mode/temperature in real time upon enabling a test scene (see the Behavioral note above).

### Disable Scene

```
PUT /api/scene/{sceneId}/disable
```
*(web host: `melcloudhome.com`)*

**New endpoint, confirmed 2026-07-23** — previously assumed not to exist as a dedicated path ("disabling likely goes through the general update instead"). Empty request body, empty `200` response, confirmed via the web UI: clicking an already-enabled scene's tile calls this and flips `enabled` back to `false` in the subsequent `GET /api/user/scenes` response. Unlike Enable, disabling does not appear to send any command to the unit (the unit's state was left as Enable had set it; disabling only stops the scene from being "active", it doesn't revert the unit).

### Delete Scene

```
DELETE /api/scene/{sceneId}
```
*(web host: `melcloudhome.com`)*

Confirmed via browser network monitoring, 2026-07-23 (method/URL/status only — request has no body to capture). Path matches the original 2026-07-11 observation exactly.

**Evidence Level for this 2026-07-23 session's gaps:** the same injected `fetch`/`XMLHttpRequest` hook that successfully captured full request/response bodies for List, Create, Enable, and Disable did **not** fire for Get-single, Update, or Delete, despite all three being confirmed as real `200` calls via the browser's own network monitor. The pattern doesn't correlate with anything obvious (URL shape, HTTP method, or path parameters — Enable/Disable are equally ID-scoped and were captured fine), and wasn't root-caused in this session; flagging it here as a known gap in this capture technique rather than a claim about the API itself. Anyone re-capturing these three endpoints should try a different interception approach (e.g. a proxy-level tool like mitmproxy instead of a page-level JS hook). The captured session (everything the hook *did* see, plus the network-monitor-only entries for what it didn't) is committed anonymized at [docs/research/scenes-trendsummary-capture/](../research/scenes-trendsummary-capture/README.md).

---

## Error Handling

**Observed Responses:**
- Success: `200 OK` with empty body
- All test requests succeeded

**Best Practices:**
1. Validate against device capabilities before sending
2. Only send values observed from UI
3. Use null for unchanged parameters
4. Include all 8 parameters in every request
5. Check for 401 (session expired) and re-authenticate

---

## Session Management

- Bearer token authentication via OAuth 2.0 PKCE
- Access token expires periodically; use refresh token to renew
- 401 response indicates need to refresh token
- Content-Type for data endpoints: `text/plain; charset=utf-8` (token endpoint returns `application/json`)

---

## Related Documentation

- **[Architecture Overview](../architecture.md)** - System design and component interactions
- **[Testing Best Practices](../testing-best-practices.md)** - Home Assistant integration patterns
- **[Contributing Guide](../../CONTRIBUTING.md)** - Development workflow and standards
- **[ATW API Reference](atw-api-reference.md)** - Air-to-Water heat pump API
- **[Device Type Comparison](device-type-comparison.md)** - ATA vs ATW API differences
- **[Web BFF & WebSocket Capture](../research/web-bff-websocket-capture/README.md)** - Related web-app HAR capture (WebSocket + `cloudschedule`); Scenes and legacy-web Trend Summary above come from a separate, broader HAR review the same week
- **[Scenes & Trend Summary Capture](../research/scenes-trendsummary-capture/README.md)** - Anonymized capture backing the Scenes and Trend Summary legacy-variant sections above

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-11-16 | Initial comprehensive API reference with UI-verified values |
| 1.3 | 2026-07-20 | Added Scenes section and legacy-web Trend Summary variant, sourced from 2026-07-11 web-app HAR capture |

**Data Collection Session:** 2025-11-16
**Equipment:** Mitsubishi Electric air conditioning system
**Location:** Dining Room unit (0efce33f-5847-4042-88eb-aaf3ff6a76db)
