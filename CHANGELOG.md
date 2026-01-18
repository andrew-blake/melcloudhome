# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-01-18

**Major Release: Air-to-Water (ATW) Heat Pump Support - Production Ready**

ATW support graduates from experimental beta to stable, production-ready status after extensive testing on real hardware with multiple controller types.

### Added

**Air-to-Water (ATW) Heat Pump Support:**
- **Climate Platform** (Zone 1): Heating/cooling* control, temperature setting (10-30°C), preset modes (Room/Flow/Curve), HVAC modes (OFF/HEAT/COOL*)
- **Water Heater Platform** (DHW Tank): Temperature control (40-60°C), operation modes (Eco/High demand)
- **Switch Platform** (System Power): Primary power control
- **Sensors**: Zone 1 temperature, tank temperature, operation status, WiFi signal (RSSI), 6 telemetry sensors (flow/return temperatures)
- **Energy Monitoring***: Energy consumed (kWh), energy produced (kWh), COP (efficiency ratio) - compatible with Home Assistant Energy Dashboard
- **Binary Sensors**: Error state, connection state, forced DHW mode active
- **3-Way Valve Logic**: Automatic priority management between space heating and DHW
- **Capability-Based Features**: Energy monitoring and cooling mode auto-detected from device capabilities

*Feature availability depends on device capabilities (`hasCoolingMode`, `hasEstimatedEnergyConsumption`/`hasEstimatedEnergyProduction`)

**Controller Support:**
- ERSC-VM2D: Full features (heating, cooling, energy monitoring, telemetry)
- EHSCVM2D: Core features (heating-only, telemetry, no energy monitoring)

**Development Tools:**
- Local Docker Compose development environment with mock API server (2 ATA + 1 ATW test devices)
- Mock server supports energy, RSSI, and cooling endpoints
- Automated deployment tool for remote testing
- Upgrade verification tooling

### Changed

- Entity naming pattern updated to use `has_entity_name=True` for Home Assistant compatibility
  - Device names show friendly locations (e.g., "Living Room") instead of UUIDs
  - Entity IDs include descriptive suffixes (e.g., `_climate`, `_zone_1`, `_tank`)
  - Existing installations: Entity IDs preserved, device names automatically updated
  - No action required for existing users

- **ATA Climate State Attributes Now Lowercase**
  - State values for `fan_mode`, `swing_mode`, and `swing_horizontal_mode` are now lowercase per HA standards
  - Migration: Change `state_attr('climate.entity', 'fan_mode') == 'Auto'` → `== 'auto'`

### Fixed

- ATW zones showing IDLE when actively heating - added support for undocumented `"Heating"` operation status
- Water heater temperature control respects device capability (whole degree vs half degree steps)
- "Recreate entity ID" button now generates stable IDs instead of breaking automations
- Zone 1 heating status display - correctly shows HEATING when valve serves zone
- Blank icon button labels in thermostat cards for ATA and ATW

### Documentation

- [ADR-014: ATW Telemetry Sensors](docs/decisions/014-atw-telemetry-sensors.md) - Temperature sensor implementation
- [ADR-015: Skip ATW Energy Monitoring](docs/decisions/015-skip-atw-energy-monitoring.md) - Initial decision (superseded by ADR-016)
- [ADR-016: Implement ATW Energy Monitoring](docs/decisions/016-implement-atw-energy-monitoring.md) - Capability-based energy implementation
- ATW API Reference updated with cooling modes, telemetry sensors, and energy reporting sections
- README.md: ATW section updated, EXPERIMENTAL warnings removed
- EXPERIMENTAL-ATW.md removed (content integrated into README)

### Acknowledgments

