# Outdoor Temperature Sensor Design

**Date:** 2026-02-03
**Feature Request:** [GitHub Discussion #28](https://github.com/andrew-blake/melcloudhome/discussions/28)
**Status:** Design approved, ready for implementation

---

## Overview

Add outdoor temperature sensor support for ATA (air conditioning) devices, exposing ambient temperature data from outdoor units in Home Assistant.

### Scope

- **ATA only** - Air-to-Air devices confirmed to have outdoor temp data via HAR analysis
- **ATW excluded** - Heat pumps don't expose outdoor temp through API (telemetry endpoint lacks this measure)
- **One sensor per indoor unit** - Simple approach, accepts duplicate readings for multi-split systems sharing outdoor units
- **30-minute polling** - Matches existing energy monitoring pattern, appropriate for slowly-changing outdoor temperature

### Data Source

- **Endpoint:** `/api/report/trendsummary`
- **Format:** Returns room temp, set temp, and outdoor temp in single response
- **Query:** Last 1 hour of data, extract most recent outdoor temperature value
- **Already used:** MELCloud web UI uses this for temperature charts

### User Impact

- New sensor entity: `sensor.melcloudhome_{short_id}_outdoor_temperature`
- Automatically created for ATA devices with outdoor sensors
- Shows in Home Assistant with temperature history
- Compatible with Energy Dashboard and automation triggers

---

## Technical Implementation

### API Client Layer

Add new method to `MELCloudHomeClient` (`custom_components/melcloudhome/api/client.py`):

```python
async def get_outdoor_temperature(self, unit_id: str) -> float | None:
    """Get latest outdoor temperature for an ATA unit.

    Queries trendsummary endpoint for last hour, extracts most recent
    outdoor temperature from the OUTDOOR_TEMPERATURE dataset.

    Args:
        unit_id: ATA unit UUID

    Returns:
        Outdoor temperature in Celsius, or None if not available
    """
    # Build time range: last 1 hour
    now = datetime.now(timezone.utc)
    from_time = now - timedelta(hours=1)

    # Format: 2026-01-12T20:00:00.0000000
    params = {
        "unitId": unit_id,
        "from": from_time.strftime("%Y-%m-%dT%H:%M:%S.0000000"),
        "to": now.strftime("%Y-%m-%dT%H:%M:%S.0000000"),
    }

    response = await self._request("GET", "/api/report/trendsummary", params=params)
    return self._parse_outdoor_temp(response)

def _parse_outdoor_temp(self, response: dict) -> float | None:
    """Extract outdoor temperature from trendsummary response.

    Response format:
    {
      "datasets": [
        {
          "label": "REPORT.TREND_SUMMARY_REPORT.DATASET.LABELS.ROOM_TEMPERATURE",
          "data": [{"x": "2026-01-12T20:00:00", "y": 17}, ...]
        },
        {
          "label": "REPORT.TREND_SUMMARY_REPORT.DATASET.LABELS.OUTDOOR_TEMPERATURE",
          "data": [{"x": "2026-01-12T20:00:00", "y": 11}, ...]
        }
      ]
    }
    """
    datasets = response.get("datasets", [])
    for dataset in datasets:
        label = dataset.get("label", "")
        if "OUTDOOR_TEMPERATURE" in label:
            data = dataset.get("data", [])
            if data:
                # Return latest value
                return data[-1].get("y")
    return None  # No outdoor temp dataset found
```

### Data Model

Extend `AirToAirUnit` dataclass (`custom_components/melcloudhome/api/models_ata.py`):

```python
@dataclass
class AirToAirUnit:
    # ... existing fields ...

    # Outdoor temperature monitoring (set by coordinator, not from main API)
    outdoor_temperature: float | None = None  # °C
    has_outdoor_temp_sensor: bool = False  # Runtime discovery flag
```

### Coordinator Updates

Extend `MELCloudHomeCoordinator._async_update_data()` (`custom_components/melcloudhome/coordinator.py`):

**Runtime capability discovery (first update only):**

```python
# After fetching UserContext, discover outdoor sensor capability
for building in user_context.buildings:
    for unit in building.air_to_air_units:
        # Probe once per device to check if outdoor sensor exists
        if not hasattr(unit, '_outdoor_temp_checked'):
            try:
                temp = await self.client.get_outdoor_temperature(unit.id)
                unit._outdoor_temp_checked = True
                if temp is not None:
                    unit.has_outdoor_temp_sensor = True
                    unit.outdoor_temperature = temp
                    _LOGGER.debug(
                        "Device %s has outdoor temperature sensor: %s°C",
                        unit.name, temp
                    )
                else:
                    _LOGGER.debug(
                        "Device %s has no outdoor temperature sensor",
                        unit.name
                    )
            except Exception as err:
                _LOGGER.warning(
                    "Failed to check outdoor temp for %s: %s",
                    unit.name, err
                )
                unit._outdoor_temp_checked = True
```

**Ongoing polling (subsequent updates):**

```python
# Poll outdoor temp every 30 minutes for devices with sensors
if unit.has_outdoor_temp_sensor:
    if self._should_poll_outdoor_temp():
        try:
            unit.outdoor_temperature = await self.client.get_outdoor_temperature(unit.id)
        except Exception as err:
            _LOGGER.warning(
                "Failed to update outdoor temp for %s: %s",
                unit.name, err
            )
            unit.outdoor_temperature = None

def _should_poll_outdoor_temp(self) -> bool:
    """Check if outdoor temp should be polled (30 minute interval)."""
    if not hasattr(self, '_last_outdoor_temp_poll'):
        self._last_outdoor_temp_poll = 0

    now = time.time()
    if now - self._last_outdoor_temp_poll > 1800:  # 30 minutes
        self._last_outdoor_temp_poll = now
        return True
    return False
```

### Sensor Entity

Add to `ATA_SENSOR_TYPES` in `custom_components/melcloudhome/sensor_ata.py`:

```python
# Outdoor temperature - ambient temperature from outdoor unit sensor
# Only created for devices where outdoor sensor detected during capability discovery
# Updates every 30 minutes via trendsummary API endpoint
ATASensorEntityDescription(
    key="outdoor_temperature",
    translation_key="outdoor_temperature",
    device_class=SensorDeviceClass.TEMPERATURE,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    value_fn=lambda unit: unit.outdoor_temperature,
    available_fn=lambda unit: unit.outdoor_temperature is not None,
    should_create_fn=lambda unit: unit.has_outdoor_temp_sensor,
)
```

**Translation strings** in `custom_components/melcloudhome/strings.json`:

```json
{
  "entity": {
    "sensor": {
      "outdoor_temperature": {
        "name": "Outdoor temperature"
      }
    }
  }
}
```

---

## Error Handling & Edge Cases

### Graceful Degradation

Outdoor temperature is a nice-to-have sensor, not critical for operation. If fetching fails:

- Log warning (not error level)
- Set `unit.outdoor_temperature = None`
- Sensor shows "unavailable" in HA
- Main coordinator update continues successfully

### Edge Cases

**1. Missing OUTDOOR_TEMPERATURE dataset:**

- Some units may not have outdoor sensors
- Parse trendsummary, return `None` if dataset missing
- Runtime discovery marks unit as `has_outdoor_temp_sensor = False`
- Sensor entity not created, no ongoing API polling

**2. Empty data array:**

- Dataset exists but `data` array is empty
- Return `None`, sensor shows unavailable temporarily
- Continue polling (may be temporary API issue)

**3. API timeout/failure:**

- Use existing client timeout handling (30s default)
- Catch exceptions, log warning and continue
- Don't block main UserContext refresh

**4. Rate limiting:**

- 30-minute polling interval (conservative)
- Only poll devices confirmed to have sensors
- Unlikely to hit rate limits

### Runtime Capability Discovery

**Why:** Don't spam the API polling for data that doesn't exist.

**Approach:**

1. **First coordinator refresh:** Fetch trendsummary for all ATA devices (one-time probe)
2. **If OUTDOOR_TEMPERATURE dataset exists:** Set `has_outdoor_temp_sensor = True`
3. **If missing:** Mark device as no sensor, skip future polling
4. **Ongoing:** Only poll devices where sensor confirmed

**Benefits:**

- No wasted API calls for devices without sensors
- Simple entity list (only shows sensors that exist)
- Automatic discovery, no user configuration needed

---

## Testing Strategy

### Unit Tests

**API Client** (`tests/api/test_outdoor_temperature.py`):

- `test_parse_outdoor_temperature_success()` - Normal case with outdoor temp dataset
- `test_parse_outdoor_temperature_missing_dataset()` - No OUTDOOR_TEMPERATURE in response
- `test_parse_outdoor_temperature_empty_data()` - Dataset exists but data array empty
- `test_parse_outdoor_temperature_malformed()` - Bad response structure

### Integration Tests

**Sensor Platform** (`tests/integration/test_sensor_ata.py`):

- `test_outdoor_temperature_sensor_created()` - Device has sensor, entity created
- `test_outdoor_temperature_sensor_not_created()` - Device lacks sensor, no entity
- `test_outdoor_temperature_updates()` - Value changes on coordinator refresh
- `test_outdoor_temperature_unavailable()` - Graceful failure handling

### VCR Cassettes

Create test fixtures from real HAR data:

- Extract trendsummary response with outdoor temp (from Study, Dining Room, Living Room)
- Create mock response without outdoor temp dataset (for negative test case)
- Device names already anonymous in HAR (Study, Dining Room, Living Room)

### Mock Server Updates

Update `tools/mock_melcloud_server.py`:

**Add trendsummary endpoint:**

```python
from datetime import datetime

@app.get("/api/report/trendsummary")
async def get_trend_summary(unitId: str, **params):
    """Mock trendsummary endpoint for testing.

    Uses query time range to generate realistic timestamps.
    Query params: from, to (format: YYYY-MM-DDTHH:MM:SS.0000000)
    """
    # Parse 'to' timestamp from query (use for latest datapoint)
    # Query params come as 'from' and 'to' but 'from' is Python keyword
    to_param = params.get('to', '')

    # Parse timestamp (remove nanosecond precision for parsing)
    to_time = to_param.replace('.0000000', '') if to_param else datetime.now().isoformat()

    # Scenario 1: Device WITH outdoor sensor
    if unitId in ["unit-with-outdoor-sensor"]:
        return {
            "datasets": [
                {
                    "label": "REPORT.TREND_SUMMARY_REPORT.DATASET.LABELS.ROOM_TEMPERATURE",
                    "data": [{"x": to_time, "y": 20.5}]
                },
                {
                    "label": "REPORT.TREND_SUMMARY_REPORT.DATASET.LABELS.SET_TEMPERATURE",
                    "data": [{"x": to_time, "y": 21.0}]
                },
                {
                    "label": "REPORT.TREND_SUMMARY_REPORT.DATASET.LABELS.OUTDOOR_TEMPERATURE",
                    "data": [{"x": to_time, "y": 12.0}]
                }
            ]
        }

    # Scenario 2: Device WITHOUT outdoor sensor
    return {
        "datasets": [
            {
                "label": "REPORT.TREND_SUMMARY_REPORT.DATASET.LABELS.ROOM_TEMPERATURE",
                "data": [{"x": to_time, "y": 20.5}]
            },
            {
                "label": "REPORT.TREND_SUMMARY_REPORT.DATASET.LABELS.SET_TEMPERATURE",
                "data": [{"x": to_time, "y": 21.0}]
            }
        ]
    }
```

**Key improvements:**
- Parses query `to` parameter for realistic timestamps
- Tests work regardless of when they run
- Validates client sends correct time range
- Simple implementation (just uses latest timestamp from query)

### Manual Testing Checklist

**Pre-implementation:**

- [ ] Verify dev environment works: `make dev-up`
- [ ] Check HA at <http://localhost:8123> (dev/dev)
- [ ] Note existing ATA entity IDs for comparison
- [ ] Confirm entity ID format: `sensor.melcloudhome_{short_id}_room_temperature`

**Post-implementation (incremental test):**

- [ ] Update code with outdoor temp feature
- [ ] Restart HA: `make dev-restart`
- [ ] Verify NEW outdoor temp sensor appears: `sensor.melcloudhome_{short_id}_outdoor_temperature`
- [ ] Verify existing entities unchanged, no duplicates
- [ ] Check sensor shows correct temperature value
- [ ] Confirm sensor updates every 30 minutes
- [ ] Verify sensor history/graphs work in HA
- [ ] Check logs for errors or warnings

**Real hardware testing:**

- [ ] Deploy to remote HA instance: `make deploy`
- [ ] Verify outdoor temp sensor appears for Dining Room
- [ ] Check temperature value is reasonable
- [ ] Monitor logs for 1 hour (2 polling cycles)

---

## Documentation Updates

**Entity Reference** (`docs/entities.md`):

Add to ATA Sensors section:

```markdown
### Sensors

- **Room Temperature**: `sensor.melcloudhome_{short_id}_room_temperature`
- **Outdoor Temperature**: `sensor.melcloudhome_{short_id}_outdoor_temperature` (if available)
- **WiFi Signal**: `sensor.melcloudhome_{short_id}_wifi_signal` (diagnostic)
- **Energy**: `sensor.melcloudhome_{short_id}_energy` (cumulative kWh)
```

Add note:

```markdown
**Outdoor Temperature Sensor:**
- Only created for devices with outdoor temperature sensors
- Automatically detected during integration setup
- Updates every 30 minutes
- Shows ambient temperature from outdoor unit
- Useful for efficiency monitoring and automations
```

**API Reference** (`docs/api/ata-api-reference.md`):

Add new section:

```markdown
### Telemetry Endpoints

#### Trend Summary (Temperature Reports)

**GET** `/api/report/trendsummary`

Returns historical temperature data for charts.

**Query Parameters:**
- `unitId` - Device UUID
- `from` - Start datetime (ISO 8601: `YYYY-MM-DDTHH:MM:SS.0000000`)
- `to` - End datetime (ISO 8601: `YYYY-MM-DDTHH:MM:SS.0000000`)

**Response:**
```json
{
  "datasets": [
    {
      "label": "REPORT.TREND_SUMMARY_REPORT.DATASET.LABELS.ROOM_TEMPERATURE",
      "data": [{"x": "2026-01-12T20:00:00", "y": 17}]
    },
    {
      "label": "REPORT.TREND_SUMMARY_REPORT.DATASET.LABELS.OUTDOOR_TEMPERATURE",
      "data": [{"x": "2026-01-12T20:00:00", "y": 11}]
    }
  ]
}
```

**Integration Usage:**

- Polled every 30 minutes for devices with outdoor sensors
- Extracts latest outdoor temperature value from dataset
- Not all devices have outdoor sensors (capability auto-detected)

```

---

## Implementation Notes

### Multi-Split Systems

**Physical Reality:**
- Multiple indoor units can share one outdoor unit
- Shared outdoor unit = shared outdoor temperature sensor
- Example: Dining Room + Living Room share same outdoor unit

**API Reality:**
- Trendsummary endpoint is per indoor unit: `/api/report/trendsummary?unitId={indoor_unit_id}`
- Each indoor unit makes its own API call
- Units sharing outdoor unit report identical outdoor temperature values

**Implementation Decision:**
- Create one outdoor temp sensor per indoor unit (simple)
- Accept duplicate sensors showing same value for multi-split systems
- Alternative (complex): Detect shared outdoor units and deduplicate → rejected due to:
  - API provides no outdoor unit grouping information
  - systemId doesn't represent outdoor unit relationship
  - Would require user configuration or unreliable guessing

### Why Not ATW?

ATW (Air-to-Water heat pumps) physically have outdoor sensors for weather compensation, but:
- ATW uses different API pattern: `/api/telemetry/actual` with individual measures
- Available measures: flow temps, return temps, tank temps, rssi
- **No `outdoor_temperature` measure available in API**
- HAR analysis confirmed: no trendsummary endpoint for ATW
- If MELCloud later adds outdoor temp to ATW API, we can add support then

### Polling Strategy

**30-minute interval chosen because:**
- Outdoor temperature changes slowly (not minute-by-minute)
- MELCloud app shows historic data with infrequent updates
- Matches existing energy monitoring pattern
- Conservative API usage, unlikely to hit rate limits
- Sufficient for automation triggers (detecting temp drops/rises)

---

## Success Criteria

- [ ] Outdoor temp sensor auto-created for ATA devices with sensors
- [ ] Sensor shows correct temperature value from trendsummary API
- [ ] Updates every 30 minutes without errors
- [ ] Devices without outdoor sensors don't spam API
- [ ] No duplicate entities, entity IDs match existing pattern
- [ ] Temperature history/graphs work in HA
- [ ] Integration tests pass with VCR cassettes
- [ ] Mock server supports both scenarios (with/without sensor)
- [ ] Documentation updated (entities.md, API reference)

---

## References

- **Feature Request:** [GitHub Discussion #28](https://github.com/andrew-blake/melcloudhome/discussions/28)
- **API Discovery:** `_claude/reference/api-discoveries/outdoor-temperature-api-discovery.md`
- **HAR Files:** `_claude/har/melcloudhome.com-outdoor.har`, `_claude/har/melcloudhome.com - ATA.har`
- **Existing Patterns:** Energy monitoring (sensor_ata.py), ATW telemetry (sensor_atw.py)
