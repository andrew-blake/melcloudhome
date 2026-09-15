# Hardware sweep: control writes, 13 to 14 September 2026

Results for the removal of control-write deduplication, PR #323, stacked on #319. The plan these
checks come from is [manual-hardware-checks.md](../manual-hardware-checks.md); the decision is
[ADR-026](../../decisions/026-remove-control-write-dedup.md).

Unit throughout: the Dining Room ATA unit, log id `ff6a76db`. Prod means the production HA
against the real cloud and real hardware; devserver means the local compose environment against
the mock. **All times are BST**, as they appear in the prod log.

Three commits were tested. `786f5d8` is the starting point, with deduplication removed from ATA
power only. `d08c57a` and `a7d5591` are this branch.

---

## `786f5d8`, 13 September, prod

| Check | Driver | Observed | Verdict |
| --- | --- | --- | --- |
| Drag up from off to 60% | Home app | `17:43:03.959 power+mode … power=True`; `17:43:05.717 fan speed … Three`; entity on at 60 | PASS, one write of each |
| Drag 60 to 100 on a running unit | Home app | `17:44:09.213 power+mode … power=True`; `17:44:10.150 fan speed … Five`; entity at 100 | PASS. The power write is new with power dedup gone, and there is one per drag |
| Tile off then on | Home app | `17:48:00.473 power+mode … power=True`; `17:48:00.974 Fan speed already Five for ff6a76db, skipping API call` | Speed dedup present, as this commit has it. The bridge sends `Active` and `RotationSpeed` together and dedup suppresses the speed |
| Fast up then zero, from off | Home app | `17:46:06.890 power+mode True`; `:07.667 power False`; `:08.419 power False`; `:09.518 ATA Poll Power=False`; unit ran briefly then stopped | PASS. Both offs reached the API. No speed write: the reversal fell inside the debounce, and zero is a power command |
| Slider to zero and straight back up | Home app | `17:52:34.404 power+mode True` (downward drag on a running unit); `:34.420 power False`; `:35.984 power+mode True`, +1.56 s; `:36.990 fan speed Two`; entity on at 40 | PASS. The +1.56 s power-on falls inside the guard window, so this is the first hardware run of the guard-clearing fix |
| Tile off, then a speed one second later | REST service calls | `17:54:16.679 power False`; `:17.859 power+mode True`, +1.18 s; `:18.360 fan speed Four`; `:20.630 ATA Poll Power=True` | PASS. Exercises the entity's `async_turn_off` path, not the bridge |
| Stepped 60, 40, 20, 40 | Home app | `18:01:00.183 fan speed Two`; `:02.402 ATA Poll`; `:05.537 fan speed One`; `:11.109 power+mode True`; `:12.119 Fan speed already Two for ff6a76db, skipping API call`; `:12.523 ATA Poll`; slider sprang back to 20 | FAIL. The copy was 6.58 s stale and the check lost the race by 0.4 s |
| Same steps through `climate.set_fan_mode` | REST | `18:05:17.884 Three`; `:20.187 ATA Poll`; `:21.051 Two`; `:24.211 Fan speed already Three for ff6a76db, skipping API call`; `:30.353 ATA Poll`, 9.3 s after the write it needed | FAIL, and caller-agnostic: no bridge involved, on an entity that predates the fan platform |
| Bridge push after a speed change | Home app, bridge debug | `17:57:48.373 fan speed Three`; `:50.633 ATA Poll Power=True`; `:50.661 set_value: RotationSpeed to 60`, event pushed to the paired client | Bridge correct. The home-screen tile had held 40 after the previous check until the app was force-quit and relaunched |

On this commit HomeKit learned a speed change about 2.3 s after the API write, because
`percentage` came from coordinator data and the write, the debounced refresh and the poll all
had to complete first.

## `d08c57a`, 14 September, prod

Deployed copy checked before the run: 0 `skipping API call` lines, 7 notify hooks in
`control_client_ata.py`. REST steps about 3.3 s apart, entity state read after each.

