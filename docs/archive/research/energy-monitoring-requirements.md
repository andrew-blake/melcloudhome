# Energy Monitoring Requirements

**Document Version:** 1.0
**Last Updated:** 2025-11-19
**Target Version:** v1.3 (Post-WiFi, Pre-HACS)
**Estimated Effort:** 4-5 hours

---

## Executive Summary

MELCloud Home API provides energy consumption data via a telemetry endpoint. This document outlines the requirements, architecture decisions, and implementation plan for adding energy monitoring sensors to the integration.

**Key Finding:** Energy data requires separate telemetry API polling, not available in main `/api/user/context` response.

---

## API Capabilities

### Device Capability Flag

**Location:** `/api/user/context` response
```json
{
  "capabilities": {
    "hasEnergyConsumedMeter": true
  }
}
```

**Status:** ✅ Already parsed by `DeviceCapabilities.from_dict()` in `api/models.py:57`

### Telemetry Endpoint

**Endpoint:** `GET /api/telemetry/energy/{unit_id}`

**Query Parameters:**
- `from` - Start datetime (format: `YYYY-MM-DD HH:MM`)
- `to` - End datetime (format: `YYYY-MM-DD HH:MM`)
- `interval` - Aggregation interval: `Hour`, `Day`, `Week`, `Month`
- `measure` - `cumulative_energy_consumed_since_last_upload`

**Example Request:**
```
GET /api/telemetry/energy/0efce33f-5847-4042-88eb-aaf3ff6a76db?from=2025-11-16%2000:00&to=2025-11-16%2023:59&interval=Hour&measure=cumulative_energy_consumed_since_last_upload
```

**Example Response:**
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

**Data Characteristics:**
- Values are **cumulative** (TOTAL_INCREASING pattern)
- Values are **strings** that need parsing to float
- Aggregated by specified interval
- Timestamps include nanosecond precision
- Empty response or 304 if no data available

**Reference:** `../api/melcloudhome-telemetry-endpoints.md:128`

---

## Home Assistant Standards

### Sensor Configuration

**Device Class:** `SensorDeviceClass.ENERGY`
- Standard HA device class for energy consumption
- Automatically integrates with Energy Dashboard
- Proper icon and unit display

**State Class:** `SensorStateClass.TOTAL_INCREASING`
- For cumulative values that only increase
- Can reset to 0 (e.g., monthly billing cycle)
- HA handles reset detection and long-term statistics

**Unit:** `UnitOfEnergy.KILO_WATT_HOUR` (kWh)
- Standard SI unit for energy
- Must match Energy Dashboard expectations
- API may return Wh, needs conversion

**Entity Category:** None (main entity, not diagnostic)
- Should appear in main entity list
- Used for energy tracking and cost calculation

### Entity Description Pattern

```python
MELCloudHomeSensorEntityDescription(
    key="energy_consumed",
    translation_key="energy_consumed",
    device_class=SensorDeviceClass.ENERGY,
    state_class=SensorStateClass.TOTAL_INCREASING,
    native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    value_fn=lambda unit: unit.energy_consumed,
    available_fn=lambda unit: (
        unit.capabilities.has_energy_consumed_meter
        and unit.energy_consumed is not None
    ),
)
```

---

## Architecture Decisions Needed

### Decision 1: Polling Strategy

**Options:**

#### A. Coordinator Extension (Recommended)
- Add telemetry fetching to `MELCloudHomeCoordinator`
- Poll every 15-30 minutes (separate from main 60s poll)
- Cache energy data with main device state
- Use HA's `async_track_time_interval` for separate schedule

**Pros:**
- ✅ Centralized data management
- ✅ Proper error handling via coordinator
- ✅ Entity updates via existing coordinator pattern
- ✅ No duplicate session management

**Cons:**
- ⚠️ Two different polling intervals to manage
- ⚠️ Coordinator becomes more complex

#### B. Separate Service Class
- Create `MELCloudHomeTelemetryService`
- Independent polling mechanism
- Sensors subscribe to telemetry updates
- Separate from main coordinator

**Pros:**
- ✅ Clean separation of concerns
- ✅ Independent polling schedule
- ✅ Can be disabled if not needed

**Cons:**
- ❌ Duplicate session/auth management
- ❌ More complex architecture
- ❌ Harder to maintain state consistency

#### C. Sensor Self-Polling
- Each energy sensor polls independently
- Uses coordinator's API client
- Manages own update schedule

