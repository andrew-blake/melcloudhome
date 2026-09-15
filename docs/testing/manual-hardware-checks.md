# Manual hardware checks for the control path

Read this before claiming a control-path change is verified on hardware, and again while reading
the log. It says which driver can prove which property, what each run must start from, and the
ways the log misleads. Record a run's results in the PR that relies on them.

## Properties and how each is proved

| Property | Suite test | `tools/hardware_check.py` | Devserver | Home app | Vendor app |
| --- | --- | --- | --- | --- | --- |
| 1. Every command reaches the API, whatever the coordinator's copy holds ([ADR-026](../decisions/026-remove-control-write-dedup.md)) | `test_a_command_matching_current_state_is_still_sent`, `test_the_same_speed_twice_is_sent_twice` | `reversal`, `restart-after-zero` | same shape over REST; zone setpoint 20, 21, 20 gives three writes | release at A, pause a second, release at B: two writes | source of a change only |
| 2. A power-off issued behind a power-on reaches the API ([#318](https://github.com/andrew-blake/melcloudhome/issues/318)) | `test_power_off_is_sent_to_a_unit_already_off`, `test_power_off_disarms_the_power_on_guard` | `off-behind-on [--gap S]`, `drop-boundary` | ATW power only, as wiring | from off, drag up and straight to zero | no |
| 3. The entity shows a command as soon as the API accepts it | `test_entity_shows_a_written_speed_before_the_next_refresh`, `test_a_write_landing_during_a_poll_still_shows_the_written_speed`, `test_zone1_entity_shows_a_written_setpoint_before_the_next_refresh` | every check reads the entity after each step | only place to see it on a heat-pump entity | `set_value: RotationSpeed` in the bridge log, then the push to the phone | no |
| 4. A value the unit already has is still sent | one `…matching_current_state_is_still_sent` test per setter, plus `test_atw_power_is_sent_even_when_the_cache_already_agrees` | `same-value` | only place the heat-pump setters can be driven | out of reach: a slider does not send a value it already shows | no |
| 5. A command matching an out-of-band change is still sent (discussion #135) | mechanism only: the mock is both the cloud and the copy | `out-of-band-match` | out of reach: nothing changes the mock out of band | vendor app first, then drag the slider to the value HA now holds | the source of the change |

Suite tests live under `tests/integration/`; each has been checked by reintroducing the old
comparison and watching it fail. The suite proves what the integration sends and nothing about
the cloud or the unit. The devserver mock accepts every command and never loses one, so it
proves wiring only; it is also the only place the heat pumps are driven, because the ones on the
test account belong to other people. The script reaches the real cloud and unit with exact timing and cannot
reach the HomeKit bridge. The Home app is the only source of the real gesture shapes: a drag
arrives as `Active` plus a run of `RotationSpeed` values, the fan entity's debounce sends the
released value only, and the power-on guard decides whether `power+mode` precedes the speed.

## Preconditions

- **Property 1 through the Home app needs a release at each end.** A pause shorter than the
  debounce collapses the two into one write of the released value. That tests the debounce.
- **Property 2 starts from off.** From on, the copy already reads on and the old code would have
  sent the off too, so the run proves only that it was sent. A run on 14 September 2026 made
  this mistake.
- **Property 5 needs the change made outside Home Assistant first**, and Home Assistant must
  have shown it before the matching command is sent.

## The script

```bash
uv run python tools/hardware_check.py [-k] [--no-debug] [--entity <fan entity id>] <check>
```

Checks: `state`, `reversal`, `same-value`, `off-behind-on [--gap SECONDS]`,
`restart-after-zero`, `out-of-band-match`, `drop-boundary [--gaps 0.2,0.4,0.7,1.0,1.5]`.
Without `--entity` or a check it lists the fan entities and exits. It reads `HA_URL`,
`HA_TOKEN`, `HA_SSH_HOST` and `HA_CONTAINER` from `.env`, and `MELCLOUD_USER_OWNER` and
`MELCLOUD_PASSWORD_OWNER` for `out-of-band-match`, which sets the speed through the bundled
API client. `-k` disables TLS verification; the LAN hostname in `HA_URL` serves a certificate
issued for another name, and the public hostname is behind Cloudflare Access and returns 403 to
API tokens. Unless `--no-debug` is given it sets the three loggers below to debug for the run
and restores them, reads the log back over SSH, waits 90 seconds after two commands sent close
together for the unit's status report, and leaves the unit in the power state it found.

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
