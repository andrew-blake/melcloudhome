# MELCloud Home Telemetry & Reporting Endpoints

**Document Version:** 1.0
**Last Updated:** 2026-01-10
**Discovery Method:** Passive UI observation

---

## About This Document

This is a **complete API reference** documenting all read-only (GET) telemetry and reporting endpoints available in the MELCloud Home API.

**Implementation Status:**
- ✅ **Implemented** - Available in Home Assistant integration
- 📋 **Reference Only** - Documented for contributors but not yet integrated

**Currently Implemented:**
- Energy consumption telemetry (Section 3) - Used for energy monitoring sensors in ATA devices
- WiFi RSSI for ATA devices (sourced from UserContext, not telemetry polling endpoint)

**Reference Only (Not Implemented):**
- Actual telemetry data polling (Section 1) - Flow/return temps for ATW, RSSI via polling endpoint
- Operation mode history (Section 4) - Historical operation tracking
- Error log endpoint (Section 2) - Device error history
- Report types (Section 5) - Historical reporting features

**Why not implemented?**
- UserContext already provides current temperatures (zone, tank) and RSSI for ATA
- Telemetry polling requires separate API call per measure per device (significant API load)
- Energy monitoring is the high-value use case and is implemented
- Additional sensors (flow/return temps for ATW) can be added in future releases if users request them

For current integration features, see [README.md](../../README.md).

---

## Overview

MELCloud Home provides several reporting and telemetry endpoints for reading historical data, monitoring device health, and tracking performance metrics. These are READ-ONLY endpoints that provide time-series data and diagnostic information.

---

## Telemetry Endpoints

### 1. Actual Telemetry Data 📋 (Reference Only)

**GET** `/api/telemetry/actual/{unit_id}`

Retrieves time-series data for various measurements over a specified time range.

**Query Parameters:**
- `from` - Start datetime (format: `YYYY-MM-DD HH:MM`)
- `to` - End datetime (format: `YYYY-MM-DD HH:MM`)
- `measure` - Type of measurement (see below)

**Available Measures:**
- `room_temperature` - Actual room temperature readings
- `set_temperature` - Target temperature history
- `rssi` - Wi-Fi signal strength (RSSI)

**Example Request:**
```
GET /api/telemetry/actual/0efce33f-5847-4042-88eb-aaf3ff6a76db?from=2025-11-16%2008:00&to=2025-11-16%2008:59&measure=room_temperature
```

**Response Format:**
```json
{
  "measureData": [
    {
      "deviceId": "0efce33f-5847-4042-88eb-aaf3ff6a76db",
      "type": "roomTemperature",
      "values": [
        {
          "time": "2025-11-16 07:59:35.890000000",
          "value": "19.5"
        },
        {
          "time": "2025-11-16 08:00:36.720000000",
          "value": "20.5"
        },
        {
          "time": "2025-11-16 08:01:36.581000000",
          "value": "21.0"
        }
      ]
    }
  ]
}
```

**Response Fields:**
- `measureData[]` - Array of measurement datasets
  - `deviceId` - Unit UUID
  - `type` - Measurement type (camelCase version)
  - `values[]` - Array of timestamped values
    - `time` - ISO-8601 timestamp with nanosecond precision
    - `value` - String representation of the value

**Notes:**
- Values are returned as strings, not numbers
- Timestamps include nanosecond precision
- Data points are typically ~1 minute apart
- Response returns 304 (Not Modified) if data hasn't changed

**Headers Required:**
```http
x-csrf: 1
```

---

### 2. Operation Mode History 📋 (Reference Only)

**GET** `/api/telemetry/operationmode/{unit_id}`

Retrieves operation mode changes over a specified time range.

**Query Parameters:**
- `from` - Start datetime (format: `YYYY-MM-DD HH:MM`)
- `to` - End datetime (format: `YYYY-MM-DD HH:MM`)

**Example Request:**
```
GET /api/telemetry/operationmode/0efce33f-5847-4042-88eb-aaf3ff6a76db?from=2025-11-16%2008:00&to=2025-11-16%2008:33
```

**Response Format:**
```json
{
  "operationModeData": [
    {
      "deviceId": "0efce33f-5847-4042-88eb-aaf3ff6a76db",
      "values": [
        {
          "time": "2025-11-16 08:00:00.000000000",
          "mode": "Heat"
        },
        {
          "time": "2025-11-16 08:22:17.599000000",
          "mode": "Cool"
        }
      ]
    }
  ]
}
```

**Use Cases:**
- Track when operation mode changes occurred
- Verify mode changes were applied
- Generate usage reports by mode type

---

### 3. Energy Consumption ✅ (Implemented)

**GET** `/api/telemetry/energy/{unit_id}`

Retrieves energy consumption data over a specified time range.