**Pros:**
- ✅ Simple to implement
- ✅ Self-contained

**Cons:**
- ❌ Multiple API calls for multiple units
- ❌ No coordination between sensors
- ❌ Inefficient for multiple devices

**Recommendation:** **Option A (Coordinator Extension)** - Best balance of simplicity and proper architecture.

### Decision 2: Polling Interval

**Considerations:**
- API aggregates by Hour/Day/Week/Month
- Energy Dashboard updates every 5 minutes
- Rate limiting concerns
- Data freshness vs API load

**Options:**
- Every 5 minutes - ⚠️ May be too aggressive, unnecessary API load
- Every 15 minutes - ✅ Reasonable balance
- Every 30 minutes - ✅ Conservative, good for production
- Every 60 minutes - ⚠️ May be too slow for responsive dashboard

**Recommendation:** **30 minutes** initially, configurable via options flow in v1.4

**Rationale:**
- Energy consumption changes slowly
- 30min is responsive enough for dashboard
- Lower API load
- Can be reduced if needed

### Decision 3: Time Range Strategy

**What to Fetch:**

#### Option A: Last Hour (Recommended)
```python
# Get last hour of data, use most recent value
from = now - 1 hour
to = now
interval = Hour
```

**Pros:**
- ✅ Simple implementation
- ✅ Always current
- ✅ Minimal data transfer

**Cons:**
- ⚠️ Discards historical data

#### Option B: Since Last Fetch
```python
# Get data since last successful fetch
from = last_fetch_time
to = now
interval = Hour
```

**Pros:**
- ✅ No data loss
- ✅ Can backfill gaps

**Cons:**
- ⚠️ More complex state management
- ⚠️ Larger responses if offline for hours

**Recommendation:** **Option A** for v1.3, **Option B** if users request backfill

### Decision 4: Unit Handling

**API Returns:** Unknown unit (possibly Wh or kWh)
**HA Expects:** kWh for Energy Dashboard

**Strategy:**
1. Test with real device to determine API unit
2. If Wh: Convert to kWh (divide by 1000)
3. If kWh: Use directly
4. Document in code and ADR

**Testing Needed:**
- Capture real energy data
- Compare with physical meter if available
- Verify unit conversion correctness

### Decision 5: Cumulative Reset Handling

**Scenario:** Energy counter resets to 0 (monthly billing, device reset, etc.)

**HA Behavior:**
- `TOTAL_INCREASING` state class handles resets automatically
- HA detects decrease and treats as reset
- Long-term statistics continue correctly

**Implementation:**
- ✅ No special handling needed (HA handles it)
- ✅ Just report raw cumulative value
- ✅ Document that resets are expected and handled

---

## Implementation Plan

### Session 13: Architecture & Setup (1 hour)

**Tasks:**
1. Create ADR-008: Energy Monitoring Architecture
2. Extend coordinator with telemetry fetching
3. Add telemetry API methods to client
4. Test telemetry endpoint with real device

**Deliverables:**
- ADR document with architecture decisions
- Telemetry API methods in `api/client.py`
- Basic coordinator extension (no UI yet)

**Questions to Answer:**
- What unit does API actually return?
- How often does data update?
- What happens when device is offline?
- Are there rate limits on telemetry endpoint?

### Session 14: Sensor Implementation (3 hours)

**Tasks:**
1. Add `energy_consumed` property to `AirToAirUnit` model
2. Update coordinator to fetch and cache energy data
3. Create energy sensor entity description
4. Implement polling schedule (30min interval)
5. Test with real devices
6. Verify Energy Dashboard integration

**Files to Modify:**
- `custom_components/melcloudhome/api/client.py` - Add telemetry methods
- `custom_components/melcloudhome/api/models.py` - Add energy property
- `custom_components/melcloudhome/coordinator.py` - Add telemetry polling
- `custom_components/melcloudhome/sensor.py` - Update energy sensor
- `custom_components/melcloudhome/const.py` - Add constants for intervals

**Deliverables:**
- Working energy sensor
- Energy Dashboard integration
- 30-minute polling
- Proper error handling

### Session 15: Testing & Polish (1 hour)

**Tasks:**
1. Test energy sensor over 24+ hours
2. Verify cumulative values increase correctly
3. Test reset handling
4. Verify Energy Dashboard integration
5. Update documentation
6. Deploy to production

