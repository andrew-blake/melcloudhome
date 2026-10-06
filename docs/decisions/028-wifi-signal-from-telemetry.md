# ADR-028: Wi-Fi Signal from the Telemetry Series

**Status:** Accepted
**Date:** 2026-10-06
**Amends:** [ADR-020](020-unknown-for-missing-readings.md) (an empty Wi-Fi signal response keeps the previous reading)
**Relates to:** [ADR-021](021-deferred-startup-fetch.md) (first fetch off the setup path), [ADR-022](022-reading-provenance.md) (`last_reading`), [ADR-023](023-atw-water-temperatures-from-report.md) (this endpoint's earlier failure rate, and its rule for divergences from ADR-020)
**Decision Makers:** @andrew-blake

## Context

The `wifi_signal` sensor on both device types read the top-level `rssi` field of `/context`. Issue #198 (PR #204) moved heat pumps to that field from an hourly telemetry poll, because the hourly poll left the value up to an hour old. Air conditioners always used it.

MELCloud stopped updating that field. Each unit's value froze, and about a week later every unit changed to exactly -30 (#350, seen on two independent installs). A day-long soak about three weeks after that (8 units, 2,304 one-hour queries) found -30 in all 184 `/context` samples. Some units genuinely read about -30, so the value cannot be treated as "no data".

The vendor app's Wi-Fi screen charts `GET /telemetry/telemetry/actual/{unit_id}?measure=rssi`, which still returns live values. The soak measured how it behaves:

- Every non-empty response starts with the unit's last reading before `from`, with that reading's own timestamp (2,183 of 2,183), seen up to 183 minutes back. The rest of the response covers about one hour from `from`, however wide the window is.
- 4.8% of responses were empty (2.1% to 12.2% per unit). In 110 of the 111 empty responses, an earlier query had already returned the reading that the empty one left out. The exception was the soak's first cycle.
- 2 of 2,304 queries timed out. Apart from one expiry of the soak script's own login, there were no other errors. ADR-023 left this endpoint after 89% of water-temperature requests failed over two days; the `rssi` measure shows nothing like that rate.
- Half the units upload on a fixed period, every 2 or 10 minutes. The other half upload only when the value changes, so a healthy unit with a steady signal can go three hours without a new point.

## Decision

**`wifi_signal` comes from the telemetry series for both device types.** The integration requests `measure=rssi` for each unit with a one-hour UTC window ending now and takes the point with the newest timestamp. A wider window returns older data. The `rssi` field of `/context` is no longer parsed. This reverses #204, whose premise was that `/context` refreshed faster. It no longer refreshes at all.

**The poll runs every 30 minutes** on its own timer, one request per unit, with the first fetch in the startup background task (ADR-021).

**`last_reading` is the timestamp of the newest point**, as ADR-022 defines it. On units that upload only on change it is the time of the last change, and it can be hours old while the unit is healthy. A stamp taken at fetch time would look fresh even if MELCloud froze this series as it froze `/context`, because every response repeats the last reading. Diagnostics carry the time of the last poll and its last error, which separate a failing fetch from a quiet unit.

**An empty response keeps the previous reading.** This amends ADR-020 for this sensor, as ADR-023 requires of any divergence. On this endpoint an empty response cannot mean "no current value", because every non-empty response carries the last reading forward. The server intermittently withholds data it has already served. A unit that has never reported reads `unknown` either way.

A failed request also keeps the previous reading. The poll logs one warning when a unit starts failing and one when it recovers. The shared request wrapper still logs each server error itself, as it does for outdoor temperature.

## Consequences

- The sensor shows a real signal again, from the same series the vendor app charts.
- `wifi_signal` gains a `last_reading` attribute. On a unit that uploads only on change, an old `last_reading` with an unchanged value can mean a steady signal or a failing fetch. The diagnostics fields tell them apart.
- After a restart the sensor reads `unknown` until the startup fetch reaches it. Before this change it had a value from the first `/context` poll.
- Each cycle adds one request per unit to the shared request pacer. The soak's requests were about 3.4 seconds apart, so eight units take about 24 seconds every 30 minutes. The pacer serves requests in arrival order, so a command that arrives during the batch waits for the one request in flight, a few seconds.
- The WebSocket offers no alternative source. About 29 hours of frames carried no Wi-Fi signal message and no `rssi` value.

**What would revisit it:** a failure rate on this endpoint approaching ADR-023's, empty responses that stop being transient, or MELCloud updating `/context` `rssi` again.