> **✅ Implementation:** This endpoint is implemented in the integration.
> See `client.py:170-236` (`get_energy_data()` method).
> Used by energy monitoring sensors in ATA devices.

**Query Parameters:**
- `from` - Start datetime (format: `YYYY-MM-DD HH:MM`)
- `to` - End datetime (format: `YYYY-MM-DD HH:MM`)
- `interval` - Aggregation interval: `Hour`, `Day`, `Week`, `Month`
- `measure` - `cumulative_energy_consumed_since_last_upload`

**Example Request:**
```
GET /api/telemetry/energy/0efce33f-5847-4042-88eb-aaf3ff6a76db?from=2025-11-16%2000:00&to=2025-11-16%2023:59&interval=Hour&measure=cumulative_energy_consumed_since_last_upload
```

**Response Format:**
```json
{
  "deviceId": "0efce33f-5847-4042-88eb-aaf3ff6a76db",
  "measureData": [
    {
      "type": "cumulativeEnergyConsumedSinceLastUpload",
      "values": [
        {
          "time": "2025-11-16 02:00:00.000000000",
          "value": "100.0"
        },
        {
          "time": "2025-11-16 07:00:00.000000000",
          "value": "100.0"
        },
        {
          "time": "2025-11-16 08:00:00.000000000",
          "value": "200.0"
        }
      ]
    }
  ]
}
```

**Response Fields:**
- `deviceId` - Unit UUID
- `measureData[]` - Array of energy datasets
  - `type` - "cumulativeEnergyConsumedSinceLastUpload"
  - `values[]` - Array of timestamped consumption values
    - `time` - Timestamp (nanosecond precision)
    - `value` - Cumulative energy value (string format)

**Notes:**
- Values are cumulative (not per-interval)
- Aggregated by specified interval (Hour/Day/Week/Month)
- Energy values in watt-hours or similar units (exact unit TBD)
- Requires device capability: `hasEnergyConsumedMeter: true`

**Use Cases:**
- Track energy consumption over time
- Generate cost estimates
- Identify high-usage periods
- Create energy efficiency reports
- Display consumption graphs in HA

---

## Diagnostic Endpoints

### 4. Error Log 📋 (Reference Only)

**GET** `/api/ataunit/{unit_id}/errorlog`

Retrieves error history for the specified unit.

**Query Parameters:** None

**Example Request:**
```
GET /api/ataunit/0efce33f-5847-4042-88eb-aaf3ff6a76db/errorlog
```

**Response Format (No Errors):**
```json
[]
```

**Response Format (With Errors):**
```json
[
  {
    "errorCode": "1234",
    "from": "2025-11-16T08:00:00.000Z",
    "to": "2025-11-16T08:05:00.000Z"
  }
]
```

**Response Fields:**
- Empty array when no errors
- Array of error objects when errors exist:
  - `errorCode` - Error code identifier
  - `from` - Error start timestamp
  - `to` - Error end timestamp (or null if ongoing)

**Use Cases:**
- Monitor device health
- Alert on new errors
- Track error history for diagnostics
- Display error status in UI

---

## Report Types 📋 (Reference Only)

The MELCloud Home UI provides 4 report types:

### 1. TEMPERATURES Report
- **Endpoint:** `/api/telemetry/actual/{unit_id}`
- **Measures:** `room_temperature`, `set_temperature`
- **Time ranges:** Hour, Day, Week, Month
- **URL:** `/0efce33f-5847-4042-88eb-aaf3ff6a76db/trendsummary`

### 2. ERROR LOG Report
- **Endpoint:** `/api/ataunit/{unit_id}/errorlog`
- **Shows:** Error code, start time, end time
- **URL:** `/0efce33f-5847-4042-88eb-aaf3ff6a76db/uniterrorlog`

### 3. ENERGY Report
- **Endpoint:** `/api/telemetry/energy/{unit_id}`
- **Measure:** `cumulative_energy_consumed_since_last_upload`
- **Intervals:** Hour, Day, Week, Month
- **Shows:** Energy consumption data aggregated by interval
- **URL:** `/{unit_id}/energy`

### 4. WI-FI SIGNAL Report
- **Endpoint:** `/api/telemetry/actual/{unit_id}` with `measure=rssi`
- **Shows:** Wi-Fi signal strength over time
- **URL:** TBD

---

## Home Assistant Integration Use Cases

### Real-Time Monitoring
```python
# Poll current temperature
GET /api/user/context  # Get current state
# OR
GET /api/telemetry/actual/{id}?from={now-5min}&to={now}&measure=room_temperature
# Use most recent value
```

### Historical Data for Graphs
```python
# Get last 24 hours of temperature data
GET /api/telemetry/actual/{id}?from={now-24h}&to={now}&measure=room_temperature

# Create HA sensor with state_class='measurement'
# Enable long-term statistics in HA
```

