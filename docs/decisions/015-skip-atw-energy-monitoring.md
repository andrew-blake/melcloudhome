# ADR-015: Skip ATW Energy Monitoring

**Date:** 2026-01-14
**Status:** Accepted
**Decision Makers:** @andrew-blake

---

## Context

The MELCloud Home API reports energy monitoring capabilities for ATW devices through the capabilities object:

```json
{
  "hasMeasuredEnergyConsumption": false,
  "hasMeasuredEnergyProduction": false,
  "hasEstimatedEnergyConsumption": true,
  "hasEstimatedEnergyProduction": true
}
```

**Question:** Should we implement energy monitoring for ATW devices similar to ATA devices?

---

## Decision

**Do NOT implement energy monitoring for ATW devices.**

**Rationale:** Insufficient data quality - only "Energy Produced" has data, "Energy Consumed" and "COP" are blank.

---

## Investigation

### API Capabilities

ATW devices report **estimated** energy (not measured):
- `hasMeasuredEnergyConsumption`: **false**
- `hasMeasuredEnergyProduction`: **false**
- `hasEstimatedEnergyConsumption`: **true** ← API claims this is available
- `hasEstimatedEnergyProduction`: **true** ← API claims this is available

**Contrast with ATA:**
- ATA devices have `hasEnergyConsumedMeter`: **true**
- ATA provides real measured consumption data
- ATA energy sensors are valuable and reliable

### MELCloud App Observation

**Checked energy charts in MELCloud Home app for ATW device:**

**Daily/Weekly/Monthly charts show:**
- ✅ **Energy Produced:** Has data (bar chart with values)
- ❌ **Energy Consumed:** Blank (no data)
- ❌ **COP (Coefficient of Performance):** Blank (no data)

**Conclusion:** Despite API capabilities claiming estimated data is available, only "Energy Produced" actually has values. Energy Consumed and COP are empty.

### Energy Data Quality Assessment

**Energy Produced alone is insufficient for useful monitoring because:**
1. Cannot track actual energy consumption (main use case)
2. Cannot calculate COP without both produced and consumed
3. "Produced" alone doesn't help with energy cost tracking
4. Not compatible with HA Energy Dashboard (requires consumption)

**ATA comparison:**
- ATA: Measured consumption → valuable for cost tracking, Energy Dashboard
- ATW: Estimated production only → limited value

---

## Alternatives Considered

### Alternative 1: Implement Energy Produced Only

**Approach:** Create single `sensor.melcloudhome_*_energy_produced` sensor

**Pros:**
- Shows some energy data
- Might be interesting for efficiency tracking

**Cons:**
- Limited usefulness without consumption
- Can't calculate COP
- Can't track costs
- Confusing to users ("why no consumption?")
- Sets expectation that energy monitoring works (it doesn't fully)

**Decision:** REJECTED - partial implementation creates more confusion than value

### Alternative 2: Wait for API Improvement

**Approach:** Skip for now, revisit when API provides real data

**Pros:**
- Clean decision boundary
- Can implement later if API improves
- No technical debt from partial implementation

**Cons:**
- None identified

**Decision:** ACCEPTED ✅

### Alternative 3: Implement with Warning Labels

**Approach:** Add energy sensors but label as "estimated" and "incomplete"

**Pros:**
- Provides available data
- Clear about limitations

**Cons:**
- Clutters UI with low-value sensors
- Extra maintenance burden
- User confusion likely

**Decision:** REJECTED - better to skip than provide confusing partial data

---

## Implementation

### Code Changes

**None required** - simply don't implement ATW energy sensors.

### Documentation

**README.md:**
- Document that energy monitoring is ATA-only
- Explain ATW has telemetry sensors instead

**EXPERIMENTAL-ATW.md:**
- Note energy monitoring not available for ATW
- Explain why (estimated only, incomplete data)
- Mention may be added in future if API improves

---

## Consequences

### Positive

✅ **Clear user expectations**
- Users understand ATW doesn't have energy monitoring
- No confusion from partial/incomplete data
- Focus on valuable sensors (telemetry temps)

✅ **Reduced complexity**
- No need to handle estimated vs measured energy
- No confusing sensor states
- Cleaner codebase

✅ **Future flexibility**
- Can easily add later if API provides real data
- No technical debt to clean up
- Decision can be revisited

### Negative

⚠️ **Missing feature for some users**
- Users who want *any* energy data will be disappointed
- Power users might want "Energy Produced" even if incomplete

⚠️ **Feature parity**
- ATA has energy, ATW doesn't
- May seem inconsistent (but justified by data quality)

### Mitigation

📝 **Clear documentation:**
- Explain why energy is skipped
- Document what data IS available (telemetry temps)
- Note decision is reversible if API improves

---

## Validation

### Manual Testing (2026-01-14)

**Verified in MELCloud Home web app:**
1. Opened Energy charts for ATW device
2. Checked Daily, Weekly, Monthly views
3. Confirmed: Only "Energy Produced" has data
4. Confirmed: "Energy Consumed" and "COP" are blank

**Conclusion:** Data quality insufficient for implementation.

### User Impact Assessment

**Who this affects:**
- ATW device owners expecting energy monitoring
- Users migrating from ATA (which has energy)

**Mitigation:**
- Document clearly in README and EXPERIMENTAL-ATW
- Provide alternative value: 6 telemetry temperature sensors
- Flow/return temps enable efficiency monitoring (alternative to COP)

---

## Future Considerations

### Conditions for Revisiting

**We should implement ATW energy monitoring IF:**
1. MELCloud API provides measured consumption (not just estimated)
2. Energy Consumed and COP populate with real data
3. Community requests it with clear use cases
4. API reliability improves

### Implementation Path (If Needed)

**If API improves:**
1. Check capabilities: `hasMeasuredEnergyConsumption`
2. Verify data availability in telemetry endpoint
3. Implement similar to ATA energy tracking
4. Add to Energy Dashboard integration
5. Update documentation

**Estimated effort:** 2-4 hours (can reuse ATA energy tracker pattern)

---

## References

**API Documentation:**
- Energy endpoint: `GET /api/telemetry/energy/{unit_id}`
- Capabilities: `custom_components/melcloudhome/api/models_atw.py:50-54`
- See: `docs/api/atw-api-reference.md:447-456`

**Related Decisions:**
- [ADR-014: ATW Telemetry Sensors](014-atw-telemetry-sensors.md) - What we implemented instead
- [ADR-012: ATW Entity Architecture](012-atw-entity-architecture.md) - ATW platform structure

**Evidence:**
- HAR captures show blank energy consumed/COP charts
- API capabilities claim estimated data available
- Actual app shows only partial data

---

## Notes

**Why "Energy Produced" has data but "Consumed" doesn't:**
- Unknown - possible API limitation or device capability
- Heat pumps inherently "produce" heat (output)
- Electrical consumption may not be metered on this model
- Estimated values may be unreliable/disabled

**Alternative for efficiency monitoring:**
- Flow/return temperature delta indicates efficiency
- Temperature sensors provide indirect performance metrics
- Users can create custom templates for efficiency calculations

---

## Conclusion

**Skip ATW energy monitoring due to insufficient data quality.** Focus on implementing valuable telemetry sensors (flow/return temperatures) that provide useful system monitoring capabilities. Decision is reversible if API improves in the future.
