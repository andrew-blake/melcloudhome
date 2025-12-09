# MELCloud Home Energy API Behavior - Confirmed Patterns

**Date:** 2025-12-09
**Test Duration:** 08:45 - 11:51 (3+ hours, 13+ polls)
**Test Unit:** Test Unit (ID redacted)
**Data Source:** Real API responses captured every 10 minutes

---

## API Endpoint

```
GET /api/telemetry/energy/{unit_id}
  ?from=YYYY-MM-DD HH:MM
  &to=YYYY-MM-DD HH:MM
  &interval=Hour
  &measure=cumulative_energy_consumed_since_last_upload
```

---

## Core Behavior Patterns

### 1. **Per-Hour Consumption Values**

**What the API Returns:**
- Each timestamp represents a 1-hour bin (e.g., `08:00` = 08:00-09:00 period)
- The value is the **total energy consumed during that specific hour**
- Values are in **Watt-hours (Wh)**, need conversion to kWh (÷1000)
- Values are **independent per hour**, not lifetime cumulative

**Example:**
```json
{
  "values": [
    {"time": "2025-12-09 09:00:00", "value": "400.0"},  // 400 Wh consumed 09:00-10:00
    {"time": "2025-12-09 10:00:00", "value": "300.0"},  // 300 Wh consumed 10:00-11:00
    {"time": "2025-12-09 11:00:00", "value": "200.0"}   // 200 Wh consumed 11:00-12:00
  ]
}
```

---

### 2. **Progressive Value Updates (CRITICAL!)**

**Values for the same hour increase over time as device uploads data.**

**Confirmed Pattern from Real Data:**

**09:00 Hour Progression:**
| Poll Time | Minutes into Hour | Value | Delta |
|-----------|-------------------|-------|-------|
| 09:05     | 5 mins           | 100 Wh | First appearance |
| 09:39     | 39 mins          | 300 Wh | +200 Wh |
| 10:03     | Past hour        | 400 Wh | +100 Wh (final) |
| 10:13+    | Past hour        | 400 Wh | Stable |

**10:00 Hour Progression:**
| Poll Time | Minutes into Hour | Value | Delta |
|-----------|-------------------|-------|-------|
| 10:03     | 3 mins           | 100 Wh | First appearance |
| 10:32     | 32 mins          | 200 Wh | +100 Wh |
| 10:42     | 42 mins          | 300 Wh | +100 Wh |
| 11:41     | Past hour        | 300 Wh | Stable (final) |

**11:00 Hour Progression:**
| Poll Time | Minutes into Hour | Value | Delta |
|-----------|-------------------|-------|-------|
| 11:20     | 20 mins          | 100 Wh | First appearance |
| 11:41     | 41 mins          | 200 Wh | +100 Wh |

**Key Insights:**
- ✅ Hours appear **immediately** (within 5-20 mins) with partial data
- ✅ Values **increase 2-4 times** during the hour
- ✅ Typical increases at ~30-40 mins into hour
- ✅ Values **stabilize** after hour ends (become "final")
- ✅ Pattern is **consistent and predictable** across all hours

---

### 3. **Update Timing Patterns**

**Early in Hour (0-20 mins):**
- Hour appears with low value (typically 100 Wh)
- Represents partial data from first ~20 minutes
- Value often stable during this period

**Mid-Hour (20-40 mins):**
- First significant increase often occurs
- Device uploads accumulated data
- Typically +100-200 Wh increases

**Late Hour (40-60 mins):**
- Additional increases common
- More data uploads from device
- Values approach final total

**After Hour Ends:**
- Values become "final" within 1-10 minutes
- No further changes observed
- Stable across all subsequent polls

---

### 4. **Sparse Data for Inactive Periods**

**Hours with no consumption are OMITTED from response:**
- API only returns hours where device was active
- No zero values returned
- Gaps in hour sequence are normal

