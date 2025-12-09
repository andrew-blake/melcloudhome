# Fix Energy Monitoring Undercount - Implementation Plan

**Issue:** GitHub #23 - Wrong amount of consumed energy (60-75% undercount)
**Root Cause:** Algorithm uses timestamp comparison instead of value-based delta tracking
**Status:** Ready for implementation

---

## API Behavior Recap

### How the MELCloud Home Energy API Actually Works

**Endpoint:**

```
GET /api/telemetry/energy/{unit_id}
  ?from=YYYY-MM-DD HH:MM
  &to=YYYY-MM-DD HH:MM
  &interval=Hour
  &measure=cumulative_energy_consumed_since_last_upload
```

**Response Format:**

```json
{
  "deviceId": "unit-id",
  "measureData": [{
    "type": "cumulativeEnergyConsumedSinceLastUpload",
    "values": [
      {"time": "2025-12-09 09:00:00.000000000", "value": "100.0"},
      {"time": "2025-12-09 10:00:00.000000000", "value": "300.0"}
    ]
  }]
}
```

**Key Behaviors (Confirmed with Real Data):**

1. **Per-Hour Consumption Values**
   - Each timestamp represents energy consumed during that hour
   - `09:00` = energy consumed from 09:00-10:00
   - Values are independent per hour (not lifetime cumulative)
   - Units: Watt-hours (Wh), need ÷1000 conversion to kWh

2. **Progressive Updates Within Hour** ⚠️ CRITICAL
   - Values for same hour increase multiple times (2-4 updates typical)
   - Pattern from real data (09:00 hour):
     - 09:05: 100 Wh (5 mins into hour, partial data)
     - 09:39: 300 Wh (39 mins, increased by 200 Wh)
     - 10:03: 400 Wh (past hour, final value, increased by 100 Wh)
   - Values stabilize after hour ends (become "final")

3. **Immediate Availability**
   - Hours appear within 3-20 minutes of starting
   - Provide partial data during the hour
   - No need to wait for hour completion

4. **Sparse Data**
   - Hours with no consumption are omitted (no zero values)
   - Only active hours appear in response
   - Gaps in sequence are normal

5. **Value Rounding**
   - All values rounded to nearest 100 Wh
   - Values: 0, 100, 200, 300, 400, 500, etc.
   - No fractional values

6. **No Decreases**
   - Values only increase or stay same within a hour
   - Never observed decrease (would indicate API error)

---

## The Bug in Current Implementation

**Current Algorithm (coordinator.py:188-229):**

```python
# Uses timestamp comparison
last_hour = self._energy_last_hour.get(unit.id)  # Single string timestamp

for value_entry in values:
    hour_timestamp = value_entry["time"]
    kwh_value = wh_value / 1000.0

    if hour_timestamp > last_hour:  # ❌ Only processes NEW hours
        self._energy_cumulative[unit.id] += kwh_value
        self._energy_last_hour[unit.id] = hour_timestamp
```

**Why It Fails:**

- Processes 09:00 at first sight (100 Wh) → adds 0.1 kWh ✓
- Later polls see 09:00 = 300 Wh → skips (not "newer" than 09:00) ✗
- Later polls see 09:00 = 400 Wh → skips again ✗
- **Result:** Tracked 100 Wh instead of 400 Wh = **75% undercount**

**Real-world impact:**

- From recorded data: 60-75% undercount per hour
- User report: 0.7 kWh/hour vs 2.2 kWh/hour = 68% undercount ✓
- Confirmed via 3+ hours of real API monitoring

---

## Solution: Delta-Based Tracking with 48-Hour Window

### Core Changes

**1. Track Individual Hour Values**

```python
# Replace single timestamp with per-hour value tracking
# OLD: self._energy_last_hour: dict[str, str] = {}
# NEW: self._energy_hour_values: dict[str, dict[str, float]] = {}

# Structure:
# {
#   "unit-id": {
#     "2025-12-09 08:00:00.000000000": 0.1,  # String timestamp → float kWh
#     "2025-12-09 09:00:00.000000000": 0.4,
#     "2025-12-09 10:00:00.000000000": 0.3
#   }
# }
```

**2. Process All Hours, Add Deltas**

