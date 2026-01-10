# MELCloud Home

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub Release](https://img.shields.io/github/release/andrew-blake/melcloudhome.svg)](https://github.com/andrew-blake/melcloudhome/releases)
![License](https://img.shields.io/github/license/andrew-blake/melcloudhome.svg)
[![Test](https://github.com/andrew-blake/melcloudhome/workflows/Test/badge.svg)](https://github.com/andrew-blake/melcloudhome/actions/workflows/test.yml)
[![codecov](https://codecov.io/gh/andrew-blake/melcloudhome/graph/badge.svg?token=WW97CHORNS)](https://codecov.io/gh/andrew-blake/melcloudhome)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
![Python](https://img.shields.io/badge/python-3.12%2B-blue)

Home Assistant custom integration for **MELCloud Home** - Control Mitsubishi Electric air conditioning units via the MELCloud Home API.

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

### ⚠️ Air-to-Water (ATW) Heat Pumps (EXPERIMENTAL)

- **Climate Control**: Zone 1 heating with temperature and mode control
- **DHW Tank Control**: Water heater platform for domestic hot water management
- **System Power**: Switch platform for system on/off control
- **Preset Modes**: Room Temperature, Flow Temperature, Curve Control
- **Sensors**: Tank temperature, flow temperature, return temperature, DHW flow temperature, WiFi signal, error status
- **⚠️ WARNING**: ATW support is EXPERIMENTAL - based on HAR captures, not yet tested on real hardware
- **See [EXPERIMENTAL-ATW.md](EXPERIMENTAL-ATW.md) for full details, limitations, and testing instructions**

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

### ⚠️ Air-to-Water (ATW) - Heat Pumps (EXPERIMENTAL)

- **Status:** NOT yet tested on real hardware - based on HAR captures only
- **Implementation targets:** Mitsubishi Electric Ecodan heat pumps with FTC controllers
- **Reference system:** Ecodan EHSCVM2D Hydrokit
- **Supports:** Zone 1 heating, DHW control, 3-way valve systems (single zone only)
- **⚠️ Read [EXPERIMENTAL-ATW.md](EXPERIMENTAL-ATW.md) before using ATW features**

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

This integration uses **stable UUID-based entity IDs** (e.g., `climate.melcloudhome_bf8d_5119`) to ensure your automations never break when device names change.

**Device names** are automatically set to friendly names from your MELCloud Home account (e.g., "Living Room", "Bedroom") for easy identification in the UI.

**⚠️ Entity ID Recreation Warning:**

- If you delete entities and use the **"Recreate entity IDs"** option, Home Assistant will regenerate entity IDs based on the friendly device name instead of the stable UUID
- This will change entity IDs from `climate.melcloudhome_bf8d_5119` to `climate.living_room`, breaking existing automations
- **To preserve entity IDs:** Don't delete entities unless necessary. If you need to reset, delete and re-add the integration instead.

## Entities Created

### Air-to-Air (ATA) Systems

For each air conditioning unit, the following entities are created:

#### Climate Entity

- **Entity ID**: `climate.melcloudhome_<unit_id>`
- **Features**: Power on/off, temperature control, HVAC modes, fan speeds, swing modes
- **HVAC Action**: Real-time heating/cooling/idle status

#### Sensors

- **Room Temperature**: `sensor.melcloudhome_<unit_id>_room_temperature`
- **WiFi Signal**: `sensor.melcloudhome_<unit_id>_wifi_signal` (diagnostic)
- **Energy**: `sensor.melcloudhome_<unit_id>_energy` (cumulative kWh)

#### Binary Sensors

- **Error State**: `binary_sensor.melcloudhome_<unit_id>_error_state`
- **Connection**: `binary_sensor.melcloudhome_<unit_id>_connection_state`

### ⚠️ Air-to-Water (ATW) Systems (EXPERIMENTAL)

For each heat pump system, the following entities are created:

> **Note:** Entity IDs use stable UUID-based device names (e.g., `melcloudhome_bf8d_5119`). The friendly device name is displayed in the UI.

#### Climate Entity (Zone 1)

- **Entity ID**: `climate.melcloudhome_<uuid>_zone_1`
  - Example: `climate.melcloudhome_bf8d_5119_zone_1`
- **Features**: Zone 1 heating control, temperature setting, preset modes
- **Preset Modes**:
  - `room` - Room Temperature (thermostat control)
  - `flow` - Flow Temperature (direct flow control)
  - `curve` - Weather Compensation Curve

#### Water Heater Entity (DHW Tank)

- **Entity ID**: `water_heater.melcloudhome_<uuid>_tank`
  - Example: `water_heater.melcloudhome_bf8d_5119_tank`
- **Features**: DHW tank temperature control, operation modes
- **Operation Modes**:
  - `Auto` - DHW heats when below target
  - `Force DHW` - Force immediate DHW heating (priority mode)
- **Note**: Water heater does NOT control system power (power state is read-only)

#### Switch Entity (System Power)

- **Entity ID**: `switch.melcloudhome_<uuid>_system_power`
  - Example: `switch.melcloudhome_bf8d_5119_system_power`
- **Features**: System power control (primary power control point)
- **Note**: Climate OFF also controls system power (delegates to same control method as switch)

#### Sensors

- **Zone 1 Temperature**: `sensor.melcloudhome_<uuid>_zone_1_temperature`
- **Tank Temperature**: `sensor.melcloudhome_<uuid>_tank_temperature`
- **Operation Status**: `sensor.melcloudhome_<uuid>_operation_status`
  - Shows current 3-way valve position: "Stop", "HotWater", "HeatRoomTemperature", etc.

#### Binary Sensors

- **Error State**: `binary_sensor.melcloudhome_<uuid>_error_state`
- **Connection**: `binary_sensor.melcloudhome_<uuid>_connection_state`
- **Forced DHW Active**: `binary_sensor.melcloudhome_<uuid>_forced_dhw_active`

## Supported HVAC Modes

- **Off**: Unit powered off
- **Heat**: Heating mode
- **Cool**: Cooling mode
- **Dry**: Dehumidification mode
- **Fan Only**: Fan only (no heating/cooling)
- **Auto**: Automatic mode

## Fan Speeds

- Auto
- Level 1 (Quiet)
- Level 2 (Low)
- Level 3 (Medium)
- Level 4 (High)
- Level 5 (Very High)

## Swing Modes

### Vertical (Standard Swing)

- Auto
- Swing
- One (Top)
- Two
- Three (Middle)
- Four
- Five (Bottom)

### Horizontal (Swing Horizontal Mode)

- Auto
- Swing
- Left
- LeftCentre
- Centre
- RightCentre
- Right

## Energy Dashboard Integration

Energy consumption sensors are compatible with Home Assistant's Energy Dashboard:

1. Go to **Settings** → **Dashboards** → **Energy**
2. Add your devices under "Individual devices"
3. Select the energy sensor for each unit
4. Energy data accumulates over time and persists across restarts

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

For development setup and testing guidelines, see [docs/testing-best-practices.md](docs/testing-best-practices.md).

## Support

- **Issues**: [GitHub Issues](https://github.com/andrew-blake/melcloudhome/issues)
- **Documentation**: [GitHub Repository](https://github.com/andrew-blake/melcloudhome)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This is an unofficial integration and is not affiliated with, endorsed by, or connected to Mitsubishi Electric or MELCloud. Use at your own risk.

## Credits

Developed by Andrew Blake ([@andrew-blake](https://github.com/andrew-blake))
