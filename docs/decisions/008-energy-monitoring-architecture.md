# ADR-008: Energy Monitoring Architecture

**Status:** Accepted
**Date:** 2025-11-19
**Deciders:** Development Team
**Related:** ADR-006 (Entity Description Pattern)

## Context

MELCloud Home API provides energy consumption data via a separate telemetry endpoint (`/api/telemetry/energy/{unit_id}`). This data is not included in the main `/api/user/context` response and requires separate polling. We need to integrate energy monitoring into the Home Assistant integration to enable energy dashboard functionality.

### API Capabilities

**Device Capability Detection:**
- Devices report `hasEnergyConsumedMeter: true` in capabilities
- Both test devices support energy monitoring

**Telemetry Endpoint:**
```
GET /api/telemetry/energy/{unit_id}
  ?from=YYYY-MM-DD HH:MM
  &to=YYYY-MM-DD HH:MM
  &interval=Hour|Day|Week|Month
  &measure=cumulative_energy_consumed_since_last_upload
```

**Data Format:**
- Returns hourly energy consumption values
- Values are strings that need float parsing
- **Unit: Watt-hours (Wh)** - confirmed via testing
- Typical range: 100-400 Wh/hour (0.1-0.4 kWh/hour)
- Values represent per-hour consumption, not lifetime cumulative
- Timestamps include nanosecond precision

### Testing Results

**Test Date:** 2025-11-19
**Test Devices:**
- Dining Room (0efce33f-5847-4042-88eb-aaf3ff6a76db) ✅
- Living Room (bf8d39c6-4f32-49fb-801b-b05cbe5c5119) ✅

**Sample Data:**
```json
{
  "deviceId": "0efce33f-5847-4042-88eb-aaf3ff6a76db",
  "measureData": [{
    "type": "cumulativeEnergyConsumedSinceLastUpload",
    "values": [
      {"time": "2025-11-18 09:00:00.000000000", "value": "300.0"},
      {"time": "2025-11-18 10:00:00.000000000", "value": "300.0"},
      {"time": "2025-11-18 11:00:00.000000000", "value": "400.0"}
    ]
  }]
}
```

**Key Finding:** Values in Wh, need conversion to kWh (÷1000) for HA

## Decision

### Architecture: Coordinator Extension

**Selected Approach:** Extend existing `MELCloudHomeCoordinator` with separate energy polling

**Rationale:**
- ✅ Centralized data management
- ✅ Proper error handling via coordinator
- ✅ Single authentication/session management
- ✅ Consistent with existing architecture
- ✅ Entity updates via established coordinator pattern

**Rejected Alternatives:**
1. **Separate Service Class** - Adds complexity and duplicate auth management
2. **Sensor Self-Polling** - Inefficient for multiple devices, no coordination

### Polling Strategy

**Polling Interval:** 30 minutes

**Rationale:**
- Energy data updates hourly from API
- 30 minutes provides responsive updates without excessive API load
- Conservative approach respects rate limiting
- Can be made configurable in future versions

**Time Range:** Last 1 hour

**Rationale:**
- Simple implementation
- Always current data
- Minimal data transfer
- Can add backfill in future if needed

**Impact:**
- Main polling: 1 req/60s (existing)
- Energy polling: 1 req/device/30min = 4 req/hour for 2 devices
- Total: 64 req/hour (minimal impact)

### Data Model

**Unit Conversion:** Wh → kWh (divide by 1000)

**State Class:** `SensorStateClass.TOTAL_INCREASING`
- Values increase over time (per billing period)
- May reset monthly
- HA handles reset detection automatically

**Device Class:** `SensorDeviceClass.ENERGY`
- Standard HA energy sensor
- Integrates with Energy Dashboard automatically
- Proper icon and unit display

**Unit:** `UnitOfEnergy.KILO_WATT_HOUR` (kWh)
- Required by HA Energy Dashboard
- Standard SI unit for energy

### Entity Naming

**Entity ID Format:** `sensor.melcloud_{short_id}_energy`

**Example:** `sensor.melcloud_0efc_76db_energy`

**Rationale:**
- Consistent with existing entity ID pattern (ADR-003)
- Short and clean (not `energy_consumed`)
- Follows entity description pattern (ADR-006)

### Error Handling

**No Data (304):** Return None, keep previous value
**Device Offline:** Sensor becomes unavailable via coordinator
**API Error:** Log error, retry on next poll
**Parse Error:** Log warning, return None

### Availability

**Sensor Available When:**
1. Coordinator is available (device online)
2. Device has `has_energy_consumed_meter: true`
3. Energy data successfully fetched (not None)

**Unavailable When:**
- Device offline
- API error persists
- Device doesn't support energy metering

## Implementation

### Phase 1: API Client Methods

Add to `custom_components/melcloudhome/api/client.py`:

