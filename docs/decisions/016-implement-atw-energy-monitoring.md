# ADR-016: Implement ATW Energy Monitoring

**Date:** 2026-01-18
**Status:** Accepted
**Supersedes:** [ADR-015: Skip ATW Energy Monitoring](015-skip-atw-energy-monitoring.md)
**Decision Makers:** @andrew-blake

---

## Context

ADR-015 (2026-01-14) decided to skip ATW energy monitoring due to insufficient data quality. Testing with an EHSCVM2D controller showed only "Energy Produced" had data, while "Energy Consumed" and "COP" were blank.

**New Discovery (2026-01-18):** A beta tester's ERSC-VM2D controller provides **COMPLETE** energy data:

```json
{
  "hasEstimatedEnergyConsumption": true,
  "hasEstimatedEnergyProduction": true
}
```

**HAR capture analysis revealed:**
- ✅ **Energy Consumed:** Complete hourly data via `interval_energy_consumed`
- ✅ **Energy Produced:** Complete hourly data via `interval_energy_produced`
- ✅ **COP:** Calculable from produced/consumed ratio

**Question:** Should we reverse ADR-015 and implement ATW energy monitoring?

---

## Decision

**IMPLEMENT energy monitoring for ATW devices with capability-based detection.**

**Approach:**
1. Add 3 new sensors: `energy_consumed`, `energy_produced`, `cop`
2. Capability-based detection: Only create sensors if `hasEstimatedEnergyConsumption=true` AND `hasEstimatedEnergyProduction=true`
3. Reuse ATA energy tracker pattern (DRY)
4. Device-specific behavior: ERSC-VM2D gets sensors, EHSCVM2D does not

---

## Investigation

### Device Type Comparison

**ERSC-VM2D (Belgrade device - Complete energy data):**
```json
{
  "hasEstimatedEnergyConsumption": true,
  "hasEstimatedEnergyProduction": true
}
```
- ✅ Energy consumed: Full hourly data
- ✅ Energy produced: Full hourly data
- ✅ COP: Calculated (produced/consumed)
- ✅ Home Assistant Energy Dashboard compatible
- **Use case:** New installations with energy metering capability

**EHSCVM2D (Madrid device - Incomplete data):**
```json
{
  "hasEstimatedEnergyConsumption": false,
  "hasEstimatedEnergyProduction": false
}
```
- ❌ No energy sensors created (capabilities = false)
- ✅ Still gets 6 telemetry temperature sensors
- **Use case:** Older installations without energy metering

### Why This Works

**Capability-based detection ensures:**
1. ERSC-VM2D users get valuable energy monitoring
2. EHSCVM2D users don't see broken/incomplete sensors
3. No confusion - sensors only appear when data is complete
4. Future-proof - supports new controller types automatically

---

## Alternatives Considered

### Alternative 1: Universal Implementation (REJECTED)

**Approach:** Create energy sensors for all ATW devices regardless of capabilities

**Why rejected:**
- EHSCVM2D devices would show broken/empty sensors
- Violates principle of only showing working sensors
- User confusion ("why is my energy data blank?")

### Alternative 2: Keep ADR-015 (REJECTED)

**Approach:** Don't implement, even though ERSC-VM2D has complete data

**Why rejected:**
- Beta tester has requested this feature
- Data quality is confirmed excellent
- Missing valuable feature for ERSC-VM2D users
- Capability detection solves the partial data problem

### Alternative 3: Capability-Based Detection (ACCEPTED) ✅

**Approach:**
- Check capabilities before creating sensors
- Only create if BOTH consumed and produced are available
- Automatically supports future controller types

**Pros:**
- ✅ Works perfectly for ERSC-VM2D (complete data)
- ✅ Skips EHSCVM2D (incomplete data)
- ✅ No user confusion
- ✅ Future-proof design
- ✅ Home Assistant best practices

---

## Implementation

### API Layer

**File:** `custom_components/melcloudhome/api/client_atw.py`

```python
async def get_energy_consumed(...) -> dict | None:
    """Fetch interval_energy_consumed measure."""
    return await self._get_energy_data(
        unit_id, "interval_energy_consumed", from_time, to_time, interval
    )

async def get_energy_produced(...) -> dict | None:
    """Fetch interval_energy_produced measure."""
    return await self._get_energy_data(
        unit_id, "interval_energy_produced", from_time, to_time, interval
    )
```

**Endpoint:** `GET /api/telemetry/energy/{unit_id}?measure=interval_energy_*`

### Energy Tracker

**File:** `custom_components/melcloudhome/energy_tracker_atw.py`

**Pattern:** Reuses `EnergyTrackerBase` from ATA implementation (DRY)

**Multi-measure support:**
- Tracks both consumed and produced in single storage file
- COP calculated on-the-fly: `produced / consumed`
- Handles edge cases (consumed=0, None values)

### Sensor Platform

**File:** `custom_components/melcloudhome/sensor_atw.py`

**Sensors created (if capabilities present):**
1. `sensor.melcloudhome_*_energy_consumed` - kWh consumed (statistics, energy)
2. `sensor.melcloudhome_*_energy_produced` - kWh produced (statistics, energy)
3. `sensor.melcloudhome_*_cop` - Coefficient of performance (ratio)

**Capability check:**
```python
if (
    unit.capabilities.has_estimated_energy_consumption
    and unit.capabilities.has_estimated_energy_production
):
    # Create energy sensors
```

### Storage Migration

**Format:** v1.3.4 → v2.0.0

