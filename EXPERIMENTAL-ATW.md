# ⚠️ Experimental: Air-to-Water (ATW) Heat Pump Support

**Status:** EXPERIMENTAL - Not tested on real hardware
**Based On:** HAR captures from user's MELCloud Home web interface
**Version:** v2.0.0+
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

## What's Implemented

### Tested via HAR Captures
- ✅ Zone 1 climate control (read/write)
- ✅ DHW tank control via water heater platform (read/write)
- ✅ System power control via switch platform
- ✅ Temperature sensors (tank, flow, return, DHW flow)
- ✅ WiFi signal and error sensors
- ✅ Preset modes (Room, Flow, Curve)

### Known Limitations
- ❌ Not tested on real hardware
- ❌ Zone 2 support not yet implemented (planned)
- ❌ Some advanced features may be missing
- ❌ Error handling may be incomplete
- ❌ API behavior might differ from actual hardware

---

## Compatible Hardware (Theoretical)

Based on HAR analysis, should work with:
- Mitsubishi Electric Ecodan heat pumps
- FTC6 controllers (confirmed in HARs)
- FTC4/FTC5 controllers (likely compatible)
- EHSCVM2D Hydrokit (confirmed in HARs)

**User's test system:**
- Model: Ecodan EHSCVM2D Hydrokit
- Controller: FTC6
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

- [ ] Climate entity: Temperature setting, mode changes, preset modes
- [ ] Water heater: Tank temperature, operation modes (Auto/Force DHW)
- [ ] Switch: System power on/off
- [ ] Sensors: Verify readings match physical display
- [ ] Multi-hour operation: Check for stability over time
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

### Planned (Future Versions)

- ⏳ Zone 2 climate support
- ⏳ Real hardware validation
- ⏳ Advanced features (holiday mode, etc.)
- ⏳ Energy consumption tracking for ATW

### Help Wanted

- Hardware testers with Ecodan systems
- HAR captures from different FTC models
- Feedback on entity behavior and UX

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