```python
for value_entry in values:
    hour_timestamp = value_entry["time"]
    wh_value = float(value_entry["value"])
    kwh_value = wh_value / 1000.0

    # Get previous value for this specific hour (default 0)
    previous_value = self._energy_hour_values[unit.id].get(hour_timestamp, 0.0)

    if kwh_value > previous_value:
        # Value increased - add DELTA only
        delta = kwh_value - previous_value
        self._energy_cumulative[unit.id] += delta
        self._energy_hour_values[unit.id][hour_timestamp] = kwh_value

        _LOGGER.debug(
            "Energy: %s - Hour %s: +%.3f kWh delta (%.3f→%.3f) cumulative: %.3f kWh",
            unit.name, hour_timestamp[:16], delta, previous_value, kwh_value,
            self._energy_cumulative[unit.id]
        )
    elif kwh_value < previous_value:
        # Unexpected decrease - log warning, keep previous value
        _LOGGER.warning(
            "Energy: %s - Hour %s decreased %.3f→%.3f kWh - keeping previous value",
            unit.name, hour_timestamp[:16], previous_value, kwh_value
        )
```

**3. Increase Query Window to 48 Hours**

```python
# coordinator.py:150-151
to_time = datetime.now(UTC)
from_time = to_time - timedelta(hours=48)  # Increased from 2 hours
```

---

## Mitigating Reboots and Connectivity Issues

### Reboot Resilience

**Storage Persistence:**

```python
# Save after every energy poll
async def _save_energy_data(self) -> None:
    data = {
        "cumulative": self._energy_cumulative,
        "hour_values": self._energy_hour_values,  # NEW!
    }
    await self._store.async_save(data)
```

**Load with Migration:**

```python
stored_data = await self._store.async_load()
if stored_data:
    self._energy_cumulative = stored_data.get("cumulative", {})
    self._energy_hour_values = stored_data.get("hour_values", {})

    # Backward compatibility: migrate old format
    if not self._energy_hour_values and "last_hour" in stored_data:
        for unit_id in self._energy_cumulative.keys():
            self._energy_hour_values[unit_id] = {}
        _LOGGER.debug("Migrated from legacy storage format")
```

**Benefits:**

- ✅ Preserves cumulative totals across reboots
- ✅ Preserves hour value tracking
- ✅ Catches retroactive updates missed during downtime
- ✅ No data loss if reboot during hour updates

### Connectivity Outages

**48-Hour Window Handles:**

- ✅ Outages up to 48 hours without data loss
- ✅ Backfills all missed hours when connection restored
- ✅ Catches finalized values for hours that updated during outage

**Beyond 48 Hours:**

- Gap in data (intentional limitation: although the API retains older data, we restrict requests to a 48-hour window to balance data completeness with responsible API consumption)
- Cumulative sensor continues from stored total
- Energy Dashboard shows discontinuity
- Optional: Log warning when gap >48 hours detected

---

## Edge Cases Around Midnight

### Midnight Transition

**With 48-hour rolling window:**

```python
# At 2025-12-10 00:30 (30 mins after midnight)
to_time = 2025-12-10 00:30
from_time = 2025-12-08 00:30  # 48 hours ago

# Returns hours spanning multiple days seamlessly
```

**No special handling needed:**

- ✅ Rolling window naturally crosses midnight
- ✅ ISO timestamp strings compare correctly across days
- ✅ No boundary issues
- ✅ Unlike day-based queries (00:00-23:59), no discontinuity at midnight

### Year Boundary (New Year)

**Also handled naturally:**

```python
# At 2025-01-01 00:30
from_time = 2024-12-30 00:30
to_time = 2025-01-01 00:30

# String comparison works:
"2024-12-31 23:00:00" < "2025-01-01 00:00:00"  # TRUE ✓
```

**No edge cases** with ISO format and rolling window.

---

## ADR Strategy

### Update Existing ADR-008 (Not New ADR)

**Rationale:**

- Same architectural decision (energy monitoring)
- Corrects incorrect assumptions in original
- Documents bug fix in same context

**Changes to ADR-008:**

**1. Update "Data Format" Section (line 27-34):**

Add after line 34:

