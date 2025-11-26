# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2025-11-25

### Added

- **Automatic Device Discovery**: New devices added to your MELCloud account are automatically detected and entities created without manual intervention
- Persistent notification when new devices are discovered
- Integration automatically reloads to create entities for new devices

### Changed

- **BREAKING**: Entity ID prefix changed from `melcloud_` to `melcloudhome_` for consistency with integration domain
  - Old: `climate.melcloud_0efc_76db`
  - New: `climate.melcloudhome_0efc_76db`
  - **Action required**: Update any automations, dashboards, or scripts referencing old entity IDs

### Fixed

- ADR-009 incorrectly referenced "MAC addresses" instead of "UUIDs" for entity ID generation

## [1.1.0] - 2025-11-25

### Added

- Reconfigure flow for updating credentials without removing the integration
- `force_refresh` service for manual data refresh

## [1.0.0] - 2025-11-18

### Added

- Initial release
- Full HVAC control (power, temperature, mode, fan speed, swing modes)
- Energy monitoring with persistent storage
- Room temperature sensor
- WiFi signal strength sensor
- Error state binary sensor
- Connection status binary sensor
- Diagnostics support
