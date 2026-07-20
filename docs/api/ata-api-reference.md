# MELCloud Home API Reference - Air-to-Air Units
## Complete Air-to-Air (ATA) API Specification

> **Note:** This document covers Air-to-Air (ATA) units only.
> - For Air-to-Water heat pumps, see [atw-api-reference.md](atw-api-reference.md)
> - For device type comparison, see [device-type-comparison.md](device-type-comparison.md)

**Document Version:** 1.4
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

---

## Schedules

**Implementation Status:** Not integrated in the Home Assistant integration — documented for reference only. Home Assistant has its own automation/scheduler, so exposing cloud-side schedules may be out of scope; see [#174](https://github.com/andrew-blake/melcloudhome/issues/174) for the maintainer discussion this is bundled into.

All three write operations below (create, update, delete) were directly observed and confirmed on 2026-07-20 via a live, driven capture against the **legacy web host** (`melcloudhome.com`) — three real schedule entries were created through the actual UI, edited, and deleted again, with request bodies captured via an injected `fetch`/`XHR` interceptor rather than passively reviewed from a HAR file. This superseded and resolved several items earlier documentation here had flagged as inferred-not-observed (see Evidence Level below).

### Create Schedule

```
POST /api/cloudschedule/{unitId}
```

**Request Body (confirmed, flat shape):**

```json
{
  "id": "11111111-1111-4111-8111-111111111111",
  "days": [2],
  "time": "18:16:00",
  "enabled": false,
  "power": true,
  "operationMode": 1,
  "setPoint": 26,
  "vaneVerticalDirection": 0,
  "vaneHorizontalDirection": 3,
  "setFanSpeed": 0
}
```

### Update Schedule

```
PUT /api/cloudschedule/{unitId}
```

⚠️ **Different from Create**: same base URL (no schedule ID in the path — it's the same URL Create posts to, just a different HTTP method) and a **nested** body, not the flat shape Create uses:

```json
{
  "id": "22222222-2222-4222-8222-222222222222",
  "schedule": {
    "id": "22222222-2222-4222-8222-222222222222",
    "days": [1, 0],
    "time": "18:12:00",
    "enabled": false,
    "power": true,
    "operationMode": 3,
    "setPoint": 26,
    "vaneVerticalDirection": 1,
    "vaneHorizontalDirection": 3,
    "setFanSpeed": 3
  }
}
```

**Field Details (Create and Update):**

- `id`: Client-generated UUID (a real random v4, not a placeholder) — confirmed the client, not the server, mints the schedule ID.
- `days`: Array of day numbers, **confirmed** `0=Sunday, 1=Monday, 2=Tuesday, ..., 6=Saturday` — same convention as the ATW schedule API ([atw-api-reference.md](atw-api-reference.md#5-schedules)). Confirmed from three separate captures (`[2]` for a Tuesday-only entry, `[1, 0]` for a Monday+Sunday entry) plus an earlier passively-observed `[6]` for a Saturday entry — all consistent with this scheme and with no other scheme tried.
- `time`: `HH:MM:SS` (24-hour) — matches the ATW schedule format.
- `setPoint`: carries the target temperature as a plain number (confirmed `26` for a UI-set 26°C) — still unconfirmed whether this is a schedule-API-specific rename of `setTemperature` or a distinct field, but it behaves identically.
- `operationMode`, `setFanSpeed`, `vaneVerticalDirection`, `vaneHorizontalDirection`: **confirmed integer-encoded** (not the strings the control endpoint `PUT /monitor/ataunit/{id}` uses). Confirmed pairs from these captures: `operationMode` `1`=Heat, `3`=Cool; `setFanSpeed` `0`=Auto, `3`=Three; `vaneVerticalDirection` `0`=Auto, `1`=Position 1; `vaneHorizontalDirection` `3`=Centre. Consistent with the separately-observed Scenes endpoint mapping (see below), now confirmed independently on this endpoint too.
- `enabled`: sent as **`false` in every captured create and update**, including ones where the UI's per-entry power on/off toggle was visibly ON (green) — that toggle maps to `power`, not `enabled`. What actually flips this field to `true`, or whether the web client ever does, was **not determined** in this session; don't assume it tracks the visible on/off state. The per-unit master switch below is a separate mechanism and wasn't tested for interaction with this field.
- A "power-off" schedule was separately observed (passive HAR review) sending `null` for `operationMode`/`setPoint`/both vane fields alongside `power:false` — not re-confirmed in this session, but presumably still the Create-endpoint's flat-body behavior.

**Enum mapping (confirmed on both Schedules and the adjacent Scenes endpoint):**

| Field | Int value | Meaning | Confirmed on |
|-------|-----------|---------|---------------|
| `operationMode` | `1` | Heat | Schedules (this session) |
| `operationMode` | `3` | Cool | Schedules + Scenes |
| `setFanSpeed` | `0` | Auto | Schedules (this session) |
| `setFanSpeed` | `3` | Three | Schedules (this session) |
| `setFanSpeed` | `5` | Five | Scenes |
| `vaneVerticalDirection` | `0` | Auto | Schedules + Scenes |
| `vaneVerticalDirection` | `1` | Position 1 | Schedules (this session) |
| `vaneHorizontalDirection` | `3` | Centre | Schedules + Scenes |

### Enable/Disable Schedules (master switch)

```
PUT /api/cloudschedule/{unitId}/enabled
```

```json
{ "enabled": true }
```

Per-unit switch that toggles all of that unit's schedules at once, independent of each individual schedule's own `enabled` field (see above — not tested for interaction with it in this session). Path form per the passively-observed HAR; not re-driven in this session, so left as previously documented.

### Delete Schedule

```
DELETE /api/cloudschedule/{unitId}/{scheduleId}
```

**Confirmed** — both test schedule entries created during this capture were deleted this way, cleanly removing them from the account with no other side effects observed.

### Evidence Level

Two sources feed this section: a passive 2026-07-11 HAR review of the web app (dev account), and a live, driven capture on 2026-07-20 (a real account, three schedule entries created/edited/deleted through the actual UI on a live ATA unit and cleaned up immediately after, with no other side effects observed). The 2026-07-20 session resolved every item this section previously flagged as inferred-by-analogy: day-number encoding, and the int typing of `operationMode`/`setFanSpeed`/vane fields on this specific endpoint. See also the [Web BFF endpoint catalog](../research/web-bff-websocket-capture/README.md#web-bff-endpoint-catalog-observed) for the original HAR-sourced endpoint list. Guest/shared accounts were separately observed (2026-07-11 review) to have full write access to schedules on units shared with them.

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
- **[Web BFF & WebSocket Capture](../research/web-bff-websocket-capture/README.md)** - Source HAR capture for the Schedules section below

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-11-16 | Initial comprehensive API reference with UI-verified values |
| 1.3 | 2026-07-20 | Added Schedules section (cloud-schedule CRUD), sourced from 2026-07-11 web-app HAR capture |
| 1.4 | 2026-07-20 | Schedules section rewritten with confirmed data from a live driven capture: day-number encoding and int-typed mode/fan/vane fields moved from inferred to confirmed; documented the Update (PUT) endpoint and its distinct nested body shape |

**Data Collection Session:** 2025-11-16
**Equipment:** Mitsubishi Electric air conditioning system
**Location:** Dining Room unit (0efce33f-5847-4042-88eb-aaf3ff6a76db)
