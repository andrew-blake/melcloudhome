# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.3] - 2025-12-01

### Security

- Replace URL substring checks with proper URL parsing in authentication flow
- Fix 9 CodeQL security alerts (3 HIGH, 6 MEDIUM severity)

### Added

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