**Example:**
```json
{
  "values": [
    {"time": "2025-12-09 01:00:00", "value": "100.0"},
    // 02:00, 03:00, 04:00, 05:00 omitted (unit was off)
    {"time": "2025-12-09 06:00:00", "value": "200.0"},
    {"time": "2025-12-09 08:00:00", "value": "100.0"}
  ]
}
```

---

### 5. **Value Rounding**

**API rounds to nearest 100 Wh:**
- Values: 0, 100, 200, 300, 400, 500, etc.
- Never fractional (e.g., no 150 Wh or 275 Wh)
- Repeated values across hours are expected (e.g., 300, 300, 300)

---

### 6. **No Decreases Observed**

**Values only increase or stay the same within an hour:**
- Never observed a value decrease for the same hour timestamp
- If decrease occurred, would indicate API issue or data correction
- Should be treated as error condition (log warning, keep previous value)

---

### 7. **Response Window**

**API returns hours within the requested time range:**
- `from` and `to` parameters define query window
- Typically query last 2-6 hours to ensure coverage
- Only returns hours with data (sparse array)
- Returns hours that overlap with time range

**Example Request at 10:30:**
```
from: 2025-12-09 04:30 (6 hours ago)
to:   2025-12-09 10:30 (now)

Returns hours: 06:00, 08:00, 09:00, 10:00
(07:00 omitted = no consumption)
```

---

## Current Implementation Bug

### The Flaw

**Coordinator uses single timestamp tracking:**
```python
# coordinator.py:188-229
last_hour = self._energy_last_hour.get(unit.id)  # String timestamp

for value_entry in values:
    hour_timestamp = value_entry["time"]
    kwh_value = wh_value / 1000.0

    if hour_timestamp > last_hour:  # ❌ Only processes NEW hours
        self._energy_cumulative[unit.id] += kwh_value
        self._energy_last_hour[unit.id] = hour_timestamp
```

**What Happens:**
1. First poll sees `09:00 = 100 Wh` → adds 0.1 kWh, marks 09:00 as "last_hour"
2. Second poll sees `09:00 = 300 Wh` → skips (`"09:00" > "09:00"` = false)
3. Third poll sees `09:00 = 400 Wh` → skips again
4. **Result:** Tracked 100 Wh instead of 400 Wh = **75% undercount**

### Real-World Impact

**From our recording data:**

**09:00 Hour:**
- Current algorithm: 100 Wh tracked
- Actual consumption: 400 Wh
- Undercount: **75%**

**10:00 Hour:**
- Current algorithm: 100 Wh tracked
- Actual consumption: 300 Wh (minimum, may increase further)
- Undercount: **67%+**

**11:00 Hour:**
- Current algorithm: 100 Wh tracked (if first polled at 11:20)
- Actual consumption: 200+ Wh (still increasing)
- Undercount: **50%+**

**Average undercount: ~60-75%**

This **exactly matches** user report in GitHub issue #23:
- User's app shows: 2.2 kWh/hour
- Integration shows: 0.7 kWh/hour
- Ratio: 0.7 / 2.2 = **32% tracked (68% undercount)**

---

## Required Fix: Delta-Based Tracking

### Algorithm Change

**Instead of tracking "last hour seen":**
```python
# OLD (wrong)
last_hour = self._energy_last_hour.get(unit.id)  # Single timestamp
```

**Track individual hour values:**
```python
# NEW (correct)
hour_values = self._energy_hour_values.get(unit.id, {})  # Dict of {timestamp: value}
```

### Processing Logic

```python
for value_entry in values:
    hour_timestamp = value_entry["time"]
    wh_value = float(value_entry["value"])
    kwh_value = wh_value / 1000.0

    # Get previous value for THIS SPECIFIC hour
    previous_value = hour_values.get(hour_timestamp, 0.0)

    if kwh_value > previous_value:
        # Value increased - add the DELTA
        delta = kwh_value - previous_value
        self._energy_cumulative[unit.id] += delta
        hour_values[hour_timestamp] = kwh_value

        _LOGGER.info(
            "Energy: %s - Hour %s: +%.3f kWh delta (%.3f → %.3f) cumulative: %.3f kWh",
            unit.name,
            hour_timestamp[:16],
            delta,
            previous_value,
            kwh_value,
            self._energy_cumulative[unit.id],
        )
    elif kwh_value < previous_value:
        # Unexpected decrease - log warning, keep previous value
        _LOGGER.warning(
            "Energy: %s - Hour %s decreased from %.3f to %.3f kWh - keeping previous value",
            unit.name,
            hour_timestamp[:16],
            previous_value,
            kwh_value,
        )
    # else: value unchanged, no action needed
```