```markdown
**⚠️ Critical API Behavior: Progressive Updates**

Values for the same hour increase progressively as device uploads data:
- Hour appears early with partial data (e.g., 100 Wh)
- Values increase 2-4 times during the hour (e.g., 100→300→400 Wh)
- Values stabilize after hour ends (become "final")

**Example from Real API Monitoring:**
| Poll Time | 09:00 Hour | Notes |
|-----------|------------|-------|
| 09:05     | 100 Wh    | Partial (5 mins into hour) |
| 09:39     | 300 Wh    | Updated (+200 Wh) |
| 10:03     | 400 Wh    | Final (+100 Wh) |
| 10:13+    | 400 Wh    | Stable |

**Implementation Requirement:** Integration MUST track per-hour values and add deltas when values increase. Failing to handle progressive updates causes 60-75% energy undercount.
```

**2. Update "Polling Strategy" Section (line 76-98):**

Change line 86:

```markdown
**Time Range:** Last 2 hours → Last 48 hours

**Rationale:**
- Handles progressive value updates (values change during hour)
- Survives outages up to 48 hours without data loss
- Catches retroactive updates missed during downtime
- Handles midnight boundaries naturally (rolling window)
- Minimal API load increase (~2.4 KB vs 150 bytes)
```

**3. Add New Section After Line 98:**

```markdown
### Algorithm: Delta-Based Tracking

**Challenge:** API values update progressively, requiring delta-based accumulation.

**Implementation:**
1. Track individual hour values in dict: `{hour_timestamp: kwh_value}`
2. For each hour in API response:
   - Compare current value with stored value for that hour
   - If increased: add **delta** (not full value) to cumulative total
   - Update stored value for that hour
3. Store hour values for persistence across reboots

**Storage Format:**
```python
{
  "cumulative": {"unit-id": 12.8},      # Running total (kWh)
  "hour_values": {                       # Per-hour tracking
    "unit-id": {
      "2025-12-09 08:00:00": 0.1,
      "2025-12-09 09:00:00": 0.4,
      "2025-12-09 10:00:00": 0.3
    }
  }
}
```

**Benefits:**

- ✅ Captures all energy (no undercount)
- ✅ Handles progressive updates correctly
- ✅ Reboot-safe (preserves hour tracking)
- ✅ Outage-safe (up to 48 hours)

```

**4. Update "Consequences" Section (line 331-346):**

Add to Positive:
```markdown
- ✅ Delta-based tracking eliminates 60-75% undercount bug
- ✅ Resilient to reboots during hour updates
- ✅ Handles API progressive updates correctly
- ✅ 48-hour outage recovery
```

Update Negative:

```markdown
- ⚠️ Larger storage per device (~2 KB vs 50 bytes) - negligible impact
- ⚠️ More complex tracking logic - well-tested and documented
```

---

## Testing Strategy: TDD with Real Data Fixtures

### Testing Infrastructure

**HA Integration Tests run in Docker:**

```bash
make test-ha  # Builds Docker container, runs pytest in isolated environment
```

This ensures tests run with proper Home Assistant dependencies without version conflicts.

### Approach: Red → Green Refactoring

**Phase 1: Create Failing Tests (RED) ✗**

**File:** `tests/integration/test_coordinator_energy.py`

**Test 1: Progressive Updates (CRITICAL - Currently Missing)**

