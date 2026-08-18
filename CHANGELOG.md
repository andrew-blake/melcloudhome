# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [2.4.2] - 2026-08-18

### Fixed

- Heat pump (ATW) outdoor temperature could get stuck at an incorrect value (e.g. a value of 0) with no way to tell it was wrong. It's now read from the same source as the MELCloud Home app's Reports → Comfort graph, which doesn't have this problem. (#251)
- Air conditioning (ATA) outdoor temperature could occasionally fail to update because the underlying request looked back over a week of history, which could trigger an error from the MELCloud API. It now looks back 48 hours instead, which is more reliable - the trade-off is that a unit idle for more than 48 hours (rather than 7 days) will show outdoor temperature as "unknown" until it's used again.


## [2.4.1] - 2026-08-14

### Added

- Norwegian (nb) translations (thanks @Jan-Arild-Blekken)

### Fixed

- Sensor and binary sensor names (WiFi signal, Room temperature, Frost protection, Holiday mode, and others) always displayed in English regardless of your Home Assistant language setting. Identified and diagnosed by @Jan-Arild-Blekken. (#240)

### Changed

- New devices (and fresh installs) will get entity IDs that follow your Home Assistant language, not just English, for a few diagnostic sensors — including the COP sensor and the minimum/maximum frost and overheat protection sensors — now that they're generated correctly from the translated name rather than the raw internal key. Existing entities are unaffected.


## [2.4.0] - 2026-08-01

### Added

- **Real-time updates**: changes made with the remote control, the MELCloud Home app, or a schedule now appear in Home Assistant within seconds instead of up to a minute. On by default with nothing to set up; if the connection drops, the integration falls back to regular polling automatically. Contributed by @mrdjtoto. (#176, #185)
- "Real-time updates" sensor showing whether the live connection is active. (#187)
- **Frost protection, overheat protection and holiday mode for air conditioning units**: each unit now shows whether these modes are set up, the temperature limits they use, and the start and end dates of holiday mode. A mode reads "on" when it is set up, not only while it is actively running. For viewing only — you still switch these modes on and off in the MELCloud Home app or on the remote control. Contributed by @mrdjtoto. (#205)
- Outdoor temperature sensors now include a "last reading" timestamp showing when the reading was actually taken. MELCloud's outdoor temperature can be several hours old, especially overnight, so this tells you how current the value really is. Contributed by @mrdjtoto. (#173, #224)
- Error state sensors now include the error code reported by the unit, which is useful when reporting a fault to an installer. Contributed by @mrdjtoto. (#172)

### Changed

- Requires Home Assistant 2025.8.0 or newer. On older versions, HACS will not offer this update — upgrade Home Assistant first. (#185)
- **New entities appear after upgrading.** MELCloud reports a frost protection setting for every air conditioning unit, so each one gains a "Frost protection" sensor with minimum and maximum temperatures — even if you have never used the feature. "Overheat protection" and "Holiday mode" appear only on units where you have set them up (these modes are managed by the account owner in the MELCloud Home app); a mode set up for the first time appears after Home Assistant next restarts. (#205)
- **Sensors show "unknown" instead of "unavailable" when a reading is missing.** "Unavailable" now means only that the device cannot be reached - MELCloud down, the unit offline, or its sharing removed. A sensor whose unit is reachable but has not supplied that particular value - outdoor temperature while a unit is idle, for example - reads "unknown". If an automation of yours checks these sensors for "unavailable", update it; templates using `has_value()` behave exactly as before. (#222)
- Now available directly in the HACS default repository — search "MELCloud Home" in HACS to install, no need to add it as a custom repository. Existing installs via the custom repository keep working as-is; removing the custom repository entry is optional cleanup, not required. (#83)

### Fixed

- WiFi signal sensor on heat pumps showed a stale signal strength instead of the current one. (#204)
- Room temperature and WiFi signal sensors could go missing entirely. If Home Assistant restarted while an air conditioning unit was offline or not reporting, those sensors were never created, and only came back after reloading the integration. They are now always created and simply show as "unknown" until a reading arrives. (#219)
- The "sign in again" prompt was missing its wording. When MELCloud needed you to re-enter your password, the dialog appeared with no title or explanation, and showed placeholder text instead of your language. It now reads properly in all 13 supported languages. (#209)
- Heat pump flow and return temperature sensors could be missing after a restart. They were only created if a reading had already arrived, so a brief connection problem while Home Assistant was starting made them disappear until you reloaded the integration. They are now always created, and show as "unknown" if your heat pump does not report that particular reading - if several of them stay "unknown" permanently, please let us know in a GitHub issue. (#220)
- Outdoor temperature sensors could go missing after a restart. The sensor was only created if its first reading happened to arrive during startup, so a brief connection problem could drop it for the whole session until you reloaded - and on air conditioning units that share one outdoor unit, one could disappear while the other kept working. They are now always created and show as "unknown" until a reading arrives. (#226)


## [2.3.5] - 2026-07-06

### Added

- Diagnostic tool `tools/find_corrupt_energy_readings.py` that scans your Home Assistant statistics for energy spikes caused by corrupt cloud readings and tells you exactly which entity and timestamp to fix. See `tools/README.md` for setup and step-by-step fix instructions. (#161)

### Fixed

- Corrupt hourly energy readings from the MELCloud cloud (~6,553 kWh for a single hour) are now rejected instead of being added to the energy sensor, which could permanently inflate totals and corrupt the Energy Dashboard. A warning is logged once per rejected reading. (#161)
- Installs that already accumulated a corrupt reading have the affected energy sensor reset to 0 automatically on upgrade, and it counts normally from there. Note this does not repair Energy Dashboard history: spikes already recorded there need a one-time manual fix (see `tools/README.md`). (#161)


## [2.3.4] - 2026-06-18

### Added

- Outdoor temperature sensor for ATW heat pump devices (Ecodan, Hydrobox). The sensor reads directly from the regular polling response — no additional API calls needed. (#143)

### Fixed

- Indoor units on multi-zone systems occasionally flash or fault when turned on via HA (#132)

### Security

- Sensitive data (email addresses, IP addresses) could appear in diagnostic reports and log files (#130)


## [2.3.3] - 2026-06-04

### Added

- Vietnamese (vi) translations (thanks @0jar)
- Confirmed support for MSZ-HR25VFK2 and MSZ-HR35VFK indoor units (thanks @FerranMartin and @HansOtten)

### Fixed

- Outdoor temperature sensor stuck `unavailable` for mostly-idle units. The integration now uses the `Daily` report period instead of `Hourly` — the hourly window silently drops data for units inactive for more than ~1 hour. Units idle at startup are also re-probed every 30 minutes so the sensor recovers automatically when the AC next runs, without needing an HA restart. ([#110](https://github.com/andrew-blake/melcloudhome/issues/110))


## [2.3.2] - 2026-04-22

### Added

- Greek (el) translations (thanks @h-ram)


## [2.3.1] - 2026-04-20

### Fixed

- Vertical swing mode "Swing" silently ignored on A/C units without horizontal vanes (e.g. MSZ-HR25VFK2). The integration now sends vane commands per axis — matching the official MELCloud app — instead of always sending both axes together. ([#100](https://github.com/andrew-blake/melcloudhome/issues/100))


## [2.3.0] - 2026-04-16

### Added

- Dutch (nl) translations (thanks @yw13931835525-cyber)
- French (fr) translations (thanks @pfauchet)
- Turkish (tr) translations (thanks @freedomwarriorx86)
- Clear error messages when MELCloud servers are unavailable

### Changed

- Migrated from web BFF to mobile BFF API with OAuth 2.0 PKCE authentication

## [2.2.5] - 2026-04-04

### Added

- Swedish (sv) translations (thanks @MHultman)
- HACS default repository preparation: render_readme, workflow_dispatch validation trigger (thanks @sginestrini)


## [2.2.4] - 2026-04-04

### Added

- Spanish (es) translations (thanks @gabrnavarro)

### Changed

- Updated pre-commit hooks: ruff v0.8.4→v0.15.9, mypy v1.13.0→v1.20.0, pre-commit-hooks v5→v6, codespell v2.3.0→v2.4.2


## [2.2.3] - 2026-04-02

### Added

- German (de) and Thai (th) translations (thanks @thaikolja)
- Finnish (fi) translations (thanks @zrajna)
- Portuguese (pt) translations (thanks @tixastronauta)


## [2.2.2] - 2026-04-02

### Added

- Italian (it) translations (thanks @sginestrini)


## [2.2.1] - 2026-02-19

### Changed

- Updated README "What's New" section to reflect v2.2.0 Zone 2 support

## [2.2.0] - 2026-02-15

### Added

- **Zone 2 support** for Air-to-Water (ATW) devices with automatic capability detection
  - Climate entity with full HVAC control (heating/cooling, preset modes, temperature)
  - Zone 2 room temperature sensor
  - Zone 2 flow and return temperature telemetry sensors
  - Shared base class architecture for consistent Zone 1/Zone 2 behavior

## [2.1.0] - 2026-02-08

### Added

- **Outdoor Temperature Sensor** for Air-to-Air (ATA) devices with automatic capability discovery (30-minute updates)

## [2.0.0] - 2026-01-24

**Air-to-Water (ATW) heat pump support is now production-ready.**

### Added

**Air-to-Water (ATW) Heat Pump Support:**

- Climate platform for Zone 1 with heating/cooling\*, preset modes (Room/Flow/Curve), and temperature control (10-30°C)
- Water heater platform for DHW tank control (40-60°C, Eco/High demand modes)
- Switch platform for system power control
- Sensors: Zone 1 temperature, tank temperature, operation status, WiFi signal (RSSI), 6 telemetry sensors (flow/return temperatures)
- Energy monitoring\*: Sensors for consumed energy (kWh), produced energy (kWh), and COP (efficiency ratio) - compatible with Home Assistant Energy Dashboard
- Binary sensors: Error state, connection state, forced DHW mode indicator
- 3-way valve logic with automatic priority management between space heating and DHW
- Capability-based feature detection for energy monitoring and cooling mode

\*Feature availability auto-detected from device capabilities.

**Development Tools:**

- Local Docker Compose development environment with mock API server (2 ATA + 1 ATW test devices)
- Automated deployment tool for remote testing

### Changed

- **ATA Climate State Attributes Now Lowercase** - State values for `fan_mode`, `swing_mode`, and `swing_horizontal_mode` are now lowercase per Home Assistant standards.
- **Migration required:** Change `state_attr('climate.entity', 'fan_mode') == 'Auto'` → `== 'auto'`
- Entity naming pattern updated to `has_entity_name=True` for Home Assistant compatibility. Device names now show friendly locations (e.g., "Living Room") instead of UUIDs. Entity IDs include descriptive suffixes (e.g., `_climate`, `_zone_1`, `_tank`). Existing installations: Entity IDs preserved, device names automatically updated.

### Fixed

- Request pacing prevents 429 errors when scenes/automations control multiple devices simultaneously (minimum 500ms spacing between API requests)
- Water heater temperature control respects device capability (whole degree vs half degree steps)
- "Recreate entity ID" button now generates stable IDs instead of breaking automations
- Memory leak in config flow - Client sessions now properly closed when login fails

### Acknowledgments

Thanks to [@pwa-2025](https://github.com/pwa-2025) and [@Alexxx1986](https://github.com/Alexxx1986) for providing guest building access, enabling real hardware testing and validation of ATW features.

## [2.0.0-rc.2] - 2026-01-23

**Beta Release: Authentication and Performance Fixes**

### Fixed

- **Reauth flow after power outages** - Integration now automatically recovers when credentials expire instead of getting stuck in broken state (Fixes #39)
  - Added Home Assistant reauth flow support (`async_step_reauth`, `async_step_reauth_confirm`)
  - Handles "already authenticated" edge case when auth cookies outlive API session
  - Prompts user to re-enter password when authentication fails
  - No more manual reconfiguration or HA restart required after power outages

- **Memory leak in config flow** - Client sessions are now properly closed when login fails during setup, reauth, or reconfigure
  - Previously leaked aiohttp ClientSession, TCP connections, memory buffers, and SSL contexts with each failed login attempt
  - Added `try-finally` pattern to ensure `client.close()` always called
  - Affects user setup, reauth, and reconfigure flows

- **Login performance** - Removed unnecessary 3-second delay after OAuth login
  - Chrome DevTools testing confirmed session is ready immediately after OAuth redirect
  - Login now completes as soon as OAuth finishes (3 seconds faster)
  - Affects initial setup, reauth after credential expiration, and reconfiguration

### Changed

- Mock server now validates passwords for authentication testing (accepts any password except 'WRONG_PASSWORD')

## [2.0.0-rc.1] - 2026-01-23

**Major Release: Air-to-Water (ATW) Heat Pump Support**

### Added

**Air-to-Water (ATW) Heat Pump Support:**

- **Climate Platform** (Zone 1): Heating/cooling*control, temperature setting (10-30°C), preset modes (Room/Flow/Curve), HVAC modes (OFF/HEAT/COOL*)
- **Water Heater Platform** (DHW Tank): Temperature control (40-60°C), operation modes (Eco/High demand)
- **Switch Platform** (System Power): Primary power control
- **Sensors**: Zone 1 temperature, tank temperature, operation status, WiFi signal (RSSI), 6 telemetry sensors (flow/return temperatures)
- **Energy Monitoring\***: Energy consumed (kWh), energy produced (kWh), COP (efficiency ratio) - compatible with Home Assistant Energy Dashboard
- **Binary Sensors**: Error state, connection state, forced DHW mode active
- **3-Way Valve Logic**: Automatic priority management between space heating and DHW
- **Capability-Based Features**: Energy monitoring and cooling mode auto-detected from device capabilities

\*Feature availability depends on device capabilities

**Tested Devices:**

- ERSCVM2D: Full features (heating, cooling, energy monitoring, telemetry)
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

- **Rate limiting:** Add request pacing to prevent 429 errors when scenes/automations control multiple devices simultaneously. The integration now enforces a minimum 500ms spacing between API requests, preventing MELCloud from rejecting rapid-fire requests. This is especially important for ATW heat pump devices which have multiple entities (zones + DHW + power) that may be controlled together.
- ATW zones showing IDLE when actively heating - added support for undocumented `"Heating"` operation status
- Water heater temperature control respects device capability (whole degree vs half degree steps)
- "Recreate entity ID" button now generates stable IDs instead of breaking automations
- Zone 1 heating status display - correctly shows HEATING when valve serves zone
- Blank icon button labels in thermostat cards for ATA and ATW

### Acknowledgments

Special thanks to [@pwa-2025](https://github.com/pwa-2025) and [@Alexxx1986](https://github.com/Alexxx1986) for providing guest building access, enabling real hardware testing and validation of ATW features.

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
