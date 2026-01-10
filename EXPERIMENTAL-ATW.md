# ⚠️ Experimental: Air-to-Water (ATW) Heat Pump Support

**Status:** EXPERIMENTAL - Not tested on real hardware
**Based On:** HAR captures from user's MELCloud Home web interface
**Version:** v2.0.0-beta.1 (beta pre-release)
**Last Updated:** 2026-01-06

---

## Important Warnings

🚨 **ATW support is EXPERIMENTAL and has NOT been tested on real Ecodan hardware.**

- Implementation based on reverse-engineered API from HAR (HTTP Archive) captures
- No guarantees of correctness or safety
- May cause unexpected behavior or errors
- Not recommended for production use without thorough testing

**USE AT YOUR OWN RISK**

---

## What's Implemented (v2.0.0)

### Implementation Status

| Feature | Status | Testing |
|---------|--------|---------|
| Zone 1 climate control | ✅ Implemented | ⚠️ HAR only (not tested on hardware) |
| DHW tank control (water heater) | ✅ Implemented | ⚠️ HAR only (not tested on hardware) |
| System power control (switch) | ✅ Implemented | ⚠️ HAR only (not tested on hardware) |
| Temperature sensors (Zone 1, tank) | ✅ Implemented | ⚠️ HAR only (not tested on hardware) |
| Operation status sensor | ✅ Implemented | ⚠️ HAR only (not tested on hardware) |
| Binary sensors (error, connection, forced DHW) | ✅ Implemented | ⚠️ HAR only (not tested on hardware) |
| Preset modes (Room/Flow/Curve) | ✅ Implemented | ⚠️ HAR only (not tested on hardware) |
| Zone 2 support | ❌ Not implemented | Single zone systems only |
| Energy monitoring | ❌ Not available | ATA-only feature |

---

## Implementation Target Hardware

Based on HAR analysis from one user system:

