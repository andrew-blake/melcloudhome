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

Control writes on both device types compared the requested value against the
coordinator's copy of the unit and skipped the API call when the two matched.
Not every setter had the check, ATA power lost its own first in `786f5d8`, and
one that had it, ATA `async_set_mode`, had no caller at all and is deleted
here. That copy learned a written value only at the next completed
refresh.

### Two causes, one symptom

ADR-018 documents **out-of-band staleness**: someone changes the unit in the
vendor app, the cache does not know, and a command from HA matching that unseen
state is dropped. Discussion #135 is that report.

**Self-inflicted staleness** is the cache lagging our own previous write. It
needs no second actor, applies to every command from every caller, and lasts
for the whole window between a write and the next completed refresh.

Both end in a command that never reaches the hardware.

### Evidence

Measured on prod on 2026-09-13. A refresh lands 2 to 12 s after a write: the
integration requests one 2 s after, and `DataUpdateCoordinator.async_request_refresh`
adds a 10 s cooldown on top. Stepping an ATA fan speed 60 → 40 → 20 → 40 through
the HomeKit slider:

```
18:01:05.537  Setting fan speed for ff6a76db to One          (20%, landed)
18:01:11.109  Setting power+mode for ff6a76db to power=True  (power fix live, goes out)
18:01:12.119  Fan speed already Two for ff6a76db, skipping API call   <-- dropped
18:01:12.523  ATA Poll: Dining Room                          (0.4s too late)
```

One gesture had its power half forwarded, because `786f5d8` had already removed
dedup from ATA power for [issue #318](https://github.com/andrew-blake/melcloudhome/issues/318),
and its speed half dropped. Our own write of **6.58 seconds** earlier had still not
reached the copy the check consulted.

Driving `climate.set_fan_mode` over REST, on an entity that predates the fan
platform and never touches the HomeKit bridge, reproduced it with a refresh
**9.3 seconds** behind the write it needed. The defect sat in shared code,
reachable by the climate dropdown, scripts, scenes, automations and voice
assistants alike.

Those two measurements rule out any timer or freshness threshold: both sit
inside that 2 to 12 s band, and both exceed any constant that would still
suppress a scene burst, so every constant is wrong in the direction that loses
commands.

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
command reaches the API. Power stopped being the exception: no field is checked.

After a successful write the value is applied to the coordinator's copy of the unit and
listeners are notified, so an entity shows a command as soon as the API accepts
it rather than one refresh later.

The device is looked up again after the write rather than reusing the object
fetched before it. A poll completing while the write is in flight runs
`_rebuild_caches`, which discards every cached unit object for freshly parsed
ones, so writing into the earlier object would update a copy no entity reads.

## Consequences

### The trade

A scene applied to units already at target now sends one PUT per attribute per
unit. `RequestPacer` has spaced every request 0.5 s apart since `27e3600`, so a
scene that changed values always cost that and is unaffected here. What changes
is the number of requests a redundant scene makes: one unit at target goes from
one request to one per attribute, and the whole-account ceiling from six to
thirty-six. A typical scene touching one or two units with three or
four attributes projects to roughly 1.5 to 4 s. The ceiling, every ATA unit on
this account and every attribute, was measured at about 18 s.

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

### What the copy holds until the poll

The coordinator's copy holds what we sent, confirmed by a 200, until the poll
confirms it. A write the unit does not end up applying reads as applied until
then. One written field is read as a physical status rather than a setpoint:
`forced_hot_water_mode` backs the `forced_dhw_active` binary sensor (device
class running) and the water heater's operation mode, so an automation on that
sensor fires when the PUT is accepted rather than when the valve moves, and a
declined command shows as an on/off pair in the recorder, lasting until the
unit's own report reaches the cloud. Accepted so the
water heater's mode does not lag its own control. The one documented instance
of a write not applying was
[issue #100](https://github.com/andrew-blake/melcloudhome/issues/100), where our
own payload sent both vane axes to a unit with only one and the server rejected
the combination. A malformed payload is a bug to fix wherever the cache sits.

### A close pair can be lost at the device

Writes to one unit that arrive in the same event-loop turn share a single request, so the pair a
HomeKit thermostat produces is gone: `homekit/type_thermostats.py` fires `set_hvac_mode` and then
`set_temperature` as un-awaited tasks. Siri, a HomeKit scene and the transition out of Off reach
it; the fan tile cannot, since `homekit/type_fans.py` turns Active plus RotationSpeed into one
`set_percentage`. `WriteCoalescer` in `api/coalescing.py` merges the pair. A power-on that also
sets a speed was never a pair: the fan entity passes the speed into `set_power_and_mode`, which
builds one payload.

Two writes separated by a sequential await still leave as two requests, floored 0.5 s apart by
`RequestPacer`. A scene is the case: `climate/reproduce_state.py` and `fan/reproduce_state.py`
each await one entity's service calls in turn, and although the scene helper gathers across
entities, the fan entity holds a slider position for its debounce window. A scene setting a unit's
temperature, vane and fan speed was measured on hardware sending four requests over 1.6 s in one
run, the fan's landing 220 ms behind the climate's. Three attributes were asked for;
`climate/reproduce_state.py` reasserts the HVAC mode as well. Both figures are that single run. A
retry after an authentication failure is another such pair, since `_reauth_lock` serialises the
callers.

A command arriving that close behind another to the same unit can be accepted by the cloud, with
a 200 and a websocket delta for each, and ignored by the device. The unit keeps running while the
coordinator's copy, the cloud and the Home app all read off, until the unit's own status report
corrects them 30 to 60 seconds later. Seen three times on hardware.

No interval is claimed for those three. The `Setting` log lines are written before the pacer is
acquired, so they time intent rather than dispatch, and the `API Response: PUT` lines that would
time dispatch were not recorded for them. A poll inside a minute of a pair reports the cloud's
optimistic copy, so only the unit's own report disagrees.

Removing the comparison makes close pairs more common, since writes that would have been skipped
now go out: a scene applied to units already at target sends a request per attribute where it sent
only the one for `hvac_mode`, which reached `async_set_power_and_mode` and had never had the check. A command re-sent on its own is applied, which is the manual recovery, and one this decision
is what makes possible: the comparison removed here would have skipped an off sent to a unit whose
copy already read off. Mitigation 1 below does not reach this pair, because it merges only
writes that arrive in the same turn.

### Mitigations

- **1. Coalesce near-simultaneous writes to one unit into a single
  multi-field PUT. Done.** The API body already carries every field, so writes
  that arrive together share one request with no dependence on cached state.
  Each caller awaits the dispatch task through a shield, so one caller's
  cancellation leaves the others alone, and the two vane axes are never merged
  because the server
  answers 200 and drops that combination on a unit without horizontal vanes
  (issue #100). The collection window is margin: both writes of a same-turn pair
  are queued before the dispatch task takes its first step, so a window of zero
  already merges them.
- **2. MELCloud's own cloud scenes**, applied server-side in one request,
  exposed as HA entities. Discussed in #201.
- **3. The pacer's 0.5 s** is unjustified in either direction. The ceiling was
  deliberately not probed, since hammering an unofficial API on the maintainer's
  own account risks a soft ban that would also stall prod polling.
- **4. Firing only changed attributes** is `scene.apply` behaviour on the Home
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
- GitHub issue #310 — the stale-cloud case, proposed for ATA power only; extending the removal to ATW and to every field is this record's own call
- GitHub issue #318 — the HomeKit vane/swing issue whose fan entity surfaced the power drops, fixed first on their own in `786f5d8`
- GitHub discussion #135 — the original out-of-band report
