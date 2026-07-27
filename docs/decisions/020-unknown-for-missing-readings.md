# ADR-020: Report `unknown`, Not `unavailable`, for Missing Readings

**Status:** Accepted
**Date:** 2026-07-28
**Amends:** [ADR-006](006-entity-description-pattern.md) (removes `available_fn` from the pattern); [ADR-008](008-energy-monitoring-architecture.md) (its availability rules for energy sensors)

## Context

ADR-006's entity description pattern included an `available_fn` field, and 20
sensor descriptions (16 ATW, 4 ATA) used it as exactly
`value_fn(...) is not None` — a missing reading made the entity report
`unavailable`. Both binary sensor platforms declared the field but never set
it.

Home Assistant's `entity-unavailable` quality-scale rule draws the line
differently: `unavailable` means data **cannot be fetched**; a successful
fetch with a missing field should read **`unknown`**. Core's own
`melcloud_home` integration follows this — its sensors never override
`available` for missing values.

The mislabelling had a real cost: ATA `outdoor_temperature` stops updating
while the unit is idle (#110, #152), and `unavailable` made users read a
server-side data gap as the integration being broken.

An alternative was considered: computing availability as
`value_fn(...) is not None` in the `available` property itself. Rejected —
seven descriptions have a `value_fn` and never gated availability, so a
computed rule would have *added* unavailable behaviour to them. Removing the
field touches only the sensors that already gated, all in one direction.

## Decision

**Entity descriptions have no per-field availability gate.** `available_fn`
is removed from all four description dataclasses.

`available` is driven only by conditions that mean "cannot fetch":

- coordinator update failed
- device missing from coordinator data
- device reports an error state (sensors only)

A reading that is absent from an otherwise-successful fetch reads `unknown`
(the entity stays available and `native_value` returns `None`).

## Consequences

- 20 sensors read `unknown` instead of `unavailable` when a reading is
  missing. Templates using `is_state(x, 'unavailable')` against them change
  behaviour; `has_value()` is unaffected (False for both states).
- `should_create_fn` remains the only per-description gate, and it must test
  stable capabilities only — a transient value now reads `unknown` rather
  than suppressing or degrading the entity (see #219, #220).
- Contributors should not reintroduce `available_fn`, even though other
  integrations' code commonly has one — a missing value is not
  unavailability.
