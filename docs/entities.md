# Entity Reference

Complete reference for all entities created by the MELCloud Home integration.

**Last Updated:** 2026-11-24

---

## Entity Names and IDs

Each unit is a device. New devices are named after the unit in your MELCloud Home account, for example "Living Room AC". Devices added by earlier versions keep their name, your label and their area.

Home Assistant shows each entity's name after the device name. The fan, the heat pump zones, the tank and the system power switch have names in the install's language; the English names are listed here.

Home Assistant builds each new entity ID from the area, the device name and the entity name, following your entity ID setting. The integration doesn't promise an ID format, and existing entity IDs never change. To find a unit's entities, open its device page.

A fresh install with no areas gets IDs such as:

| Entity                    | Example ID                                             |
| ------------------------- | ------------------------------------------------------ |
| Air conditioner (climate) | `climate.living_room_ac`                               |
| A/C fan                   | `fan.living_room_ac_a_c_fan`                           |
| Heat pump Zone 1, Zone 2  | `climate.heat_pump_zone_1`, `climate.heat_pump_zone_2` |
| Tank                      | `water_heater.heat_pump_tank`                          |
| System power              | `switch.heat_pump_system_power`                        |

If two units in different buildings share a name, the second unit's IDs get a `_2` suffix; rename one of them to tell them apart.

### A unit named after its room

Units are often named after their room. On Home Assistant 2026.11, giving such a device the area of the same name in the setup dialog repeats the room in its entity IDs: a unit called "Living Room" in the area Living Room gets `climate.living_room_living_room`. The names shown on dashboards don't repeat it. Home Assistant's own MELCloud Home integration names devices the same way and gives the same IDs.

To get IDs without the repeat, use any of these:

- **In the setup dialog:** rename the device as you pick its area, for example to "Air conditioner". Its IDs become `climate.living_room_air_conditioner` and `fan.living_room_air_conditioner_a_c_fan`.
- **Later, on the device page:** rename the device and set its area, then open ⋮ → **Recreate entity IDs**. Renaming alone keeps the old IDs. Home Assistant warns that automations using the old IDs need updating.
- **One entity at a time:** edit the entity ID in the entity's settings, for example to `climate.living_room`.

**Serial number:** each device's serial number is its short ID, `melcloudhome_` followed by the first 4 and last 4 characters of the unit's UUID with the hyphens removed. For example, UUID `bf8d5119-abcd-1234-5678-9999abcd5119` gives `melcloudhome_bf8d_5119`. Installs set up by earlier versions have the same text in their entity IDs, so the serial number matches a device to them.

---

## Air-to-Air (ATA) Systems

For each air conditioning unit, the following entities are created:

### Climate Entity

- **Name**: none of its own; it shows the device's name
- **Area**: on Home Assistant 2026.11 or later, an area set on this entity without a name of its own raises a repair. Move the area to the device or give the entity a name.
- **Features**: Power on/off, temperature control, HVAC modes, fan speeds, swing modes
- **HVAC Action**: Heating/cooling/idle, inferred from room temperature against the setpoint (the API reports no heating or cooling state). A unit can keep heating at or above its setpoint, or cooling at or below it, and reads idle while it does.

### Fan Entity

- **Name**: A/C fan (translated on non-English installs)
- **Created when**: The unit reports `number_of_fan_speeds` of 1 or more

Carries fan speed as a percentage, the vertical vane as oscillation, and unit
power. It exists because Home Assistant's HomeKit bridge cannot expose either
control from the climate entity; see ADR-025.

Fan speed is settable from both this entity and the climate entity's fan mode
dropdown. Both control the same unit and read one coordinator field.

Turning this entity off powers the air conditioner down, because an air
conditioner has no "fan off, unit running" state. The same should apply anywhere
else the entity is exposed, such as Google Home or Alexa, though only HomeKit
has been tested.

Oscillation is only offered on units that report a vane, so a unit with neither
swing nor air direction gets the speed slider and power without it.

Under `auto` the percentage keeps the last speed you chose and the unit picks
its own, so the speed it is actually running is in the Actual Fan Speed sensor
below.

**Using this in Apple Home?** See [the HomeKit guide](homekit.md), which covers
adding the fan to your bridge, what the tile does, and the behaviour that
surprises people.

### Sensors