```python
async def test_energy_topping_up_progressive_updates(hass: HomeAssistant) -> None:
    """Test that hour values are topped up as they increase.

    Uses real API behavior pattern:
    - Poll 1: 09:00 = 100 Wh (partial)
    - Poll 2: 09:00 = 300 Wh (increased)
    - Poll 3: 09:00 = 400 Wh (final)

    Should accumulate: 0.1 + 0.2 + 0.1 = 0.4 kWh total
    NOT: 0.1 kWh only (current bug)

    Based on real recorded data from 2025-12-09 testing.
    """
    mock_context = create_mock_user_context_with_energy()

    initial_storage = {
        "cumulative": {TEST_UNIT_ID: 10.0},
        "hour_values": {TEST_UNIT_ID: {}}
    }

    with patch(MOCK_CLIENT_PATH) as mock_client_class, \
         patch(MOCK_STORE_PATH) as mock_store_class:

        # Setup mocks
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        mock_store = mock_store_class.return_value
        mock_store.async_load = AsyncMock(return_value=initial_storage)
        mock_store.async_save = AsyncMock()

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)

        # Poll 1 at 09:05: 09:00 = 100 Wh (partial)
        mock_client.get_energy_data = AsyncMock(
            return_value=create_mock_energy_response([
                ("2025-12-09 09:00:00.000000000", 100.0),
            ])
        )
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.melcloudhome_0efc_9abc_energy")
        assert state is not None
        assert float(state.state) == pytest.approx(10.1, rel=0.01)  # 10.0 + 0.1

        # Poll 2 at 09:39: 09:00 = 300 Wh (increased!)
        coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        mock_client.get_energy_data = AsyncMock(
            return_value=create_mock_energy_response([
                ("2025-12-09 09:00:00.000000000", 300.0),  # Increased from 100
            ])
        )
        await coordinator._async_update_energy_data()
        await hass.async_block_till_done()

        state = hass.states.get("sensor.melcloudhome_0efc_9abc_energy")
        # Should add delta: 0.3 - 0.1 = 0.2 kWh
        assert float(state.state) == pytest.approx(10.3, rel=0.01)  # 10.1 + 0.2
        # ❌ WILL FAIL with current implementation (stays at 10.1)

        # Poll 3 at 10:03: 09:00 = 400 Wh (final)
        mock_client.get_energy_data = AsyncMock(
            return_value=create_mock_energy_response([
                ("2025-12-09 09:00:00.000000000", 400.0),  # Increased again
                ("2025-12-09 10:00:00.000000000", 100.0),  # New hour
            ])
        )
        await coordinator._async_update_energy_data()
        await hass.async_block_till_done()

        state = hass.states.get("sensor.melcloudhome_0efc_9abc_energy")
        # Should add: delta 09:00 (0.1) + new 10:00 (0.1) = 0.2 kWh
        assert float(state.state) == pytest.approx(10.5, rel=0.01)  # 10.3 + 0.2
        # ❌ WILL FAIL with current implementation (would be 10.2)

        # Verify storage has hour values
        saved_data = mock_store.async_save.call_args[0][0]
        assert "hour_values" in saved_data
        assert saved_data["hour_values"][TEST_UNIT_ID]["2025-12-09 09:00:00.000000000"] == 0.4
        assert saved_data["hour_values"][TEST_UNIT_ID]["2025-12-09 10:00:00.000000000"] == 0.1
```

**Expected with Current Code (Run in Docker):**

```bash
# Run the failing test to prove bug exists
make test-ha

# Or run specific test:
docker run --rm -v $(PWD):/app -w /app melcloudhome-test:latest \
  pytest tests/integration/test_coordinator_energy.py::test_energy_topping_up_progressive_updates -v

# Expected output:
# FAILED tests/integration/test_coordinator_energy.py::test_energy_topping_up_progressive_updates
# AssertionError: assert 10.1 == 10.3
# Test FAILS ✗ - proves bug exists
```

**Test 2: Reboot During Hour Update**

```python
async def test_reboot_during_hour_update_preserves_tracking(hass: HomeAssistant) -> None:
    """Test that reboot during hour update doesn't lose data.

    Scenario:
    - Pre-reboot poll: 09:00 = 100 Wh, stored
    - Reboot
    - Post-reboot poll: 09:00 = 400 Wh (finalized during downtime)
    - Should add delta: 400 - 100 = 300 Wh
    """
    # First session state (before reboot)
    pre_reboot_storage = {
        "cumulative": {TEST_UNIT_ID: 10.1},
        "hour_values": {
            TEST_UNIT_ID: {"2025-12-09 09:00:00.000000000": 0.1}
        }
    }

    # Load as if restarted
    mock_store.async_load = AsyncMock(return_value=pre_reboot_storage)

    # Post-reboot poll shows increased value
    mock_client.get_energy_data = AsyncMock(
        return_value=create_mock_energy_response([
            ("2025-12-09 09:00:00.000000000", 400.0),  # Increased!
        ])
    )

    # Setup and verify
    # Should add delta: 0.4 - 0.1 = 0.3 kWh
    assert float(state.state) == pytest.approx(10.4, rel=0.01)
```

**Test 3: Storage Migration from Legacy Format**

