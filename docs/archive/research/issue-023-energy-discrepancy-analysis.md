# GitHub Issue #23: Wrong Amount of Consumed Energy

**Date:** 2025-12-09
**Reporter:** hornyak2
**Status:** Investigating

## Problem Summary

The integration reports **lower energy consumption** than the MELCloud Home app and wall display:

- **MELCloud App / Wall Display:** 1.1 kWh per 30 minutes (≈ 2.2 kWh/hour)
- **This Integration:** 0.7 kWh/hour
- **Discrepancy:** Integration shows ~32% of actual consumption (0.7 / 2.2 = 0.318)

**Hardware:**
- Unit: SUZ-M50VAR2 + PEAD-M50JA2
- Adapter: MAC-587IF-E
- Wall Display: PAR-41MAA
- Integration Version: v1.3.3

## Root Cause Analysis

### API Endpoint Behavior

The integration uses this API endpoint:
```
GET /api/telemetry/energy/{unit_id}
?from=YYYY-MM-DD HH:MM
&to=YYYY-MM-DD HH:MM
&interval=Hour
&measure=cumulative_energy_consumed_since_last_upload
```

**Key Finding:** The API documentation (docs/api/melcloudhome-telemetry-endpoints.md:180) states:
> "Values are cumulative (not per-interval)"

Example API response:
```json
{
  "measureData": [{
    "values": [
      {"time": "2025-11-16 02:00:00", "value": "100.0"},
      {"time": "2025-11-16 07:00:00", "value": "100.0"},
      {"time": "2025-11-16 08:00:00", "value": "200.0"}
    ]
  }]
}
```

### Current Integration Logic (INCORRECT)

In `coordinator.py:210-226`, the integration treats each hour's value as an **incremental** amount:

```python
for value_entry in values:
    wh_value = float(value_entry["value"])
    kwh_value = wh_value / 1000.0

    if hour_timestamp > last_hour:
        # BUG: Adding cumulative value directly
        self._energy_cumulative[unit.id] += kwh_value
```

**Example with bug:**
If API returns hourly cumulative values:
- Hour 1: 1000 Wh (1.0 kWh consumed this hour)
- Hour 2: 3000 Wh (3.0 kWh consumed total for the period)
- Hour 3: 6000 Wh (6.0 kWh consumed total for the period)

Integration incorrectly calculates:
- cumulative = 0
- cumulative += 1.0 = 1.0 kWh
- cumulative += 3.0 = 4.0 kWh ❌ (should be 3.0 kWh)
- cumulative += 6.0 = 10.0 kWh ❌ (should be 6.0 kWh)

### Correct Logic (NEEDED)

The integration should either:

**Option 1: Use Latest Cumulative Value**
```python
# Just take the most recent cumulative value
if values:
    latest_value = values[-1]
    kwh_value = float(latest_value["value"]) / 1000.0
    self._energy_cumulative[unit.id] = kwh_value
```

**Option 2: Calculate Deltas Between Hours**
```python
# Calculate increment from previous hour
for i, value_entry in enumerate(values):
    hour_timestamp = value_entry["time"]
    wh_value = float(value_entry["value"])

    if hour_timestamp > last_hour:
        if i > 0:
            # Calculate delta from previous hour
            prev_wh = float(values[i-1]["value"])
            delta_wh = wh_value - prev_wh
            delta_kwh = max(0, delta_wh / 1000.0)  # Prevent negative
            self._energy_cumulative[unit.id] += delta_kwh
        else:
            # First value, need previous API call for delta
            # For now, skip or use full value
            pass
```

## Test Issues

The integration tests in `tests/integration/test_coordinator_energy.py` appear to be written assuming **per-interval** values, not cumulative:

```python
# Test expects to ADD each hour's value
mock_energy_data = create_mock_energy_response([
    ("2025-01-15T11:00:00Z", 600.0),  # NEW - add 0.6 kWh
    ("2025-01-15T12:00:00Z", 700.0),  # NEW - add 0.7 kWh
])
# Expected: 0.5 (initial) + 0.6 (11:00) + 0.7 (12:00) = 1.8 kWh
```

If values are truly cumulative, the test expectations are incorrect.

## Questions to Answer

1. **What does "cumulative_energy_consumed_since_last_upload" actually mean?**
   - Does it reset hourly, daily, or at each data upload?
   - Is "last_upload" per-device state or per-request?

2. **What do real API responses look like?**
   - Need to capture actual network traffic from MELCloud Home app
   - Compare consecutive hourly values to see if they're incremental or cumulative

3. **Does the behavior vary by device model?**
   - The closed issue #9 mentioned some A/C units don't report correctly
   - Could different hardware report in different formats?

## Next Steps

1. ✅ Capture actual API responses from MELCloud Home web app
2. Verify whether values are truly cumulative or per-interval
3. Determine the correct calculation logic
4. Update coordinator energy calculation
5. Update tests to match actual API behavior
6. Test with user's specific hardware (MAC-587IF-E adapter)

## Related Issues

- Issue #9 (closed, wontfix): "No energy usage for some A/C units"
  - That was an API limitation where no data was available at all
  - This issue (#23) is different: data exists but values are incorrect

## Additional Context

The user confirms that the MELCloud Home app shows correct values that match their main house meter, so the issue is definitely in the integration's calculation, not the API data itself.
