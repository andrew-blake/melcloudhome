# Using MELCloud Home with Apple HomeKit

How your air conditioning units appear in the Apple Home app, and the handful of
things about them that catch people out.

**Last Updated:** 2026-09-20

---

## What you will see

Each air conditioning unit gives you two tiles in the Home app. You add the
second of them to your bridge yourself; see the next section.

The thermostat tile is the one you already have. It carries the temperature and
the heating or cooling mode.

The fan tile is the new one. It carries the fan speed, the vane and the unit's
power. It takes its name from the unit, so a unit called Living Room gives you a
tile called "Living Room A-C fan".

Both tiles are the same air conditioner, so a change made on one shows up on the
other. Both show the last command Home Assistant sent, which is almost always
what the unit is doing. On the rare occasion a unit does not act on a command,
the tiles catch up when it next reports for itself, within about a minute.

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

I have only checked this through HomeKit. The entity is an ordinary Home
Assistant fan, so if you also expose your entities to Google Home or Alexa it
appears there as a fan too, and asking either of them to turn that fan off
should stop the air conditioning the same way. Alexa should also offer the speed
and the swing. Google Home offers the speed alone, because a Google fan has no
swing control.

If what you actually want is the unit running quietly, set the lowest speed and
leave the fan on.

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
percentage at the top of the page is the speed the unit will return to when you
switch back to Manual. It is not a live reading of the current speed. The Home
app has no way to show both, and it keeps your choice.

A unit that has been in Auto ever since Home Assistant first saw it has no last speed to keep,
and the Home app shows 100% instead. Nothing chose that figure. HomeKit treats zero as off, so
the bridge starts a fan's slider at a non-zero value and only replaces it once a numbered speed
has been seen; until then the 100% stands whatever the unit is doing. Choose a speed once and
the slider tracks your choice from then on.

Switching back to Manual returns the unit to the speed you last chose.

The speed the unit is genuinely running is in Home Assistant, in the **Actual
Fan Speed** sensor. That one does not reach HomeKit at all, so if you want to
watch the unit modulating in Auto, watch it there.

## Fan speed changes while the unit is off

Change the fan speed in Home Assistant while the air conditioner is off and the Home app keeps
showing the old speed. The change did happen: Home Assistant and the unit both have the new
speed, and the Home app catches up the moment you turn the unit on.

This comes from Home Assistant's HomeKit bridge, and no part of it is this integration's to
change. The bridge only sends a fan's speed to HomeKit while the fan is on, so with the unit off
the Home app keeps whatever speed it was last told. That displayed speed is simply out of date.
Turning the unit on applies the speed Home Assistant holds.

## Units that report no vane

Some units report no vane to the MELCloud Home service, and those get no
Oscillate control. There is nothing missing and nothing to configure.

If you think one of your units has a vane but gets no Oscillate control, please
[raise an issue](https://github.com/andrew-blake/melcloudhome/issues).

## Setting a mode and a temperature in one go

Changing a thermostat tile to, say, Heat at 21 sends Apple's two changes as two separate
commands to Home Assistant, a few microseconds apart. Those now leave as a single request to
MELCloud carrying both.

This matters because the unit can accept one command and quietly ignore a second that arrives
immediately behind it, which used to leave the tile and the unit disagreeing until the unit
reported for itself half a minute later. One request cannot lose half of itself.

The same applies to an automation that sets a mode and a temperature together, and to the hot
water tank's mode and temperature.

## Why the thermostat tile stays a plain thermostat

It would be tidier to have one tile with the temperature, the speed and the vane
all on it. Apple does have an accessory type that does exactly that, but a unit
only qualifies for it if its fan speeds carry Apple's own names, which would
mean renaming five numbered speeds onto low, medium and high. That would leave
three of your five speeds reachable, and it would break existing automations and
templates that refer to the current names.

A separate fan tile keeps every speed reachable and changes nothing you already
have. [ADR-025](decisions/025-homekit-fan-entity.md) records the full reasoning
for anyone who wants it.

## See also

- [Entity Reference](entities.md) for the fan entity and the Actual Fan Speed
  sensor as they appear inside Home Assistant
- [HomeKit Bridge documentation](https://www.home-assistant.io/integrations/homekit/)
  for bridge setup in general