### Example with Fix

**Poll at 09:05:** sees 09:00 = 100 Wh
```python
previous = 0.0
delta = 0.1 - 0.0 = 0.1 kWh
cumulative += 0.1
hour_values["09:00"] = 0.1
```

**Poll at 09:39:** sees 09:00 = 300 Wh
```python
previous = 0.1
delta = 0.3 - 0.1 = 0.2 kWh  ✓ Adds the increase!
cumulative += 0.2
hour_values["09:00"] = 0.3
```

**Poll at 10:03:** sees 09:00 = 400 Wh
```python
previous = 0.3
delta = 0.4 - 0.3 = 0.1 kWh  ✓ Adds the increase!
cumulative += 0.1
hour_values["09:00"] = 0.4
```

**Total tracked: 0.1 + 0.2 + 0.1 = 0.4 kWh** ✓ CORRECT!

---

## Storage Format Change

### Old Format (Current)
```json
{
  "cumulative": {
    "unit-id": 12.8
  },
  "last_hour": {
    "unit-id": "2025-12-09T07:00:00Z"
  }
}
```

**Problems:**
- Only tracks single timestamp per device
- Can't detect value increases for already-seen hours
- Loses information about individual hour values

### New Format (Required)
```json
{
  "cumulative": {
    "unit-id": 12.8
  },
  "hour_values": {
    "unit-id": {
      "2025-12-09T06:00:00Z": 0.2,
      "2025-12-09T07:00:00Z": 0.3,
      "2025-12-09T08:00:00Z": 0.1,
      "2025-12-09T09:00:00Z": 0.4,
      "2025-12-09T10:00:00Z": 0.3,
      "2025-12-09T11:00:00Z": 0.2
    }
  }
}
```

**Benefits:**
- ✅ Tracks each hour's current value
- ✅ Enables delta calculation on updates
- ✅ Prevents double-counting
- ✅ Supports topping up

### Migration Strategy

**On storage load:**
```python
stored_data = await self._store.async_load()
if stored_data:
    self._energy_cumulative = stored_data.get("cumulative", {})

    # NEW: Load hour values if available
    self._energy_hour_values = stored_data.get("hour_values", {})

    # OLD: Support legacy format (backward compatibility)
    if not self._energy_hour_values and "last_hour" in stored_data:
        # Initialize empty hour values, will populate on next poll
        self._energy_hour_values = {}
        _LOGGER.info("Migrated from legacy storage format (last_hour → hour_values)")
```

**No data loss:** Existing cumulative totals preserved, new tracking starts from next poll.

---

## Test Requirements

### Critical Missing Test

**Test:** Hour value increases (topping up)
**Status:** NOT IMPLEMENTED - This would have caught the bug!

**Test Case:**
```python
async def test_energy_value_increases_for_same_hour():
    """Test that hour values can increase as API data becomes complete.

    Simulates:
    - Poll 1: 09:00 = 100 Wh (partial)
    - Poll 2: 09:00 = 300 Wh (more complete)
    - Should add delta: 300 - 100 = 200 Wh
    """
    # Initial: First poll processed 09:00 with 100 Wh
    initial_storage = {
        "cumulative": {TEST_UNIT_ID: 10.0},
        "hour_values": {
            TEST_UNIT_ID: {"2025-01-15T09:00:00Z": 0.1}  # 100 Wh = 0.1 kWh
        }
    }

    # Second poll: same hour, increased value
    mock_energy_data = create_mock_energy_response([
        ("2025-01-15T09:00:00Z", 300.0),  # Increased from 100!
    ])

    # Expected: 10.0 + 0.2 (delta) = 10.2 kWh
    state = hass.states.get("sensor.melcloudhome_0efc_9abc_energy")
    assert float(state.state) == pytest.approx(10.2, rel=0.01)

    # Verify hour value updated
    saved_data = mock_store.async_save.call_args[0][0]
    assert saved_data["hour_values"][TEST_UNIT_ID]["2025-01-15T09:00:00Z"] == 0.3
```

