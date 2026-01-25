# ADR-014: ATW Telemetry Sensors (Flow/Return Temperatures)

**Date:** 2026-01-14
**Status:** Accepted
**Decision Makers:** @andrew-blake

---

## Context

ATW heat pumps expose additional temperature sensors via the MELCloud Home telemetry API that are useful for monitoring heating system efficiency:
- Flow and return temperatures (system-level)
- Flow and return temperatures for Zone 1
- Flow and return temperatures for boiler circuit

These temperatures are not available in the main `/api/user/context` endpoint and require separate telemetry API calls.

**Question:** How should we fetch and expose this telemetry data in Home Assistant?

---

## Decision

**Implement telemetry sensors using normal sensor pattern with automatic statistics creation.**

**Approach:**
1. Create 6 new temperature sensors with `state_class=MEASUREMENT`
2. Poll telemetry API every 60 minutes
3. Update sensor state with latest telemetry value
4. Let HA recorder automatically create statistics

**No manual statistics import** - HA's built-in recorder handles everything.

---

## Alternatives Considered

### Alternative 1: Manual Statistics Import (REJECTED)

**Approach:**
- Fetch 48 hours of dense telemetry data
- Manually import all datapoints via `async_import_statistics`
- Backfill historical statistics for smooth graphs

**Why rejected:**
- Over-engineered (~300 lines of code)
- HAR analysis revealed telemetry data is **sparse** (0-4 datapoints/hour, not minute-level)
- Official MELCloud app only fetches 1-hour windows
- No dense data to backfill
- HA recorder already creates statistics automatically

### Alternative 2: Real-time Polling (REJECTED)

**Approach:**
- Poll every 5-10 minutes for fresher data
- Fetch minimal time window (15-30 minutes)

**Why rejected:**
- 6 API calls × 12 polls/hour = 72 calls/hour (too frequent)
- Temperature changes slowly (hourly polling sufficient)
- Risk of rate limiting

---

## Rationale

### 1. Spike Validation

**We built a prototype to validate the approach:**

**Spike scope:**
- Single measure (`flow_temperature`)
- Inline test code in coordinator
- 5-minute polling (for quick testing)

**Results:** ✅ Complete success
- Sensor created and displays value
- HA auto-created statistics ("No issue" in Statistics tab)
- History graph displays correctly with 5-minute aggregation
- No manual `async_import_statistics` needed

**Conclusion:** Normal sensor pattern with `state_class=MEASUREMENT` is sufficient.

### 2. Simplified Implementation

**Comparison:**

| Aspect | Manual Import | Normal Sensor |
|--------|--------------|---------------|
| Code complexity | ~300 lines | ~200 lines |
| Statistics logic | Manual | Automatic |
| Timestamp handling | Round to hour | HA handles |
| Deduplication | Manual tracking | HA handles |
| Storage | Custom | HA recorder |
| Testing | Complex | Simple |

**Benefit:** 33% less code, much simpler maintenance

### 3. Sparse Data Reality

**HAR analysis findings:**
- Telemetry data is sparse (0-4 datapoints/hour)
- Sometimes hours or days old
- Not dense minute-level data

**Implication:** No need for complex backfilling logic since there's minimal data to backfill.

### 4. HA Recorder Capabilities

**HA recorder automatically:**
- Creates short-term statistics (5-minute aggregation)
- Creates long-term statistics (hourly aggregation)
- Handles sparse data gracefully (interpolation/aggregation)
- Manages storage and cleanup
- Provides history graphs

**Benefit:** Leverage existing, well-tested HA functionality instead of reimplementing.

---

## Implementation Details

### TelemetryTracker Class

**Responsibilities:**
- Poll telemetry API every 60 minutes
- Fetch 4-hour lookback window (sparse data)
- Extract latest value for each measure
- Update ATW unit telemetry cache
- Add jitter (2-5s between measures, 1-3s between devices)