```python
async def test_legacy_storage_format_migration(hass: HomeAssistant) -> None:
    """Test migration from old storage format.

    Old format: {"cumulative": {...}, "last_hour": {...}}
    New format: {"cumulative": {...}, "hour_values": {...}}
    """
    old_storage = {
        "cumulative": {TEST_UNIT_ID: 25.0},
        "last_hour": {TEST_UNIT_ID: "2025-12-08T23:00:00Z"}
        # Note: no hour_values key
    }

    mock_store.async_load = AsyncMock(return_value=old_storage)

    # Setup integration
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Verify cumulative preserved
    state = hass.states.get("sensor.melcloudhome_0efc_9abc_energy")
    # After migration + first poll, should have preserved cumulative
    # and started tracking hour_values

    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    assert coordinator._energy_cumulative[TEST_UNIT_ID] == 25.0
    assert TEST_UNIT_ID in coordinator._energy_hour_values
```

**Test 4: Unchanged Values (No-op)**

```python
async def test_unchanged_values_no_action(hass: HomeAssistant) -> None:
    """Test that repeated polls with same values don't change cumulative.

    Multiple polls showing same hour with same value = no delta.
    """
    initial_storage = {
        "cumulative": {TEST_UNIT_ID: 10.0},
        "hour_values": {
            TEST_UNIT_ID: {"2025-12-09 09:00:00.000000000": 0.3}
        }
    }

    # Poll returns same value
    mock_client.get_energy_data = AsyncMock(
        return_value=create_mock_energy_response([
            ("2025-12-09 09:00:00.000000000", 300.0),  # Same as stored
        ])
    )

    # Cumulative should remain 10.0 (no delta)
    assert float(state.state) == pytest.approx(10.0, rel=0.01)
```

**Test 5: Value Decrease Handling**

```python
async def test_value_decrease_keeps_previous(hass: HomeAssistant) -> None:
    """Test that value decreases are logged and ignored.

    If API returns lower value than previously seen (API glitch),
    keep previous higher value and log warning.
    """
    initial_storage = {
        "cumulative": {TEST_UNIT_ID: 10.3},
        "hour_values": {
            TEST_UNIT_ID: {"2025-12-09 09:00:00.000000000": 0.3}
        }
    }

    # Poll returns DECREASED value (unexpected)
    mock_client.get_energy_data = AsyncMock(
        return_value=create_mock_energy_response([
            ("2025-12-09 09:00:00.000000000", 200.0),  # Decreased from 300!
        ])
    )

    # Should NOT subtract, keep previous value
    assert float(state.state) == pytest.approx(10.3, rel=0.01)  # Unchanged

    # Should have logged warning (check logs in actual test)
```

### Using Real Data as Test Fixtures

**Create fixtures file:**

```python
# tests/integration/fixtures/energy_real_api_data.py
"""Real API response fixtures from production testing.

Data captured: 2025-12-09 08:45-11:41
Source: tools/energy_recording_redacted.json
Unit: Test Unit (unit-id-redacted)
"""

# 09:00 hour progression (real data)
HOUR_09_PROGRESSIVE_UPDATES = [
    {
        "poll_time": "09:05",
        "values": [("2025-12-09 09:00:00.000000000", 100.0)]
    },
    {
        "poll_time": "09:39",
        "values": [("2025-12-09 09:00:00.000000000", 300.0)]  # +200 Wh
    },
    {
        "poll_time": "10:03",
        "values": [("2025-12-09 09:00:00.000000000", 400.0)]  # +100 Wh
    },
]

# Can be imported in tests for realistic scenarios
```

---

## Phase 2: Fix Implementation (GREEN)

### File: `custom_components/melcloudhome/coordinator.py`

**Line 63: Add hour_values tracking**

```python
# After line 62
# Per-hour value tracking for delta calculation (handles progressive updates)
self._energy_hour_values: dict[str, dict[str, float]] = {}
```

**Line 64-65: Remove old tracking (AFTER migration added)**

```python
# DELETE these lines (after adding migration code):
# self._energy_last_hour: dict[str, str] = {}
```

**Lines 113-122: Update storage load with migration**