---

## Additional Observations

### Timing Characteristics

**Initial Appearance:**
- Hours appear 3-20 minutes after hour starts
- Not instantaneous, but quite prompt
- Appears even during the hour (not delayed until hour ends)

**Update Frequency:**
- 2-4 updates per hour typical
- More frequent later in the hour
- Common pattern: early value (100), mid-hour increase (200-300), final value (300-400)

**Finalization:**
- Values stabilize 1-10 minutes after hour ends
- Once next hour starts, previous hour stops changing
- "Final" values remain constant

### Data Availability Delay

**No significant delay observed:**
- Hours appear within minutes of starting
- Don't need to wait until hour completes to see data
- Current hour bin returns partial data

**Implication:** No need to "wait 2 hours before processing" - can process immediately and top up as values increase.

### Rounding and Precision

**100 Wh granularity:**
- All values are multiples of 100 Wh
- No fractional values (no 150, 275, etc.)
- Repeated values across hours are normal (consumption pattern, not API issue)

**Example:** Three consecutive hours showing 300, 300, 300 Wh simply means each hour consumed ~300 Wh.

---

## API Quirks and Edge Cases

### 1. **Measure Parameter Name is Misleading**

Parameter: `cumulative_energy_consumed_since_last_upload`

**What it sounds like:** Cumulative total that resets periodically
**What it actually is:** Per-hour consumption values that update progressively

The "cumulative...since_last_upload" refers to how the **device** accumulates data locally before uploading to the cloud, NOT how the API returns the data.

### 2. **Values Can Update After Being Reported**

**Not a bug, it's a feature:**
- API provides best-available data at query time
- As device uploads more data, previous hours get updated
- This is normal behavior, not an API error
- Integration MUST handle this by reprocessing hours

### 3. **No 304 (Not Modified) Responses Observed**

- Every API call returned 200 OK with data
- Even when values unchanged, full response returned
- 304 handling may be unnecessary or only for specific conditions

### 4. **Response Always Includes Recent Hours**

- Even past hours (06:00, 08:00) continue appearing in responses
- API doesn't drop old hours immediately
- Need to limit storage to prevent unbounded growth

**Storage Cleanup Strategy:**
- Keep last 48 hours of hour values
- Older hours won't change anyway (finalized)
- Prevents memory/storage bloat

---

## Summary for Implementation

**What to change:**

1. **Data structures:**
   - Add `self._energy_hour_values: dict[str, dict[str, float]]`
   - Keep `self._energy_cumulative: dict[str, float]`
   - Remove `self._energy_last_hour: dict[str, str]` (no longer needed)

2. **Algorithm:**
   - For each hour in API response:
     - Get previous value for that hour (default 0)
     - If current > previous: add delta to cumulative
     - Update stored value for that hour

3. **Storage:**
   - Save `hour_values` instead of `last_hour`
   - Migrate old format gracefully
   - Add cleanup for hours older than 48 hours

4. **Tests:**
   - Add test for value increases (topping up)
   - Update test expectations to match delta logic
   - Add test for multiple increases per hour

5. **Logging:**
   - Log deltas, not absolute values
   - Show previous → current value for clarity
   - Warn on unexpected decreases

**Expected outcome:**
- ✅ Captures all energy consumption accurately
- ✅ Handles progressive updates correctly
- ✅ Eliminates 60-75% undercount
- ✅ Matches MELCloud app values
