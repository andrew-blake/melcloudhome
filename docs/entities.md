# Entity Reference

Complete reference for all entities created by the MELCloud Home integration.

**Last Updated:** 2026-02-07

---

## Entity Naming Convention

All entities use **stable UUID-based entity IDs** to ensure automations never break when device names change.

**Entity ID Format:** `{domain}.melcloudhome_{short_id}_{entity_name}`

The `short_id` is derived from the MELCloud device UUID by taking the first 4 and last 4 characters (after removing hyphens).

**Example:** UUID `bf8d5119-abcd-1234-5678-9999abcd5119` → short ID `bf8d_5119`

**Device names** are automatically set to friendly names from your MELCloud Home account (e.g., "Living Room", "Bedroom") for easy identification in the UI.

**Note:** `entity_id` is set once, at first registration, and never recomputed. Entities registered before the #240 translation fix keep their original `entity_id` permanently; only entities registered for the first time after that fix get the corrected IDs shown below.

---

## Air-to-Air (ATA) Systems

For each air conditioning unit, the following entities are created:

### Climate Entity

- **Entity ID**: `climate.melcloudhome_{short_id}_climate`
- **Features**: Power on/off, temperature control, HVAC modes, fan speeds, swing modes
- **HVAC Action**: Real-time heating/cooling/idle status

### Sensors

- **Room Temperature**: `sensor.melcloudhome_{short_id}_room_temperature`
- **Outdoor Temperature**: `sensor.melcloudhome_{short_id}_outdoor_temperature` (if available)
- **WiFi Signal**: `sensor.melcloudhome_{short_id}_wifi_signal` (diagnostic)
- **Energy**: `sensor.melcloudhome_{short_id}_energy` (cumulative kWh)
- **Frost Protection Minimum/Maximum**: `sensor.melcloudhome_{short_id}_frost_protection_minimum` / `_maximum` (°C, diagnostic; created when the API reports the `frostProtection` object — every ATA unit does, as a server-side default, whether or not the mode has ever been configured)
- **Overheat Protection Minimum/Maximum**: `sensor.melcloudhome_{short_id}_overheat_protection_minimum` / `_maximum` (°C, diagnostic; only created once ever configured)
- **Holiday Mode Start/End Date**: `sensor.melcloudhome_{short_id}_holiday_mode_start` / `_end` (raw ISO string as returned by the API, not parsed into a timestamp device class; diagnostic, only created once ever configured). Live-tested twice: local wall-clock time passed through naively, not UTC — the building's own `timezone` field is not a reliable way to interpret it (see code comment in `sensor_ata.py`), so no conversion is attempted

### Binary Sensors

- **Error State**: `binary_sensor.melcloudhome_{short_id}_error_state`
  - Attribute `error_code`: device error code as reported by the API, `null` when no error. The API returns all settings values as strings, so a string is expected, but only the no-error case (empty string) has been observed so far — the exact format of active error codes is unconfirmed
- **Connection**: `binary_sensor.melcloudhome_{short_id}_connection_state`
- **Frost Protection**: `binary_sensor.melcloudhome_{short_id}_frost_protection` (created when the API reports the `frostProtection` object — every ATA unit does, as a server-side default, whether or not the mode has ever been configured)
  - Attribute `active`: currently engaging (e.g. room has crossed the threshold) — see the min/max sensors above for the configured band
- **Overheat Protection**: `binary_sensor.melcloudhome_{short_id}_overheat_protection` (only created once ever configured)
  - Attribute `active`
- **Holiday Mode**: `binary_sensor.melcloudhome_{short_id}_holiday_mode` (only created once ever configured)
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
  to detect stale data in automations

---

## Air-to-Water (ATW) Systems

For each heat pump system, the following entities are created:

### Climate Entity (Zone 1)

- **Entity ID**: `climate.melcloudhome_{short_id}_zone_1`
- **Features**: Zone 1 heating control, temperature setting (10-30°C), preset modes, HVAC modes

### Climate Entity (Zone 2)

- **Entity ID**: `climate.melcloudhome_{short_id}_zone_2` (if device supports Zone 2)
- **Features**: Same capabilities as Zone 1: HVAC modes, preset modes, temperature control (10-30°C)
- **Created automatically** when `hasZone2=true` in device capabilities

### Water Heater Entity (DHW Tank)

- **Entity ID**: `water_heater.melcloudhome_{short_id}_tank`
- **Features**: DHW tank temperature control (40-60°C), operation modes
- **Note**: Water heater reflects system power state but cannot control it (use switch for power)

### Switch Entity (System Power)

- **Entity ID**: `switch.melcloudhome_{short_id}_system_power`
- **Features**: System power control (primary power control point)
- **Note**: Climate OFF also controls system power (both delegate to same control method)

### Sensors

**Temperature Sensors:**