```python
async def get_energy_data(
    self,
    unit_id: str,
    from_time: datetime,
    to_time: datetime,
    interval: str = "Hour",
) -> dict[str, Any] | None:
    """Get energy consumption data for a unit.

    Args:
        unit_id: Unit UUID
        from_time: Start time (UTC)
        to_time: End time (UTC)
        interval: Aggregation interval (Hour, Day, Week, Month)

    Returns:
        Energy telemetry data, or None if no data available

    Raises:
        AuthenticationError: If session expired
        ApiError: If API request fails
    """
    endpoint = f"/api/telemetry/energy/{unit_id}"
    params = {
        "from": from_time.strftime("%Y-%m-%d %H:%M"),
        "to": to_time.strftime("%Y-%m-%d %H:%M"),
        "interval": interval,
        "measure": "cumulative_energy_consumed_since_last_upload",
    }

    try:
        response = await self._api_request("GET", endpoint, params=params)
        return response
    except aiohttp.ClientResponseError as e:
        if e.status == 304:
            # No new data
            return None
        raise

def parse_energy_response(self, data: dict[str, Any] | None) -> float | None:
    """Parse energy telemetry response.

    Returns the most recent energy value in kWh.
    Converts from Wh to kWh.
    """
    if not data or "measureData" not in data:
        return None

    measure_data = data.get("measureData", [])
    if not measure_data:
        return None

    values = measure_data[0].get("values", [])
    if not values:
        return None

    # Get most recent value
    latest = values[-1]
    value_str = latest.get("value")
    if not value_str:
        return None

    try:
        # Convert Wh to kWh
        value_wh = float(value_str)
        return value_wh / 1000.0
    except (ValueError, TypeError) as e:
        _LOGGER.warning("Failed to parse energy value '%s': %s", value_str, e)
        return None
```

### Phase 2: Coordinator Extension

Update `custom_components/melcloudhome/coordinator.py`:

```python
from datetime import timedelta
from homeassistant.helpers.event import async_track_time_interval

class MELCloudHomeCoordinator(DataUpdateCoordinator):
    """Coordinator with separate energy polling."""

    def __init__(self, hass, client):
        super().__init__(...)
        self._energy_data: dict[str, float | None] = {}
        self._energy_update_interval = timedelta(minutes=30)
        self._cancel_energy_updates = None

    async def _async_setup(self) -> None:
        """Set up coordinator with energy polling."""
        # Initial energy fetch
        await self._async_update_energy_data()

        # Schedule periodic updates
        self._cancel_energy_updates = async_track_time_interval(
            self.hass,
            self._async_update_energy_data,
            self._energy_update_interval,
        )

    async def _async_update_energy_data(self, now: datetime | None = None) -> None:
        """Update energy data for all units."""
        from datetime import datetime, timezone

        try:
            to_time = datetime.now(timezone.utc)
            from_time = to_time - timedelta(hours=1)

            for building in self.data.buildings:
                for unit in building.air_to_air_units:
                    if not unit.capabilities.has_energy_consumed_meter:
                        continue

                    try:
                        data = await self.client.get_energy_data(
                            unit.id, from_time, to_time, "Hour"
                        )

                        energy = self.client.parse_energy_response(data)
                        self._energy_data[unit.id] = energy

                    except Exception as err:
                        _LOGGER.error(
                            "Error fetching energy for unit %s: %s",
                            unit.id, err
                        )

            # Notify sensors of energy update
            self.async_update_listeners()

        except Exception as err:
            _LOGGER.error("Error updating energy data: %s", err)

    def get_unit_energy(self, unit_id: str) -> float | None:
        """Get cached energy data for a unit."""
        return self._energy_data.get(unit_id)

    async def async_shutdown(self) -> None:
        """Clean up resources."""
        if self._cancel_energy_updates:
            self._cancel_energy_updates()
```

### Phase 3: Model Extension

Update `custom_components/melcloudhome/api/models.py`:

```python
@dataclass
class AirToAirUnit:
    # ... existing fields ...

    # Energy consumption (set by coordinator, not from main API)
    energy_consumed: float | None = None  # kWh
```

### Phase 4: Sensor Update

Update `custom_components/melcloudhome/sensor.py`:

Change entity description key from `"energy_consumed"` to `"energy"`:

```python
MELCloudHomeSensorEntityDescription(
    key="energy",  # Entity ID: sensor.melcloud_*_energy
    translation_key="energy",
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

## Consequences

### Positive

- ✅ Energy monitoring integrated with HA Energy Dashboard
- ✅ Automatic detection of energy-capable devices
- ✅ Consistent with existing architecture patterns
- ✅ Minimal API load (30-minute polling)
- ✅ Proper error handling and recovery
- ✅ Unit conversion handled transparently

### Negative

- ⚠️ 30-minute lag vs real-time data (acceptable for energy monitoring)
- ⚠️ Coordinator becomes more complex (managed via clean separation)
- ⚠️ Two polling intervals to maintain (well-encapsulated)

### Future Enhancements

**v1.4+:**
- User-configurable polling interval
- Historical data backfill option
- WebSocket integration for real-time updates
- Per-device enable/disable options

## Validation

### Success Criteria

- ✅ Energy sensors created for capable devices
- ✅ Values in kWh match physical consumption
- ✅ Energy Dashboard integration works
- ✅ 30-minute polling confirmed in logs
- ✅ Handles device offline gracefully
- ✅ No errors over 24+ hours

### Testing

1. **API Testing** ✅ - Confirmed Wh units, data format
2. **Integration Testing** - Deploy and verify sensors
3. **Dashboard Testing** - Add to Energy Dashboard
4. **Long-term Testing** - Monitor for 24+ hours
5. **Error Testing** - Test offline scenarios

## References

- [Energy Monitoring Requirements](_claude/energy-monitoring-requirements.md)
- [Telemetry API Documentation](_claude/melcloudhome-telemetry-endpoints.md)
- [ADR-006: Entity Description Pattern](006-entity-description-pattern.md)
- [ADR-003: Entity Naming Strategy](003-entity-naming-strategy.md)
- [HA Sensor Documentation](https://developers.home-assistant.io/docs/core/entity/sensor/)
- [HA Energy Dashboard](https://www.home-assistant.io/docs/energy/)