```python
stored_data = await self._store.async_load()
if stored_data:
    self._energy_cumulative = stored_data.get("cumulative", {})
    self._energy_hour_values = stored_data.get("hour_values", {})

    # Backward compatibility: support legacy format
    if not self._energy_hour_values:
        if "last_hour" in stored_data:
            # Initialize empty hour_values for existing units
            for unit_id in self._energy_cumulative.keys():
                self._energy_hour_values[unit_id] = {}
            _LOGGER.debug(
                "Migrated %d device(s) from legacy storage format (last_hour → hour_values)",
                len(self._energy_cumulative)
            )
        else:
            # Brand new, initialize empty
            _LOGGER.debug("No stored energy data found, starting fresh")
    else:
        _LOGGER.debug(
            "Restored energy data for %d device(s) from storage",
            len(self._energy_cumulative)
        )
```

**Lines 149-151: Increase query window**

```python
to_time = datetime.now(UTC)
# Fetch last 48 hours to handle outages and progressive updates
from_time = to_time - timedelta(hours=48)  # Changed from hours=2
```

**Lines 188-237: Replace processing logic**

Replace entire section with:

```python
# Get last processed hour for this device
# Initialize hour values dict if needed
if unit.id not in self._energy_hour_values:
    self._energy_hour_values[unit.id] = {}

# Initialize cumulative total if first time
if unit.id not in self._energy_cumulative:
    self._energy_cumulative[unit.id] = 0.0

# Check if this is first initialization (no hours tracked yet)
is_first_init = len(self._energy_hour_values[unit.id]) == 0

if is_first_init:
    # First initialization: mark all current hours as seen
    # but DON'T add them (avoid inflating with historical data)
    for value_entry in values:
        hour_timestamp = value_entry["time"]
        wh_value = float(value_entry["value"])
        kwh_value = wh_value / 1000.0
        self._energy_hour_values[unit.id][hour_timestamp] = kwh_value

    _LOGGER.debug(
        "Initializing energy tracking for %s at 0.0 kWh "
        "(marked %d hour(s) as seen, will track deltas from next update)",
        unit.name,
        len(values),
    )
else:
    # Normal operation: process each hourly value with delta tracking
    for value_entry in values:
        hour_timestamp = value_entry["time"]
        wh_value = float(value_entry["value"])
        kwh_value = wh_value / 1000.0

        # Get previous value for this specific hour (default 0 if new)
        previous_value = self._energy_hour_values[unit.id].get(
            hour_timestamp, 0.0
        )

        if kwh_value > previous_value:
            # Value increased - add the DELTA
            delta = kwh_value - previous_value
            self._energy_cumulative[unit.id] += delta
            self._energy_hour_values[unit.id][hour_timestamp] = kwh_value

            _LOGGER.debug(
                "Energy: %s - Hour %s: +%.3f kWh delta (%.3f→%.3f) cumulative: %.3f kWh",
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
                "Energy: %s - Hour %s decreased from %.3f to %.3f kWh - "
                "keeping previous value (possible API issue)",
                unit.name,
                hour_timestamp[:16],
                previous_value,
                kwh_value,
            )
            # Don't update stored value, keep previous
        # else: value unchanged, no action needed

# Store cumulative total for this unit
self._energy_data[unit.id] = self._energy_cumulative[unit.id]

_LOGGER.debug(
    "Total energy for %s: %.3f kWh (%d hour(s) tracked)",
    unit.name,
    self._energy_cumulative[unit.id],
    len(self._energy_hour_values[unit.id]),
)
```

**Lines 272-282: Update storage save**

```python
async def _save_energy_data(self) -> None:
    """Save energy cumulative totals and hour values to storage."""
    try:
        data = {
            "cumulative": self._energy_cumulative,
            "hour_values": self._energy_hour_values,  # NEW! (replaces last_hour)
        }
        await self._store.async_save(data)
        _LOGGER.debug("Saved energy data to storage")
    except Exception as err:
        _LOGGER.error("Error saving energy data: %s", err)
```

**Add new method: Storage cleanup (optional)**

