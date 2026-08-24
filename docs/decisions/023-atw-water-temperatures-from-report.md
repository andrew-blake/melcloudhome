# ADR-023: ATW Water Temperatures Come From the Internal Temperatures Report

**Status:** Accepted
**Date:** 2026-08-22
**Amends:** [ADR-014](014-atw-telemetry-sensors.md) (the endpoint those sensors read)
**Decision Makers:** @andrew-blake

---

## Context

ATW flow and return temperatures were read one measure at a time from
`/telemetry/telemetry/actual/{unitId}?measure=…`. That endpoint was never
chosen for ATW: it was copied from the web UI's *ATA* temperature chart
(`13c986d`, 2025-11-16) and reused for water temperatures without re-checking
what the ATW chart does. `git grep -i internaltemperatures` over
`git rev-list --all` returns nothing, so the alternative had never been on the
table.

`/report/v1/internaltemperatures` returns every water-temperature series for a
unit in one response, keyed by dataset id, and those ids are byte-identical to
the measure names the per-measure endpoint used. Dispatch is an identity
mapping.

**The reason to switch is reliability, and it is measured.** From one prod
container log over roughly two days, counting the integration's own traffic so
both sides share account, client, token, window and concurrent load:

| endpoint | 200 | 500 |
|---|---|---|
| `/context` | 2608 | 0 |
| `report/v1/trendsummary` | 384 | 0 |
| `report/v1/comfort-graph` | 127 | 0 |
| `telemetry/telemetry/energy` | 640 | 0 |
| **`telemetry/telemetry/actual`** | **14** | **118 (89%)** |

3,759 responses across four endpoints with zero 500s, beside 89% failure on the
one being replaced. One broken route rather than a flaky backend, and a rate or
concurrency limit would not spare four endpoints and hit the fifth. The count is
a floor: it is client-logged requests, and it does not separate any that were
retried and later succeeded.

**Request count is not the argument.** After #266 gated the suffixed measures on
capabilities, a single-zone boilerless unit made 2 `telemetry-actual` calls per
cycle, so this replaces 2 requests with 1. A two-zone unit with a boiler still
made 8. ADR-014's "6 API calls × 12 polls/hour" arithmetic was true when
written and stopped being true before this change.

**Convergence and deletion are the secondary argument.** `get_telemetry_actual`,
the per-measure loop, the inter-measure jitter and its two constants, the
`DATA_LOOKBACK_HOURS_TELEMETRY` constant and the per-measure error handling all
collapse into one call plus dataset dispatch, reusing report parsing that two
other endpoints already exercise. One time-series pattern in the codebase
instead of two.

## Decision

**ATW water temperatures come from one `report/v1/internaltemperatures` request
per unit per cycle.**