Special thanks to [@pwa-2025](https://github.com/pwa-2025) for providing guest building access, enabling real hardware testing and validation of ATW features.

---

## [2.0.0-beta.5] - 2026-01-14

### Added

- ATW: 6 new telemetry sensors for flow and return temperatures (system, zone 1, and boiler circuits)

### Changed

- API client refactored to be more DRY

## [2.0.0-beta.4] - 2026-01-12

### Fixed

- ATW zones showing IDLE when actively heating - added support for undocumented `"Heating"` operation status
- Water heater temperature control respects device capability (whole degree vs half degree steps)
- Mock server now returns realistic `"Heating"` status matching real API behavior

### Changed

- API documentation updated to reflect real API behavior (removed unobserved status values)
- Integration tests updated to use realistic operation status values

### Acknowledgments

Special thanks to [@pwa-2025](https://github.com/pwa-2025) for granting guest building access, enabling real hardware testing and discovery of the undocumented `"Heating"` operation status.

## [2.0.0-beta.2] - 2026-01-11

### Fixed

- Zone 1 heating status display - now correctly shows HEATING when valve is actively heating the zone
- Blank icon button labels in thermostat cards for ATA and ATW - icons now display correctly (beta.1 feedback #26)

### Changed

- **ATA Climate State Attributes Now Lowercase**

  State values for `fan_mode`, `swing_mode`, and `swing_horizontal_mode` are now lowercase for Home Assistant compliance:
  - `"Auto"` → `"auto"`, `"One"` → `"one"`, `"LeftCentre"` → `"leftcentre"`, etc.

  **Impact:** Automations/templates checking these attributes must use lowercase values.

  **Migration:** Change `state_attr('climate.entity', 'fan_mode') == 'Auto'` → `== 'auto'`

## [2.0.0-beta.1] - 2026-01-10

### ⚠️ Beta Release - Testers Wanted

**Air-to-Water (ATW) Heat Pump Support - BETA TESTING**

This is a **pre-release beta** for community testing. ATW heat pump support is based on HAR captures and has **NOT been tested on real hardware**.

**How to test:**

1. Enable beta releases in HACS:
   - Go to **Settings → Devices & Services → Integrations → HACS**
   - Find **MELCloud Home** in your repository list
   - Enable the **"Show beta versions"** switch entity (disabled by default)
2. Install this beta version (will appear in available updates)
3. Test with your Ecodan ATW system
4. Report findings: <https://github.com/andrew-blake/melcloudhome/issues>

**⚠️ USE AT YOUR OWN RISK ⚠️**

- Implementation is theoretical and may not work correctly with physical hardware
- No guarantees of safety or correctness
- See README.md ATW section for full details and limitations

### Added

- **⚠️ EXPERIMENTAL:** Air-to-Water (ATW) heat pump support (Ecodan)
  - Water heater platform for DHW tank control
  - Switch platform for system power control
  - Climate platform for Zone 1 heating
  - Preset modes (Room Temperature, Flow Temperature, Curve Control)
  - ATW-specific sensors (Zone 1 room temperature, tank temperature, operation status)
  - Binary sensors (error state, connection state, forced DHW active)
  - See README.md ATW section for full details and limitations
- Local development environment with Docker Compose and mock API server
- Upgrade verification tooling (`tools/compare_upgrade_snapshots.py`)

### Changed

- Entity naming pattern updated to use `has_entity_name=True` for Home Assistant compatibility
  - **Existing installations:** Entity IDs preserved, device names automatically set to friendly location names
  - **New installations:** ATA Climate entity IDs include descriptive suffix (e.g., `_climate`)
  - Device names show friendly locations (e.g., "Living Room") instead of UUIDs
  - **No action required** for existing users

### Fixed

- "Recreate entity ID" button now generates stable IDs instead of breaking automations

## [1.3.4] - 2025-12-09

### Fixed

- **Energy monitoring accuracy** - Fixed critical bug causing 60-75% undercount of energy consumption
  - Root cause: API returns progressive updates for same hour (values increase as data uploads)
  - Fix: Implemented delta-based tracking to handle increasing values correctly
  - Impact: Energy values now match MELCloud app and wall display
  - Migration: Automatic from v1.3.3, no user action required
  - Closes #23

### Changed

- Increased energy API query window from 2 hours to 48 hours
  - Enables recovery from outages up to 48 hours
  - Handles reboots during hour updates without data loss

## [1.3.3] - 2025-12-01

### Security

- Replace URL substring checks with proper URL parsing in authentication flow
- Fix 9 CodeQL security alerts (3 HIGH, 6 MEDIUM severity)

### Added

- CONTRIBUTING.md with contribution guidelines and API discovery methodology
- SUPPORTED_DEVICES.md with hardware compatibility details
- SECURITY.md with security policy
- testing-best-practices.md guide
- Explicit workflow permissions for GitHub Actions

### Changed

- Confirm all four WiFi adapter families: MAC-597, MAC-577, MAC-567, MAC-587
- Add MSZ-LN35VG2B and MSZ-LN25VGWRAC to tested indoor units
- Update GitHub Actions dependencies (checkout v6, setup-python v6, setup-uv v7)

### Removed

- Redundant lint.yml workflow

**Note:** No functional changes. Authentication and HVAC control behaviour identical to v1.3.2.

## [1.3.2] - 2025-11-26

### Changed

- Internal documentation cleanup

## [1.3.1] - 2025-11-26

### Fixed

- LICENSE badge in README (removed clickable link to prevent HACS from creating malformed URLs)

## [1.3.0] - 2025-11-26

### Added

- **Automatic session recovery**: Climate service calls now automatically recover from session expiry with retry and re-authentication
- **Debounced coordinator refresh**: Prevents race conditions when scenes or automations make multiple rapid service calls
- **Smart deduplication**: Skips redundant API calls when values haven't changed, reducing API load by ~70% for typical scene activation
- **Enhanced deployment tool**: Improved reliability with retry logic and better error diagnostics

### Fixed

- **Session expiry errors**: Climate service calls no longer fail with "Session expired" errors
- **Race conditions**: Multiple rapid service calls from scenes now properly debounce refresh to prevent stale state
- **Duplicate API calls**: Eliminated redundant calls (e.g., vanes being set 3x with same values)
- **Energy polling exception handling**: Authentication failures now properly trigger repair UI instead of being silently logged
- **Deployment tool**: Fixed intermittent SSH failures when running under `uv run`

### Changed

- **Authentication failure notification**: Auth failures now immediately show repair UI (instead of retry with backoff) for faster user notification
- **Service call flow**: All climate service calls now use coordinator wrappers for consistency

### Technical Details

- Coordinator-based retry mechanism with asyncio.Lock and double-check pattern
- 5 new coordinator wrapper methods with session recovery
- Debounced refresh with 2-second delay for rapid service calls
- State-aware deduplication to prevent unnecessary API calls
- 12 new integration tests including concurrent call and deduplication tests
- Modern Python 3.11+ type hints with deferred annotation evaluation
- SSH robustness improvements (disable multiplexing, retry logic)

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
