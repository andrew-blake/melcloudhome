# Manual hardware checks for the control path

What a control write has to do, and which drivers can prove each part of it.

The rows below are properties of the control path. The columns are the ways of driving it. Each
cell either says how that driver proves the property, with the log lines that are the evidence,
or says the property is out of that driver's reach and why.

This is Tier 3 of [testing-strategy.md](../testing-strategy.md), written out. The suite column
is the part that runs in CI; the rest is a person at a keyboard, or in the room with the unit.

Results of a run go in `hardware-sweeps/`, one file per sweep. The most recent is
[2026-09-14-control-writes.md](hardware-sweeps/2026-09-14-control-writes.md).

---

## Properties

- **P1. Every command reaches the API whatever the coordinator's copy holds.** A change and a
  change back, a few seconds apart, both arrive. See
  [ADR-026](../decisions/026-remove-control-write-dedup.md).
- **P2. A power-off issued behind a power-on lands.** The off goes out even though the copy
  still reads off, which is the shape of
  [issue #318](https://github.com/andrew-blake/melcloudhome/issues/318).
- **P3. The entity shows a command as soon as the API accepts it**, rather than one refresh
  later.
- **P4. A value the unit already has still sends.** No field is compared against anything.
- **P5. A command matching an out-of-band change still sends.** Someone moves the unit in the
  vendor app, HA learns it at the next poll, and a command from HA for that same value still
  reaches the API. Discussion #135.

## Drivers

- **Suite.** `make test-integration`, mocked at the `MELCloudHomeClient` boundary. The
  witnesses are mutation-verified: reintroduce the skip and they fail. Runs on every push and
  costs nothing, so it is the first place a property should live.
- **REST (prod).** `tools/hardware_check.py` against the production HA and the real cloud, over
  the REST API and SSH. Real hardware, no bridge, timing under the script's control rather than
  a thumb's.
- **Devserver.** `make dev-restart` against the mock server, driven over REST. The only place
  the ATW half runs against a live HA, because the account's heat pumps are shared devices and
  are not driven on prod. Proves client wiring and entity behaviour; proves nothing about the
  cloud or the hardware.
- **Home app.** A paired iPhone through the HomeKit bridge. The only driver with the real
  gesture shapes: a drag arrives as `Active` plus a burst of `RotationSpeed`, the fan entity's
  debounce sends only the released position, and its power-on guard decides whether a
  `power+mode` write precedes the speed. See [ADR-025](../decisions/025-homekit-fan-entity.md)
  and [homekit.md](../homekit.md).
- **Vendor app.** The MELCloud Home app. Not a driver of the integration at all. It is the
  second actor that makes P5 real, and nothing else.

## The matrix

| Property | Suite | REST (prod) | Devserver | Home app | Vendor app |
| --- | --- | --- | --- | --- | --- |
| P1 every command reaches the API | proves | proves | proves (mock) | proves | source only |
| P2 off behind on lands | proves | proves | ATW power only | proves | not a driver |
| P3 entity shows an accepted command | proves | proves | proves (mock) | proves | not a driver |
| P4 same value still sends | proves | proves | proves (mock) | out of reach | not a driver |
| P5 out-of-band match still sends | mechanism only | proves | out of reach | proves | the source |

### The script

```bash
uv run python tools/hardware_check.py [-k] [--no-debug] [--entity <fan entity id>] <check>
```

Checks: `state`, `reversal`, `same-value`, `off-behind-on [--gap SECONDS]`,
`restart-after-zero`, `out-of-band-match`, `drop-boundary [--gaps 0.2,0.4,0.7,1.0,1.5]`.
Omitting `--entity` or the check lists the fan entities and exits.

It reads `HA_URL`, `HA_TOKEN`, `HA_SSH_HOST` and `HA_CONTAINER` from `.env`, and
`MELCLOUD_USER_OWNER` / `MELCLOUD_PASSWORD_OWNER` for `out-of-band-match`, which sets the speed
through the bundled API client, outside HA.

`-k` disables TLS verification. The LAN hostname in `HA_URL` serves a certificate for a
different name, so on the LAN it is needed; the public hostname sits behind Cloudflare Access
and returns 403 to API tokens, so it is not an alternative.

Unless `--no-debug` it sets the three loggers to debug for the run and restores them after. It
reads the log back over SSH and prints the `Setting …` lines, PUT statuses and polls for the
unit, waits 90 s after any rapid pair for the device report, and leaves the unit in the power
state it found.

---

## P1. Every command reaches the API whatever the coordinator's copy holds

**Suite.** `test_a_command_matching_current_state_is_still_sent` in
`tests/integration/test_climate_ata.py`, one parametrised case per ATA field, and
`test_the_same_speed_twice_is_sent_twice` in `test_fan_ata.py`. A change and a change back is
not a witness here, because the copy is updated after every accepted write and so never matches
the next request; both witnesses send the copy's own value twice instead.

**REST (prod).** `hardware_check.py reversal`. Unit on at a known speed; three steps, A then B
then A, about 3.3 s apart; entity state read after each. Evidence: three `Setting fan speed for
<unit> to …` lines, no `Fan speed already … skipping API call` line anywhere in the run, and the
entity reading each value in turn. `restart-after-zero` covers the power half of the same
property: a speed, then zero, then a non-zero percentage a second later gives `Setting power …
to False`, `Setting power+mode … power=True`, `Setting fan speed …`, and the unit restarts.

**Devserver.** Same `reversal` shape over REST against `localhost:8123`, three seconds between
steps, plus the ATW equivalents: a zone setpoint stepped 20 to 21 to 20 gives three `Setting
Zone 1 temperature` lines. No skip lines and no `Listener update failed`. Mock only.

**Home app.** Drag to A, release, pause about a second, drag to B, release. Evidence: two
`Setting fan speed` lines and the matching WebSocket `SetFanSpeed` deltas. A pause under the
fan entity's debounce collapses the pair into one write of the released position, which is the
debounce working and is not this property.

**Vendor app.** Not a driver. It can be the source of the second value, but the command has to
come from HA for the property to mean anything.

## P2. A power-off issued behind a power-on lands

**Precondition, every driver: the run STARTS FROM OFF.** From on, the power-on is a write the
copy already agrees with and the off is compared against a copy reading on, so a landed off
proves only that it was sent. A run started from on is recorded in the 14 September sweep for
exactly this reason.

**Suite.** `test_power_off_is_sent_to_a_unit_already_off` and
`test_power_off_disarms_the_power_on_guard` in `tests/integration/test_fan_ata.py`, both
parametrised over the two off paths, the `fan.turn_off` service and the slider's zero detent.
`test_dragging_through_zero_does_not_power_off` is the other side: passing the zero detent
mid-drag must not reach the control client at all.

**REST (prod).** `hardware_check.py off-behind-on [--gap SECONDS]`. From off: set a non-zero
percentage, then zero after the gap. Evidence: `Setting power+mode for <unit> to power=True`,
then `Setting power for <unit> to False`, both with a 200, and the unit off. Wait for the
device's own status report before calling it, not for the poll; below about a second of gap the
device may act on the power-on only (see the sweep's findings). `drop-boundary
[--gaps 0.2,0.4,0.7,1.0,1.5]` walks that gap deliberately.

**Devserver.** ATW power only, and as wiring rather than behaviour: the system power switch
turned off twice gives two `Setting power for ATW unit` lines with no skip. The ATA half of this
property needs the real cloud, since the mock accepts anything and never loses a command.

**Home app.** From off, drag up and straight back to zero in one motion. Evidence:
`Setting power+mode … power=True`, then `Setting power … to False` within a few hundred
milliseconds, and both cloud deltas. There is no speed write, because the zero cancels the
pending speed debounce. Confirm the unit by ear and by the next `ActualFanSpeed` delta, not by
the poll.

**Vendor app.** Not a driver.

## P3. The entity shows a command as soon as the API accepts it

**Suite.** `test_entity_shows_a_written_speed_before_the_next_refresh` and
`test_a_write_landing_during_a_poll_still_shows_the_written_speed` in
`tests/integration/test_fan_ata.py`, and
`test_zone1_entity_shows_a_written_setpoint_before_the_next_refresh` in `test_climate_atw.py`.
The first deliberately leaves the refresh in flight, so the only thing that can have updated
`hass.states` is the post-write notify.

**REST (prod).** Any check that writes; the script reads entity state after each step. Evidence:
the entity reads the new value within about a second of the `Setting …` line, and before the
next `ATA Poll` line.

**Devserver.** Same, against the mock, and the only place to see it on an ATW entity: a zone
setpoint read one second after the change.

**Home app.** The bridge's `set_value: RotationSpeed to <n>` line, followed by the event pushed
over the paired session. Needs `homeassistant.components.homekit` and `pyhap` at debug. HA's own
state moves first; the tile follows it.

**Vendor app.** Not a driver.

## P4. A value the unit already has still sends

**Suite.** The same-value witnesses, one per setter so that a check reintroduced on one fails
alone: `test_a_command_matching_current_state_is_still_sent` and
`test_set_hvac_mode_writes_even_when_already_matching` (`test_climate_ata.py`),
`test_the_same_speed_twice_is_sent_twice` (`test_fan_ata.py`),
`test_a_zone1_setpoint_matching_current_state_is_still_sent` (`test_climate_atw.py`),
`test_a_zone2_setpoint_matching_current_state_is_still_sent` and
`test_a_zone2_preset_matching_current_state_is_still_sent` (`test_climate_atw_zone2.py`),
`test_a_dhw_setpoint_matching_current_state_is_still_sent` and
`test_an_operation_mode_matching_current_state_is_still_sent` (`test_water_heater.py`),
`test_atw_power_is_sent_even_when_the_cache_already_agrees` (`test_switch.py`).

**REST (prod).** `hardware_check.py same-value`. Send the same percentage twice, about three
seconds apart. Evidence: two identical `Setting fan speed for <unit> to …` lines, no skip line.

**Devserver.** Same shape, and the only place the ATW setters can be driven: a zone setpoint,
the DHW setpoint or system power sent twice at its current value gives two writes.

**Home app.** Out of reach. A native slider does not send a value it already shows, so the
gesture cannot be made. The nearest thing the app can do is P5, where the slider's own value is
stale and the drag happens to land on the value HA holds.

**Vendor app.** Not a driver.

## P5. A command matching an out-of-band change still sends

**Suite.** Mechanism only. The mocked client is both the cloud and the source of the
coordinator's copy, so a genuine divergence between the two cannot be staged. What the suite
does cover is the comparison that used to drop the command, in the same-value witnesses above.

**REST (prod).** `hardware_check.py out-of-band-match`. It sets the speed through the bundled
API client using `MELCLOUD_USER_OWNER` / `MELCLOUD_PASSWORD_OWNER`, outside HA entirely, waits
for HA to pick the new value up, then commands that same value through HA. Evidence: the
`Setting fan speed for <unit> to …` line for the value HA already holds, and its WebSocket
delta.

**Devserver.** Out of reach. Nothing changes the mock out of band, so there is no second actor
to diverge from.

**Home app.** Change the speed in the vendor app, wait for HA and the Home app's home-screen
tile to show it, then drag the Home app slider to that same value. Evidence: the bridge
receiving the drag, and a `Setting fan speed` line for a value HA already holds. This is the
discussion #135 gesture end to end.

**Vendor app.** The source. It is the only realistic way to move the unit without HA knowing.

---

## Reading the log

```bash
ssh "$HA_SSH_HOST" "sudo docker logs --tail 400 $HA_CONTAINER 2>&1 | grep -a '<unit id>' \
  | grep -aiE 'Setting|already|Poll'"
```

`HA_SSH_HOST` and `HA_CONTAINER` are the `.env` values `tools/hardware_check.py` reads; it does
this read-back for you.

- **Turn debug on for the run.** `Setting …` lines are INFO, but `ATA Poll`, the WebSocket
  deltas and the `already … skipping API call` lines are DEBUG, and the absence of a skip line
  is only evidence if skip lines could have appeared. Set `custom_components.melcloudhome` to
  debug, and `homeassistant.components.homekit` and `pyhap` as well when the Home app is the
  driver. The change is made over the `logger.set_level` service and reverts on restart, so a
  deploy undoes it. Naming the parent logger alone is not enough: prod pins several children in
  `configuration.yaml`, and a pinned child ignores its parent, which looks exactly like code
  that never ran.
- **A refresh is not a poll, and the window is wide.** HA's
  `DataUpdateCoordinator.async_request_refresh` runs through a Debouncer whose
  `REQUEST_REFRESH_DEFAULT_COOLDOWN` is 10 s, so the integration's 2 s debounced refresh lands
  anywhere from 2 to 12 s after a write. `Debounced refresh executing` is the debounce firing,
  not data arriving; wait for the `ATA Poll` line. This is the mechanism behind the 6.58 s and
  9.3 s windows in [ADR-026](../decisions/026-remove-control-write-dedup.md).
- **A poll inside a minute of a rapid command pair is not confirmation.** The cloud's
  `/context` response and its WebSocket deltas reflect the command optimistically. The device's
  own status report arrives every 30 to 60 s and is the truth, and it overrides the cloud's
  optimistic value when the two disagree. Wait for an `ActualFanSpeed` delta, or for two polls a
  minute apart agreeing, before believing either.
- **Prod log times are BST; `date -u` is UTC.** Convert one way or the other before comparing a
  log line against anything timed from the laptop.
- **Entity state proves what HA believes, the log proves what was sent, and only a person in the
  room proves what the unit did.** All three are needed for any check that touches power.

## What the drivers cannot show

The mock answers faster than MELCloud, never rate-limits and never silently drops a PUT, so the
devserver proves client wiring and nothing about the cloud. REST cannot exercise the bridge at
all, so the gesture shapes, the drag burst and the debounce are invisible to it. The Home app
has a display cache of its own: on 14 September its fan detail page held a stale value twice
while its home-screen tile, HA and the cloud all agreed on the new one, which is the app's
behaviour rather than the integration's, so a stale reading there is not a result until HA and
the log have been checked behind it.
