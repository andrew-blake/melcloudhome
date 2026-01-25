# Entity Reference

Complete reference for all entities created by the MELCloud Home integration.

**Last Updated:** 2026-01-24

---

## Entity Naming Convention

All entities use **stable UUID-based entity IDs** to ensure automations never break when device names change.

**Entity ID Format:** `{domain}.melcloudhome_{short_id}_{entity_name}`

The `short_id` is derived from the MELCloud device UUID by taking the first 4 and last 4 characters (after removing hyphens).

**Example:** UUID `bf8d5119-abcd-1234-5678-9999abcd5119` → short ID `bf8d_5119`

**Device names** are automatically set to friendly names from your MELCloud Home account (e.g., "Living Room", "Bedroom") for easy identification in the UI.

---

## Air-to-Air (ATA) Systems

For each air conditioning unit, the following entities are created:

### Climate Entity

- **Entity ID**: `climate.melcloudhome_{short_id}_climate`
- **Features**: Power on/off, temperature control, HVAC modes, fan speeds, swing modes
- **HVAC Action**: Real-time heating/cooling/idle status

### Sensors

- **Room Temperature**: `sensor.melcloudhome_{short_id}_room_temperature`
- **WiFi Signal**: `sensor.melcloudhome_{short_id}_wifi_signal` (diagnostic)
- **Energy**: `sensor.melcloudhome_{short_id}_energy` (cumulative kWh)

### Binary Sensors

- **Error State**: `binary_sensor.melcloudhome_{short_id}_error_state`
- **Connection**: `binary_sensor.melcloudhome_{short_id}_connection_state`

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
4. Energy data accumulates over time and persists across restarts

---

## Air-to-Water (ATW) Systems

For each heat pump system, the following entities are created:

### Climate Entity (Zone 1)

- **Entity ID**: `climate.melcloudhome_{short_id}_zone_1`
- **Features**: Zone 1 heating control, temperature setting (10-30°C), preset modes, HVAC modes

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
- **Tank Temperature**: `sensor.melcloudhome_{short_id}_tank_temperature`

**Operation Status:**

- **Operation Status**: `sensor.melcloudhome_{short_id}_operation_status`
  - Shows current 3-way valve position: "Stop", "HotWater", "HeatRoomTemperature", etc.

**Telemetry Sensors (Flow/Return Temperatures):**

- **Flow Temperature**: `sensor.melcloudhome_{short_id}_flow_temperature`
- **Return Temperature**: `sensor.melcloudhome_{short_id}_return_temperature`
- **Flow Temperature Zone 1**: `sensor.melcloudhome_{short_id}_flow_temperature_zone1`
- **Return Temperature Zone 1**: `sensor.melcloudhome_{short_id}_return_temperature_zone1`
- **Flow Temperature Boiler**: `sensor.melcloudhome_{short_id}_flow_temperature_boiler`
- **Return Temperature Boiler**: `sensor.melcloudhome_{short_id}_return_temperature_boiler`

**Purpose:** Monitor heating system efficiency and performance

- Flow vs return delta indicates heat transfer efficiency
- Zone-specific temps show heating loop performance
- Boiler temps available if external boiler present

**Update frequency:** Every 60 minutes (sensor state updated with latest API value)
**Data density:** 10-15 datapoints per hour during active heating (sparse when idle)
**Statistics:** HA auto-creates statistics and history graphs automatically

**Note:** Boiler temps may show "unavailable" if no external boiler present (normal behavior)

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
- **COP (Coefficient of Performance)**: `sensor.melcloudhome_{short_id}_cop`
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

**Most users should use Room/Cool Room modes** - they're the most intuitive

**Note:** Cooling availability depends on device capabilities (`hasCoolingMode=true`). When switching between heating and cooling, system automatically adjusts available presets. Curve mode not available for cooling (fallback to room temperature control).

**Water Heater Operation Modes:**

- **Eco** - Energy efficient balanced operation (auto DHW heating when needed)
- **High demand** - Priority mode for faster DHW heating (suspends zone heating)

> **Note:** These use Home Assistant's standard water heater modes. The MELCloud app calls these "Auto" and "Force DHW" respectively.

**Temperature Ranges:**

- Zone 1: 10-30°C
- DHW Tank: 40-60°C

---

## Understanding ATW Operation (3-Way Valve)

Your heat pump uses a 3-way valve that can only heat ONE target at a time (zones OR DHW tank, never both). This affects what you'll see in Home Assistant.

For complete operational details and state diagram, see [docs/architecture.md](architecture.md#atw-3-way-valve-behavior).

---

## Entity ID Recreation Warning

⚠️ **If you delete entities and use the "Recreate entity IDs" option**, Home Assistant will regenerate entity IDs based on the friendly device name instead of the stable UUID. This will change entity IDs from `climate.melcloudhome_bf8d_5119_climate` to `climate.living_room_climate`, breaking existing automations.

**To preserve entity IDs:** Don't delete entities unless necessary. If you need to reset, delete and re-add the integration instead.