| Check | Driver | Observed | Verdict |
| --- | --- | --- | --- |
| From off to 60% | REST | `power+mode … True mode=Cool`, `fan speed … Three`; entity `('on', 60)` | PASS |
| 40 then 60 | REST | `fan speed … Two` 17:00:25.9; `fan speed … Three` 17:00:29.1; entity `('on', 40)` then `('on', 60)` | PASS. Both reached the API; on `786f5d8` the return to the earlier speed was dropped |
| 40 twice | REST | `fan speed … Two` at 17:00:32.2 and 17:00:35.4 | PASS. Nothing is deduplicated |
| From off, 60 then 0 | REST | `power+mode … True`, `power … False` 0.6 s later; no speed write, the zero cancelled the pending speed debounce; unit ended off | PASS on HA's view; no device report was recorded for it |
| 60, wait, 0, 1 s, 40 | REST | `power+mode … True`, `Three`; `power … False`; `power+mode … True`, `Two`; unit restarted | PASS |
| Final 0 | REST | `power … False`; unit left off, as found | Teardown |
| 40 then 60, brief pause at 40 | Home app | `power+mode True` 18:37:26.7; `Two` :27.7; `Three` :28.7; polls :30.99 and :41.1 both `Fan=Three` | PASS. The cloud confirmed Three 2.25 s after the write |
| One continuous drag through 40 | Home app | `power+mode True` :43.99; `Three` :45.7 only; poll :51.3 `Fan=Three` | PASS for the debounce: one write, the released position. A pass-through never becomes a command; a reversal needs a release at each end |
| Release at 40, pause over 3 s, release at 60 | Home app | `power+mode True` 18:40:56.4; `Two` :56.9 (200, WS `SetFanSpeed` :57.05); poll :59.1 `Fan=Two`; `power+mode True` :59.6; `Three` 18:41:00.1 (200 at :00.17, WS `SetFanSpeed` :00.24). Then with no further command from HA: WS delta :07.66 and polls :09.3, :19.4, :29.5, :40.1 all `Fan=Two`; WS delta 18:42:08.9 and polls :11.1, :22.8 `Fan=Three` | PASS for both writes; both were accepted. The unit ran Two for about a minute before Three, which is Findings 1 and 2 and not deduplication |

Refresh timing measured in the same run: `Debounced refresh executing` at :02.24 produced no poll
until :09.26, against a 2 s debounce. That is HA's 10 s `REQUEST_REFRESH_DEFAULT_COOLDOWN` and is
the mechanism behind the 6.58 s and 9.3 s windows above.

## `a7d5591`, 14 September

Redeployed at 19:36:54 BST, fingerprinted after deploy: 0 `apply` closures, no
`async_set_standby_mode`, `_notify_listeners` guard present, 0 skip lines. Home app gestures
continued across the restart, so everything below ran on `a7d5591`.

