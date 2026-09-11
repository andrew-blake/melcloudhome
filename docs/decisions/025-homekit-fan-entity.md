# ADR-025: Exposing Fan Speed and Vane to HomeKit

**Status:** Accepted
**Date:** 2026-09-11
**Relates to:** [ADR-013](013-automatic-friendly-device-names.md) (the device
naming these entities inherit),
[ADR-018](018-out-of-band-state-sync-limitation.md) (the deduplication that
applies to these writes)
**Decision Makers:** @andrew-blake

---

## Context

An ATA unit bridged to HomeKit appears as a bare thermostat. Temperature and
operating mode are controllable, and fan speed and the vane are not reachable at
all, from the Home app or from Siri. Both are fully controllable inside Home
Assistant, so the capability exists and stops at the bridge.

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

The bridge builds each control only when the entity's vocabulary intersects a
fixed set, and neither integration vocabulary does.

Fan speed needs `fan_modes` to intersect `PRE_DEFINED_FAN_MODES`, which is
`{low, middle, medium, high}`. `ATA_FAN_SPEEDS` is
`["auto", "one", ..., "five"]`, sliced per device to `auto` plus
`capabilities.number_of_fan_speeds` entries, so `ordered_fan_speeds` stays empty
and no speed characteristic is added. `CHAR_TARGET_FAN_STATE` needs `auto` plus
either `on` or a non-empty `ordered_fan_speeds`, so it is skipped too, leaving
`fan_chars` empty and no fan service built at all.

The vane needs `swing_modes` to contain one of `PRE_DEFINED_SWING_MODES` (`on`,
`both`, `horizontal`, `vertical`) and, from 2026.8.0, also `off`.
`ATA_VANE_POSITIONS` is `["auto", "swing", "one", ..., "five"]`, which satisfies
neither. `swing_horizontal_modes` is never consulted by the bridge.

The **reported** value must itself be one of the recognised names, not merely
present in the advertised list, which constrains any fix:

```python
if (CHAR_ROTATION_SPEED in self.fan_chars
        and fan_mode_lower in self.ordered_fan_speeds):
    self.char_speed.set_value(
        ordered_list_item_to_percentage(self.ordered_fan_speeds, fan_mode_lower))
```

So adding standard names as extra selectable values while `fan_mode` continues
to report `"three"` would leave the slider permanently stale. The vane read-back
has no such gate: an unrecognised value simply reads as not oscillating.

### Accessory types available

From 2026.8.0 the bridge can publish a climate entity as `HeaterCooler`
(`type_heater_coolers.py`) rather than `Thermostat`. `HeaterCooler` is HAP's
air-conditioner service: it is categorised `CATEGORY_AIR_CONDITIONER`, and it
carries `CHAR_ROTATION_SPEED` and `CHAR_SWING_MODE` on the accessory itself
rather than on a linked fan service. It is the correct representation of an air
conditioner in the Home app.

Routing to it requires `climate_supports_heater_cooler`, which passes on
**either** two or more standard fan names **or** a standard swing pair. The
swing route is therefore reachable without touching fan speed.

### How many installs this affects

Both controls are missing for anyone bridging ATA units to HomeKit, and the gap
is structural rather than intermittent, so it affects every such install rather
than some. How many that is remains unknown: there is no telemetry on how many
installs bridge to HomeKit, and the direct evidence is a single issue report, so
this record claims no measured population.

HomeKit, and Siri with it, is often the interface used by people in a household
who never open Home Assistant, so a control missing there is missing entirely
for those users rather than merely inconvenient.