- **Zone 1 Temperature**: `sensor.melcloudhome_{short_id}_zone_1_temperature`
- **Zone 2 Temperature**: `sensor.melcloudhome_{short_id}_zone_2_temperature` (if device supports Zone 2)
- **Tank Temperature**: `sensor.melcloudhome_{short_id}_tank_temperature`
- **Outdoor Temperature**: `sensor.melcloudhome_{short_id}_outdoor_temperature`
  - Ambient temperature from the outdoor unit
  - Created for every ATW unit; shows `unknown` until a reading arrives. Sourced
    exclusively from the comfort-graph report, never the live polling response —
    that value can be silently wrong or absent with no way to tell from the
    value alone (issue #251)
  - Attribute `last_reading`: timestamp of when the unit actually recorded the
    value, for detecting stale data in automations (same pattern as ATA above)

**Operation Status:**

- **Operation Status**: `sensor.melcloudhome_{short_id}_operation_status`
  - Shows current 3-way valve position: "Stop", "HotWater", "HeatRoomTemperature", etc.

**Telemetry Sensors (Flow/Return Temperatures):**

- **Flow Temperature**: `sensor.melcloudhome_{short_id}_flow_temperature`
- **Return Temperature**: `sensor.melcloudhome_{short_id}_return_temperature`
- **Flow Temperature Zone 1**: `sensor.melcloudhome_{short_id}_flow_temperature_zone_1` (if device supports Zone 2)
- **Return Temperature Zone 1**: `sensor.melcloudhome_{short_id}_return_temperature_zone_1` (if device supports Zone 2)
- **Flow Temperature Zone 2**: `sensor.melcloudhome_{short_id}_flow_temperature_zone_2` (if device supports Zone 2)
- **Return Temperature Zone 2**: `sensor.melcloudhome_{short_id}_return_temperature_zone_2` (if device supports Zone 2)
- **Flow Temperature Boiler**: `sensor.melcloudhome_{short_id}_flow_temperature_boiler` (if device reports a boiler)
- **Return Temperature Boiler**: `sensor.melcloudhome_{short_id}_return_temperature_boiler` (if device reports a boiler)

The unsuffixed Flow and Return pair is created for every heat pump. The rest are gated on
capabilities, because MELCloud returns a constant 25 °C for measures the hardware doesn't
have rather than no data at all — so creating them unconditionally produced sensors that
looked like readings and never were.

The Zone 1 pair requires the device to have a **second** zone. On a single-zone system those
two measures return the placeholder rather than a reading, and the plain Flow Temperature and
Return Temperature are the zone 1 flow and return. The boiler pair requires the device to
report a boiler.

A gated sensor that does exist can still sit at `unknown` when a telemetry fetch returns no
datapoints for it. That is expected and separate from the gating above.

**Attribute `last_reading`** (all eight): the time the unit itself recorded the value. `null`
means no reading has arrived yet — the attribute is always present, so automations can rely on
the key existing. This endpoint fails often, and a failed poll leaves the sensor showing its
previous value, so `last_reading` is how you tell a fresh reading from an hours-old one.

Reading it together with the value tells you which of three things is happening:

| `last_reading` | value | meaning |
|---|---|---|
| advancing | unchanging | the reading itself is steady — a settled circuit, or MELCloud's constant 25 °C where the hardware is absent |
| stale | unchanging | the fetch is failing; the value you see is old |
| advancing | moving | healthy |

Because the attribute changes on every poll that brings a newer reading, these sensors now
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

**WiFi Signal Sensor:**

- **WiFi Signal (RSSI)**: `sensor.melcloudhome_{short_id}_wifi_signal` (diagnostic)
  - WiFi signal strength in dBm (values: -40 to -90, lower = weaker signal)
  - Update frequency: Every 60 minutes

**Energy Sensors (devices with energy capabilities):**

- **Energy Consumed**: `sensor.melcloudhome_{short_id}_energy_consumed`
  - Electrical energy consumed by heat pump (kWh)
  - Compatible with Home Assistant Energy Dashboard
- **Energy Produced**: `sensor.melcloudhome_{short_id}_energy_produced`
  - Thermal energy produced by heat pump (kWh)
- **COP (Coefficient of Performance)**: `sensor.melcloudhome_{short_id}_coefficient_of_performance`
  - Heat pump efficiency ratio (produced/consumed)
  - Typical values: 2.5-4.0 (higher is more efficient)
  - Update frequency: Every 30 minutes

**Availability:**
- **Energy Consumed sensor:** Created when device has `hasEstimatedEnergyConsumption=true` OR `hasMeasuredEnergyConsumption=true`
- **Energy Produced sensor:** Created when device has `hasEstimatedEnergyProduction=true` OR `hasMeasuredEnergyProduction=true`
- **Note:** Sensors are created independently. A device may have only one sensor if it has only one capability flag.
- See [ADR-016](decisions/016-implement-atw-energy-monitoring.md) for technical details.

### Binary Sensors

- **Error State**: `binary_sensor.melcloudhome_{short_id}_error_state`
  - Attribute `error_code`: device error code as reported by the API, `null` when no error. The API returns all settings values as strings, so a string is expected, but only the no-error case (empty string) has been observed so far — the exact format of active error codes is unconfirmed
- **Connection**: `binary_sensor.melcloudhome_{short_id}_connection_state`
- **Forced DHW Active**: `binary_sensor.melcloudhome_{short_id}_forced_dhw_active`

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

- **Real-time updates**: `binary_sensor.melcloud_home_real_time_updates` — diagnostic
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

## Entity ID Recreation Warning

⚠️ **If you delete entities and use the "Recreate entity IDs" option**, Home Assistant will regenerate entity IDs based on the friendly device name instead of the stable UUID. This will change entity IDs from `climate.melcloudhome_bf8d_5119_climate` to `climate.living_room_climate`, breaking existing automations.

**To preserve entity IDs:** Don't delete entities unless necessary. If you need to reset, delete and re-add the integration instead.
