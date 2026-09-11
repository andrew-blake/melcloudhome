# ADR-025: Exposing Fan Speed and Vane to HomeKit

**Status:** Accepted
**Date:** 2026-09-11
**Relates to:** [ADR-013](013-automatic-friendly-device-names.md) (the device
naming this entity inherits),
[ADR-018](018-out-of-band-state-sync-limitation.md) (the deduplication that
applies to these writes)
**Decision Makers:** @andrew-blake

---

## Context

An ATA unit bridged to HomeKit appears as a bare thermostat. Whilst temperature
and operating mode are exposed to HomeKit, the fan speed and the vane are not,
even though they are fully controllable inside Home Assistant.

### Evidence

An ATA unit was bridged to HomeKit on HA 2026.7.4 and paired to an iOS client.
The published accessory contains two services and nothing else, read from
`.storage/homekit.<entry>.iids` for that accessory's aid:

- `3E` AccessoryInformation
- `4A` Thermostat, with `0F` CurrentHeatingCoolingState, `33`
  TargetHeatingCoolingState, `11` CurrentTemperature, `35` TargetTemperature,
  `36` TemperatureDisplayUnits

There is no `B6` SwingMode characteristic and no `B7` Fanv2 service.

### Why both controls are missing

The bridge builds each control only when the climate entity's vocabulary
intersects a fixed set, and neither integration vocabulary does. Fan speed needs
`fan_modes` to intersect `{low, middle, medium, high}`; `ATA_FAN_SPEEDS` is
`["auto", "one", ..., "five"]`. The vane needs `swing_modes` to contain one of
`{on, both, horizontal, vertical}` and, from 2026.8.0, also `off`;
`ATA_VANE_POSITIONS` is `["auto", "swing", "one", ..., "five"]`.
`swing_horizontal_modes` is never consulted at all.

A second gate applies to both and constrains any fix made on the climate entity:
the **reported** value must itself be one of the recognised names, not merely
present in the advertised list. `climate_util.fan_mode_to_speed` returns `None`
unless the reported mode lowercases into `ordered_fan_speeds`, and
`climate_util.is_swing_on` tests the reported `swing_mode` against the predefined
set. Advertising standard names while continuing to report `"three"` or
`"swing"` leaves the corresponding control permanently stale.

### The accessory type is mostly out of reach

From 2026.8.0 the bridge can publish a climate entity as `HeaterCooler`
(`type_heater_coolers.py`), HAP's air-conditioner service, which carries speed
and swing on the accessory itself. Qualifying for it needs
`climate_supports_heater_cooler`, which a standard swing pair alone satisfies.

`_async_resolve_climate_type` auto-routes only when `stored_type is None and allow_auto and not
aid_storage.entity_is_allocated(entity_id)`, so an entity that is already bridged
keeps its Thermostat until a user changes the accessory type by hand in the
bridge options. Every install affected by this problem today is in exactly that
position.

### How many installs this affects

Both controls are missing for anyone bridging ATA units to HomeKit, and the gap
is structural rather than intermittent, so it affects every such install rather
than some. How many that is remains unknown: there is no telemetry on how many
installs bridge to HomeKit, and the direct evidence is a single issue report, so
this record claims no measured population.

HomeKit, and Siri with it, is often the interface used by people in a household
who never open Home Assistant, so a control missing there is missing entirely for
those users rather than merely inconvenient.