### Error Monitoring
```python
# Check for errors every 5 minutes
GET /api/ataunit/{id}/errorlog

# Create HA binary_sensor for error state
# Trigger notification when errors appear
```

### Wi-Fi Signal Monitoring
```python
# Track connectivity
GET /api/telemetry/actual/{id}?from={now-1h}&to={now}&measure=rssi

# Create HA sensor for RSSI
# Alert on weak signal
```

### Operation Mode Tracking
```python
# Get mode change history
GET /api/telemetry/operationmode/{id}?from={start}&to={end}

# Track usage patterns
# Generate efficiency reports
```

---

## Data Retention

**Observed:**
- Temperature data: At least hourly retention
- Operation mode: Event-based storage
- Error log: Full history available

**UI Time Ranges:**
- Hour: Last 60 minutes
- Day: Last 24 hours
- Week: Last 7 days
- Month: Last 30 days

---

## Rate Limiting

**Not documented** - Use conservative polling:
- Current state: Every 30-60 seconds
- Historical data: Every 5-15 minutes
- Error log: Every 5 minutes

**Best Practice:** Use WebSocket for real-time updates (see WebSocket token endpoint in API discovery doc).

---

## Implementation Example

```python
import aiohttp
from datetime import datetime, timedelta

async def get_temperature_history(session, unit_id, hours=1):
    """Get temperature history for the last N hours."""
    now = datetime.utcnow()
    start = now - timedelta(hours=hours)

    url = f"https://melcloudhome.com/api/telemetry/actual/{unit_id}"
    params = {
        "from": start.strftime("%Y-%m-%d %H:%M"),
        "to": now.strftime("%Y-%m-%d %H:%M"),
        "measure": "room_temperature"
    }
    headers = {
        "x-csrf": "1"
    }

    async with session.get(url, params=params, headers=headers) as resp:
        data = await resp.json()

        # Extract values
        if data.get("measureData"):
            values = data["measureData"][0]["values"]
            return [
                {
                    "time": datetime.fromisoformat(v["time"].split(".")[0]),
                    "temp": float(v["value"])
                }
                for v in values
            ]
        return []

async def check_errors(session, unit_id):
    """Check for device errors."""
    url = f"https://melcloudhome.com/api/ataunit/{unit_id}/errorlog"
    headers = {"x-csrf": "1"}

    async with session.get(url, headers=headers) as resp:
        errors = await resp.json()
        return len(errors) > 0, errors
```

---

## Data Types & Conversions

### Temperature Values
- **API format:** String (e.g., `"20.5"`)
- **Convert to:** `float(value)`
- **Unit:** Celsius

### RSSI Values
- **API format:** String (e.g., `"-65"`)
- **Convert to:** `int(value)`
- **Unit:** dBm
- **Typical range:** -30 (excellent) to -90 (poor)

### Timestamps
- **API format:** String with nanosecond precision
- **Example:** `"2025-11-16 08:00:36.720000000"`
- **Convert to:** `datetime.fromisoformat(value.split(".")[0])`

---

## Response Status Codes

| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | Parse response data |
| 304 | Not Modified | Use cached data |
| 401 | Unauthorized | Re-authenticate |
| 404 | Not Found | Invalid unit ID |

---

## Error Handling

```python
async def safe_telemetry_fetch(session, unit_id, measure):
    """Fetch telemetry with error handling."""
    try:
        # Make request
        response = await fetch_telemetry(session, unit_id, measure)
        return response

    except aiohttp.ClientResponseError as e:
        if e.status == 401:
            # Session expired - re-authenticate
            await re_authenticate(session)
            return await fetch_telemetry(session, unit_id, measure)
        elif e.status == 404:
            # Invalid unit ID
            raise ValueError(f"Unit {unit_id} not found")
        else:
            raise

    except aiohttp.ClientError as e:
        # Network error - retry with backoff
        await asyncio.sleep(5)
        return await fetch_telemetry(session, unit_id, measure)
```

---

## Related Documentation

- **[ATA API Reference](ata-api-reference.md)** - Air-to-Air control API
- **[ATW API Reference](atw-api-reference.md)** - Air-to-Water control API
- **[Device Type Comparison](device-type-comparison.md)** - ATA vs ATW API differences
- **[Architecture Overview](../architecture.md)** - System design and authentication flow
- **[Testing Best Practices](../testing-best-practices.md)** - Home Assistant integration patterns

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-11-16 | Initial telemetry endpoints documentation |

**Discovery Session:** 2025-11-16
**Equipment:** Mitsubishi Electric air conditioning system
**Location:** Dining Room unit (0efce33f-5847-4042-88eb-aaf3ff6a76db)
