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
even though they are fully controllable inside Home Assistant. Reported as
[issue #318](https://github.com/andrew-blake/melcloudhome/issues/318), which
identified the vane gate correctly and proposed renaming the vane values; the fan
gap was found while verifying that report against hardware.

### Evidence

An ATA unit was bridged to HomeKit on HA 2026.7.4 and paired to an iOS client.
Reading `.storage/homekit.<entry>.iids` for that accessory's aid shows two
services and nothing else: `3E` AccessoryInformation and `4A` Thermostat. There
is no `B6` SwingMode characteristic and no `B7` Fanv2 service.

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

### The Heater Cooler accessory type

From 2026.8.0 the bridge can publish a climate entity as a Heater Cooler rather
than a Thermostat. That is HAP's air-conditioner service, and it puts mode,
temperature, fan speed and swing on a single tile, which is how the device
actually works. The HomeKit Bridge documentation says which entities get it:

> Air conditioners and heat pumps that offer two or more fan speeds or a swing
> mode that can be turned off.

The fan speeds here are numbered rather than named, and the vane has no `off`, so
these units meet neither condition and do not qualify.

More importantly, qualifying does not bring fan speed with it. An entity that
qualifies on its swing values alone still advertises no standard fan names, so
its tile would gain a swing switch and no speed slider. Reaching both controls on
one tile means changing both vocabularies.

One smaller limit, which shrinks over time rather than persisting: the
documentation also says entities "already exposed before this feature was
introduced keep their Thermostat accessory", so anyone who has already bridged a
unit must change the accessory type by hand. Issue #318 is the first time HomeKit
has come up for this integration, so that is a handful of people, and anyone
bridging later would get the Heater Cooler automatically.

### Who this affects

Both controls are missing for anyone bridging ATA units to HomeKit, so it affects
every such install rather than some.

HomeKit, and Siri with it, is often the interface used by people in a household
who never open Home Assistant, so a control missing there is missing entirely for
those users rather than merely inconvenient.

## Decision

A `fan` platform is added for ATA units, carrying fan speed, vane oscillation and
unit power. The climate vocabulary is left alone: `ATA_FAN_SPEEDS`,
`ATA_VANE_POSITIONS` and `ClimateEntityFeature.FAN_MODE` all stay as they are, so
the climate entity keeps its own dropdowns and the new entity is an additional
surface rather than a replacement.

`home_connect` is the precedent, shipping both a climate and a fan entity for one
air conditioner. `smartthings` is the counter-precedent, refusing a fan entity
for anything with a cooling setpoint because the climate entity already carries
the control, which is the one thing that is not true here.

### Why a fan entity rather than the climate entity

`type_fans` builds its speed slider from `FanEntityFeature.SET_SPEED` and its
swing switch from `FanEntityFeature.OSCILLATE`, with no fixed name set involved,
so a fan entity has no vocabulary gate and both controls work from values the
integration computes directly.

`FanEntity.percentage_step` is `100 / speed_count`, which the bridge passes as
`PROP_MIN_STEP`, so setting `speed_count` from
`capabilities.number_of_fan_speeds` puts one slider detent on each real speed.
Every speed stays reachable only while `speed_count` tracks that capability;
hard-code it and the slider's detents stop matching the hardware. That same
division is why a unit reporting no fan speeds at all gets no fan entity: a
`speed_count` of zero would make every state update raise.

`oscillating` is a boolean the integration derives from
`vane_vertical_direction == "Swing"`, so the vane round-trips without any
vocabulary or reported-value change. `Swing` sweeps and `Auto` is a fixed angle
chosen by operating mode, so reporting `Auto` as not oscillating is true of the
hardware. The seven real vane positions remain on the climate entity's
`swing_mode`, since HomeKit's control is binary and cannot express them.
`OSCILLATE` is declared only where `capabilities.has_swing` or
`has_air_direction` is set, the gate the climate entity already puts on
`SWING_MODE`, so a unit without a vane gets no switch rather than a dead one.

Oscillating writes the vane and nothing else, so switching it on does not start
a stopped unit. It sets the vane for the next time the unit runs.

### How `auto` is represented

`auto` goes in `preset_modes`, alone, because a percentage cannot express it.
Being alone is the decision rather than an accident: with exactly one preset the
bridge appends `CHAR_TARGET_FAN_STATE`, giving HomeKit's proper Auto toggle,
whereas a second preset would silently turn both into stray switches. The cost
is borne inside Home Assistant, where the fan dialog renders no preset selector
for a single preset, so `auto` is chosen from the climate entity's `fan_mode`
dropdown or a service call rather than from this entity.

While `auto` is selected, `percentage` keeps reporting the last numbered speed
the unit has been seen on rather than going blank, and is unknown only before
any numbered speed has been seen at all. That matches HAP's own model, in which
`RotationSpeed` is the manual setpoint that persists while `TargetFanState` is
Auto rather than a value that goes blank when Auto is selected. It also matters
for the Manual/Auto toggle specifically: `type_fans.set_single_preset_mode`
reads that percentage back when the user leaves Auto and falls back to a
hard-coded 50% if it finds `None`, moving the unit to whatever speed that maps
to instead of the one the user was actually on.

### Power maps to the unit

`TURN_ON` and `TURN_OFF` are declared and mapped to unit power. An air
conditioner has no "fan off, unit running" state, so power here can only mean
unit power. Withholding the features does not avoid the question: `CHAR_ACTIVE`
is mandatory on the Fanv2 service and wired straight to `fan.turn_off`, so the
Home app shows the button either way, and leaving it undeclared merely makes it
fail and spring back. Given a button that cannot be removed, one that works is
preferred to one that does nothing, so "turn off the A/C fan" switching the unit
off is accepted knowingly.

Setting a non-zero speed powers the unit on as well as commanding the speed. The
bridge sends `Active=1` and `RotationSpeed` together when the slider is dragged
up on an inactive tile, then deliberately skips `fan.turn_on` on the documented
assumption that a `SET_SPEED` fan powers itself on. A power-on carries the
device's current `operation_mode`, because a bare power write sends
`operationMode=null`, which can fault a multi-zone outdoor unit; the mode is
omitted only when the device reports none to preserve. Powering off carries
nothing, since there is no mode to keep on the way down.

### One write per slider drag

A HomeKit slider drag is not one command. The bridge sends every intermediate
position the finger passes through, so one gesture arrives as a burst of speed
writes. Those writes overlap in flight and the server applies them in the order
they arrive rather than the order they were issued, so the position the user
released on can lose to an earlier one: a drag ending on speed three settled the
unit on speed two.

Only the final position is written, half a second after the slider stops moving.
One write per gesture makes the ordering race impossible. The window has to be
wider than the gap between intermediate positions, which is around a quarter of
a second, and short enough that deliberate steps a few seconds apart are each
treated as their own settled position rather than swallowed.

The power-on is not deferred, so the unit starts the moment a drag begins. It is
suppressed for a few seconds after one succeeds instead, because the shared
write-deduplication compares against coordinator data that stays stale until the
next refresh and so cannot recognise the repeats itself. An explicit
`fan.turn_on` is never suppressed: the suppression exists to tame the drag
burst, not to make the documented service unreliable.

## Alternatives Considered

**Adding `off` and `vertical` to `swing_modes`** is what #318 proposed. It is
recorded at this length because it looks additive and safe, and is neither; each
of the three problems below is verified in core source.

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

The justification for accepting all that was promotion to the Heater Cooler
accessory. That payoff is real for anyone bridging later, and delayed for anyone
already bridged, who must change the accessory type by hand. What it would not
deliver is fan speed, which needs the rename below as well, so the swing change
alone buys a better-looking tile and leaves half the reported problem in place.

**Renaming `fan_modes` to standard names** has the most precedent in core:
`midea`, `gree`, `sensibo` and `lg_thinq` all map vendor speeds onto standard
names, and `midea` shows it need not cost HA anything, keeping five speeds by
using standard names in the middle and custom `silent` and `full` at the
extremes. It is rejected because of the read-back gate, which would force the
reported `fan_mode` from `"three"` to `"medium"` and silently break templates,
because HomeKit would reach only three of five speeds, and because the same
renaming has already been tried on this hardware and rejected by its users.

`geoffdavis/esphome-mitsubishiheatpump` drives the same hardware through a library
whose fan map is numbered, then had to invent a mapping onto `low`, `medium`,
`high` and `middle` because ESPHome forces a fixed set of names. Its
[issue #135](https://github.com/geoffdavis/esphome-mitsubishiheatpump/issues/135)
is three users asking for numbers back, one keeping a lookup table to remember
which of `medium` and `middle` is which, and it was closed when the reporter
installed a template component to undo the renaming from outside.

Renaming would also destroy the case-fold symmetry of `normalize_to_api`,
currently a pure round trip against the API's own vocabulary.

Putting speed on the `HeaterCooler` accessory would be the tidiest outcome of
all, but it is unreachable without this rename and so falls with it. Note that
it would not have been the better outcome for resolution: `HeaterCooler` derives
its slider step from `100 / len(ordered_fan_speeds)` exactly as the Thermostat's
linked fan service does, so it too would reach three of five speeds. The fan
entity gives five.

**Documenting a template recipe instead of shipping a platform** would work, and
it is what the ESPHome users fell back on. Core's template integration has no
climate platform, which is why they needed a third-party component from HACS, but
it does have a template fan supporting `speed_count`, `percentage`,
`preset_modes` and `oscillating`, so a user could wrap the climate entity in
plain YAML and bridge that instead. It is rejected as the answer because it asks
every affected user to write and maintain the same mapping by hand, in a project
whose users are Home Assistant owners rather than developers, and it still
creates a second entity, so it carries this decision's main cost without its
convenience.

**Doing nothing** is core's position and is defensible: the developer
documentation explicitly permits custom fan modes, and in
[architecture discussion #553](https://github.com/home-assistant/architecture/discussions/553)
a maintainer rejected expanding the built-in sets on the grounds that the options
are vendor-specific. HA core's own `melcloud_home` integration has the same gap
for the same hardware. Doing nothing is the right answer when a fix costs more
than the problem, and it is rejected here because the fan entity costs existing
users nothing.

## Consequences

- HomeKit gains a second tile per unit, for example "Living Room A-C fan". The
  Home app shows a hyphen because the bridge substitutes one for the slash in
  the entity name; the name stays as it is, since "A-C fan" still reads as an
  air conditioner rather than a room fan. The tile carries power and the speed
  slider, with Oscillate and the Manual/Auto toggle on the accessory page behind
  it. That placement is the Home app's own layout for a fan service and is not
  something the integration chooses. The climate accessory is untouched and
  continues to publish temperature and mode only.
- The air conditioner keeps publishing as a Thermostat rather than as an air
  conditioner. Correct classification needs `HeaterCooler`, which needs the
  rejected vocabulary change and a manual accessory-type change besides.
- The fan entity reaches every voice assistant, not only HomeKit. A `fan`
  domain entity appears in Google Home and Alexa as a fan with a power switch,
  for every user, whether or not they bridge to HomeKit. Anyone asking Google or
  Alexa to turn that fan off switches the air conditioner off.
- Fan speed becomes settable from two places in HA, the climate entity's
  `fan_mode` dropdown and the new entity's percentage, visible on the device page
  and in both more-info dialogs but not on the dashboard thermostat card unless
  the user opted into the `climate-fan-modes` card feature. The two surfaces
  cannot disagree, since both read the same coordinator field, and either one
  reflects a change made from the other. The overlap is accepted, because
  suppressing the dropdown would mean dropping `ClimateEntityFeature.FAN_MODE`
  and breaking every existing `climate.set_fan_mode` call.
- The vane is binary through HomeKit. Positions one to five stay reachable from
  Home Assistant only, and switching oscillation off returns the vane to `Auto`
  rather than to the position it held before. A unit set to position three, then
  swung and unswung from the Home app, ends on `Auto`. Restoring the prior
  position would mean holding state the coordinator does not keep, which is not
  worth it for a binary control, so the loss is accepted.
- Units whose capabilities report no vane get no oscillation control at all.
  That is common rather than exceptional: three of the six units in the
  installation this was verified against report none, so without the capability
  gate half of them would have carried a swing switch wired to hardware that
  cannot swing.
- `percentage` reports the commanded speed and the `auto` preset carries the
  auto state. Leaving `auto` returns the unit to the speed the user last chose
  rather than to a bridge default, and the percentage is unknown only before any
  numbered speed has been seen.
- **In `auto`, the Home app's title misreports the running speed, and this is
  accepted.** Its accessory page renders `RotationSpeed` as "N% Speed"
  regardless of `TargetFanState`, so in `auto` it shows the speed the unit will
  resume, not the one it is running. Observed on hardware: the title read
  "100% Speed" while the unit modulated itself down to speed two, audibly. The
  bridge reads the same `percentage` for both the title and the Manual fallback,
  so the two cannot be answered differently. Reporting `actual_fan_speed` (#285)
  would make the title honest, but it makes reads and writes reference different
  API fields, and that field lags by several minutes, so the manual slider would
  visibly spring back after a drag and look like the control rejecting input.
  Between a title that misinforms and a control that appears broken, the title
  is preferred, and #285 stays deferred. The running speed remains visible in
  the Actual Fan Speed sensor, which under `auto` is the only place it appears.
- Existing automations, templates and service calls keep working unchanged,
  because every advertised list and every reported value stays as it is.

## Conditions for Revisiting

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
- [HomeKit Bridge documentation](https://www.home-assistant.io/integrations/homekit/),
  which is the source of both quotations above
- [Climate entity developer docs](https://developers.home-assistant.io/docs/core/entity/climate/#fan-modes),
  which permit custom fan modes
- [issue #318](https://github.com/andrew-blake/melcloudhome/issues/318)
- [architecture#553](https://github.com/home-assistant/architecture/discussions/553)
- Mitsubishi MSZ-LN VG operating instructions; MELCloud Home user manual,
  "Vane (Horizontal and Vertical)"
