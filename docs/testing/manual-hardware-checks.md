# Manual hardware checks for the control path

Read this before claiming a control-path change is verified on hardware, and again while reading
the log. It says which driver can prove which property, what each run must start from, and the
ways the log misleads. Record a run's results in the PR that relies on them.

## Properties and how each is proved

| Property | Suite test | `tools/hardware_check.py` | Devserver | Home app | Vendor app |
| --- | --- | --- | --- | --- | --- |
| 1. Every command is issued to the API, whatever the coordinator's copy holds ([ADR-026](../decisions/026-remove-control-write-dedup.md)) | `test_a_command_matching_current_state_is_still_sent`, `test_the_same_speed_twice_is_sent_twice` | `reversal` (`restart-after-zero` proves a sequence, not this property: write-through updates the copy after each write, so every write it issues already differs from the copy) | same shape over REST; zone setpoint 20, 21, 20 gives three writes | release at A, pause a second, release at B: two writes | source of a change only |
| 2. A power-off issued behind a power-on reaches the API ([#318](https://github.com/andrew-blake/melcloudhome/issues/318)) | `test_power_off_is_sent_to_a_unit_already_off`, `test_a_drag_to_zero_reads_off_before_its_write_lands` | `off-behind-on [--gap S]` | ATW power only, as wiring | from off, drag up and straight to zero | no |
| 3. The entity shows a command as soon as the API accepts it | `test_entity_shows_a_written_speed_before_the_next_refresh`, `test_a_write_landing_during_a_poll_still_shows_the_written_speed`, `test_zone1_entity_shows_a_written_setpoint_before_the_next_refresh` | none: the fan entity reports a pending speed *before* the API is asked, so an entity read cannot tell what the API accepted from what was queued locally. The suite tests are this row's only driver | only place to see it on a heat-pump entity | `set_value: RotationSpeed` in the bridge log, then the push to the phone | no |
| 4. A value the unit already has is still sent | a `…matching_current_state_is_still_sent` case per ATA setter (temperature, both vanes, fan mode) plus `test_set_hvac_mode_writes_even_when_already_matching`, `test_power_off_is_sent_to_a_unit_already_off` and `test_atw_power_is_sent_even_when_the_cache_already_agrees`: the last three do not match that name, so grepping it alone reads as two setters untested | `same-value` (fan speed), `same-value-sweep` (temperature, both vanes, fan mode) | only place the heat-pump setters can be driven | out of reach: a slider does not send a value it already shows | no |
| 5. A command matching an out-of-band change is still sent (discussion #135) | mechanism only: the mock is both the cloud and the copy | `out-of-band-match` | out of reach: nothing changes the mock out of band | vendor app first, then drag the slider to the value HA now holds | the source of the change |
| 6. Writes arriving in one turn share a single request ([ADR-026](../decisions/026-remove-control-write-dedup.md) mitigation 1) | `test_same_turn_writes_share_one_request`, `test_two_ata_writes_in_one_turn_send_one_put`, `test_ten_concurrent_requests_succeeds` counts the PUTs | `combined-write`: the only driver that shows the *unit* acted on every field, which a request count cannot | the e2e suite runs against it | set a thermostat tile to a mode and a temperature in one gesture; one `API Response: PUT` in the log | no |

**A row is a property, not a setter.** ADR-026 counts nine checks removed, five ATA and four ATW;
this page counts six ATA setters because ATA power lost its own check earlier, in `786f5d8`.
Either way, and a driver that proves a property for one of them proves nothing about the rest: the
script's first five checks exercise fan speed and power only, which is why `same-value-sweep`
exists for temperature and the vanes. Before claiming a row, check which setters its driver
actually writes.

Suite tests live under `tests/integration/`; each has been checked by reintroducing the old
comparison and watching it fail. The suite proves what the integration sends and nothing about
the cloud or the unit. The devserver mock accepts every command and never loses one, so it
proves wiring only; it is also the only place the heat pumps are driven, because the ones on the
test account belong to other people. The script reaches the real cloud and unit with exact timing and cannot
reach the HomeKit bridge. The Home app is the only source of the real gesture shapes: a drag
arrives as `Active` plus a run of `RotationSpeed` values, the fan entity's debounce sends the
released value only, and that release carries the power and the speed in one request.

## Preconditions

- **Property 1 through the Home app needs a release at each end.** A pause shorter than the
  debounce collapses the two into one write of the released value. That tests the debounce.
- **Property 2 starts from off.** From on, the copy already reads on and the old code would have
  sent the off too, so the run proves only that it was sent. A run on 14 September 2026 made
  this mistake.
- **Property 5 needs the change made outside Home Assistant first**, and Home Assistant must
  have shown it before the matching command is sent.
- **Walking a range of gaps needs a check that does not exist.** `drop-boundary` did this and was
  removed: its left column was the pause between two service calls, which the pacer floors at
  0.5 s, so it never observed the interval the cloud received and no reading of its table in
  either direction was supported. Conclusions drawn from it have been retracted. Building one
  that says something means timing each pair off its two `API Response: PUT` lines, repeating per
  gap, and leaving a quiet period after each reset long enough that the previous iteration's
  device report cannot land inside the next settle window.

## The script

```bash
uv run python tools/hardware_check.py [-k] [--no-debug] [--entity <fan entity id>] <check>
```

Checks: `state`, `reversal`, `same-value`, `same-value-sweep`, `combined-write`,
`off-behind-on [--gap SECONDS]`, `restart-after-zero` and `out-of-band-match`.
Without `--entity` or a check it lists the fan entities and exits. It reads `HA_URL`,
`HA_TOKEN`, `HA_SSH_HOST` and `HA_CONTAINER` from `.env`, and `MELCLOUD_USER_OWNER` and
`MELCLOUD_PASSWORD_OWNER` for `out-of-band-match`, which sets the speed through the bundled
API client. `-k` disables TLS verification; the LAN hostname in `HA_URL` serves a certificate
issued for another name, and the public hostname is behind Cloudflare Access and returns 403 to
API tokens. Unless `--no-debug` is given it sets the three loggers below to debug for the run
and restores them, reads the log back over SSH, waits 90 seconds after two commands sent close
together for the unit's status report, and leaves the unit in the power state it found.

`--gap` is the pause between the two service calls and **cannot be delivered below 0.5 s**. One
`RequestPacer` per client serialises every request and holds its lock across the round trip, so
the second of any pair waits out the remainder of 0.5 s and the first's response. A gap asked for
below that floor produces the same experiment as the floor itself.

Read the delivered interval off the two `API Response: PUT` lines. **Not off the `Setting` lines:
those are logged in the control client before the pacer is acquired, so they record when a write
was decided, not when it was sent.** A pair timed from them reads far closer together than it was.

The coordinator's polls share that pacer, so an unrelated request can be dispatched between a
pair and widen the delivered interval further, differently on each run.

## Reading the log

```bash
ssh "$HA_SSH_HOST" "sudo docker logs --tail 400 $HA_CONTAINER 2>&1 | grep -a '<unit id>' \
  | grep -aiE 'Setting|already|Poll'"
```

- **Set debug logging first.** `Setting` lines are INFO; `ATA Poll`, the WebSocket deltas and
  `already … skipping API call` are DEBUG, and the absence of a skip line means something only if
  one could have appeared. Set `custom_components.melcloudhome` to debug, and
  `homeassistant.components.homekit` and `pyhap` when the Home app is the driver, through the
  `logger.set_level` service. It reverts on restart. The production `configuration.yaml` pins
  several child loggers and a pinned child ignores its parent, so setting the parent alone leaves
  the lines absent.
- **A refresh lands 2 to 12 seconds after the write.** The integration requests one two seconds
  after a write; `DataUpdateCoordinator.async_request_refresh` has a 10 second cooldown.
  `Debounced refresh executing` records the request; the poll is the `ATA Poll` line. ADR-026's
  6.58 s and 9.3 s windows come from this.
- **The unit's status report is authoritative and arrives late.** `/context` and the WebSocket
  deltas repeat the command back before the unit has acted. The unit reports every 30 to 60
  seconds and its report replaces the cloud's value when they disagree. A poll within a minute of
  two commands sent close together can be wrong; wait for an `ActualFanSpeed` delta or two polls
  a minute apart that agree.
- **Prod log times are BST; `date -u` is UTC.**
- **The Home app has a display cache.** On 14 September its fan detail page held a stale value
  twice while its home-screen tile, Home Assistant and the cloud agreed. Check Home Assistant and
  the log before recording a stale reading from the app.

The entity shows what Home Assistant believes, the log shows what was sent, and only a person in
the room knows what the unit did. A check that touches power needs all three.