**v1.3.4 (single measure):**
```json
{
  "unit_id": {"cumulative": 123.45, "hour_values": {...}}
}
```

**v2.0.0 (multi-measure):**
```json
{
  "unit_id": {
    "interval_energy_consumed": {"cumulative": 123.45, "hour_values": {...}},
    "interval_energy_produced": {"cumulative": 456.78, "hour_values": {...}}
  }
}
```

**Migration:** Automatic on first load (preserves v1.3.4 data for ATA devices)

---

## Testing

### API Tests

**File:** `tests/api/test_energy_atw.py` (73 tests)

- ✅ Energy consumed fetching with VCR cassette
- ✅ Energy produced fetching with VCR cassette
- ✅ COP calculation edge cases
- ✅ Empty data handling

### Integration Tests

**File:** `tests/integration/test_sensor_atw.py` (123 tests)

- ✅ Energy sensors created when capabilities present
- ✅ Energy sensors NOT created when capabilities absent
- ✅ COP calculation in coordinator
- ✅ Energy Dashboard integration

### Real Device Testing

**Belgrade Device (ERSC-VM2D):**
- ✅ 3 energy sensors created
- ✅ Energy consumed: 2-4 kWh/hour
- ✅ Energy produced: 6-12 kWh/hour
- ✅ COP: 2.5-3.5 (realistic heat pump efficiency)
- ✅ Energy Dashboard: Consumption tracking works

**Madrid Device (EHSCVM2D):**
- ✅ 0 energy sensors created (capabilities=false)
- ✅ Still has 6 telemetry temperature sensors
- ✅ No broken/empty sensors visible

---

## Consequences

### Positive

✅ **Feature parity with ATA**
- ATW now has energy monitoring like ATA
- Both device types support Energy Dashboard
- Consistent user experience

✅ **Valuable for ERSC-VM2D owners**
- Track energy consumption
- Monitor COP (heat pump efficiency)
- Integrate with Energy Dashboard
- Cost tracking with energy tariffs

✅ **Clean implementation**
- Reuses ATA energy tracker (DRY)
- Capability-based detection (no broken sensors)
- Minimal code duplication
- Future-proof for new controller types

✅ **No downside for EHSCVM2D**
- Capabilities=false → sensors not created
- Still get telemetry sensors
- No confusion or broken UI

### Negative

⚠️ **Controller-specific behavior**
- ERSC-VM2D: Has energy sensors
- EHSCVM2D: Does not have energy sensors
- May confuse users with both controller types
- **Mitigation:** Document in README and ADR

⚠️ **Estimated vs Measured**
- ATA: Measured consumption (hardware meter)
- ATW: Estimated consumption/production (calculated)
- Accuracy may vary by installation
- **Mitigation:** Document data source in sensor descriptions

### Mitigation

📝 **Documentation:**
- README explains energy is controller-dependent
- CLAUDE.md notes ERSC-VM2D vs EHSCVM2D differences
- API reference documents capability flags
- ADR-016 provides technical details

---

## Validation

### HAR Capture Analysis (2026-01-17)

**Source:** `_claude/melcloudhome.com-ATW-pumpa.har`

**Verified:**
1. `/api/user/context` returns `hasEstimatedEnergy*=true` for Belgrade device
2. `/api/telemetry/energy/{id}?measure=interval_energy_consumed` returns 24 hours of data
3. `/api/telemetry/energy/{id}?measure=interval_energy_produced` returns 24 hours of data
4. Values are realistic (consumed: 2-4 kWh/hour, produced: 6-12 kWh/hour)
5. COP calculation produces expected values (2.5-3.5)

### Beta Tester Feedback

**Request:** "Can you add energy monitoring for my ERSC-VM2D heat pump?"

**Result:** Feature implemented and tested with beta tester's device data

---

## Related Decisions

- **[ADR-015: Skip ATW Energy Monitoring](015-skip-atw-energy-monitoring.md)** - SUPERSEDED by this ADR
- **[ADR-014: ATW Telemetry Sensors](014-atw-telemetry-sensors.md)** - Temperature sensor implementation
- **[ADR-012: ATW Entity Architecture](012-atw-entity-architecture.md)** - ATW platform structure
- **[ADR-008: Energy Monitoring Architecture](008-energy-monitoring-architecture.md)** - ATA energy pattern (reused for ATW)

---

## References

**API Documentation:**
- `docs/api/atw-api-reference.md` - Energy endpoints section
- Energy endpoint: `GET /api/telemetry/energy/{unit_id}`
- Capabilities: `hasEstimatedEnergyConsumption`, `hasEstimatedEnergyProduction`

**Implementation:**
- API client: `custom_components/melcloudhome/api/client_atw.py:285-320`
- Energy tracker: `custom_components/melcloudhome/energy_tracker_atw.py`
- Sensors: `custom_components/melcloudhome/sensor_atw.py:145-180`

**Testing:**
- API tests: `tests/api/test_energy_atw.py` (73 tests)
- Integration tests: `tests/integration/test_sensor_atw.py` (123 tests)
- Test device: Belgrade ERSC-VM2D (unit ID: `37de5a0f-4d42-4e9e-92f4-362aada35f18`)

---

## Conclusion

**Implement ATW energy monitoring with capability-based detection.** This reverses ADR-015 based on new evidence that ERSC-VM2D controllers provide complete energy data. The capability-based approach ensures only devices with complete data show energy sensors, avoiding the partial data problem identified in ADR-015 with EHSCVM2D controllers.

**Result:** ATW devices graduate from experimental to stable with feature parity to ATA devices.
