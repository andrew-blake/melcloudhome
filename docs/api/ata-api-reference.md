# MELCloud Home API Reference - Air-to-Air Units
## Complete Air-to-Air (ATA) API Specification

> **Note:** This document covers Air-to-Air (ATA) units only.
> - For Air-to-Water heat pumps, see [atw-api-reference.md](atw-api-reference.md)
> - For device type comparison, see [device-type-comparison.md](device-type-comparison.md)

**Document Version:** 1.3
**Last Updated:** 2026-07-20
**Device Type:** Air-to-Air Air Conditioning Units
**Method:** Passive UI observation; some sections verified by driven capture — see per-section evidence notes

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

## Protection Modes & Holiday Mode

**Implementation Status:** Not integrated in the Home Assistant integration — documented for reference only.

**Corrects earlier documentation:** [device-type-comparison.md](device-type-comparison.md#endpoint-comparison) previously marked Holiday Mode and Frost Protection as "ATW exclusive". That was never true — both are **shared, building-level endpoints** that accept ATA unit IDs too, confirmed here via a live HAR capture (2026-07-20, real account) that exercised all three endpoints below end-to-end (enable → verify in `/context` → disable → verify again) on a set of ATA units, then restored everything to its original disabled state.

These are **not** per-unit endpoints like the control/schedule APIs above — a single call takes a *list* of unit IDs and applies the same setting to all of them at once, matching the batch pattern already noted for ATW in [device-type-comparison.md](device-type-comparison.md#endpoint-comparison).

### Frost Protection

```
POST /api/protection/frost
```
*(web host: `melcloudhome.com` — the mobile-BFF equivalent path is unconfirmed; see [Hosts](#hosts))*

**Request Body (confirmed):**

```json
{
  "enabled": true,
  "min": 10,
  "max": 12,
  "units": {
    "ATA": ["unit-uuid-1", "unit-uuid-2", "unit-uuid-3"]
  }
}
```

Prevents units from freezing by maintaining a minimum temperature. `min`/`max` define the target band. Set `enabled: false` (keeping the last `min`/`max`) to turn it off — confirmed by capturing both directions.

### Overheat Protection

```
POST /api/protection/overheat
```
*(web host: `melcloudhome.com` — the mobile-BFF equivalent path is unconfirmed; see [Hosts](#hosts))*

**New discovery** — not documented anywhere before this, for either device type.

**Request Body (confirmed):**

```json
{
  "enabled": true,
  "min": 35,
  "max": 37,
  "units": {
    "ATA": ["unit-uuid-1", "unit-uuid-2", "unit-uuid-3"]
  }
}
```

Same shape as Frost Protection — presumably the ceiling-temperature counterpart, keeping units from overheating. Same `enabled:false` pattern confirmed to disable it.

### Holiday Mode

```
POST /api/holidaymode
```
*(web host: `melcloudhome.com` — the mobile-BFF equivalent path is unconfirmed; see [Hosts](#hosts))*

**Request Body (confirmed):**

```json
{
  "enabled": true,
  "startDate": "2026-07-20T18:30:53.79",
  "endDate": "2026-07-22T12:00:00",
  "units": {
    "ATA": ["unit-uuid-1", "unit-uuid-2", "unit-uuid-3"]
  }
}
```

`startDate`/`endDate` are ISO 8601 without a timezone suffix. Confirmed both `enabled: true` (with a 2-day window) and `enabled: false` (disabling, sent with a fresh `startDate` timestamped at the moment of the call rather than the original one — worth noting if replaying this call, though the effect of `enabled:false` presumably makes the dates moot).

All three POSTs above returned `200 OK` with an **empty body** — same pattern as the main control endpoint.

### Response Shape (in `GET /context`)

Confirmed field shapes on each `airToAirUnits[]` entry, previously only shown as `{...}` placeholders in the ATW reference. Independently corroborated on the **mobile BFF** (this integration's own VCR cassettes show the same three keys with the same null-when-unconfigured behavior), even though the POST paths above were only captured on the web host — see [Hosts](#hosts).

Cross-checking against the one ATW unit in that same cassette (`tests/api/cassettes/test_get_devices.yaml`, line 667) gives a different evidence level per field, not one uniform claim:

- **`frostProtection`** — confirmed zone-split on ATW: `{"zone1Active":false,"zone2Active":false,"enabled":false,"min":9,"max":11}`. See [atw-api-reference.md](atw-api-reference.md#6-holiday-mode).
- **`holidayMode`** — confirmed a **single** `active` field on ATW, same shape as ATA (not zone-split): `{"enabled":false,"startDate":"2025-12-14T14:20:03.064","endDate":"2025-12-17T12:00:00","active":false}`.
- **`overheatProtection`** — unconfirmed on ATW: `null` on every ATW unit in every cassette in this repo, so there's no direct evidence of its shape there. The object shown below is inferred by analogy with `frostProtection`, not observed.

That same ATW unit has `hasZone2: false`, so the zone-split on `frostProtection` isn't evidence of a "multi-zone systems get independent zones" rule — it's just how that field happens to be shaped on ATW, independent of zone count.

```json
{
  "frostProtection": { "enabled": true, "active": false, "min": 10, "max": 12 },
  "overheatProtection": { "enabled": true, "active": false, "min": 35, "max": 37 },
  "holidayMode": { "enabled": true, "active": false, "startDate": "2026-07-20T18:30:53.79", "endDate": "2026-07-22T12:00:00" }
}
```

All three are `null` when never configured (the default/original state on every unit in this capture). Once configured they persist as an object even when `enabled: false` — only the value flips, the object doesn't revert to `null`.

**`enabled` vs `active`** — not previously documented and easy to conflate: `enabled` means the protection mode is armed/configured; `active` means it is *currently* engaged (e.g. the room is actually at/below the frost threshold right now). Both stayed `false`/`false` and `true`/`false` respectively throughout this capture since no unit's temperature crossed the configured thresholds — `active:true` was not observed, so its exact trigger condition (probably current room or outdoor temperature vs. `min`/`max`) is inferred from the field names, not directly confirmed.

### Evidence Level

Confirmed via a live HAR capture, 2026-07-20, real account: all three endpoints called with `enabled:true` then `enabled:false` on a set of ATA units, with `GET /context` read back after each call to confirm the resulting state. Unit IDs in the examples above are placeholders. `active:true` (a mode actually engaging) was not observed or tested — inferred from field naming only.

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

**Confirmed via a real DevTools HAR capture, 2026-07-23** (see Evidence Level below — this superseded the earlier gap where the exact Create body couldn't be re-verified): the client sends `id` as the all-zero GUID exactly as originally documented, and the server responds with a freshly assigned real UUID in place of it — both directions now directly confirmed, not just inferred from one side.

**New finding (2026-07-23): a single scene can target multiple units with independently different settings each.** The captured Create request included three ATA units in `ataSceneSettings`, each with its own `ataSettings` object — one had `power: true`, another `power: false`, matching what each unit should do when the scene is applied. Not a single shared settings block replicated per unit.

**Response also confirmed to include `atwSceneSettings` (2026-07-23):** present as `[]` on this ATA-only account — resolving the naming-symmetry guess below from "not observed" to "confirmed key exists, empty when unused." Whether it's ever populated (i.e. whether a scene can mix ATA and ATW units) is still unconfirmed.

**Field Details:**

- `id`: confirmed sent as the all-zero GUID `00000000-0000-0000-0000-000000000000` on create (see above) — the server replaces it with its own assigned ID.
- `ataSceneSettings`: array, one entry per ATA unit included in the scene, keyed by `unitId` — confirmed to support multiple units per scene with independent settings each (see above).
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

**New endpoint, confirmed 2026-07-23** — fetches a single scene by ID; the web UI calls this when opening a scene for editing. **Response body confirmed via a real DevTools HAR capture**: identical shape to one entry of the `GET /api/user/scenes` array (`id`, `userId`, `name`, `enabled`, `icon`, `ataSceneSettings`, `atwSceneSettings`).

### Update Scene

```
PUT /api/scene/{sceneId}
```
*(web host: `melcloudhome.com`)*

**Corrects earlier documentation** — this section previously assumed Update reused `POST /api/scene` (same as Create). **Confirmed 2026-07-23 via a real DevTools HAR capture: Update is `PUT` to the scene's own ID-scoped URL** with a **flat** request body — the *entire* scene object (`id`, `userId`, `name`, `enabled`, `icon`, `ataSceneSettings`, `atwSceneSettings`), with `id`/`userId` repeated matching the URL, not just the changed fields. This is a genuinely different shape from Schedules' Update, which nests the payload as `{id, schedule: {...}}` — don't assume the two APIs share a convention just because both offer Create/Update/Delete.

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

Confirmed via a real DevTools HAR capture, 2026-07-23 (no request body; empty response). Path matches the original 2026-07-11 observation exactly.

**Evidence Level:** Two 2026-07-23 sources back this Scenes section, on top of the original 2026-07-11 passive HAR review. First, a Claude-in-Chrome-driven session (create→enable→disable→edit→delete round trip) captured via an injected `fetch`/`XMLHttpRequest` hook — this caught List, Create (partially — the exact request body wasn't recovered that pass), Enable, and Disable in full, but never fired for Get-single, Update, or Delete despite the browser's own network monitor confirming all three completed with real `200`s. That gap is why a second pass followed: a genuine Chrome DevTools "Save all as HAR" export of the same round trip, done manually, which filled in exactly the three missing bodies (Get-single, Update, Delete) plus a cleaner Create body — including the multi-unit finding above. Both captures are committed anonymized at [docs/research/scenes-trendsummary-capture/](../research/scenes-trendsummary-capture/README.md): `scenes_anonymized.har` (the real DevTools export — primary evidence for the Scenes endpoints) and `captured-requests_anonymized.json` (the earlier JS-hook log — still the only source for the Trend Summary legacy-variant findings below, since that pass wasn't repeated with a native HAR).

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
| 1.3 | 2026-07-20 | Added Protection Modes & Holiday Mode section (frost/overheat protection, holiday mode), confirmed via live HAR capture; corrects earlier "ATW exclusive" claim |
| 1.4 | 2026-07-20 | Added Scenes section and legacy-web Trend Summary variant, sourced from 2026-07-11 web-app HAR capture |

**Data Collection Session:** 2025-11-16
**Equipment:** Mitsubishi Electric air conditioning system
**Location:** Dining Room unit (0efce33f-5847-4042-88eb-aaf3ff6a76db)
