# Using MELCloud Home with Apple HomeKit

How your air conditioning units appear in the Apple Home app, and the handful of
things about them that catch people out.

**Last Updated:** 2026-09-20

---

## What you will see

Each air conditioning unit gives you two tiles in the Home app.

The thermostat tile is the one you already have. It carries the temperature and
the heating or cooling mode.

The fan tile is the new one. It carries the fan speed, the vane and the unit's
power.

Both tiles are the same air conditioner, so a change made on one shows up on the
other.

The fan tile takes its name from the unit, so a unit called Living Room gives
you a tile called "Living Room A-C fan". Inside Home Assistant the same entity
is called **A/C fan**. The bridge swaps the slash for a hyphen on its way to
HomeKit, which is why there are two spellings.

One exception: a unit that reports no fan speeds gets no fan tile. Heat pumps are
not affected by any of this and never had one.

## Getting the fan tile

**Most people need to do nothing.** The bridge builds its list of accessories
when it starts, so restart Home Assistant and look for the new tile. It arrives
in whichever room the Home app chooses by default, so you may want to move it.

### If the tile does not appear

Your bridge is probably set to expose named entities one by one, so it needs
telling about the new one.

Go to **Settings**, then **Devices & Services**, then **HomeKit Bridge**, and
open the options for your bridge entry. The entry carries the bridge's own name,
so it reads something like "HASS Bridge:21064".

On the first screen, leave HomeKit mode on **bridge** and make sure **Domains to
include** lists **Fan** alongside **Climate**. Without it no fan reaches HomeKit,
whichever Inclusion mode you use. Note which Inclusion mode is selected, because
it decides what the next screen means.

The next screen is one of two:

- **Select the entities to be included.** Tick the **A/C fan** entities you
  want.
- **Select the entities to be excluded.** Leave your A/C fans **unticked**.
  Ticking one here is what keeps it out of HomeKit.

If **Advanced Mode** is on in your Home Assistant profile there is one more
screen, offering programmable switches for device triggers. Leave it empty
unless you want them.

Saving reloads the bridge, so the tile appears without restarting Home
Assistant, and the tiles you already had keep their names and rooms.

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
setting applies the next time it runs.

Switching Oscillate off returns the vane to Auto, which is a fixed angle the
unit chooses to suit what it is doing. It does not go back to a numbered vane
position you might have set in Home Assistant earlier.

## Auto fan speed

Fan Mode has two settings. On **Manual** you choose the speed. On **Auto** the
unit chooses it, and will change it by itself as the room warms or cools.

While you are in Auto, the speed slider keeps the last speed you chose. So the
percentage at the top of the page is the speed the unit will return to when you
switch back to Manual. It is not a live reading of the current speed, and the
Home app has no way to show both.

A unit that has been in Auto ever since Home Assistant first saw it has no last speed to keep,
and the Home app shows 100% instead. Nothing chose that figure. HomeKit treats zero as off, so
the bridge starts a fan's slider at a non-zero value and only replaces it once a numbered speed
has been seen; until then the 100% stands whatever the unit is doing. Choose a speed once and
the slider tracks your choice from then on.

Switching back to Manual returns the unit to the speed you last chose.

The speed the unit is genuinely running is in Home Assistant, in the **Actual
Fan Speed** sensor. That one does not reach HomeKit at all, so if you want to
watch the unit modulating in Auto, watch it there.

## Units that report no vane

Some units report no vane to the MELCloud Home service, and those get no
Oscillate control. There is nothing missing and nothing to configure.

If you think one of your units has a vane but gets no Oscillate control, please
[raise an issue](https://github.com/andrew-blake/melcloudhome/issues).

## See also

- [Entity Reference](entities.md) for the fan entity and the Actual Fan Speed
  sensor as they appear inside Home Assistant
- [HomeKit Bridge documentation](https://www.home-assistant.io/integrations/homekit/)
  for bridge setup in general
- [ADR-025](decisions/025-homekit-fan-entity.md) for why the controls arrive on
  a separate fan tile