```python
def _cleanup_old_hour_values(self) -> None:
    """Remove hour values older than 48 hours.

    Prevents unbounded storage growth. Hour values older than 48 hours
    are finalized and won't change, safe to remove.
    """
    cutoff = datetime.now(UTC) - timedelta(hours=48)
    cutoff_str = cutoff.strftime("%Y-%m-%d %H:00:00")

    for unit_id in list(self._energy_hour_values.keys()):
        if unit_id not in self._energy_hour_values:
            continue

        old_hours = [
            ts
            for ts in self._energy_hour_values[unit_id].keys()
            if ts < cutoff_str  # String comparison works with ISO format
        ]

        for hour_ts in old_hours:
            del self._energy_hour_values[unit_id][hour_ts]

        if old_hours:
            _LOGGER.debug(
                "Cleaned up %d old hour value(s) for %s (>48h old)",
                len(old_hours),
                unit_id[-8:],
            )

# Call at end of _async_update_energy_data (after line 267)
self._cleanup_old_hour_values()
```

### Step 3: Run Tests - Verify GREEN

**Run in Docker container:**

```bash
# Build test container and run all integration tests
make test-ha

# This builds the Docker image and runs:
# docker run --rm -v $(PWD):/app -w /app melcloudhome-test:latest \
#   pytest tests/integration/ -v -c tests/integration/pytest.ini

# Expected output:
# tests/integration/test_coordinator_energy.py::test_energy_topping_up_progressive_updates PASSED ✓
# tests/integration/test_coordinator_energy.py::test_reboot_during_hour_update_preserves_tracking PASSED ✓
# tests/integration/test_coordinator_energy.py::test_legacy_storage_format_migration PASSED ✓
# tests/integration/test_coordinator_energy.py::test_initial_energy_fetch_with_first_init PASSED ✓
# tests/integration/test_coordinator_energy.py::test_energy_accumulation_cumulative_totals PASSED ✓
# tests/integration/test_coordinator_energy.py::test_energy_persistence_across_restarts PASSED ✓
#
# ======================== All tests PASSED ✓ ========================

# Run specific test only:
docker run --rm -v $(PWD):/app -w /app melcloudhome-test:latest \
  pytest tests/integration/test_coordinator_energy.py::test_energy_topping_up_progressive_updates -v
```

---

## Files to Modify

### Core Implementation (Required)

1. **`custom_components/melcloudhome/coordinator.py`**
   - Lines 63: Add `_energy_hour_values`
   - Lines 64-65: Remove `_energy_last_hour` (after migration added)
   - Lines 113-122: Storage load with migration
   - Lines 149-151: Increase window to 48 hours
   - Lines 188-237: Delta-based processing logic
   - Lines 272-282: Update storage save
   - New method: `_cleanup_old_hour_values()`

2. **`tests/integration/test_coordinator_energy.py`**
   - Add `test_energy_topping_up_progressive_updates` (critical!)
   - Add `test_reboot_during_hour_update_preserves_tracking`
   - Add `test_legacy_storage_format_migration`
   - Add `test_unchanged_values_no_action`
   - Add `test_value_decrease_keeps_previous`
   - Update `test_double_hour_prevention` → rename and adjust

### Documentation (Required)

3. **`docs/decisions/008-energy-monitoring-architecture.md`**
   - Update "Data Format" section with progressive update pattern
   - Update "Polling Strategy" - 48 hour window
   - Add "Algorithm: Delta-Based Tracking" section
   - Update "Consequences" section

### Code Documentation (Optional but Recommended)

4. **`custom_components/melcloudhome/api/models.py`** - Update `energy_consumed` docstring
5. **`custom_components/melcloudhome/sensor.py`** - Update energy sensor description comment

### Test Fixtures (Optional but Helpful)

6. **`tests/integration/fixtures/energy_real_api_data.py`** - Extract real data patterns

### Diagnostic Tools (Keep for Future Use)

7. **`tools/energy_monitoring_recorder.py`** - API response recorder ✓ KEEP
   - Monitors API responses at regular intervals
   - Logs full JSON responses with timestamps
   - Supports resume mode for extended sessions
   - Useful for future API behavior investigations
   - Usage: `uv run python tools/energy_monitoring_recorder.py --help`

8. **`tools/debug_energy_api.py`** - One-off API query tool ✓ KEEP
   - Fetches and analyzes current energy data
   - Shows value progressions and patterns
   - Quick diagnostic for API behavior
   - Usage: `source .env && uv run python tools/debug_energy_api.py`

---

## Validation Plan

### 1. Unit Test Validation

**Run HA integration tests in Docker:**