- Mitsubishi Electric Ecodan heat pumps
- EHSCVM2D Hydrokit (HAR data from Discussion #26)
- FTC controllers with `ftcModel: 3` in API (physical model unknown)

**User's test system (Discussion #26):**

- Model: Ecodan EHSCVM2D Hydrokit
- API reports: `ftcModel: 3` (physical FTC controller model not confirmed)
- Zones: Single zone + DHW

---

## How to Test (Call for Testers!)

### Prerequisites

- Mitsubishi Electric Ecodan heat pump with FTC controller
- Existing MELCloud Home account with ATW system
- Willingness to monitor system behavior closely
- Ability to revert to previous integration version if needed

### Testing Steps

1. **Backup Current Setup**

   ```bash
   # Take snapshot of Home Assistant config
   # Note current entity IDs and automations
   ```

2. **Install Experimental Version**

   ```bash
   # Via HACS or manual installation
   # Version v2.0.0 or later
   ```

3. **Monitor Closely**
   - Check entity creation (climate, water_heater, switch, sensors)
   - Test manual controls in small increments
   - Verify physical device responds as expected
   - Watch for errors in HA logs

4. **Report Findings**
   - GitHub Issues: [melcloudhome/issues](https://github.com/andrew-blake/melcloudhome/issues)
   - Include: Hardware model, FTC version, entity IDs, logs
   - Describe any unexpected behavior

### What to Test

> **Entity ID Format:** All entities use pattern `{domain}.melcloudhome_{short_id}_{entity_name}`
> The short_id is derived from device UUID (first 4 + last 4 chars). Example: `melcloudhome_bf8d_5119`

#### Climate Entity (Zone 1)
- [ ] **Entity ID**: `climate.melcloudhome_{short_id}_zone_1`
  - Example: `climate.melcloudhome_bf8d_5119_zone_1`
- [ ] Temperature setting (10-30°C range)
- [ ] Preset mode changes (heating strategies):
  - [ ] **Room** (Recommended) - Maintains room at target temp (like a thermostat)
  - [ ] **Flow** (Advanced) - Directly controls heating water temperature
  - [ ] **Curve** (Advanced) - Auto-adjusts based on outdoor temperature
- [ ] HVAC mode:
  - [ ] `HEAT` - Turn on system and enable Zone 1 heating
  - [ ] `OFF` - Turn off entire system (delegates to switch)

#### Water Heater Entity (DHW Tank)
- [ ] **Entity ID**: `water_heater.melcloudhome_{short_id}_tank`
  - Example: `water_heater.melcloudhome_bf8d_5119_tank`
- [ ] Tank temperature setting (40-60°C range)
- [ ] Operation mode changes:
  - [ ] `Auto` - DHW heats automatically when below target
  - [ ] `Force DHW` - Force immediate DHW heating (priority mode)
- [ ] **Important**: Water heater does NOT have turn_on/turn_off methods (power state is read-only)
- [ ] Verify operation_status attribute shows valve position

#### Switch Entity (System Power)
- [ ] **Entity ID**: `switch.melcloudhome_{short_id}_system_power`
  - Example: `switch.melcloudhome_bf8d_5119_system_power`
- [ ] Turn on system power
- [ ] Turn off system power
- [ ] **Note**: Both climate OFF and switch OFF control the same system power (by design)

#### Sensors
- [ ] **Zone 1 Temperature**: `sensor.melcloudhome_{short_id}_zone_1_temperature`
  - Example: `sensor.melcloudhome_bf8d_5119_zone_1_temperature`
  - Verify reading matches physical thermostat display
- [ ] **Tank Temperature**: `sensor.melcloudhome_{short_id}_tank_temperature`
  - Example: `sensor.melcloudhome_bf8d_5119_tank_temperature`
  - Verify reading matches DHW tank display
- [ ] **Operation Status**: `sensor.melcloudhome_{short_id}_operation_status`
  - Example: `sensor.melcloudhome_bf8d_5119_operation_status`
  - Values: "Stop", "HotWater", "HeatRoomTemperature", etc.
  - Shows current 3-way valve position

#### Binary Sensors
- [ ] **Error State**: `binary_sensor.melcloudhome_{short_id}_error_state`
  - Example: `binary_sensor.melcloudhome_bf8d_5119_error_state`
- [ ] **Connection**: `binary_sensor.melcloudhome_{short_id}_connection_state`
  - Example: `binary_sensor.melcloudhome_bf8d_5119_connection_state`
- [ ] **Forced DHW Active**: `binary_sensor.melcloudhome_{short_id}_forced_dhw_active`
  - Example: `binary_sensor.melcloudhome_bf8d_5119_forced_dhw_active`

#### System Behavior
- [ ] Multi-hour operation: Check for stability over time
- [ ] 3-way valve switching: Verify system alternates between Zone 1 and DHW as needed
- [ ] Force DHW mode: Verify Zone 1 heating suspends when DHW has priority
- [ ] Error conditions: How system handles connection losses

---

## Troubleshooting

### Integration Won't Load

- Check Home Assistant logs: `Settings > System > Logs`
- Look for "melcloudhome" errors
- Verify MELCloud Home credentials are correct

### Entities Not Appearing

- Confirm device type is ATW in MELCloud Home app
- Check integration device list in HA
- Reload integration: `Settings > Devices & Services > MELCloud Home > Reload`

### Unexpected Behavior

- **IMMEDIATELY REVERT** to previous integration version
- Report issue on GitHub with full logs
- Monitor physical device behavior closely

---

## Development Status

### Completed (v2.0.0)

- ✅ ATW API client implementation
- ✅ Zone 1 climate platform
- ✅ Water heater platform (DHW)
- ✅ Switch platform (system power)
- ✅ Sensor platform (temperatures, WiFi, errors)
- ✅ Mock API server for development
- ✅ Integration tests (mock-based)

### Help Wanted

**Have hardware?**
- Test with real Ecodan systems
- Capture HAR files from different FTC controllers
- Report entity behavior and UX feedback

**Want to help without hardware?**
- Use our reverse engineering tools to understand API behavior
- Analyze HAR captures from users
- Contribute to API documentation
- **See:** [tools/reverse-engineering/](tools/reverse-engineering/) for Chrome override and request proxying tools

---

## Disclaimer

This integration is provided "AS IS" without warranty of any kind. The author(s) are not responsible for any damage to equipment or property resulting from use of this experimental feature.

Use of this integration with ATW systems is entirely at your own risk.

---

## Contact & Support

- **GitHub Issues:** <https://github.com/andrew-blake/melcloudhome/issues>
- **Documentation:** See README.md for general integration info
- **API Reference:** docs/api/atw-api-reference.md

**Please clearly label all ATW-related issues as "experimental ATW"**

---

## See Also

- **[README.md](README.md)** - General integration overview and installation
- **[SUPPORTED_DEVICES.md](SUPPORTED_DEVICES.md)** - Hardware compatibility and tested models
- **[docs/api/atw-api-reference.md](docs/api/atw-api-reference.md)** - Complete ATW API specification
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - How to report findings and contribute