- **`period=Hourly`, 8h lookback.** Hourly is the only period whose points carry
  genuine reading timestamps; `Daily` returns 30-minute bucket labels whose
  values can diverge from the latest reading (#152). The server floors `from` to
  midnight of its own date, in the unit's own timezone, and a floored span of one
  day is always served. 8h keeps the window inside that day for any poll running
  after 08:00 local, and a poll before then reaches into the previous day, which
  returns *more* data when it is served. Wider lookbacks are not dependable: a
  two-day floored span is served at some times of day and refused at others (see
  `docs/api/atw-api-reference.md`). A sparse uploader quiet for hours still has a real last reading
  worth showing, and `last_reading` ([ADR-022](022-reading-provenance.md))
  carries its age.
- **Synthetic points are stripped by the shared rule.** The server appends
  bucket-aligned repeats and a final echo of the query's own `to`. Genuine
  readings carry arbitrary seconds, so `_latest_genuine_reading` skips points
  with `seconds == 0`, and callers send a seconds-aligned `to` so the echo is
  caught by the same rule (#224). The newest reading is chosen by timestamp
  rather than position, because `last_reading` is user-visible and an
  out-of-order response would send a stamp backwards.
- **The capability filter moved from request to response.** All eight datasets
  arrive whichever hardware a unit has; what the absent ones *contain* has been
  observed two different ways (an empty series, and a constant 25 placeholder —
  see the dated observations in `docs/api/atw-api-reference.md`). Both are
  handled without a special case: a dataset with no genuine point is omitted by
  the parser, and a placeholder value is dropped by the capability filter. The
  `ATW_TELEMETRY_MEASURES*` lists still decide what to keep, on the same rules
  as before, so #266's creation gating is untouched.
- **A measure absent from a successful response reads `unknown`.** See below.

## The Zone-2 Assumption

**Both units ever observed on this endpoint were single-zone, and neither
response carried zone-2 series. Shipping zone-2 datasets for a unit that has
zone 2 is therefore an assumption, taken deliberately (2026-08-21, reaffirmed
2026-08-22) rather than established by evidence.**

**What tilts it that way:** the vendor's decompiled `App.Shared.ReportTimeDataSet`
carries hardcoded static templates for `flow_temperature_zone2` and
`return_temperature_zone2` alongside the eight datasets seen on the wire,
`App.Shared` is shared with the server so the server builds responses from those
templates, and the `INTEMP_REPORT` label namespace has keys for both.

**What keeps it an assumption:** the same namespace carries
`ROOM_TEMPERATURE_ZONE1` and `SET_TEMPERATURE_ZONE1`, and neither is emitted even
though that hardware exists. Template and label presence is a superset of what
the server sends.

**What would falsify it:** a diagnostics capture from a real two-zone unit taken
while the system is actively heating, showing the report without zone-2 datasets.
An idle snapshot cannot separate a flat placeholder from a settled circuit.

**Accepted downside if wrong:** two-zone users' `flow_temperature_zone2` and
`return_temperature_zone2` read `unknown` with a null `last_reading`. Nothing
else regresses, and the remedy is a revert rather than a patch.

**Detection:** `_warn_if_zone2_missing` logs one WARNING per unit per HA run when
a unit whose capabilities report zone 2 receives no zone-2 datasets. The sensors
already show the problem; the warning names the cause. It is diagnostics, not a
mitigation.

**The hybrid was rejected** — base pair from the report, zone 2 from per-measure
calls. It keeps `get_telemetry_actual`, the per-measure loop and the measure-list
constants alive, which is most of what this change deletes, and a "temporary"
second path gated on a capture that may never arrive is permanent in practice.

## Missing Readings Read `unknown`, and Outdoor Temperature Differs

A measure absent from an otherwise-successful response clears that measure, so
the sensor reads `unknown` with a null `last_reading`
([ADR-020](020-unknown-for-missing-readings.md)). A **failed request** raises,
the tracker keeps its cached readings, and `last_reading` shows them ageing. The
two cases stay distinct because the client raises rather than returning an empty
result.

**Outdoor temperature does the opposite on the same input**, and that is
deliberate. `_poll_outdoor_temperature` keeps the previous `Reading` when a
successful poll yields no genuine reading, because idle units stop uploading and
a short window returned nothing for them (#111). The difference is physical: an
ambient reading hours old is still approximately true, while a flow temperature
from a circuit that has stopped running has decayed to ambient, so retaining it
publishes a number that is wrong rather than merely old. These sensors are
`state_class: MEASUREMENT`, so a retained value is rewritten every cycle and
becomes flat long-term statistics that no history graph can distinguish from a
genuinely steady circuit — the #152/#200 complaint class.

**What would revisit it:** a prod soak showing that successful reports omit a
wanted dataset *often* rather than rarely. If `unknown` becomes the common state
rather than the exception, a retained value carrying a visible age is the better
trade, and ADR-020 then needs an explicit carve-out for slow-cadence telemetry
rather than a silent divergence.

## Consequences

- **Blast radius per failure grew.** One failed request now costs every measure
  for that unit's cycle instead of one measure. After #266 that is 2 measures on
  a single-zone unit rather than 8, so the downside shrank alongside the upside,
  but failure granularity is genuinely worse.
- **A one-off discontinuity in history.** Same entity ids, different source: the
  report returned 55.8 °C where the per-measure sensor read 56.0 °C on the same
  device at the same time.
- **Absent-hardware placeholders are unchanged.** Whatever the vendor sends for
  hardware a unit lacks arrives identically through this endpoint, and #266's
  capability gates are still what suppresses the entities.
- **Prod cannot exercise the zone-2 path.** Neither real ATW unit has a second
  zone; the dev mock's dual-zone unit models the assumption rather than testing
  it.
- **`_latest_genuine_reading` is now shared with outdoor temperature**, so its
  per-point guard fixed a latent defect on that path too: one malformed
  timestamp previously aborted a whole outdoor-temperature poll.
- **`/telemetry/telemetry/actual` still exists on the vendor's side.**
  `docs/api/melcloudhome-telemetry-endpoints.md` documents it and stays, marked
  as no longer called by this integration.
