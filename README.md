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

## Requirements

- Home Assistant 2024.11.0 or newer
- MELCloud Home account with configured devices
- Internet connection for cloud API access

## Supported Devices

This integration works with Mitsubishi Electric air conditioning units connected to **MELCloud Home** via compatible Wi-Fi adapters.

**Confirmed Compatible Wi-Fi Adapters:**

- **MAC-597** (4th-generation, MELCloud Home)
- **MAC-577** (confirmed working with dual-split systems)
- **MAC-567** (confirmed working with dual-split systems)
- **MAC-587** (confirmed working with multi-split systems)

**Confirmed Compatible Indoor Units:**

- **MSZ-AY25VGK2** (single-split and multi-split configurations)
- **MSZ-LN35VG2B** (confirmed working)
- **MSZ-LN25 VGWRAC** (multi-split system)

> **Note:** If your adapter appears in the classic **MELCloud** app (not MELCloud Home), use the official Home Assistant MELCloud integration instead.

For a complete list of tested hardware, compatibility notes, and to contribute your device information, see [SUPPORTED_DEVICES.md](SUPPORTED_DEVICES.md).

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

## Entities Created

For each air conditioning unit, the following entities are created:

### Climate Entity

- **Entity ID**: `climate.melcloudhome_<unit_id>`
- **Features**: Power on/off, temperature control, HVAC modes, fan speeds, swing modes
- **HVAC Action**: Real-time heating/cooling/idle status

### Sensors

- **Room Temperature**: `sensor.melcloudhome_<unit_id>_room_temperature`
- **WiFi Signal**: `sensor.melcloudhome_<unit_id>_wifi_signal` (diagnostic)
- **Energy**: `sensor.melcloudhome_<unit_id>_energy` (cumulative kWh)

### Binary Sensors

- **Error State**: `binary_sensor.melcloudhome_<unit_id>_error_state`
- **Connection**: `binary_sensor.melcloudhome_<unit_id>_connection_state`

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
