# ADR-027: ATW Energy from the combined-energy Report

**Status:** Accepted
**Date:** 2026-09-25
**Relates to:** [ADR-016](016-implement-atw-energy-monitoring.md) (ATW energy monitoring; its telemetry data source is superseded by this), [ADR-008](008-energy-monitoring-architecture.md) (energy architecture; the ATW data source and the "updates hourly" rationale are superseded by this), [ADR-022](022-reading-provenance.md) (report timestamps are device-local)
**Decision Makers:** @andrew-blake

## Context

ATW energy came from `/telemetry/telemetry/energy/{id}` with `measure=interval_energy_consumed|produced`. That endpoint often withholds the in-progress hour: in a day-long soak on one guest heat pump, for three active hours, it returned nothing for the current hour, whether `to` was now or the next hour boundary, and released each hour at the first poll after it closed. Later prod logs show it releasing some in-progress hours mid-hour, so the withholding is frequent, not constant. With the 30-minute poll, heat pump energy reached Home Assistant up to about 90 minutes late (#333).

`/report/v1/combined-energy` has the current hour, updated every minute. Across the soak (806 responses) every completed hour's value equalled telemetry's final value exactly. Both vendor apps now read ATW energy from it (mobile app and web app captures); older web app captures show the same energy page using telemetry, so the vendor switched recently. For ATA, both apps use telemetry with `measure=cumulative_energy_consumed_since_last_upload`, which the integration already sends; combined-energy returns HTTP 500 for ATA units.

All measurements come from one guest heat pump in one zone (Europe/Stockholm, UTC+2) over about a day, plus the app captures.

Home Assistant's Energy dashboard books a rise in an energy sensor into the hour in which the sensor changes, not the hour the energy was used. With a 30-minute timer started at setup, the polls fall at an arbitrary minute, so energy used after the last poll in an hour appears in the next hour's bar: up to 30 minutes of it. In a prod soak one heat pump's heating cycles often started just after that install's poll, so most of an active hour landed in the next hour.

## Decision

1. **ATW energy comes entirely from `/report/v1/combined-energy`; there is no telemetry fallback.** It follows both vendor apps and keeps one source.
2. **ATA stays on telemetry.** It already matches the apps.
3. **Each 30-minute poll fetches two single-day windows per ATW unit, yesterday and today** (the unit's local days, built by wall-clock arithmetic so a clock-change day is 25 or 23 hours). Stateless: yesterday's last hour keeps updating after midnight, and outages up to about a day are recovered, booked in the hour they are fetched. A failed day is skipped for that poll only; if both fail, the unit's energy sensors keep their previous state, so a unit that has never had a successful fetch reads `unknown`, not 0.
4. **A window is never longer than one local day.** A 48-hour `period=Daily` request adds a fake point at the internal local midnight carrying the previous real point's value; single-day windows don't.
5. **Local labels become the telemetry endpoint's UTC keys** (`"%Y-%m-%d %H:%M:%S.000000000"`), so stored `hour_values` carry on unchanged across the upgrade and a downgrade.
6. **Energy from before tracking began is never counted:** hours older than the oldest stored hour per unit and measure are ignored. Without this, an install younger than about a day would count up to a day of pre-install energy on upgrade.
7. **A unit without a usable zone falls back to UTC.** It, and a unit whose zone offset isn't a whole number of hours, gets a WARNING once per unit and is processed anyway. `helpers.resolve_unit_timezone` is unchanged.
8. **The autumn clock change gets no special handling.** Labels are converted as they are.
9. **Energy polls twice an hour at fixed minutes past the hour, `:MM:SS` and `:MM+30:SS`, with `MM` between 20 and 27.** `MM` and `SS` come from a SHA-256 hash of the config entry id (`coordinator.energy_poll_slot`), so they are stable across restarts and spread across installs (480 slots). The later poll lands near the end of every hour. This applies to all energy, ATA included: one timer drives both trackers. The startup fetch is unchanged (ADR-021).

## Consequences

- ATW energy sensors rise during the hour, at the next poll.
- Only energy used after an install's `:50`-`:57` poll, the last 3 to 10 minutes of an hour, appears in the next hour's bar on the Energy dashboard, and at midnight in the next day's. The slots are UTC minutes; Home Assistant compiles long-term statistics in hours starting on UTC hour boundaries, so this holds in every time zone.
- Every install's energy requests fall in two 8-minute bands per hour instead of spreading over the whole half hour, roughly a 4× higher peak for MELCloud. Its rate limits are unknown and no real HTTP 429 has been observed; if one appears, widen the band at the cost of more energy moving to the next hour.
- Two requests per ATW unit per poll, the same as telemetry used.
- If the vendor changes combined-energy, ATW energy sensors stop moving; both vendor apps depend on it today.
- If a unit has no usable zone, its keys won't match stored telemetry keys: a one-off double count on upgrade and hours booked off by its offset. None has been seen; the WARNING is how one would surface.
- On the autumn clock change, at most about one hour of one night a year is lost, never double-counted: if the server labels the repeated hour twice, both labels land on one key and the base tracker keeps the larger value. The tracker's existing "decreased ... keeping previous value" WARNING may repeat while that date is inside a window.
- Requests return at most about 91 days of history (one probe). The autumn label shape can be checked once, read-only, within about 91 days of the clock change.
- Evidence is from one unit in one zone; key equality is shown for UTC+2 and holds for other whole-hour zones by construction.
