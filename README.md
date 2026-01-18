# MELCloud Home

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub Release](https://img.shields.io/github/release/andrew-blake/melcloudhome.svg)](https://github.com/andrew-blake/melcloudhome/releases)
![License](https://img.shields.io/github/license/andrew-blake/melcloudhome.svg)
[![Test](https://github.com/andrew-blake/melcloudhome/workflows/Test/badge.svg)](https://github.com/andrew-blake/melcloudhome/actions/workflows/test.yml)
[![codecov](https://codecov.io/gh/andrew-blake/melcloudhome/graph/badge.svg?token=WW97CHORNS)](https://codecov.io/gh/andrew-blake/melcloudhome)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
![Python Version from PEP 621 TOML](https://img.shields.io/python/required-version-toml?tomlFilePath=https%3A%2F%2Fraw.githubusercontent.com%2Fandrew-blake%2Fmelcloudhome%2Fmain%2Fpyproject.toml)


Home Assistant custom integration for **MELCloud Home**.

## Features

### Air-to-Air (ATA) Systems

- **HVAC Control**: Power, temperature, mode (heat/cool/dry/fan/auto), fan speed, and swing modes
- **Energy Monitoring**: Track cumulative energy consumption with persistent storage
- **Sensors**:
  - Room temperature
  - WiFi signal strength
  - Energy consumption
  - Error state monitoring
  - Connection status
- **Real-time Status**: HVAC action feedback (heating/cooling/idle/off)
- **Independent Vane Control**: Both vertical and horizontal swing modes
- **Automatic Updates**: 60-second polling for climate/sensors, 30-minute polling for energy data
- **Diagnostics Support**: Export integration diagnostics for troubleshooting

### Air-to-Water (ATW) Heat Pumps

**Platforms Implemented:**

- **Climate** (Zone 1): Temperature control (10-30°C), preset modes (Room/Flow/Curve), HVAC modes (OFF/HEAT/COOL*)
- **Water Heater** (DHW Tank): Temperature control (40-60°C), operation modes (Eco/High demand)
- **Switch** (System Power): System on/off control (primary power control point)
- **Sensors**: Zone 1 temperature, tank temperature, operation status, WiFi signal (RSSI), 6 telemetry sensors (flow/return temps), energy monitoring*
- **Binary Sensors**: Error state, connection state, forced DHW mode active

**Capability-Based Features:**

- **Energy Monitoring**: Available on devices with `hasEstimatedEnergyConsumption` and `hasEstimatedEnergyProduction` capabilities
  - Sensors: Energy consumed (kWh), energy produced (kWh), COP (efficiency ratio)
  - Compatible with Home Assistant Energy Dashboard
  - Example controllers: ERSC-VM2D ✅, EHSCVM2D ❌
- **Cooling Mode**: Available on devices with `hasCoolingMode` capability
  - 2 cooling preset modes: Cool Room, Cool Flow
  - Example controllers: ERSC-VM2D ✅, EHSCVM2D ❌

*Feature availability auto-detected from device capabilities - see [ADR-016](docs/decisions/016-implement-atw-energy-monitoring.md) for technical details

## Requirements

- Home Assistant 2024.11.0 or newer
- MELCloud Home account with configured devices
- Internet connection for cloud API access

## Supported Devices

### Air-to-Air (ATA) - Air Conditioning Units

This integration supports Mitsubishi Electric air conditioning units connected via **MELCloud Home** WiFi adapters.

**Compatible WiFi Adapters:** MAC-597, MAC-577, MAC-567, MAC-587 (all confirmed working)

**Example Indoor Units:** MSZ-AY25VGK2, MSZ-LN35VG2B, MSZ-LN25VGWRAC, and others

> **Note:** If your system uses the classic **MELCloud** app (not MELCloud Home), use the official Home Assistant MELCloud integration instead.

For the complete list of tested hardware, technical notes, and compatibility details, see [SUPPORTED_DEVICES.md](SUPPORTED_DEVICES.md).

### Air-to-Water (ATW) - Heat Pumps

- **Status:** Production-ready (tested on real hardware)
- **Supported systems:** Mitsubishi Electric Ecodan heat pumps with FTC controllers
- **Tested controllers:** ERSC-VM2D (full features), EHSCVM2D (heating-only)
- **Core features:** Zone 1 heating, DHW control, 3-way valve systems, telemetry sensors
- **Optional features:** Energy monitoring (capability-based), cooling mode (capability-based)

*Feature availability auto-detected from device capabilities - see capability-based features above

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click on "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add repository URL: `https://github.com/andrew-blake/melcloudhome`
6. Select category: "Integration"
7. Click "Add"
8. Find "MELCloud Home" in HACS and click "Download"
9. Restart Home Assistant

### Manual Installation

1. Download the latest release from [GitHub](https://github.com/andrew-blake/melcloudhome/releases)
2. Extract the `melcloudhome` folder to your `custom_components` directory
3. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for "MELCloud Home"
4. Enter your MELCloud Home credentials (email and password)
5. Click **Submit**

Your devices will be automatically discovered and added.

## Important Notes

### Device and Entity Names

This integration uses **stable UUID-based entity IDs** to ensure your automations never break when device names change.

**Entity ID Format:** `{domain}.melcloudhome_{short_id}` or `{domain}.melcloudhome_{short_id}_{entity_name}`

The `short_id` is derived from the MELCloud device UUID by taking the first 4 and last 4 characters (after removing hyphens).

**Example:** UUID `bf8d5119-abcd-1234-5678-9999abcd5119` → short ID `bf8d_5119`

**Entity ID Examples:**

- ATA climate: `climate.melcloudhome_bf8d_5119_climate`
- ATW zone climate: `climate.melcloudhome_bf8d_5119_zone_1`
- ATW water heater: `water_heater.melcloudhome_bf8d_5119_tank`
- ATW tank sensor: `sensor.melcloudhome_bf8d_5119_tank_temperature`

**Device names** are automatically set to friendly names from your MELCloud Home account (e.g., "Living Room", "Bedroom") for easy identification in the UI.

**⚠️ Entity ID Recreation Warning:**

- If you delete entities and use the **"Recreate entity IDs"** option, Home Assistant will regenerate entity IDs based on the friendly device name instead of the stable UUID
- This will change entity IDs from `climate.melcloudhome_bf8d_5119_climate` to `climate.living_room_climate`, breaking existing automations
- **To preserve entity IDs:** Don't delete entities unless necessary. If you need to reset, delete and re-add the integration instead.

## Entities Created

### Air-to-Air (ATA) Systems

For each air conditioning unit, the following entities are created:

#### Climate Entity

- **Entity ID**: `climate.melcloudhome_{short_id}_climate`
  - Example: `climate.melcloudhome_bf8d_5119_climate`
- **Features**: Power on/off, temperature control, HVAC modes, fan speeds, swing modes
- **HVAC Action**: Real-time heating/cooling/idle status

#### Sensors

- **Room Temperature**: `sensor.melcloudhome_{short_id}_room_temperature`
  - Example: `sensor.melcloudhome_bf8d_5119_room_temperature`
- **WiFi Signal**: `sensor.melcloudhome_{short_id}_wifi_signal` (diagnostic)
  - Example: `sensor.melcloudhome_bf8d_5119_wifi_signal`
- **Energy**: `sensor.melcloudhome_{short_id}_energy` (cumulative kWh)
  - Example: `sensor.melcloudhome_bf8d_5119_energy`

#### Binary Sensors

- **Error State**: `binary_sensor.melcloudhome_{short_id}_error_state`
  - Example: `binary_sensor.melcloudhome_bf8d_5119_error_state`
- **Connection**: `binary_sensor.melcloudhome_{short_id}_connection_state`
  - Example: `binary_sensor.melcloudhome_bf8d_5119_connection_state`

#### ATA Control Options

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

#### ATA Energy Dashboard Integration

Energy consumption sensors are compatible with Home Assistant's Energy Dashboard:

1. Go to **Settings** → **Dashboards** → **Energy**
2. Add your devices under "Individual devices"
3. Select the energy sensor for each unit
4. Energy data accumulates over time and persists across restarts

### Air-to-Water (ATW) Systems

For each heat pump system, the following entities are created:

#### Climate Entity (Zone 1)

- **Entity ID**: `climate.melcloudhome_{short_id}_zone_1`
  - Example: `climate.melcloudhome_bf8d_5119_zone_1`
- **Features**: Zone 1 heating control, temperature setting (10-30°C), preset modes, HVAC modes

#### Water Heater Entity (DHW Tank)

- **Entity ID**: `water_heater.melcloudhome_{short_id}_tank`
  - Example: `water_heater.melcloudhome_bf8d_5119_tank`
- **Features**: DHW tank temperature control (40-60°C), operation modes
- **Note**: Water heater reflects system power state but cannot control it (use switch for power)

#### Switch Entity (System Power)

- **Entity ID**: `switch.melcloudhome_{short_id}_system_power`
  - Example: `switch.melcloudhome_bf8d_5119_system_power`
- **Features**: System power control (primary power control point)
- **Note**: Climate OFF also controls system power (both delegate to same control method)

#### Sensors

- **Zone 1 Temperature**: `sensor.melcloudhome_{short_id}_zone_1_temperature`
  - Example: `sensor.melcloudhome_bf8d_5119_zone_1_temperature`
- **Tank Temperature**: `sensor.melcloudhome_{short_id}_tank_temperature`
  - Example: `sensor.melcloudhome_bf8d_5119_tank_temperature`
- **Operation Status**: `sensor.melcloudhome_{short_id}_operation_status`
  - Example: `sensor.melcloudhome_bf8d_5119_operation_status`
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

- **WiFi Signal (RSSI)**: `sensor.melcloudhome_{short_id}_rssi` (diagnostic)
  - Example: `sensor.melcloudhome_bf8d_5119_rssi`
  - WiFi signal strength in dBm (values: -40 to -90, lower = weaker signal)
  - Update frequency: Every 60 minutes

**Energy Sensors (devices with energy capabilities):**

- **Energy Consumed**: `sensor.melcloudhome_{short_id}_energy_consumed`
  - Example: `sensor.melcloudhome_bf8d_5119_energy_consumed`
  - Electrical energy consumed by heat pump (kWh)
  - Compatible with Home Assistant Energy Dashboard
- **Energy Produced**: `sensor.melcloudhome_{short_id}_energy_produced`
  - Example: `sensor.melcloudhome_bf8d_5119_energy_produced`
  - Thermal energy produced by heat pump (kWh)
- **COP (Coefficient of Performance)**: `sensor.melcloudhome_{short_id}_cop`
  - Example: `sensor.melcloudhome_bf8d_5119_cop`
  - Heat pump efficiency ratio (produced/consumed)
  - Typical values: 2.5-4.0 (higher is more efficient)
  - Update frequency: Every 30 minutes

**Availability:** Energy sensors only created when device reports `hasEstimatedEnergyConsumption=true` AND `hasEstimatedEnergyProduction=true`. See [ADR-016](docs/decisions/016-implement-atw-energy-monitoring.md) for technical details.

#### Binary Sensors

- **Error State**: `binary_sensor.melcloudhome_{short_id}_error_state`
  - Example: `binary_sensor.melcloudhome_bf8d_5119_error_state`
- **Connection**: `binary_sensor.melcloudhome_{short_id}_connection_state`
  - Example: `binary_sensor.melcloudhome_bf8d_5119_connection_state`
- **Forced DHW Active**: `binary_sensor.melcloudhome_{short_id}_forced_dhw_active`
  - Example: `binary_sensor.melcloudhome_bf8d_5119_forced_dhw_active`

#### ATW Control Options

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

💡 **Most users should use Room/Cool Room modes** - they're the most intuitive

**Note:** Cooling availability depends on device capabilities (`hasCoolingMode=true`). When switching between heating and cooling, system automatically adjusts available presets. Curve mode not available for cooling (fallback to room temperature control).

**Water Heater Operation Modes:**

- **Eco** - Energy efficient balanced operation (auto DHW heating when needed)
- **High demand** - Priority mode for faster DHW heating (suspends zone heating)

> **Note:** These use Home Assistant's standard water heater modes. The MELCloud app calls these "Auto" and "Force DHW" respectively.

**Temperature Ranges:**

- Zone 1: 10-30°C
- DHW Tank: 40-60°C

#### Understanding ATW Operation (3-Way Valve)

**3-Way Valve Limitation:**
Your heat pump can only heat ONE thing at a time:

- Either Zone 1 (space heating)
- OR DHW tank (hot water)
- NOT both simultaneously

**What You'll See:**

- Climate entity shows "Heating" only when valve serves Zone 1
- Climate shows "Idle" when valve serves DHW (even if zone below target)
- Operation Status sensor shows current valve position
- Force DHW mode temporarily suspends zone heating

**Example:**

1. Zone target: 21°C, DHW target: 50°C
2. Zone at 19°C (needs heat), DHW at 48°C (needs heat)
3. System heats Zone 1 → Climate shows "Heating"
4. Zone reaches 21°C → System switches to DHW
5. System heats DHW → Climate shows "Idle", Operation Status shows "HotWater"
6. DHW reaches 50°C → System returns to monitoring both

## Troubleshooting

### Integration Not Loading

- Check Home Assistant logs for errors
- Verify your MELCloud Home credentials
- Ensure devices are configured in the MELCloud Home app

### Entities Not Updating

- Check your internet connection
- Verify MELCloud Home service is accessible
- Review the integration logs for API errors

### Energy Sensor Unavailable

- Some devices may not report energy data
- Check if device shows energy consumption in the MELCloud Home app
- Energy sensors require 30 minutes for initial data

### Export Diagnostics

1. Go to **Settings** → **Devices & Services**
2. Find "MELCloud Home" integration
3. Click the three dots and select "Download diagnostics"
4. Share the file when reporting issues

## API Rate Limiting

The integration uses conservative polling intervals to respect API limits:

- **Climate/Sensors**: 60 seconds
- **Energy Data**: 30 minutes

These intervals balance update frequency with API rate limits.

## Development & Code Quality

[![Coverage Sunburst](https://codecov.io/gh/andrew-blake/melcloudhome/graphs/sunburst.svg?token=WW97CHORNS)](https://codecov.io/gh/andrew-blake/melcloudhome)

**Test Coverage:**

- Integration tests: Climate control, sensors, config flow, diagnostics
- API tests: Authentication, device control, data parsing
- Quality gates: All PRs require passing tests and coverage checks

**Documentation:**

- [Architecture Overview](docs/architecture.md) - Visual system architecture with mermaid diagrams
- [Testing Best Practices](docs/testing-best-practices.md) - Development setup and testing guidelines
- [Architecture Decision Records](docs/README.md#architecture-decision-records-adrs) - Key architectural decisions (ADR-001 through ADR-016)

## Support

- **Issues**: [GitHub Issues](https://github.com/andrew-blake/melcloudhome/issues)
- **Documentation**: [GitHub Repository](https://github.com/andrew-blake/melcloudhome)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This is an unofficial integration and is not affiliated with, endorsed by, or connected to Mitsubishi Electric or MELCloud. Use at your own risk.

## Credits

Developed by Andrew Blake ([@andrew-blake](https://github.com/andrew-blake))