**Testing Checklist:**
- [ ] Energy sensor shows initial value
- [ ] Value increases over time
- [ ] Energy Dashboard recognizes sensor
- [ ] Historical data appears in statistics
- [ ] Handles device offline gracefully
- [ ] Handles API errors gracefully
- [ ] 30-minute polling confirmed via logs

---

## API Client Methods Needed

```python
# In api/client.py

async def get_energy_data(
    self,
    unit_id: str,
    from_time: datetime,
    to_time: datetime,
    interval: str = "Hour",
) -> dict[str, Any]:
    """Get energy consumption data for a unit.

    Args:
        unit_id: Unit UUID
        from_time: Start time
        to_time: End time
        interval: Aggregation interval (Hour, Day, Week, Month)

    Returns:
        Energy telemetry data

    Raises:
        AuthenticationError: If session expired
        ApiError: If API request fails
    """
    url = f"{self.base_url}/api/telemetry/energy/{unit_id}"
    params = {
        "from": from_time.strftime("%Y-%m-%d %H:%M"),
        "to": to_time.strftime("%Y-%m-%d %H:%M"),
        "interval": interval,
        "measure": "cumulative_energy_consumed_since_last_upload",
    }
    headers = {"x-csrf": "1"}

    async with self.session.get(url, params=params, headers=headers) as resp:
        if resp.status == 304:
            # No new data
            return None
        resp.raise_for_status()
        return await resp.json()

def _parse_energy_response(self, data: dict[str, Any]) -> float | None:
    """Parse energy telemetry response.

    Returns the most recent energy value in kWh.
    """
    if not data or "measureData" not in data:
        return None

    measure_data = data["measureData"]
    if not measure_data or not measure_data[0].get("values"):
        return None

    # Get most recent value
    values = measure_data[0]["values"]
    if not values:
        return None

    latest = values[-1]
    value_str = latest.get("value")
    if not value_str:
        return None

    # Parse and convert to kWh (assuming API returns Wh)
    # TODO: Verify unit with real device testing
    value = float(value_str)
    return value / 1000.0  # Convert Wh to kWh
```

---

## Coordinator Extension

```python
# In coordinator.py

from datetime import timedelta
from homeassistant.helpers.event import async_track_time_interval

class MELCloudHomeCoordinator(DataUpdateCoordinator):
    def __init__(self, ...):
        # ... existing init ...
        self._energy_data: dict[str, float | None] = {}
        self._energy_update_interval = timedelta(minutes=30)

    async def _async_setup(self) -> None:
        """Set up the coordinator."""
        # Schedule energy updates separately from main updates
        self._cancel_energy_updates = async_track_time_interval(
            self.hass,
            self._async_update_energy_data,
            self._energy_update_interval,
        )

    async def _async_update_energy_data(self, now: datetime | None = None) -> None:
        """Update energy data for all units."""
        try:
            to_time = datetime.utcnow()
            from_time = to_time - timedelta(hours=1)

            for building in self.data.buildings:
                for unit in building.air_to_air_units:
                    if not unit.capabilities.has_energy_consumed_meter:
                        continue

                    data = await self.client.get_energy_data(
                        unit.id, from_time, to_time, "Hour"
                    )

                    if data:
                        energy = self.client._parse_energy_response(data)
                        self._energy_data[unit.id] = energy

        except Exception as err:
            _LOGGER.error("Error updating energy data: %s", err)

    def get_unit_energy(self, unit_id: str) -> float | None:
        """Get cached energy data for a unit."""
        return self._energy_data.get(unit_id)
```

---

## Model Extension

```python
# In api/models.py

@dataclass
class AirToAirUnit:
    # ... existing fields ...
    energy_consumed: float | None = None  # kWh

    # Note: This will be set by coordinator, not from main API response
```

---

## Testing Strategy

### Unit Tests

```python
async def test_energy_sensor_available():
    """Test energy sensor is only available if device has capability."""
    # Unit with energy meter
    assert sensor.available is True

    # Unit without energy meter
    unit.capabilities.has_energy_consumed_meter = False
    assert sensor.available is False

async def test_energy_value_parsing():
    """Test energy value parsing from telemetry response."""
    response = {
        "measureData": [{
            "values": [{"value": "1500.0"}]
        }]
    }
    # Should convert Wh to kWh
    assert parse_energy(response) == 1.5
```

### Integration Tests

1. **Polling Test:**
   - Enable debug logging
   - Watch for energy updates every 30 minutes
   - Verify no errors in logs

