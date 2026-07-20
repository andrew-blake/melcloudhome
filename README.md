# MELCloud Home

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub Release](https://img.shields.io/github/release/andrew-blake/melcloudhome.svg)](https://github.com/andrew-blake/melcloudhome/releases)
![License](https://img.shields.io/github/license/andrew-blake/melcloudhome.svg)
[![Test](https://github.com/andrew-blake/melcloudhome/workflows/Test/badge.svg)](https://github.com/andrew-blake/melcloudhome/actions/workflows/test.yml)
[![codecov](https://codecov.io/gh/andrew-blake/melcloudhome/graph/badge.svg?token=WW97CHORNS)](https://codecov.io/gh/andrew-blake/melcloudhome)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
![Python Version from PEP 621 TOML](https://img.shields.io/python/required-version-toml?tomlFilePath=https%3A%2F%2Fraw.githubusercontent.com%2Fandrew-blake%2Fmelcloudhome%2Fmain%2Fpyproject.toml)

Home Assistant custom integration for **MELCloud Home**.

## What's New in v2.4.0

**Real-time updates** - changes made with the remote control or the MELCloud Home app now appear in Home Assistant within seconds, instead of up to a minute. Enabled by default with automatic fallback to regular polling, so there's nothing to set up - see [Real-Time Updates](#real-time-updates) for details. Contributed by [@mrdjtoto](https://github.com/mrdjtoto), from protocol investigation through implementation.

**Requires Home Assistant 2025.8.0 or newer.** If you're on an older version, HACS will not offer this update.

See [CHANGELOG.md](CHANGELOG.md) for full history.

## Features

### Air-to-Air (ATA) - Air Conditioning

- Full climate control (power, temperature, modes, fan speeds, vane directions)
- Energy monitoring with Home Assistant Energy Dashboard support
- Sensors (room temperature, outdoor temperature*, WiFi signal, connection status)
- [Real-time updates](#real-time-updates) via WebSocket push, plus 60-second polling (30-minute for outdoor temperature)

*Auto-detected from device capabilities - not all units have outdoor temperature sensors

### Air-to-Water (ATW) - Heat Pumps

- Zone 1 & Zone 2 climate control with preset modes (Room/Flow/Curve) - Zone 2 auto-detected
- DHW tank control via water heater platform
- System power switch
- Multiple sensors (temperatures, operation status, 6 telemetry sensors)
- Energy monitoring* (consumed, produced, COP - Energy Dashboard compatible)
- Cooling mode* (Cool Room/Cool Flow presets)
- [Real-time updates](#real-time-updates) via WebSocket push

*Auto-detected from device capabilities - see [docs/entities.md](docs/entities.md) for details

## Requirements

- Home Assistant 2025.8.0 or newer
- MELCloud Home account with configured devices
- Internet connection for cloud API access

## Supported Devices

### Air-to-Air (ATA) - Air Conditioning Units

This integration supports Mitsubishi Electric air conditioning units connected via **MELCloud Home** WiFi adapters (MAC-5xx series).

**Supported systems:** Wall-mounted splits, ducted systems, and console units tested and working.

> **Note:** If your system uses the classic **MELCloud** app (not MELCloud Home), use the official Home Assistant MELCloud integration instead.

For complete hardware compatibility including specific models, WiFi adapters, and technical notes, see [SUPPORTED_DEVICES.md](SUPPORTED_DEVICES.md).

### Air-to-Water (ATW) - Heat Pumps

- **Status:** Production-ready (tested on real hardware)
- **Supported systems:** Mitsubishi Electric Ecodan heat pumps with FTC controllers
- **Core features:** Zone 1 & Zone 2 heating, DHW control, 3-way valve systems, telemetry sensors, energy monitoring*
- **Optional features:** Cooling mode (capability-based), energy monitoring (capability-based)

*Feature availability auto-detected from device capabilities

For tested controller models and capability details, see [SUPPORTED_DEVICES.md](SUPPORTED_DEVICES.md).

## Installation

### HACS (Recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=andrew-blake&repository=melcloudhome&category=integration)

Or manually: HACS → Integrations → ⋮ → Custom repositories → add `https://github.com/andrew-blake/melcloudhome`

After adding, find "MELCloud Home" in HACS, click "Download", and restart Home Assistant.

### Manual Installation

1. Download the latest release from [GitHub](https://github.com/andrew-blake/melcloudhome/releases)
2. Extract the `melcloudhome` folder to your `custom_components` directory
3. Restart Home Assistant

## Configuration

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=melcloudhome)

Or manually: **Settings** → **Devices & Services** → **Add Integration** → search "MELCloud Home"

Enter your MELCloud Home credentials (email and password). Your devices will be automatically discovered and added.

## Real-Time Updates

Changes made outside Home Assistant — the physical remote, the MELCloud Home app, a schedule — normally take up to 60 seconds to appear (the polling interval). Real-time updates shrink that to a couple of seconds: the integration listens on a MELCloud WebSocket and refreshes a device as soon as the cloud reports a change.

**On by default.** There is nothing to set up. It is safe by design:

- The socket is receive-only — all control commands use the same cloud API as before
- If the connection drops, the integration falls back to normal 60-second polling automatically; your devices keep working and never show as unavailable because of it
- Reconnection is automatic (the MELCloud server routinely recycles connections about every 2 hours — this is normal)

**How to tell it's working:** changes made on the remote or in the MELCloud app show up in Home Assistant within a few seconds. The log (Settings → System → Logs) shows `WebSocket connected` when it starts and `WebSocket connection lost; reconnecting (polling continues meanwhile)` if it drops.

**How to turn it off:** Settings → Devices & Services → MELCloud Home → Configure → switch off "Real-time updates" → Submit. The integration then uses 60-second polling only.

## Important Notes

### Stable Entity IDs

This integration uses **UUID-based entity IDs** to ensure automations never break when device names change. Entity IDs follow the format `{domain}.melcloudhome_{short_id}_{entity_name}` where `short_id` is derived from the device UUID.

**Device names** are set to friendly names from your MELCloud Home account (e.g., "Living Room").

**⚠️ Warning:** If you delete entities and use the "Recreate entity IDs" option, entity IDs will change to name-based IDs (e.g., `climate.living_room_climate`), breaking automations. To preserve IDs, delete and re-add the integration instead.

See [docs/entities.md](docs/entities.md) for complete entity ID reference.

## Entities

The integration creates the following entities for each device:

**Air-to-Air (ATA) Systems:**

- Climate control (HVAC modes, temperature, fan speeds, swing)
- Sensors (room temperature, outdoor temperature*, WiFi signal, energy consumption)
- Binary sensors (error state, connection status)

**Air-to-Water (ATW) Heat Pumps:**

- Climate control (Zone 1 & Zone 2 heating/cooling with preset modes)
- Water heater (DHW tank control)
- System power switch
- Sensors (temperatures, operation status, telemetry, WiFi signal, energy*)
- Binary sensors (error state, connection status, forced DHW active)

*Energy monitoring auto-detected from device capabilities

**Complete entity reference:** See [docs/entities.md](docs/entities.md) for detailed entity IDs, control options, and configuration examples.

## Troubleshooting

### Integration Not Loading

- Check Home Assistant logs for errors
- Verify your MELCloud Home credentials
- Ensure devices are configured in the MELCloud Home app

### Entities Not Updating

- Check your internet connection
- Verify MELCloud Home service is accessible
- Review the integration logs for API errors

### Out-of-Band Changes Slow to Appear

If changes made with the remote or MELCloud app take up to a minute to show in Home Assistant, real-time updates may not be connected:

- Check the logs for `WebSocket connected` / `WebSocket connection lost` messages
- Verify the toggle is on: Settings → Devices & Services → MELCloud Home → Configure
- Updates still arrive via 60-second polling even when the WebSocket is down

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
- **Outdoor Temperature**: 30 minutes

These intervals balance update frequency with API rate limits. Real-time updates don't add polling load — the WebSocket is a single long-lived connection, and it only triggers an extra state refresh when a device actually changes.

## Development & Code Quality

[![Coverage Sunburst](https://codecov.io/gh/andrew-blake/melcloudhome/graphs/sunburst.svg?token=WW97CHORNS)](https://codecov.io/gh/andrew-blake/melcloudhome)

**Test Coverage:**

- Integration tests: Climate control, sensors, config flow, diagnostics
- API tests: Authentication, device control, data parsing
- Quality gates: All PRs require passing tests and coverage checks

**Documentation:**

- [Architecture Overview](docs/architecture.md) - Visual system architecture with mermaid diagrams
- [Testing Best Practices](docs/testing-best-practices.md) - Development setup and testing guidelines
- [Architecture Decision Records](docs/README.md#architecture-decision-records-adrs) - Key architectural decisions

## Support

- **Issues**: [GitHub Issues](https://github.com/andrew-blake/melcloudhome/issues)
- **Documentation**: [GitHub Repository](https://github.com/andrew-blake/melcloudhome)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This is an unofficial integration and is not affiliated with, endorsed by, or connected to Mitsubishi Electric or MELCloud. Use at your own risk.

## Star History

[![Star History Chart](https://api.star-history.com/chart?repos=andrew-blake/melcloudhome&type=date&legend=top-left&sealed_token=IAuAe8mdYc94qeHiZD79IobZ9omvLsbIxKrgaa_Sp0bMwhd3sqbSuK_Ki8JpoCMHwKLtc9ez_yXHig6m6fxdvXpPhZJ_a6DrUP0W1EMsUkfdk5w24LZQdrnrxS8jaEVk4NZEOtT53xek28PfTPgZeKiplyoGGlZeSYMGfJVnxx3NWJXZLQLKCcfsqmCG)](https://www.star-history.com/?repos=andrew-blake%2Fmelcloudhome&type=date&legend=top-left)

## Credits

Developed by Andrew Blake ([@andrew-blake](https://github.com/andrew-blake))

**Contributors:**

- [@mrdjtoto](https://github.com/mrdjtoto) - real-time updates: WebSocket protocol investigation, captures, and implementation (#174-#176)
