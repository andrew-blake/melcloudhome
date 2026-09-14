# ADR-026: Remove Control-Write Deduplication

**Status:** Accepted
**Date:** 2026-09-14
**Relates to:** [ADR-018](018-out-of-band-state-sync-limitation.md) (the
deduplication trade-off, superseded by this),
[ADR-011](011-multi-device-type-architecture.md) (which introduced the control
client layer and its dedup),
[ADR-025](025-homekit-fan-entity.md) (the fan entity whose slider surfaced the
reversal)
**Decision Makers:** @andrew-blake

---

## Context

Every control write compared the requested value against the coordinator's
cached device model and skipped the API call when the two matched. That cache
learned a written value only at the next completed refresh.

### Two causes, one symptom

ADR-018 documents **out-of-band staleness**: someone changes the unit in the
vendor app, the cache does not know, and a command from HA matching that unseen
state is dropped. Discussion #135 is that report.

**Self-inflicted staleness** is the cache lagging our own previous write. It
needs no second actor, applies to every command from every caller, and lasts
for the whole window between a write and the next completed refresh.

Both end in a command that never reaches the hardware.

### Evidence

Measured on prod on 2026-09-13, against a 2 s debounced refresh. Stepping an ATA
fan speed 60 → 40 → 20 → 40 through the HomeKit slider:

```
18:01:05.537  Setting fan speed for ff6a76db to One          (20%, landed)
18:01:11.109  Setting power+mode for ff6a76db to power=True  (power fix live, goes out)
18:01:12.119  Fan speed already Two for ff6a76db, skipping API call   <-- dropped
18:01:12.523  ATA Poll: Dining Room                          (0.4s too late)
```

One gesture had its power half forwarded, because `786f5d8` had already removed
dedup from ATA power for [issue #318](https://github.com/andrew-blake/melcloudhome/issues/318),
and its speed half dropped. The cache was holding a value **6.58 seconds** old.

Driving `climate.set_fan_mode` over REST, on an entity that predates the fan
platform and never touches the HomeKit bridge, reproduced it with a refresh
**9.3 seconds** behind the write it needed. The defect sat in shared code,
reachable by the climate dropdown, scripts, scenes, automations and voice
assistants alike.

Those two measurements rule out any timer or freshness threshold: against a 2 s
debounce, both windows exceed any constant that would still suppress a scene
burst, so every constant is wrong in the direction that loses commands.

[Issue #310](https://github.com/andrew-blake/melcloudhome/issues/310) is the
third shape, a cache wrong because the cloud is wrong, where no amount of local
freshness helps.

### The rate-limit justification was unmeasured

ADR-018 rates removing dedup as High risk on the grounds that burst scene
patterns hit API limits, and says the pacer alone was not sufficient. No 429
from the MELCloud API is recorded anywhere: not in the pacer's own commits, any
issue, any discussion, any VCR cassette, any capture, or the surviving prod
logs. The production client has no 429 handling. The mock's synthetic limiter
and the pacer landed in the same squashed PR, so the mock cannot have produced
the motivating 429 either.

Probed against the real API on 2026-09-14 with dedup bypassed and the
production `RequestPacer(min_interval=0.5)`: 48 same-value PUTs, 36 of them
concurrent across all six ATA units on the account, one every 0.5 s, every one
200, state unchanged. `RequestPacer` alone carries the scene-burst shape
ADR-018 cites. The probe did not establish the ceiling below 0.5 s, ATW (the
account's heat pumps are shared devices), or sustained load.

## Decision

Deduplication is removed from every control write on both device types. Every
command reaches the API. Power is no longer a special case, because no field is.

After a successful write the value is applied to the cached device model and
listeners are notified, so an entity shows a command as soon as the API accepts
it rather than one refresh later.

The device is looked up again after the write rather than reusing the object
fetched before it. A poll completing while the write is in flight runs
`_rebuild_caches`, which discards every cached unit object for freshly parsed
ones, so writing into the earlier object would update a copy no entity reads.


## Consequences

### The trade

A scene applied to units already at target now sends one PUT per attribute per
unit at 0.5 s spacing. A typical scene touching one or two units with three or
four attributes costs 1.5 to 4 s. The ceiling measured on this account, six
units and every attribute, is about 18 s.

`RequestPacer` is one lock per client and serialises every request, so during
that time a manual command and the coordinator's `/context` poll both queue
behind writes that change nothing. The poll is delayed rather than failed: the
30 s timeout is on the request, not on the wait for the lock.

Set against that: the same dedup silently dropped commands. A slow redundant
scene is visible and explicable. A dropped command is neither.

### Server truth wins at the next poll

Each poll parses fresh unit objects from the server's response; only the
energy, telemetry and outdoor-temperature fields are re-applied from their own
trackers. Power, mode, temperature, fan speed and both vanes therefore hold the
server's value after every poll, whatever was applied between polls.

### What the cache holds

The cache holds what we sent, confirmed by a 200, until the poll confirms it. A
write the unit does not end up applying reads as applied until then. The one
documented instance of that was
[issue #100](https://github.com/andrew-blake/melcloudhome/issues/100), where our
own payload sent both vane axes to a unit with only one and the server rejected
the combination. A malformed payload is a bug to fix wherever the cache sits.

### Mitigations, none in scope

- **(D) Coalesce near-simultaneous writes to one unit into a single
  multi-field PUT.** The API body already carries every field, so a six-unit
  scene would cost about 3 s with no dependence on cached state. Sized as
  medium: error fan-out semantics across the coalesced fields, interaction with
  `fan.py`'s own debounce, and a collection window added to every command.
  Deferred until a slow scene is actually reported.
- **(E) MELCloud's own cloud scenes**, applied server-side in one request,
  exposed as HA entities. Issue #174 territory.
- **(F) The pacer's 0.5 s** is unjustified in either direction. The ceiling was
  deliberately not probed, since hammering an unofficial API on the maintainer's
  own account risks a soft ban that would also stall prod polling.
- **(G) Firing only changed attributes** is `scene.apply` behaviour on the Home
  Assistant side, not the integration's.

### Alternatives rejected

**Keep dedup and apply every successful write to the cache it compares against.**
This narrows the window rather than closing it, and leaves #135 unfixed.

**A timer or freshness threshold.** The 6.58 s and 9.3 s measurements above put
every candidate constant on the wrong side.

## References

- [ADR-011: Multi-Device-Type Architecture](011-multi-device-type-architecture.md) — introduced the control client layer and its dedup
- [ADR-018: Out-of-Band State Sync Limitation](018-out-of-band-state-sync-limitation.md) — superseded by this record
- [ADR-019: WebSocket Real-Time Updates](019-websocket-realtime-updates.md) — shortens the refresh window; does not change this decision
- [ADR-025: Exposing Fan Speed and Vane to HomeKit](025-homekit-fan-entity.md) — the entity whose slider surfaced the reversal
- GitHub issue #310 — the stale-cloud case, and the ATW power early return
- GitHub issue #318 — the ATA power drops, fixed first on their own in `786f5d8`
- GitHub discussion #135 — the original out-of-band report