- **Room temperature**
- **Actual fan speed** (`off`, `one`…`five`, never `auto`) — the speed the unit is running, as opposed to the climate entity's `fan_mode`, which is the requested one. Under `Auto` this is the only place the running speed is visible. Reported by the indoor unit, so it can be a few minutes behind after switching on or off, and it follows the fan rather than the compressor — a low speed does not mean cooling has stopped
- **Outdoor temperature**
- **WiFi signal** (diagnostic, dBm, polled every 30 minutes, with a `last_reading` attribute; see the WiFi Signal Sensor section below)
- **Energy** (cumulative kWh)
- **Frost protection minimum / maximum** (°C, diagnostic; created when the API reports the `frostProtection` object — every ATA unit does, as a server-side default, whether or not the mode has ever been configured)
- **Overheat protection minimum / maximum** (°C, diagnostic; only created once ever configured)
- **Holiday mode start / end** (raw ISO string as returned by the API, not parsed into a timestamp device class; diagnostic, only created once ever configured). Live-tested twice: local wall-clock time passed through naively, not UTC — the building's own `timezone` field is not a reliable way to interpret it (see code comment in `sensor_ata.py`), so no conversion is attempted

### Binary Sensors

- **Error state**
  - Attribute `error_code`: device error code as reported by the API, `null` when no error. The API returns all settings values as strings, so a string is expected, but only the no-error case (empty string) has been observed so far — the exact format of active error codes is unconfirmed
- **Connection state**
- **Frost protection** (created when the API reports the `frostProtection` object — every ATA unit does, as a server-side default, whether or not the mode has ever been configured)
  - Attribute `active`: currently engaging (e.g. room has crossed the threshold) — see the min/max sensors above for the configured band
- **Overheat protection** (only created once ever configured)
  - Attribute `active`
- **Holiday mode** (only created once ever configured)
  - Attribute `active` — see the start/end date sensors above for the configured window

All three reflect state read from the API only — the state is `on` when the mode is armed/configured (`enabled`), not only when it's currently engaging (`active`, exposed as an attribute); read-only, no control exposed yet.

**Why read-only:** the API endpoints that actually enable/disable these modes (`POST /api/holidaymode`, `POST /api/protection/frost`, `POST /api/protection/overheat`) live on a different host (the web BFF, `melcloudhome.com`) than the mobile BFF this integration talks to for everything else, and this integration's architecture deliberately dropped web-BFF support (see [ADR-017](decisions/017-migrate-to-mobile-bff.md)) after it caused an outage. Whether/how to reach those endpoints safely from the mobile side is still being investigated (a GET probe against `/monitor/holidaymode` on the mobile BFF returned `405 Method Not Allowed` with `Allow: POST`, suggesting the route exists there too — reported but not backed by a saved artifact, see the evidence note under [Holiday Mode](api/ata-api-reference.md#holiday-mode); frost/overheat protection's mobile equivalents were not found after extensive testing). Until that's resolved, these entities only surface what the API already reports on every regular poll — no new write path, no new risk to the unit.

These modes are configured by the account's **primary owner** — guest accounts don't see the settings in either the web or mobile app (a guest-account integration still reads their state). Entities are created once, at integration setup: a mode configured for the first time won't appear in HA until the integration is reloaded. Once a mode has ever been configured its entities persist — removing a device from the mode turns the binary sensor `off` rather than removing anything.

### ATA Control Options

**Supported HVAC Modes:**

- **Off**: Unit powered off
- **Heat**: Heating mode
- **Cool**: Cooling mode
- **Dry**: Dehumidification mode
- **Fan Only**: Fan only (no heating/cooling)
- **Auto**: Automatic mode

**Fan Speeds:**

- Auto
- Level 1 (Quiet)
- Level 2 (Low)
- Level 3 (Medium)
- Level 4 (High)
- Level 5 (Very High)

**Swing Modes (Vertical):**

- Auto, Swing, One (Top), Two, Three (Middle), Four, Five (Bottom)

**Swing Modes (Horizontal):**

- Auto, Swing, Left, LeftCentre, Centre, RightCentre, Right

### ATA Energy Dashboard Integration

Energy consumption sensors are compatible with Home Assistant's Energy Dashboard:

