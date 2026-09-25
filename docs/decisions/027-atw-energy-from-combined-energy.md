# ADR-027: ATW Energy from the combined-energy Report

**Status:** Accepted
**Date:** 2026-09-25
**Relates to:** [ADR-016](016-implement-atw-energy-monitoring.md) (ATW energy monitoring; its telemetry data source is superseded by this), [ADR-008](008-energy-monitoring-architecture.md) (energy architecture; the ATW data source and the "updates hourly" rationale are superseded by this), [ADR-022](022-reading-provenance.md) (report timestamps are device-local)
**Decision Makers:** @andrew-blake

## Context

ATW energy came from `/telemetry/telemetry/energy/{id}` with `measure=interval_energy_consumed|produced`. That endpoint withholds the in-progress hour: in a 2026-09-24 soak on one guest heat pump, for three active hours, it returned nothing for the current hour, whether `to` was now or the next hour boundary, and released each hour at the first poll after it closed. With the 30-minute poll, heat pump energy reached Home Assistant up to about 90 minutes late (#333).

`/report/v1/combined-energy` has the current hour, updated every minute. Across the soak (806 responses) every completed hour's value equalled telemetry's final value exactly. Both vendor apps now read ATW energy from it (mobile app and web app, captured 2026-09-24); web app captures from December 2025 to February 2026 show the same energy page using telemetry, so the vendor switched between February and September 2026. For ATA, both apps use telemetry with `measure=cumulative_energy_consumed_since_last_upload`, which the integration already sends; combined-energy returns HTTP 500 for ATA units.

All measurements come from one guest heat pump in one zone (Europe/Stockholm, UTC+2) over about a day, plus the app captures.

## Decision

1. **ATW energy comes entirely from `/report/v1/combined-energy`; there is no telemetry fallback.** It follows both vendor apps and keeps one source.
2. **ATA stays on telemetry.** It already matches the apps.
3. **Each 30-minute poll fetches two single-day windows per ATW unit, yesterday and today** (the unit's local days, built by wall-clock arithmetic so a clock-change day is 25 or 23 hours). Stateless: yesterday's last hour keeps updating after midnight, and outages up to about a day are recovered, booked in the hour they are fetched. A failed day is skipped for that poll only; if both fail, the unit's energy sensors keep their previous state, so a unit that has never had a successful fetch reads `unknown`, not 0.
4. **A window is never longer than one local day.** A 48-hour `period=Daily` request adds a fake point at the internal local midnight carrying the previous real point's value; single-day windows don't.
5. **Local labels become the telemetry endpoint's UTC keys** (`"%Y-%m-%d %H:%M:%S.000000000"`), so stored `hour_values` carry on unchanged across the upgrade and a downgrade.
6. **Energy from before tracking began is never counted:** hours older than the oldest stored hour per unit and measure are ignored. Without this, an install younger than about a day would count up to a day of pre-install energy on upgrade.
7. **A unit without a usable zone falls back to UTC.** It, and a unit whose zone offset isn't a whole number of hours, gets a WARNING once per unit and is processed anyway. `helpers.resolve_unit_timezone` is unchanged.
8. **The autumn clock change gets no special handling.** Labels are converted as they are.
9. **The poll interval stays 30 minutes.** Clock-aligned polling is a separate question.

## Consequences

- ATW energy sensors rise during the hour, at the next 30-minute poll.
- Two requests per ATW unit per poll, the same as telemetry used.
- If the vendor changes combined-energy, ATW energy sensors stop moving; both vendor apps depend on it today.
- If a unit has no usable zone, its keys won't match stored telemetry keys: a one-off double count on upgrade and hours booked off by its offset. None has been seen; the WARNING is how one would surface.
- On the autumn clock change, at most about one hour of one night a year is lost, never double-counted: if the server labels the repeated hour twice, both labels land on one key and the base tracker keeps the larger value. The tracker's existing "decreased ... keeping previous value" WARNING may repeat while that date is inside a window.
- Requests return at most about 91 days of history (one probe, 2026-09-25). The autumn label shape can be checked once, read-only, before about 2027-01-24.
- Evidence is from one unit in one zone; key equality is shown for UTC+2 and holds for other whole-hour zones by construction.