```bash
# Build test container and run all integration tests
make test-ha

# This runs:
# docker build -t melcloudhome-test:latest -f tests/integration/Dockerfile .
# docker run --rm -v $(PWD):/app -w /app melcloudhome-test:latest \
#   pytest tests/integration/ -v -c tests/integration/pytest.ini

# Run specific test
docker run --rm -v $(PWD):/app -w /app melcloudhome-test:latest \
  pytest tests/integration/test_coordinator_energy.py::test_energy_topping_up_progressive_updates -v

# Run with coverage (API tests only, not HA integration)
make test-cov
# OR
uv run pytest tests/ --cov=custom_components.melcloudhome --cov-report=term-missing -vv
```

### 2. Integration Test on Live System

```bash
# Deploy to HA
python tools/deploy_custom_component.py melcloudhome

# Monitor energy logs
ssh ha "sudo docker logs homeassistant -f 2>&1 | grep 'Energy:'"

# Watch for delta logging:
# ✓ "Energy: Test Unit - Hour 2025-12-09 12:00: +0.200 kWh delta (0.100→0.300)"
```

### 3. Comparison with MELCloud App

**Test procedure:**

1. Note HA energy sensor value at specific time (e.g., 15:00)
2. Check same unit in MELCloud app for same time period
3. Compare totals
4. Values should match within ±100 Wh (API rounding tolerance)

**Before fix:**

- App: 15.5 kWh
- HA: 5.2 kWh (68% undercount) ✗

**After fix:**

- App: 15.5 kWh
- HA: 15.4 kWh (within tolerance) ✓

### 4. Long-term Monitoring

**Monitor for 24+ hours:**

- Check logs for warnings (value decreases, errors)
- Verify cumulative total increases normally
- Compare daily totals with MELCloud app
- Test reboot scenario (restart HA, verify no data loss)

---

## Implementation Sequence

### Day 1: Tests (RED)

1. ✅ Write failing test: `test_energy_topping_up_progressive_updates`
2. ✅ Run test, verify it fails
3. ✅ Write additional tests (reboot, migration, etc.)
4. ✅ All tests fail as expected

### Day 2: Implementation (GREEN)

1. ✅ Update coordinator algorithm (delta-based tracking)
2. ✅ Update storage load/save
3. ✅ Add migration logic
4. ✅ Run tests, verify all pass
5. ✅ Code review

### Day 3: Validation

1. ✅ Deploy to test HA instance
2. ✅ Monitor for 2+ hours
3. ✅ Compare with MELCloud app
4. ✅ Verify no undercount
5. ✅ Test reboot scenario

### Day 4: Documentation & Release

1. ✅ Update ADR-008
2. ✅ Update code comments
3. ✅ Prepare release notes
4. ✅ Update CHANGELOG
5. ✅ User validation

---

## Release Notes (Draft)

```markdown
## Fixed

- **Energy Monitoring Accuracy** - Fixed critical bug causing 60-75% undercount of energy consumption
  - Root cause: API returns progressive updates for same hour (values increase as data uploads)
  - Fix: Implemented delta-based tracking to handle increasing values correctly
  - Impact: Energy values now match MELCloud app and wall display
  - Migration: Automatic from legacy storage format, no user action required
  - Addresses: GitHub issue #23

## Changed

- Increased energy API query window from 2 hours to 48 hours
  - Enables recovery from outages up to 48 hours
  - Handles reboots during hour updates without data loss
  - Minimal API load increase

## Technical Details

- Storage format updated: `hour_values` dict replaces `last_hour` timestamp
- Algorithm changed: Per-hour delta tracking instead of timestamp comparison
- Backward compatible: Automatic migration from v1.3.3 storage format
- Testing: Comprehensive test suite added with real API data fixtures
```

---

## Summary

**Problem:** Integration undercounts energy by 60-75% due to missing progressive API updates

**Solution:**

- Track individual hour values (dict)
- Add deltas when values increase
- 48-hour query window
- Storage migration for backward compatibility

**Approach:**

- ✅ TDD: Write failing tests first (proves bug)
- ✅ Fix algorithm (tests pass)
- ✅ Real data fixtures from production testing
- ✅ Comprehensive edge case coverage

**Impact:**

- Fixes critical user-reported bug (GitHub #23)
- Eliminates energy tracking inaccuracy
- Makes integration match official app
- Low risk, well-tested, backward compatible

**Ready to implement!**