**Key simplification:** No statistics import logic - just update sensor state.

### Sensors

**6 new ATW sensors:**
```python
ATWSensorEntityDescription(
    key="flow_temperature",
    device_class=SensorDeviceClass.TEMPERATURE,
    state_class=SensorStateClass.MEASUREMENT,  # ← Triggers auto-statistics
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    value_fn=lambda unit: unit.telemetry.get("flow_temperature"),
)
```

**Polling:**
- Initial fetch on integration setup
- Scheduled updates every 60 minutes
- Jitter prevents API spam

### API Pattern

**Endpoint:** `GET /api/telemetry/actual/{unit_id}?from=X&to=Y&measure=Z`

**Parameters:**
- `from`/`to`: 4-hour window (sparse data sufficient)
- `measure`: One of 6 temperature measures

**Response:** JSON with timestamped values (typically 0-20 sparse datapoints)

---

## Consequences

### Positive

✅ **Simplicity**
- 33% less code than manual import approach
- Leverages HA's built-in capabilities
- Easier to maintain and test

✅ **Reliability**
- HA recorder is battle-tested
- Automatic statistics creation is standard HA pattern
- No custom storage/deduplication logic to debug

✅ **User Experience**
- Sensors appear immediately in UI
- History graphs work out of the box
- Statistics available in Developer Tools
- Compatible with HA dashboards/cards

✅ **Performance**
- Minimal API load (6 calls per hour per device)
- No database write amplification
- HA handles storage efficiently

### Negative

⚠️ **Initial Learning Curve**
- Required spike to validate approach
- Initial plan was over-engineered

⚠️ **Polling Frequency**
- 60-minute updates (not real-time)
- Acceptable trade-off for temperature monitoring

### Neutral

📊 **Statistics Behavior**
- HA creates hourly long-term statistics
- 5-minute short-term statistics for recent data
- Sparse input data results in interpolated graphs
- This is standard HA behavior (not custom)

---

## Validation

### Spike Results (2026-01-14)

**Test environment:** Local dev with mock server

**Validated:**
- [x] Sensor entity created
- [x] State updates from telemetry API
- [x] HA auto-creates statistics
- [x] History graph displays correctly
- [x] No errors in logs
- [x] All 6 measures working

**Evidence:** See `_claude/spike-results.md`

### Production Testing Plan

**Beta release:** v2.0.0-beta.5
- Community validates on real ATW hardware
- Verify telemetry data matches expectations
- Monitor for API rate limiting
- Collect feedback on sensor usefulness

---

## References

**Home Assistant Documentation:**
- [Sensor Entity](https://developers.home-assistant.io/docs/core/entity/sensor/)
- [Statistics](https://data.home-assistant.io/docs/statistics/)
- [Recorder Component](https://www.home-assistant.io/integrations/recorder)

**MELCloud API:**
- Telemetry endpoint: `GET /api/telemetry/actual/{unit_id}`
- See: `docs/api/melcloudhome-telemetry-endpoints.md`

**Project Files:**
- Implementation: `custom_components/melcloudhome/telemetry_tracker.py`
- Sensors: `custom_components/melcloudhome/sensor_atw.py`
- Coordinator: `custom_components/melcloudhome/coordinator.py:205-235`
- Spike results: `_claude/spike-results.md`

---

## Related Decisions

- [ADR-012: ATW Entity Architecture](012-atw-entity-architecture.md) - ATW sensor platform structure
- [ADR-016: Implement ATW Energy Monitoring](016-implement-atw-energy-monitoring.md) - ATW energy monitoring implementation (supersedes ADR-015)

---

## Notes

**Future enhancements:**
- WiFi RSSI sensor for ATW (via telemetry API)
- Configurable polling intervals (if users request)
- Additional measures if available (outdoor temp, etc.)

**Spike approach saved significant development time** by validating assumptions early and avoiding over-engineering.
