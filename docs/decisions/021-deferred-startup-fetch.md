# ADR-021: Defer the First Energy/Telemetry Fetch Off the Setup Path

**Status:** Accepted
**Date:** 2026-08-19
**Related:** [ADR-020](020-unknown-for-missing-readings.md) (defines the `unknown` state this decision makes transiently observable after a restart, without changing its meaning)

## Context

Traced against the dev mock server on 2026-08-18: every restart fired 31
sequential HTTP requests before any entity existed — 1× `/context`, 6×
`trendsummary`, 2× `comfort-graph`, 10× telemetry-energy, 12×
telemetry-actual, on a 6 ATA + 2 ATW fixture. It scales linearly with device
count, and `RequestPacer` enforces a 0.5s minimum gap between requests
(`DEFAULT_MIN_REQUEST_INTERVAL`), so the wall-clock floor is structural
rather than mock latency — roughly 66 seconds in that trace.

None of it was optional, because `async_setup_entry` awaited
`coordinator.async_config_entry_first_refresh()` and
`coordinator.async_setup()` in full before `async_forward_entry_setups`.
No entity of any kind existed until all 31 requests had completed.

### The rejected alternative: jitter for fleet desynchronization

The investigation that found this originally proposed a different fix:
delay the first fetch by `random.uniform(0, 60)` so that many installs
restarting around the same time — say after a release announcement — would
not leave their periodic 30/60-minute timers synchronized against
MELCloud's backend.

**Rejected, because the premise is unevidenced and the arithmetic doesn't
work.** Recorded here so it isn't rediscovered and rebuilt:

- `_TrackTimeInterval._schedule_timer` (`helpers/event.py`) schedules via
  `loop.call_at(loop.time() + seconds)`. Timer phase is anchored to
  registration time, and nothing in this system anchors to a wall clock —
  no cron, no `async_track_time_change`, no shared boundary. Fleet-wide
  phase spread therefore already equals restart-time spread, which for
  manual HACS updates is hours to days.
- Even granting the premise, 60 seconds of jitter on a 1800-second period
  is a 3.3% nudge — noise on a distribution already hours wide.
- There is no evidence MELCloud rate-limits at a layer where cross-install
  timing would matter. Each install has its own account and token. The 500s
  that prompted the investigation came with **zero 429s** in the same
  window, and trace to the ATW telemetry endpoint's own reliability.

Adding jitter would also have required moving the `async_track_time_interval`
registrations into the delayed task, since a timer registered eagerly keeps
its restart-anchored phase regardless of when the first fetch runs. That
move is a robustness downgrade in its own right — see Decision.

## Decision

**The first energy and telemetry fetch runs in a background task**
(`MELCloudHomeCoordinator._run_startup_fetch`), created with
`ConfigEntry.async_create_background_task` — the same call the WebSocket
listener already uses. `async_setup` no longer awaits it.

`async_create_task` is deliberately *not* used: `async_block_till_done()`
awaits only the foreground task set, reaching background tasks solely with
`wait_background_tasks=True`, so a tracked task would still block HA
bootstrap and every test that blocks till done.

Entry-scoped rather than `hass`-scoped so the task is tied to the entry
lifecycle: if setup raises after the task is created, HA never calls
`async_shutdown` for a failed entry, and a `hass`-scoped task would go on
fetching with nothing left to cancel it.

**The periodic 30/60-minute timer registrations stay eager in
`async_setup`.** `_update_single_energy_tracker` is a complete independent
fetch-and-apply with no dependency on the initial fetch, so registering the
timers up front means a cancelled or failed startup fetch still recovers at
the next tick. Moving registration into the background task would trade that
self-healing away.

A consequence of registering first: the timers are now live *before* the
deferred fetch starts, so a pathologically slow startup fetch (30+ minutes)
could overlap a periodic tick and invoke the same tracker twice
concurrently. Benign — each unit's cumulative-total and hour-values
mutations happen in one synchronous burst with no `await` between read and
write, so a concurrent call re-reads whatever the first already wrote. That
is the same idempotency that already makes normal re-polling safe. Noted
because the previous ordering made the overlap impossible, so it is a new
property rather than an inherited one.

**The task is also cancelled and awaited explicitly in `async_shutdown`**,
before `client.close()`. HA's own entry-scoped cleanup is not enough on its
own: it runs in `_async_process_on_unload`, which fires *after*
`async_unload_entry` has already called `async_shutdown` and closed the
client, so an in-flight request would have its session closed underneath it.
Cancelling here, and awaiting rather than only cancelling, lets it unwind
first.

`/context` is unaffected and stays synchronous in
`async_config_entry_first_refresh` — core climate and power-state entities
need it to exist at all.

## Consequences

- Entities appear immediately on restart instead of after the full fetch.
  Energy and telemetry sensors (never core climate or power-state entities)
  may read `unknown` for the duration of that fetch, where previously they
  did not exist at all until it completed.
- This does not change what `unknown` means. ADR-020 already established
  that a missing reading reads `unknown`, not `unavailable`; this only
  changes when that already-correct state is observable.
- **A transient `unknown` does not corrupt long-term statistics.** Verified
  against HA's statistics compiler (`components/sensor/recorder.py`):
  `unknown` never becomes a sample, because
  `_entity_history_to_float_and_state` parses with `float()` inside
  `try/except` and drops the state before any reset logic sees it; and
  `reset_detected` is purely value-based (`fstate < 0.9 * previous_fstate`)
  with no time term, so a gap of any length is invisible to it. The
  comparison baseline is read from the database rather than memory, so it
  survives the restart, and a compile window containing only `unknown` is
  skipped rather than written as a zero. A reset is therefore triggered only
  by a value moving *backwards* — which nothing here can cause, though the
  energy-tracker lost-update in the backlog can.
- Restart traffic is unchanged in volume: this decision moves 22 of the 31
  requests off the blocking path, it does not remove any.
