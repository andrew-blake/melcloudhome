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

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-11-16 | Initial comprehensive API reference with UI-verified values |
| 1.3 | 2026-07-20 | Added Protection Modes & Holiday Mode section (frost/overheat protection, holiday mode), confirmed via live HAR capture; corrects earlier "ATW exclusive" claim |

**Data Collection Session:** 2025-11-16
**Equipment:** Mitsubishi Electric air conditioning system
**Location:** Dining Room unit (0efce33f-5847-4042-88eb-aaf3ff6a76db)
