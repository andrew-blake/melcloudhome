# ADR-029: Synthetic Report Points Are Matched by Shape

**Status:** Accepted
**Date:** 2026-11-13
**Amends:** [ADR-023](023-atw-water-temperatures-from-report.md) (its "Synthetic points are stripped by the shared rule" bullet)
**Relates to:** [ADR-022](022-reading-provenance.md) (`last_reading`), [ADR-027](027-atw-energy-from-combined-energy.md) (a synthetic midnight point on another report)
**Decision Makers:** @andrew-blake

## Context

Report responses (`trendsummary`, `comfort-graph`, `internaltemperatures`) mix genuine unit readings with synthetic chart points: hourly repeats of the last value, and a final echo of the query's `to`. Issue #224 separated them by seconds. Genuine readings were taken to carry arbitrary seconds, so `_latest_genuine_reading` skipped every point with `seconds == 0`, and `_report_params` sent a whole-minute `to` so the echo would also land on `:00`. #224 accepted the cost as rare.

**Issue #394 falsified the premise.** In one reporter's full `internaltemperatures` response, the seconds on the genuine 2-minute readings crept forward across a day: `:55` to `:58` around midnight, `:57` to `:59` by midday, then `:00` from about 15:00 local. Every `:00` reading falls on an even minute and every `:5x` reading on an odd minute, so the unit's upload phase crossed the minute boundary. The `:00` readings change value every 2 minutes, so they are genuine. The filter discarded them, and flow temperature froze for up to 360 minutes. Another unit on the maintainer's install uploads at about `:33` and was unaffected.

The same drift had been seen before on a different series. The Wi-Fi signal soak saw rssi telemetry stamps drift from `:59` onto `:00` (`_claude/plans/2026-10-05-wifi-signal-review-a-vs-b.md`), which is why `get_wifi_signal` has no seconds rule. The finding was never carried back to the report parser.

**The echo comes back in the unit's local time.** The request `to` is UTC with an explicit `Z` (ADR-022). The server echoes it back converted: in the recorded cassettes, `to=…06:00Z` came back as `08:00` and `09:30Z` as `11:30` (comfort-graph) and `10:30` (trendsummary). Every response also carries a top-level `to` field, and it equals the final point of every non-empty dataset measured: 11 of 11 across the three report cassettes and 5 of 5 in the #394 response.

## Decision

**A point is synthetic if its stamp, as sent, is exactly on the hour (`HH:00:00`), or if it equals the response's top-level `to`.** Seconds play no other part.

- **Both checks read the naive stamp as sent**, in the unit's local time, before conversion to UTC. A check on the converted stamp would misplace the hour for a unit in a half-hour zone.
- **The echo is matched against the response's `to`**, which is in the same local time as the points. The request's own `to` matches only on a UTC+0 unit; elsewhere the echo would be published as a fresh reading, which is the #224 failure.
- **A response without a top-level `to` has its final point treated as the echo.** No measured response lacks it. If one does, losing one genuine reading costs less than publishing an echo as current.
- **`_report_params` still truncates `to` to whole minutes.** Its original reason is gone, but no response to a `to` with seconds has been measured, so the request is left as it is.

## Consequences

- **A genuine reading stamped exactly `HH:00:00` is dropped.** At a 2-minute cadence that is at most one reading an hour, and only while the unit's phase sits on `:00`. When one lands on the hour, the response holds it and the hourly repeat under the same stamp, and both are dropped.
- **The net is narrower.** The seconds rule also rejected any synthetic shape not yet seen, provided it landed on `:00`. The shape rule rejects only the two known shapes. ADR-027's fake midnight point, seen on a `period=Daily` combined-energy request, is on the hour, so this rule would catch it. A `period=Daily` request would leak its `:30:00` bucket labels, which is one more reason the report requests stay on `period=Hourly`.
- **All three callers change together**: ATA outdoor temperature (`trendsummary`), ATW outdoor temperature (`comfort-graph`) and ATW water temperatures (`internaltemperatures`). The #394 response shows outdoor temperature stuck on an older `:59` reading as well.
- **The mock server sends the top-level `to`**, so mock-backed runs exercise the same path as the real API.
- **What would revisit it:** a measured synthetic point that is neither on the hour nor the echo, or a response without a top-level `to`.