Reported as [issue #318](https://github.com/andrew-blake/melcloudhome/issues/318),
which identified the vane gate correctly and proposed renaming the vane values.
The fan gap was found while verifying that report against hardware.

## Decision

A `fan` platform is added for ATA units, carrying fan speed, vane oscillation and
unit power. The climate vocabulary is left alone: `ATA_FAN_SPEEDS`,
`ATA_VANE_POSITIONS` and `ClimateEntityFeature.FAN_MODE` all stay as they are, so
the climate entity keeps its own dropdowns and the new entity is an additional
surface rather than a replacement.

Precedent for one unit carrying both a climate and a fan entity is
`home_connect`, which does this for an air conditioner. `smartthings` is the
counter-precedent, declining a fan entity for anything with a cooling setpoint on
the reasoning that the climate entity already carries the control; that reasoning
does not apply here, because on this integration the climate entity demonstrably
cannot carry it through the bridge.

### Why a fan entity rather than the climate entity

`type_fans` builds its speed slider from `FanEntityFeature.SET_SPEED` and its
swing switch from `FanEntityFeature.OSCILLATE`, with no fixed name set involved,
so a fan entity has no vocabulary gate and both controls work from values the
integration computes directly.

`FanEntity.percentage_step` is `100 / speed_count`,
which the bridge passes as `PROP_MIN_STEP`, so setting `speed_count` from
`capabilities.number_of_fan_speeds` puts one slider detent on each real speed.
Every speed stays reachable only while `speed_count` tracks that capability;
hard-code it and the slider's detents stop matching the hardware.

`oscillating` is a boolean the integration derives from
`vane_vertical_direction == "Swing"`, so the vane round-trips without any
vocabulary or reported-value change. The seven real vane positions remain on the
climate entity's `swing_mode`, since HomeKit's control is binary and cannot
express them.

### How `auto` is represented

`auto` goes in `preset_modes`, alone, because a percentage cannot express it.
With exactly one preset, `type_fans.create_services` appends
`CHAR_TARGET_FAN_STATE`, so it surfaces as HomeKit's Auto toggle rather than a
stray switch, and turning it off restores the previous percentage. This is a
decision rather than an implementation detail, because the single-preset case is
what produces that behaviour and adding a second preset would silently change it.

### Power maps to the unit

`TURN_ON` and `TURN_OFF` are declared and mapped to unit power. An air
conditioner has no "fan off, unit running" state, so power here can only mean
unit power. Withholding the features does not avoid the question: `CHAR_ACTIVE`
is mandatory on the Fanv2 service and wired straight to `fan.turn_off`, so the
Home app shows the button either way, and leaving it undeclared merely makes it
fail and spring back. Given a button that cannot be removed, one that works is
preferred to one that does nothing, so "turn off the A/C fan" switching the unit
off is accepted knowingly.

## Alternatives Considered

**Adding `off` and `vertical` to `swing_modes`** is what #318 proposed, and this
record previously adopted it. It is rejected on three counts, each verified in
core source.

For the swing toggle to read correctly, `is_swing_on` requires the *reported*
`swing_mode` to be `vertical` rather than `swing`, so the change is not additive
despite appearing so: that value would have to change, and any template comparing
against `"swing"` would break silently. That is the same breaking class this record
refuses for `fan_mode`, so the apparent asymmetry between the two vocabularies
does not exist.

Setting `swing_on_mode` also makes `fan_chars` non-empty, which builds a linked
Fanv2 on the Thermostat with `CHAR_ACTIVE` configured unconditionally, and
`_set_fan_active` rejects every write to it because `ATA_FAN_SPEEDS` contains no
`off`. That ships a dead control: a power button on the new tile that visibly
does nothing.

The justification for accepting all that was promotion to `HeaterCooler`, which
per the Context section requires a manual accessory-type change on every
already-bridged entity, so the payoff mostly does not arrive.

**Renaming `fan_modes` to standard names** has the most precedent in core:
`midea`, `gree`, `sensibo` and `lg_thinq` all map vendor speeds onto standard
names, and `midea` shows it need not cost HA anything, keeping five speeds by
using standard names in the middle and custom `silent` and `full` at the
extremes. It is rejected because of the read-back gate, which would force the
reported `fan_mode` from `"three"` to `"medium"` and silently break templates,
because HomeKit would reach only three of five speeds, and because
`geoffdavis/esphome-mitsubishiheatpump` ran this experiment on the same hardware;
its
[issue #135](https://github.com/geoffdavis/esphome-mitsubishiheatpump/issues/135)
is a user asking to be put back on numbers because `medium` and `middle` are
indistinguishable. It would also destroy the case-fold symmetry of
`normalize_to_api`, currently a pure round trip against the API's own vocabulary.
Putting speed on the `HeaterCooler` accessory would be the tidiest outcome of
all, but it is unreachable without this rename and so falls with it.

**Doing nothing** is core's position and is defensible: the developer
documentation explicitly permits custom fan modes, and in
[architecture discussion #553](https://github.com/home-assistant/architecture/discussions/553)
a maintainer rejected expanding the built-in sets on the grounds that the options
are vendor-specific. HA core's own `melcloud_home` integration has the same gap
for the same hardware. It is rejected because the complaints are being filed
here.

## Consequences

- HomeKit gains a second tile per unit, for example "Living Room A/C fan",
  carrying the speed slider, the swing switch and power. The climate accessory is
  untouched and continues to publish temperature and mode only.
- The air conditioner keeps publishing as a Thermostat rather than as an air
  conditioner. Correct classification needs `HeaterCooler`, which needs the
  rejected vocabulary change and a manual accessory-type change besides.
- **The fan entity reaches every voice assistant, not only HomeKit.** A `fan`
  domain entity appears in Google Home and Alexa as a fan with a power switch,
  for every user, whether or not they bridge to HomeKit. Anyone asking Google or
  Alexa to turn that fan off switches the air conditioner off.
- Fan speed becomes settable from two places in HA, the climate entity's
  `fan_mode` dropdown and the new entity's percentage, visible on the device page
  and in both more-info dialogs but not on the dashboard thermostat card unless
  the user opted into the `climate-fan-modes` card feature. The overlap is
  accepted, because suppressing the dropdown would mean dropping
  `ClimateEntityFeature.FAN_MODE` and breaking every existing
  `climate.set_fan_mode` call.
- The vane is binary through HomeKit. Positions one to five stay reachable from
  Home Assistant only.
- `percentage` reports the commanded speed, so in `auto` the slider shows the
  setpoint rather than the speed the fan is running. Reporting `actual_fan_speed`
  (#285) would be more informative but makes reads and writes reference different
  API fields, so it is deferred rather than adopted silently.
- Existing automations, templates and service calls keep working unchanged,
  because every advertised list and every reported value stays as it is.

## Open Questions

- Entity creation is gated on a stable capability, `number_of_fan_speeds > 0`.
  The behaviour when `unit.capabilities` is `None` is unresolved: `ATAClimate`
  falls back to all five speeds in that case, and whether the fan entity should
  follow that fallback or skip creation needs deciding during implementation.

### Conditions for Revisiting

- **If core ever auto-routes already-bridged entities to `HeaterCooler`**, or if
  changing the accessory type by hand becomes normal, the swing vocabulary
  question reopens, since correct classification would then be purchasable for
  the cost of one breaking reported-value change.
- **If the duplicated fan speed control draws support traffic**, `home_connect`'s
  shape is the one to migrate towards: `fan_modes` becomes `["auto", "manual"]`
  and speed lives only on the fan entity, at the same migration cost as renaming.
- **If [architecture#1468](https://github.com/home-assistant/architecture/discussions/1468)
  reaches the HomeKit bridge.** It proposes mapping climate `fan_modes` to a
  positional `1..N` range for Alexa. Applied to HomeKit, this entity would become
  redundant. That discussion had no replies when this was written, so it is not a
  reason to wait.

## References

- `homekit/type_fans.py`, `type_thermostats.py`, `type_heater_coolers.py`,
  `climate_base.py`, `climate_util.py`, `accessories.py` and `aidmanager.py` in
  HA core, read from the 2026.9.1 wheel and diffed against 2026.8.0
- [Climate entity developer docs](https://developers.home-assistant.io/docs/core/entity/climate/#fan-modes),
  which permit custom fan modes
- [issue #318](https://github.com/andrew-blake/melcloudhome/issues/318)
- [architecture#553](https://github.com/home-assistant/architecture/discussions/553)
- Mitsubishi MSZ-LN VG operating instructions; MELCloud Home user manual,
  "Vane (Horizontal and Vertical)"