2. **Energy Dashboard Test:**
   - Add energy sensor to Energy Dashboard
   - Configure as "Individual Device"
   - Verify data appears in dashboard
   - Check daily/monthly statistics

3. **Reset Test:**
   - Simulate counter reset (value decreases)
   - Verify HA handles gracefully
   - Check statistics still calculate correctly

4. **Offline Test:**
   - Disconnect device from WiFi
   - Verify sensor becomes unavailable
   - Reconnect and verify recovery

---

## Documentation Needed

### User-Facing

**README.md:**
```markdown
## Energy Monitoring

Energy consumption tracking is available for devices with energy meters:

- **Update Interval:** Every 30 minutes
- **Unit:** Kilowatt-hours (kWh)
- **Dashboard:** Integrates with Home Assistant Energy Dashboard

To enable energy tracking:
1. Your device must support energy monitoring (`hasEnergyConsumedMeter: true`)
2. Energy sensor will appear automatically
3. Add to Energy Dashboard under Settings > Dashboards > Energy

**Note:** Energy data updates every 30 minutes. Values are cumulative and may reset monthly.
```

### Developer-Facing

**ADR-008: Energy Monitoring Architecture**
- Architecture decisions documented
- Polling strategy and rationale
- Trade-offs considered
- Future enhancement paths

---

## Performance Considerations

### API Load

**Main Polling (60s):**
- 1 request per 60 seconds
- Gets all device state

**Energy Polling (30min):**
- 1 request per device per 30 minutes
- For 2 devices: +4 requests/hour
- Total: 60 + 4 = 64 requests/hour

**Impact:** Minimal - well within any reasonable rate limit

### Memory Usage

**Energy Cache:**
- 1 float per device
- 2 devices = 16 bytes
- Negligible memory impact

### CPU Usage

**Polling Overhead:**
- Separate async task
- Runs every 30 minutes
- JSON parsing + one API call
- Minimal CPU impact

---

## Known Limitations

1. **Update Lag:** 30-minute polling means data is not real-time
2. **Historical Data:** Currently fetches last hour only, doesn't backfill
3. **Unit Uncertainty:** Need real device testing to confirm Wh vs kWh
4. **No Rate Limit Info:** Conservative polling to avoid issues
5. **WebSocket Potential:** May have real-time energy data (investigate in v1.4+)

---

## Future Enhancements (v1.4+)

### Options Flow Configuration
- User-configurable polling interval (15/30/60 minutes)
- Enable/disable energy polling per device
- Historical data backfill option

### WebSocket Integration
- Real-time energy updates if WebSocket provides data
- Instant feedback instead of 30-minute lag
- Lower API load

### Advanced Features
- Cost calculation (if HA Energy Dashboard doesn't cover it)
- Peak usage alerts
- Efficiency scoring
- Comparison with previous periods

---

## Success Criteria

**v1.3 Energy Monitoring Success:**
- ✅ Energy sensor appears for capable devices
- ✅ Values increase over time correctly
- ✅ Integrates with HA Energy Dashboard
- ✅ Handles resets gracefully
- ✅ No errors in logs over 24+ hours
- ✅ 30-minute polling confirmed
- ✅ Proper unit conversion (Wh to kWh)
- ✅ Works with 2+ devices simultaneously

---

## References

- **Telemetry API:** `../api/melcloudhome-telemetry-endpoints.md`
- **API Discovery:** Local `_claude/melcloudhome-api-discovery.md:271` (hasEnergyConsumedMeter)
- **HA Sensor Docs:** https://developers.home-assistant.io/docs/core/entity/sensor/
- **HA Energy Dashboard:** https://www.home-assistant.io/docs/energy/
- **State Classes:** https://developers.home-assistant.io/docs/core/entity/sensor/#available-state-classes

---

## Open Questions (To Answer in Session 13)

1. ❓ What unit does the API actually return? (Wh or kWh?)
2. ❓ How often does the API update energy data?
3. ❓ Is there rate limiting on telemetry endpoints?
4. ❓ Can we fetch multiple units' data in one request?
5. ❓ Does WebSocket provide real-time energy data?
6. ❓ What happens to energy data when device is offline?
7. ❓ Is there a maximum time range for telemetry requests?

---

**Document Status:** Ready for Session 13 (Architecture & Planning)
**Next Action:** Create ADR-008 and begin implementation planning
**Blocked By:** WiFi signal sensor completion (Session 12)
