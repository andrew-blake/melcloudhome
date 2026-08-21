# ADR-022: A Reading Is a Value Plus the Time the Unit Recorded It

**Status:** Accepted
**Date:** 2026-08-21
**Amends:** [ADR-006](006-entity-description-pattern.md) (`value_fn` becomes optional, alongside a new `reading_fn`)

## Context

Most of this integration's data comes from the 60-second `/context` poll, which
the vendor serves as live state. A minority does not: ATW flow/return
temperatures come from the per-measure telemetry endpoint on a 60-minute timer,
outdoor temperature from a report endpoint on a 30-minute timer, and energy
totals from hourly buckets on a 30-minute timer.

For those, a failed poll leaves the previous value in place. The tracker
returns without writing, the sensor keeps its state, and nothing distinguishes
that from a fresh reading of the same number. This is not hypothetical: over an
11.5-hour window on 2026-08-19 the per-measure telemetry endpoint failed on
70–100% of rounds for every measure on both prod ATW devices, and the sensors
sat on readings hours old.

Home Assistant's own state timestamps cannot express it. `State` carries
`last_changed`, `last_updated` and `last_reported`, and in
`StateMachine.async_set_internal` an identical rewrite takes the
`same_state and same_attr` branch, which advances only `last_reported` and
returns. `last_reported` therefore tracks *our write*, not the unit's reading —
and because `CoordinatorEntity` rewrites state on every coordinator update, it
advances every 60 seconds for a reading that is hours old.

The concept was already shipped once, for ATA outdoor temperature (#173):
a `outdoor_temp_recorded_at` field beside the value, and a hand-rolled
`attributes_fn` lambda on each of the two sensor platforms exposing it as a
`last_reading` attribute. That single instance was smeared across six files,
and the twelve other slow-cadence sensors had nothing.

## Decision

**A value that arrives with its own recording time is one object, not two
fields.**

```python
class Reading(NamedTuple):
    value: float
    recorded_at: datetime | None
```

It lives in `api/parsing.py` — the zero-dependency leaf both device model
modules already import from.

**Sensor descriptions declare `reading_fn` instead of `value_fn`** when their
data is reading-shaped. Exactly one of the two is set; a parametrized test over
`ATA_SENSOR_TYPES + ATW_SENSOR_TYPES` enforces that, rather than an
import-time assert that `-O` would strip and that would take the sensor
platform down if it ever fired. Both platforms route through
`sensor_native_value()` and `sensor_state_attributes()` in `helpers.py`, so
`last_reading` is implemented once.

**Provenance is surfaced as a `last_reading` state attribute**, ISO-8601, and
present-but-null when there is no reading yet. Twelve companion
`SensorDeviceClass.TIMESTAMP` entities were rejected: natively graphable, but
roughly doubling the ATW sensor count for a diagnostic. If staleness ever
becomes a user-facing feature, the better shape is one
`EntityCategory.DIAGNOSTIC` "oldest reading age" sensor per device — one entity
rather than twelve. This ADR produces the data that would make that small; it
does not build it.

**`recorded_at` is optional.** A payload can carry a value with no usable time.
Dropping such a datapoint would silently keep an older value in preference to a
newer one, so it is taken with no provenance and `last_reading` reads null. A
`Reading` of `None` means no value at all; the two states are deliberately
distinguishable.

**The newest datapoint is chosen by its own timestamp, not by position.** Every
observed response is in ascending order, but once the stamp is user-visible an
out-of-order response would make it travel backwards.

## What `last_reading` Buys

An unchanging value has two causes the entity state cannot currently separate:
the reading really is constant, or the poll stopped succeeding and the old value
is being re-presented. `last_reading` separates them.

See the table in [docs/entities.md](../entities.md) for how to read the attribute
alongside the value.

Identifying a placeholder takes the value as well. The vendor serves its constant
`25` for absent hardware with fresh, advancing datapoints, which by timestamp
looks like a steady circuit. The capability gating in #266 handles that case and
stands independently of this change.

## Timezone Caveat

Telemetry timestamps are naive, with 9 fractional digits
(`2026-01-14 12:48:44.047000000`), and are treated as UTC.
`datetime.fromisoformat` parses that form as-is from Python 3.11, so no
truncation guard is needed.

The evidence is **consistent with** UTC rather than proof of it: the
`return_temperature` cassette's newest datapoint sits 76 seconds inside a
UTC-based query window, which a device at any non-zero offset would have led or
trailed by far more. The VCR account's device country is unknown, so a
genuinely UTC+0 device would be indistinguishable. This is the same standard
already applied to `trendsummary` and `comfort-graph` timestamps.

## Consequences

- Reading-backed sensors gain a `last_reading` attribute; nothing gains or
  loses an entity, a unique_id, or a value. There is no statistics
  discontinuity.
- **Once `last_reading` advances, `same_attr` is false**, so a sensor whose
  value is unchanged fires `EVENT_STATE_CHANGED` instead of
  `EVENT_STATE_REPORTED` and its `last_updated` advances (`last_changed`
  correctly stays put). Automations triggering on these entities' state changes
  will fire on every poll that brings a newer stamp — including the
  placeholder case, where the value never moves. A *failed* poll writes
  nothing, so the attribute holds still and the fast path is preserved.
- The recorder stores a row per such poll per sensor. Twelve sensors at
  hourly-ish cadence is negligible.
- `last_reading` is null until the first successful slow-cadence poll — up to
  60 minutes for ATW telemetry. Since [ADR-021](021-deferred-startup-fetch.md)
  the first fetch is off the setup path, so entities appear immediately with
  the attribute present and null.
- Nothing is persisted, so a downgrade leaves no artefacts; the attribute
  simply disappears.
- This makes staleness **visible**. It does not make stale sensors update, and
  it does not change `available` — a missing reading still reads `unknown` per
  [ADR-020](020-unknown-for-missing-readings.md).