Reported as [issue #318](https://github.com/andrew-blake/melcloudhome/issues/318),
which identified the vane gate correctly and proposed renaming the vane values.
The fan gap was found while verifying that report against hardware.

## Decision

Three changes, none of them a rename or a removal:

1. `ATA_VANE_POSITIONS` gains `off` and `vertical`, keeping `auto`, `swing` and
   `one`..`five`.
2. A `fan` entity is added per ATA unit, carrying speed and unit power.
3. `ATA_FAN_SPEEDS` and `ClimateEntityFeature.FAN_MODE` are left as they are, so
   the climate entity keeps its own fan dropdown and the new entity is an
   additional surface rather than a replacement.

### Why the vane goes on the climate entity

A standard swing pair is what qualifies the climate entity for `HeaterCooler` on
2026.8.0 and later. Declaring `OSCILLATE` on the fan entity would expose the
vane just as well but would leave the air conditioner publishing as a
Thermostat, never classified correctly.

Adding the values rather than renaming `auto` and `swing` keeps every existing
automation working, and core already ships translations for both. Mapping `off`
to API `Auto` is true of the hardware, not a convenience: Mitsubishi's MSZ-LN
instructions describe `AUTO` as "the most efficient airflow direction.
COOL/DRY/FAN: horizontal position. HEAT: position (4)" and reserve "moves up and
down intermittently" for `Swing`.

### Why fan speed needs its own entity

Exposing speed on the climate entity would require the reported `fan_mode` to
become a standard name, which silently breaks any template comparing against
`"three"`. A fan entity has no vocabulary gate, and
its slider resolution comes from the unit's own speed count, so all five speeds
stay reachable instead of three. It carries no `OSCILLATE`, so one vane has one
switch.

Precedent is `home_connect`, which ships a climate and a fan entity for one air
conditioner; `smartthings` is the counter-precedent, declining a fan entity for
anything with a cooling setpoint.

### Why the fan entity controls unit power

An air conditioner has no "fan off, unit running" state, so power here can only
mean unit power. Withholding the features does not avoid that: `CHAR_ACTIVE` is
mandatory on the Fanv2 service and wired straight to `fan.turn_off`, so the Home
app shows the button either way and leaving it undeclared merely makes it fail.
Given a button that cannot be removed, one that works is preferred to one that
does nothing, so "turn off the A/C fan" switching the unit off is accepted
knowingly.

### Version behaviour

`hacs.json` keeps its 2025.8.0 minimum, and the code branches on no HA version.
Older installs get a less tidy accessory layout, described under Consequences,
and keep every control the newer ones have.

## Alternatives Considered

**Renaming `fan_modes`** has the most precedent in core: `midea`, `gree`,
`sensibo` and `lg_thinq` all map vendor speeds onto standard names, and `midea`
shows it need not cost HA anything, keeping five speeds by using standard names
in the middle and custom `silent` and `full` at the extremes. It is rejected
because of the read-back gate: the reported `fan_mode` would have to change
from `"three"` to `"medium"`, which silently breaks any template or condition
comparing against the numbered values. HomeKit would also reach only three of
five speeds, and `geoffdavis/esphome-mitsubishiheatpump` ran this experiment on
the same hardware; its [issue #135](https://github.com/geoffdavis/esphome-mitsubishiheatpump/issues/135) is a user asking to be put back on numbers because
`medium` and `middle` are indistinguishable. It would further destroy the
case-fold symmetry of `normalize_to_api`, currently a pure round trip against
the API's own vocabulary, requiring a bidirectional map maintained in the list,
the read property and the write path. Putting speed on the `HeaterCooler`
accessory would be the tidiest outcome of all, one correctly-classified tile
carrying everything, but it is unreachable without this rename and so falls
with it.

**`OSCILLATE` on the fan entity** would expose the vane with no vocabulary
change at all. It is rejected because it leaves the climate entity failing
`climate_supports_heater_cooler`, so the air conditioner keeps publishing as a
Thermostat and the Home app never classifies it correctly.

**Both swing routes** would place two identical oscillation switches in the Home
app for one vane. They could not disagree, since both read
`vane_vertical_direction` through the one coordinator, but the duplication buys
nothing.

**Doing nothing** is core's position and is defensible: the developer
documentation explicitly permits custom fan modes, and in
[architecture discussion #553](https://github.com/home-assistant/architecture/discussions/553)
a maintainer rejected expanding the built-in sets on the grounds that the
options are vendor-specific. It is rejected because the complaints are being
filed here.

## Consequences

- On 2026.8.0 and later, HomeKit shows an air-conditioner tile with temperature,
  mode and swing, plus a second tile, for example "Living Room A/C fan",
  carrying the speed slider. On earlier versions the first tile is a thermostat
  instead.
- Airflow is split across two tiles: swing on the air conditioner, speed on the
  fan. Each control is where its own concept belongs, but they are not adjacent
  as they would be on a physical remote.
- The fan tile's power button switches the air conditioner off, and so does
  dragging the slider to zero. Deliberate, and the least-bad option given
  `CHAR_ACTIVE` cannot be suppressed.
- The vane dropdown in HA gains two entries that duplicate `auto` and `swing` in
  effect. That is the price of the standard vocabulary, and it is why the
  original names are kept rather than replaced.
- Fan speed becomes settable from two places in HA, the climate entity's
  `fan_mode` dropdown and the new entity's percentage, visible on the device
  page and in both more-info dialogs but not on the dashboard thermostat card
  unless the user opted into the `climate-fan-modes` card feature. The overlap
  is accepted, because suppressing the dropdown would mean dropping
  `ClimateEntityFeature.FAN_MODE` and breaking every existing
  `climate.set_fan_mode` call.
- `percentage` reports the commanded speed, so in `auto` the slider shows the
  setpoint rather than the speed the fan is running. Reporting
  `actual_fan_speed` (#285) would be more informative but makes reads and writes
  reference different API fields, so it is deferred rather than adopted
  silently.

## Open Questions

- Entity creation is gated on a stable capability, `number_of_fan_speeds > 0`.
  The behaviour when `unit.capabilities` is `None` is unresolved: `ATAClimate`
  falls back to all five speeds in that case, and whether the fan entity should
  follow that fallback or skip creation needs deciding during implementation.

### Conditions for Revisiting

- **If the duplicated fan speed control draws support traffic**,
  `home_connect`'s shape is the one to migrate towards: `fan_modes` becomes
  `["auto", "manual"]` and speed lives only on the fan entity, at the same
  migration cost as renaming.
- **If the two-tile layout proves confusing in practice**, the rename becomes
  worth its cost, because it is the only route to a single correctly-classified
  tile carrying both controls. That trade is three of five speeds in HomeKit and
  a breaking change to the reported `fan_mode`, against one tile instead of two.
- **If [architecture#1468](https://github.com/home-assistant/architecture/discussions/1468)
  reaches the HomeKit bridge.** It proposes mapping climate `fan_modes` to a
  positional `1..N` range for Alexa. Applied to HomeKit, the fan entity would
  become redundant. That discussion had no replies when this was written, so it
  is not a reason to wait.

## References

- `homekit/type_thermostats.py`, `type_heater_coolers.py`, `type_fans.py`,
  `climate_base.py`, `climate_util.py` in HA core
- [Climate entity developer docs](https://developers.home-assistant.io/docs/core/entity/climate/#fan-modes),
  which permit custom fan modes
- [issue #318](https://github.com/andrew-blake/melcloudhome/issues/318)
- [architecture#553](https://github.com/home-assistant/architecture/discussions/553)
- Mitsubishi MSZ-LN VG operating instructions; MELCloud Home user manual,
  "Vane (Horizontal and Vertical)"