| Check | Driver | Observed | Verdict |
| --- | --- | --- | --- |
| ATW zone 1, zone 2, DHW and system power | Devserver, mock dual-zone unit | Zone 1 sent twice at its current value then changed: three `Setting Zone 1 temperature`, entity read 21.0 one second after the change. Zone 2 twice at its current value: two writes. DHW twice at 40.0: two writes. System power off twice then on: three `Setting power`. No skip lines, no `Listener update failed` | PASS. The ATW post-write update, rewritten from a callback to inline assignment since `d08c57a`, behaves as before |
| From off to 60% | Home app | About 20:07; unit started, `Fan=Three` by the 20:07:12 poll | PASS |
| Out-of-band change, setting up the #135 check | Vendor app | Fan set to 2 at 20:08:02; WS `SetFanSpeed` :02.66; poll :04.90 `Fan=Two`; HA slider at 40 within 2.2 s; `ActualFanSpeed` delta :08.36. Home-screen tile showed 40, the fan detail page kept 60 | HA and the cloud both correct. The detail page is Finding 3 |
| Command matching the value HA already holds (#135) | Home app | 20:11:43, detail-page slider dragged from its stale 60 to 40; bridge received 60, 40, 40; `power+mode True`; `Setting fan speed … Two` :44.20, WS delta :44.35 | PASS. On `786f5d8` this line was `Fan speed already Two … skipping API call` and HA appeared to do nothing, which is discussion #135 |
| Same value sent twice | Home app | Not attempted | Out of reach: a native slider does not send an unchanged value, and the #135 drag above already sent the held value three times over |
| 60 then 40, one-second pause | Home app | 20:13:24; `Three` :24.90; `Two` :26.99; poll :27.61 `Fan=Two`; one `power+mode`, the guard still armed; slider held at 40; no audible speed change | PASS. The silence is Finding 4 |
| Zero then straight back to 40 | Home app | 20:14:36; `power False` :36.61, poll `Power=False`; `power+mode True` :38.05, guard cleared by the off; four intermediate 40s collapsed to one `Two` at :39.57; poll `Power=True Fan=Two`; unit restarted | PASS |
| Off behind on, started from on | Home app | 20:16:06; `power False` at :08.29, 1.5 s after the power-on, against a copy reading True | Inconclusive: wrong precondition, the run has to start from off, so it proves only that the off was sent |
| Off behind on, from off | Home app | 20:18:34; `power+mode True` :34.595; `power False` :34.608, 14 ms later with the copy still reading False; polls either side both `Power=False`; both cloud deltas received. The 60 release never became a speed write, the zero cancelled the debounce | HA's half PASS: the off reached the API, which on `786f5d8` it did not. The unit itself was found running, so the run's first verdict was HA's view only; see below |

The unit was still running after the off above. Full sequence:

```
20:18:34.60  power+mode True    PUT 200 :34.90   cloud delta Power/OperationMode :34.97
20:18:34.61  power False        PUT 200 :35.17   cloud delta Power :35.19  (270 ms behind)
20:18:36.02  poll Power=False      20:18:37.32  poll Power=False   (cloud optimistic)
20:19:07.98  cloud delta Power, ActualFanSpeed   <- device status report
20:19:10.22  poll Power=True  Fan=Three          <- HA now shows the device state
```

Turned off over REST at 20:22:07: HA off at once, `ActualFanSpeed` `off` at 20:23:09, 62 s later
on the device's own report. That one held.

---

## Findings

### 1. The cloud reports a command optimistically; the device's report overrides it

**Observed.** At 20:19:07.98, with no command from HA, the cloud pushed deltas for `Power` and
`ActualFanSpeed` and the 20:19:10 poll read `Power=True`, for a unit the cloud had been
reporting off since 20:18:35, 33 s earlier. The same shape on fan speed at 18:41: the cloud
accepted Three, reported Two for about 60 s, then reported Three.

**What it is.** The `/context` response and the WebSocket deltas echo the command. The device's
own status report arrives every 30 to 60 s, and when the two disagree the device report is the
one that stands.

**What it is not.** Not a polling or WebSocket fault, and not new: HA shows the real state
within one poll of the device report, as the old code did. Its practical consequence is that a
poll inside a minute of a rapid command pair is not confirmation of anything.

### 2. Two commands a few hundred milliseconds apart: the device acts on the first only

**Observed twice.** At 20:18:34 a power-on and a power-off left the entity 14 ms apart and
reached the cloud 270 ms apart; both PUTs returned 200 and both deltas arrived; the device
applied the power-on and never acted on the off. At 18:41 a `power+mode` write went out 0.5 s
before a speed write of Three; both were accepted and the unit ran Two for about a minute before
Three. Every pairing with at least a second between the two commands held: the 1 s pair at
18:37:27.7 and :28.7, and the 1.5 s pair at 20:16:06.

**What it is.** A command arriving a few hundred milliseconds behind another to the same unit
can be lost at the device or the cloud, and is reported truly only at the next device report. It
is the [#318](https://github.com/andrew-blake/melcloudhome/issues/318) symptom, a unit left
running after a fast up-then-zero, returning by a route that is not HA's.

**What it is not.** Not deduplication, which is gone from every write on both device types in
this branch, and not something #323 changes either way. HA sent the off and the cloud accepted
it.

**Possible mitigation, deferred.** The fan entity could hold an off for about a second behind a
just-sent power-on, the same shape as its power-on guard in the other direction. That belongs
to #319. One gesture on one unit is one sample, and the gap at which the
device starts losing the second command is unmeasured; the 0.6 s power-on and power-off pair
driven over REST on `d08c57a` ended off, on HA's view, so the boundary sits somewhere below a
second.

### 3. The Home app's fan detail page holds a stale value

**Observed** twice on the evening of 14 September. The recorded instance is at 20:08:02: after
the speed was changed in the vendor app, the home-screen tile showed 40 while the fan detail
page kept showing 60 until it was next written to. HA and the cloud both held 40 throughout.

**What it is.** The Home app's own display cache, on one surface of the app while another
surface of the same app is right. The bridge was verified pushing correctly on 13 September:
`set_value: RotationSpeed to 60` and an event to the paired client, with the slider tracking it
live in a freshly launched app.

**What it is not.** Not HA, not the bridge, and not a result. A stale reading there means check
HA and the log behind it before recording anything.

### 4. An idling unit does not follow a small speed step audibly

**Observed.** During the 20:13:24 run the unit was idling at setpoint (room and target both
21.0) and the Two to Three step produced no audible change; no `ActualFanSpeed` delta
accompanied any of the Two/Three reversals that evening. Yet `ActualFanSpeed` deltas did follow
two other changes: 6.4 s after the vendor app set Two from Three at 20:08:02, and 62 s after the
power-off at 20:22:07.

**What it is.** The unit's own behaviour, and unexplained: the same one-step change was once
followed by an `ActualFanSpeed` delta and otherwise not. Enough to say that a one-step speed
change cannot be confirmed by ear on an idling unit; the log line is the evidence.

**What it is not.** Not a dropped command. Both writes reached the API, and HA and the slider
held the commanded value.

---

## Not done

- **ATW on prod.** The account's heat pumps are shared devices and were not driven on prod by
  decision. The ATW half of this branch was exercised on the devserver against the mock only,
  which proves the client wiring and nothing about the cloud.
- **The pacer ceiling below 0.5 s.** Deliberately not probed: hammering an unofficial API on the
  maintainer's own account risks a soft ban that would also stall prod polling.
- **Sustained load.** Every run here is a handful of commands over a few minutes.
