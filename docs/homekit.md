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
`include_domains: [climate]`, add `fan` to the filter as well. Without it the
fan entities are not offered to HomeKit at all, so the new tile will not show
up.

Take care at the entity selection step: leaving the fan selection empty means
the whole domain, so every unit in your home gets bridged. Pick the ones you
want explicitly if you only want some of them.

Home Assistant rebuilds the bridge when you save, so the new tile appears
without restarting anything. It arrives in whichever room the Home app chooses
by default, so you may want to move it into the right room afterwards.

## Tapping the icon and tapping the label

On the tile itself, the icon and the name do different things.

Tapping the **icon** switches the unit on or off. Tapping the **label** opens
the speed slider.

If you are looking for a power button, the icon is it.

## Finding Oscillate and Fan Mode

Opening the tile gives you the speed slider and nothing else. There is no
power button in that view: the slider is the power control, and setting it to
anything above zero starts the unit. **Oscillate** and **Fan Mode** (Manual or
Auto) are one level further in, behind the cog icon in the corner.

Nothing on the slider view hints that there is more behind the cog. Apple
decides which fan controls sit on the tile and which sit on the settings page,
and the integration has no say in it.

## Turning the fan off turns the air conditioner off

An air conditioner has no "fan off, unit still running" state. The fan is the
air conditioner. So turning the fan tile off, or dragging its speed slider down
to zero, switches the whole unit off. Turning it back on starts the air
conditioner again, in the mode it was last using.

We have only checked this through HomeKit. The entity is an ordinary Home
Assistant fan though, so if you also expose your entities to Google Home or
Alexa it will appear there as a fan too, and asking either of them to turn that
fan off should stop the air conditioning in the same way.

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
Oscillate control. There is nothing missing and nothing to configure.

If you think one of your units has a vane but gets no Oscillate control, please
[raise an issue](https://github.com/andrew-blake/melcloudhome/issues).

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
