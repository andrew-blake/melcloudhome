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

<!-- Task 6 completes this section from the design's decisions 1-9. -->

## Consequences

<!-- Task 6 completes this section. -->
