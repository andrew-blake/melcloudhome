# ADR-026: Write-Through Control Cache

**Status:** Accepted
**Date:** 2026-09-13
**Relates to:** [ADR-018](018-out-of-band-state-sync-limitation.md) (the
deduplication trade-off this amends),
[ADR-011](011-multi-device-type-architecture.md) (which introduced the control
client layer and its dedup),
[ADR-025](025-homekit-fan-entity.md) (the fan entity whose slider made the
failing gesture ordinary)
**Decision Makers:** @andrew-blake

---

## Context

The control clients deduplicate a write against the coordinator's cached device
model: if the requested value already matches the cache, no API call is made.
That cache only learns a written value at the next completed refresh.

### Two causes, one symptom

ADR-018 documents **out-of-band staleness**: someone changes the unit in the
vendor app, the cache does not know, and a command from HA matching that unseen
state is dropped. This ADR does not address that, and ADR-018's limitation
stands.

**Self-inflicted staleness** is the cache lagging our own previous write. It
needs no second actor, applies to every command, and lasts for the whole window
between a write and the next completed refresh.

### Evidence

Measured on prod on 2026-09-13, against a 2 s debounced refresh. Stepping an ATA
fan speed 60 → 40 → 20 → 40 through the HomeKit slider:

```
18:01:05.537  Setting fan speed for ff6a76db to One          (20%, landed)
18:01:11.109  Setting power+mode for ff6a76db to power=True  (power fix live, goes out)
18:01:12.119  Fan speed already Two for ff6a76db, skipping API call   <-- dropped
18:01:12.523  ATA Poll: Dining Room                          (0.4s too late)
```

The same gesture had its power half forwarded and its speed half dropped. The
cache was holding a value **6.58 seconds** old.

Driving `climate.set_fan_mode` over REST, on an entity that predates the fan
platform and never touches the HomeKit bridge, reproduces it with a refresh
**9.3 seconds** behind the write it needed. The defect is in shared code,
reachable by the climate dropdown, scripts, scenes, automations and voice
assistants alike, and has been shipping for months.

Those two measurements are why no timer or freshness threshold closes this: any
constant is wrong in the direction that loses commands.

## Decision

After a control write succeeds, apply the value to the coordinator's cached
device model and notify listeners.

Deduplication keeps comparing against that cache, which now includes our own
recent writes. Entities read the same cached model, so the notify makes the
written value visible immediately rather than one refresh later.

The device is re-fetched after the write rather than reusing the reference the
dedup check holds. A poll completing while the write is in flight runs
`_rebuild_caches`, which replaces every cached unit, and the earlier reference
would then be an orphan the mutation lands on and nothing reads. `RequestPacer`
serialises requests with 0.5 s minimum spacing, so a write inside a scene burst
can sit queued for seconds and the window is not negligible.

`async_set_standby_mode` is the one setter without write-through: real devices
do not enter standby while powered on even though the API accepts the request,
so caching it would record something false. That field has no deduplication, so
no command can be suppressed by leaving it.

Power remains undeduplicated on both device types. Write-through cannot help
there, because #310's case is a cache wrong because the *cloud* is wrong, and an
owner must always be able to reassert power.

## Consequences

### The optimism is bounded

`_rebuild_caches` replaces every cached unit with one parsed from the fresh
context, carrying forward only the five outdoor-temperature fields
(`coordinator.py:713-720`). Power, mode, temperature, fan speed and both vanes
are overwritten by server truth on every poll.

### The known exposure, stated as what it costs

This API returns 200 and silently drops a PUT that fails its server-side
validation matrix ([issue #100](https://github.com/andrew-blake/melcloudhome/issues/100),
the cross-axis vane case).

Today, after such a drop the cache still holds the old value, so a user
repeating the command sends it again. After write-through the cache holds the
dropped value, so the repeat is deduplicated for up to one poll interval. The
trade is "dropped write, immediately retryable" becoming "dropped write,
unretryable until the next poll".

This is accepted because those drops are deterministic and payload-shaped rather
than random, and because the gesture this ADR fixes is an ordinary change of
mind on every field while #100 is a payload quirk on two. A reader who works the
cost out for themselves should find it written down here rather than conclude it
was missed.

### Residual window

A write landing between a poll's `get_user_context` returning and
`_rebuild_caches` running is overwritten by a context that predates it.
`_poll_outdoor_temperature` awaits HTTP in between, so the window is real. This
is no worse than the previous behaviour, where the cache was always behind, and
does not warrant a write-generation counter.

### What dedup still buys

A genuine repeat of the same value is still suppressed, which is the scene-burst
reduction ADR-018 exists to protect.

## References

- [ADR-011: Multi-Device-Type Architecture](011-multi-device-type-architecture.md) — introduced the control client layer and dedup
- [ADR-018: Out-of-Band State Sync Limitation](018-out-of-band-state-sync-limitation.md) — the trade-off this amends
- [ADR-019: WebSocket Real-Time Updates](019-websocket-realtime-updates.md) — shortens the refresh window but does not close it
- GitHub issue #310 — ATW power early return, and the stale-cloud case
- GitHub issue #318 — the ATA power drops fixed alongside this
- GitHub issue #100 — silently dropped PUTs
