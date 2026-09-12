# Using MELCloud Home with Apple HomeKit

How your air conditioning units appear in the Apple Home app, and the handful of
things about them that catch people out.

**Last Updated:** 2026-09-12

---

## What you will see

Each air conditioning unit gives you two tiles in the Home app rather than one.

The thermostat tile is the one you already have. It carries the temperature and
the heating or cooling mode.

The fan tile is the new one. It carries the fan speed, the vane and the unit's
power. It takes its name from the unit, so a unit called Living Room gives you a
tile called "Living Room A-C fan".

Both tiles are the same air conditioner. A change made on one shows up on the
other, and neither can get out of step with the unit itself.

Heat pumps are unaffected. This applies to air conditioning units only.

## Adding the fan to your bridge

The fan is a new entity, so your HomeKit Bridge will not pick it up on its own.
In Home Assistant go to **Settings** → **Devices & Services** → **HomeKit
Bridge** → **Configure**, and add the fan entities you want to the list the
bridge exposes.

If your bridge is filtered to climate entities only, for example with
`include_domains: [climate]`, the fan will never appear however long you wait.
Add `fan` to the filter.

Take care at the entity selection step: leaving the fan selection empty means
the whole domain, so every unit in your home gets bridged. Pick the ones you
want explicitly if you only want some of them.

Home Assistant rebuilds the bridge when you save, so the new tile appears
without restarting anything. It arrives in whichever room the Home app chooses
by default, so you may want to move it into the right room afterwards.

## Tapping the icon and tapping the label

On the tile itself, the icon and the name do different things.

Tapping the **icon** switches the unit on or off. Tapping the **label** opens
the controls.

This is easy to miss. If you are hunting for a power button, it is the icon.

## The controls behind the label

Open the fan tile and you get three controls: **Oscillate**, **Fan Mode**
(Manual or Auto) and **Fan Speed**.

Only the speed slider and the power are on the tile itself. Apple decides which
fan controls sit on a tile and which sit on the page behind it, and the
integration has no say in that.

## Turning the fan off turns the air conditioner off

This is the one that surprises everyone, so it is worth reading twice.

An air conditioner has no "fan off, unit still running" state. The fan is the
air conditioner. So turning the fan tile off, or dragging its speed slider down
to zero, switches the whole unit off. Turning it back on starts the air
conditioner again, in the mode it was last using.

The same applies to Google Home and Alexa, where the unit also appears as a fan.
Asking a voice assistant to turn off the living room A/C fan stops the air
conditioning in that room.

If what you actually want is the unit running quietly, set the lowest speed
rather than turning the fan off.

## Oscillate does not start the unit

Switching Oscillate on sets the vertical vane sweeping. It does not power the
unit on. If the unit is off, nothing visible happens straight away and the
setting applies the next time it runs. That is deliberate, not a fault.

Switching Oscillate off returns the vane to Auto, which is a fixed angle the
unit chooses to suit what it is doing. It does not go back to a numbered vane
position you might have set in Home Assistant earlier.

## Auto fan speed

Fan Mode has two settings. On **Manual** you choose the speed. On **Auto** the
unit chooses it, and will change it by itself as the room warms or cools.

While you are in Auto, the speed slider keeps the last speed you chose. So the
percentage at the top of the page is the speed the unit will go back to, not the
speed it is running at that moment. The Home app has no way to show those two
things separately, and a slider that remembers your choice is more useful than
one that drifts about on its own.

Switching back to Manual returns the unit to the speed you last chose.

The speed the unit is genuinely running is in Home Assistant, in the **Actual
Fan Speed** sensor. That one does not reach HomeKit at all, so if you want to
watch the unit modulating in Auto, watch it there.

## Units that report no vane

Some units report no vane to the MELCloud Home service, and those get no
Oscillate control. There is nothing missing and nothing to configure, and it is
not unusual for a unit to report no vane.

The alternative would be an Oscillate switch that did nothing at all, which is
worse than no switch.

If a unit has a vane you can move from the official MELCloud Home app and still
gets no Oscillate control here, that is worth
[raising as an issue](https://github.com/andrew-blake/melcloudhome/issues).

## Two things that look wrong and are not

**The name reads "A-C fan".** The entity is called "A/C fan". HomeKit does not
allow a slash in an accessory name and puts a hyphen in its place, so the Home
app shows "A-C fan". Nothing has gone wrong, and you can rename the accessory in
the Home app if it bothers you.

**"Not certified to work with HomeKit".** This banner appears when you pair, and
it appears for everything Home Assistant bridges, not just these fans. Home
Assistant's bridge is not part of Apple's certification programme. It is normal
and it is not a problem.

## Why the thermostat tile stays a plain thermostat

It would be tidier to have one tile with the temperature, the speed and the vane
all on it. Apple does have an accessory type that does exactly that, but a unit
only qualifies for it if its fan speeds carry Apple's own names, which would
mean renaming five numbered speeds onto low, medium and high. That would reach
three of your five speeds instead of all five, and it would break existing
automations and templates that refer to the current names.

A separate fan tile keeps every speed reachable and changes nothing you already
have. [ADR-025](decisions/025-homekit-fan-entity.md) records the full reasoning
for anyone who wants it.

## See also

- [Entity Reference](entities.md) for the fan entity and the Actual Fan Speed
  sensor as they appear inside Home Assistant
- [HomeKit Bridge documentation](https://www.home-assistant.io/integrations/homekit/)
  for bridge setup in general