1. Go to **Settings** → **Dashboards** → **Energy**
2. Add your devices under "Individual devices"
3. Select the energy sensor for each unit
4. Energy data accumulates over time and persists across restarts (see [Setup Lifecycle](architecture.md#setup-lifecycle-fresh-install-vs-restart) for how a fresh install differs — the first poll seeds a baseline rather than counting as consumption)

**Outdoor Temperature Sensor (ATA):**

- Created for every ATA unit; shows `unknown` until a reading arrives (and permanently for units that never report outdoor temperature)
- Updates every 30 minutes
- Shows ambient temperature from outdoor unit
- Useful for efficiency monitoring and automations
- Attribute `last_reading`: timestamp of when the unit actually recorded the value.
  Units stop uploading outdoor temperature while idle, so the value can lag hours
  behind (MELCloud server-side behavior, see issues #152/#171) — use this attribute
  to detect stale data in automations. A unit can hold the same reading for many
  hours while every poll succeeds, so an unchanging value does not by itself mean
  anything is wrong
- Because that attribute changes whenever a fresher reading arrives, these sensors
  register a state change on those polls even when the temperature is identical.
  Automations triggering on state changes will fire then; trigger on the value with
  a `to`/`from` or a template condition if that matters

---

## Air-to-Water (ATW) Systems

For each heat pump system, the following entities are created:

### Climate Entity (Zone 1)

- **Name**: Zone 1
- **Features**: Zone 1 heating control, temperature setting (10-30°C), preset modes, HVAC modes

### Climate Entity (Zone 2)

- **Name**: Zone 2 (if device supports Zone 2)
- **Features**: Same capabilities as Zone 1: HVAC modes, preset modes, temperature control (10-30°C)
- **Created automatically** when `hasZone2=true` in device capabilities

### Water Heater Entity (DHW Tank)

- **Name**: Tank
- **Features**: DHW tank temperature control (40-60°C), operation modes
- **Note**: Water heater reflects system power state but cannot control it (use switch for power)

### Switch Entity (System Power)

- **Name**: System power
- **Features**: System power control (primary power control point)
- **Note**: Climate OFF also controls system power (both delegate to same control method)

### Sensors

**Temperature Sensors:**

- **Zone 1 temperature**
- **Zone 2 temperature** (if device supports Zone 2)
- **Tank temperature**
- **Outdoor temperature**
  - Ambient temperature from the outdoor unit
  - Created for every ATW unit; shows `unknown` until a reading arrives. Sourced
    exclusively from the comfort-graph report, never the live polling response —
    that value can be silently wrong or absent with no way to tell from the
    value alone (issue #251)
  - Attribute `last_reading`: timestamp of when the unit actually recorded the
    value, for detecting stale data in automations (same pattern as ATA above)

**Operation Status:**

- **Operation status**
  - Shows current 3-way valve position: "Stop", "HotWater", "HeatRoomTemperature", etc.

**Telemetry Sensors (Flow/Return Temperatures):**

- **Flow temperature**
- **Return temperature**
- **Flow temperature zone 1** (if device supports Zone 2)
- **Return temperature zone 1** (if device supports Zone 2)
- **Flow temperature zone 2** (if device supports Zone 2)
- **Return temperature zone 2** (if device supports Zone 2)
- **Flow temperature boiler** (if device reports a boiler)
- **Return temperature boiler** (if device reports a boiler)

The unsuffixed Flow and Return pair is created for every heat pump. The rest are gated on
capabilities, because MELCloud still sends a series for measures the hardware doesn't have —
sometimes empty, sometimes a constant 25 °C, both observed — so creating them unconditionally
produced sensors that looked like readings and never were.

The Zone 1 pair requires the device to have a **second** zone. On a single-zone system those
two measures carry no genuine reading, and the plain Flow Temperature and Return Temperature
are the zone 1 flow and return. The boiler pair requires the device to
report a boiler.

A gated sensor that does exist can still sit at `unknown` when a telemetry fetch returns no
datapoints for it. That is expected and separate from the gating above.

**Attribute `last_reading`** (all eight): the time the unit itself recorded the value. `null`
means no reading has arrived yet — the attribute is always present, so automations can rely on
the key existing. This endpoint fails often, and a failed poll leaves the sensor showing its
previous value, so `last_reading` is how you tell a fresh reading from an hours-old one.

Reading it together with the value tells you which of three things is happening:

| `last_reading` | value      | meaning                                                                                                     |
| -------------- | ---------- | ----------------------------------------------------------------------------------------------------------- |
| advancing      | unchanging | the reading itself is steady — a settled circuit, or MELCloud's constant 25 °C where the hardware is absent |
| stale          | unchanging | the fetch is failing; the value you see is old                                                              |
| advancing      | moving     | healthy                                                                                                     |

Because the attribute changes on every poll that brings a newer reading, these sensors
register a state change each time — even when the value is identical. Automations that trigger
on state changes of these entities will fire on those polls; trigger on the value with a
`to`/`from` or a template condition if that matters.

**Purpose:** Monitor heating system efficiency and performance

- Flow vs return delta indicates heat transfer efficiency
- Zone-specific temps show per-loop performance on multi-zone systems
- Boiler temps present only when the device reports a boiler

**Update frequency:** Every 60 minutes (sensor state updated with latest API value)
**Data density:** 10-15 datapoints per hour during active heating (sparse when idle)
**Statistics:** HA auto-creates statistics and history graphs automatically

**Note:** Boiler temps are not created at all unless the device reports a boiler. They used
to be created for every heat pump, where they read a constant 25 °C on devices without one.

**WiFi Signal Sensor (air conditioners and heat pumps):**

- **WiFi signal** (diagnostic)
  - Signal strength in dBm (roughly -30 to -90; lower is weaker)
  - Update frequency: every 30 minutes
  - `last_reading`: the time the unit itself recorded the value. Some units upload a new value every few minutes. Others upload only when the value changes, and on those a steady signal can leave `last_reading` hours old while everything is working. The integration's diagnostics download shows `wifi_signal_last_poll_at` and `wifi_signal_last_error`: a recent poll with no error means the unit is quiet, and an error means the fetch is failing.
  - A failed or empty fetch leaves the previous value in place.
  - Each newer `last_reading` registers a state change even when the value is the same, as for the water-temperature sensors above. Automations that trigger on this entity's state changes fire on those polls.

**Energy Sensors (devices with energy capabilities):**

- **Energy consumed**
  - Electrical energy consumed by heat pump (kWh)
  - Compatible with Home Assistant Energy Dashboard
- **Energy produced**
  - Thermal energy produced by heat pump (kWh)
- **Coefficient of performance**
  - Heat pump efficiency ratio (produced/consumed)
  - Typical values: 2.5-4.0 (higher is more efficient)
  - Update frequency: Every 30 minutes

**Availability:**

- **Energy Consumed sensor:** Created when device has `hasEstimatedEnergyConsumption=true` OR `hasMeasuredEnergyConsumption=true`
- **Energy Produced sensor:** Created when device has `hasEstimatedEnergyProduction=true` OR `hasMeasuredEnergyProduction=true`
- **Note:** Sensors are created independently. A device may have only one sensor if it has only one capability flag.
- See [ADR-016](decisions/016-implement-atw-energy-monitoring.md) for technical details.

### Binary Sensors

- **Error state**
  - Attribute `error_code`: device error code as reported by the API, `null` when no error. The API returns all settings values as strings, so a string is expected, but only the no-error case (empty string) has been observed so far — the exact format of active error codes is unconfirmed
- **Connection state**
- **Forced DHW active**

### ATW Control Options

**Supported HVAC Modes:**

- **OFF**: System powered off
- **HEAT**: Zone 1 heating enabled (system on)
- **COOL**: Zone 1 cooling enabled (only on devices with cooling capability)

**Heating Preset Modes:**

- **Room** (Recommended) - Maintains room at target temperature (like a thermostat)
- **Flow** (Advanced) - Directly controls heating water temperature
- **Curve** (Advanced) - Auto-adjusts based on outdoor temperature

**Cooling Preset Modes** (devices with cooling capability):

- **Cool Room** - Cools to target room temperature
- **Cool Flow** - Direct flow temperature control for cooling

**Most users should use Room/Cool Room modes** for standard residential heating/cooling

**Note:** Cooling availability depends on device capabilities (`hasCoolingMode=true`). When switching between heating and cooling, system automatically adjusts available presets. Curve mode not available for cooling (fallback to room temperature control).

**Water Heater Operation Modes:**

- **Eco** - Energy efficient balanced operation (auto DHW heating when needed)
- **High demand** - Priority mode for faster DHW heating (suspends zone heating)

> **Note:** These use Home Assistant's standard water heater modes. The MELCloud app calls these "Auto" and "Force DHW" respectively.

**Temperature Ranges:**

- Zone 1: 10-30°C
- DHW Tank: 40-60°C

---

## Account-Level Entities

One per MELCloud Home account (config entry), attached to a "MELCloud Home" service device:

- **Real-time updates**: diagnostic
  connectivity sensor reporting whether the real-time WebSocket connection is up
  (`on` = connected). The `last_delta_at` attribute holds the timestamp of the last
  push update received. Only created when real-time updates are enabled (the default);
  polling continues either way, so a disconnected socket means slower updates, not
  missing data. Not created when real-time updates are switched off in the
  integration options.

---

## Understanding ATW Operation (3-Way Valve)

Your heat pump uses a 3-way valve that can only heat ONE target at a time (zones OR DHW tank, never both). This affects what you'll see in Home Assistant.

For complete operational details and state diagram, see [docs/architecture.md](architecture.md#atw-3-way-valve-behavior).

---

## Recreating Entity IDs

The "Recreate entity IDs" option (↻) proposes Home Assistant's own ID for each entity, built from the current device name and label. A recreated ID can differ from the old one, so update any automation that uses it.

Re-adding the integration restores a deleted device's label, area and entity IDs. The device's own name becomes the unit name.
