# MELCloud Home Integration

Custom Home Assistant integration for Mitsubishi Electric MELCloud Home heat pumps.

## Features

- ✅ Full climate control (HVAC modes, temperature, fan speed, swing)
- ✅ 60-second automatic polling
- ✅ Auto re-authentication on session expiry
- ✅ Standard Home Assistant climate entity
- ✅ Multi-device support
- ✅ Device registry with building context
- ✅ Works with automations, scripts, and voice assistants
- ✅ Diagnostics support for troubleshooting
- ✅ Custom integration icon

---

## Installation

### Via HACS (Recommended - Coming Soon)
1. Open HACS
2. Go to Integrations
3. Click "+ Explore & Download Repositories"
4. Search for "MELCloud Home"
5. Click "Download"
6. Restart Home Assistant

### Manual Installation
1. Copy the `melcloudhome` folder to `custom_components/`
2. Restart Home Assistant
3. Go to Configuration → Integrations
4. Click "+ Add Integration"
5. Search for "MELCloud Home"

---

## Setup

### Add Integration

1. **Configuration → Integrations**
2. Click **"+ Add Integration"**
3. Search for **"MELCloud Home"**
4. Enter your MELCloud credentials:
   - Email: Your MELCloud Home account email
   - Password: Your MELCloud Home password
5. Click **"Submit"**

The integration will:
- Authenticate with MELCloud Home
- Discover all your devices automatically
- Create climate entities for each heat pump
- Set up device registry with building names

### Entity Names

**Stable Entity IDs:** Entity IDs are generated from the MELCloud Home unit ID (not the room name), ensuring they remain stable even if you rename buildings or rooms in MELCloud Home.

**Format:** `climate.melcloud_[first4]_[last4]`

The entity ID uses the first 4 and last 4 characters of the unit's UUID from the MELCloud Home API. This ensures:
- ✅ **Stability** - IDs never change, even if you rename rooms or buildings
- ✅ **Traceability** - Can be matched back to API unit IDs for debugging
- ✅ **Uniqueness** - Each device has a unique, deterministic ID

**Examples:**
- Unit ID: `0efce33f-5847-4042-88eb-aaf3ff6a76db` → Entity: `climate.melcloud_0efc_76db`
- Unit ID: `bf8d1e84-95cc-44d8-ab9b-25b87a945119` → Entity: `climate.melcloud_bf8d_5119`

**Friendly Names:** The device name shows the friendly building + room name (e.g., "Orchard Cottage Dining Room"). You can also customize entity friendly names in the Home Assistant UI without affecting the stable entity ID.

---

## Dashboard Setup

### ⚠️ Important: Use the Thermostat Card

**Common Mistake:**
When adding climate entities to your dashboard, **DO NOT** search for the entity name directly. This will add a generic entity card that only shows the current temperature.

**Correct Method:**

1. **Edit Dashboard** (click pencil icon, top right)
2. Click **"+ ADD CARD"**
3. Search for: **"thermostat"** (the card type, not your entity!)
4. Select **"Thermostat"** from the results
5. Choose your climate entity
6. Click **"SAVE"**

### What You'll Get

✅ **Thermostat Card** (Correct)
- Full HVAC mode controls (Heat, Cool, Auto, Dry, Fan, Off)
- Large temperature display
- Target temperature with +/- buttons
- Fan speed dropdown (Auto, One-Five)
- Swing mode dropdown (vane positions)

❌ **Entity Card** (Wrong - Don't Use)
- Only shows current temperature
- No controls

### YAML Configuration

If you prefer YAML:

```yaml
type: thermostat
entity: climate.home_dining_room_heatpump
```

**With multiple devices:**
```yaml
type: entities
title: Climate Control
entities:
  - type: thermostat
    entity: climate.home_dining_room_heatpump
  - type: thermostat
    entity: climate.home_bedroom_heatpump
```

---

## Using in Automations

### Set HVAC Mode

```yaml
service: climate.set_hvac_mode
target:
  entity_id: climate.home_dining_room_heatpump
data:
  hvac_mode: heat  # Options: heat, cool, auto, dry, fan_only, off
```

### Set Temperature

```yaml
service: climate.set_temperature
target:
  entity_id: climate.home_dining_room_heatpump
data:
  temperature: 21.5  # Range: 10-31°C in 0.5° increments
```

### Set Fan Speed

```yaml
service: climate.set_fan_mode
target:
  entity_id: climate.home_dining_room_heatpump
data:
  fan_mode: "Three"  # Options: Auto, One, Two, Three, Four, Five
```

### Set Swing Mode

```yaml
service: climate.set_swing_mode
target:
  entity_id: climate.home_dining_room_heatpump
data:
  swing_mode: "Auto"  # Options: Auto, Swing, One, Two, Three, Four, Five
```

### Example Automation

**Turn on heating when temperature drops:**
```yaml
automation:
  - alias: "Heat Pump - Morning Warmup"
    trigger:
      - platform: time
        at: "06:00:00"
    condition:
      - condition: numeric_state
        entity_id: climate.home_dining_room_heatpump
        attribute: current_temperature
        below: 20
    action:
      - service: climate.set_hvac_mode
        target:
          entity_id: climate.home_dining_room_heatpump
        data:
          hvac_mode: heat
      - service: climate.set_temperature
        target:
          entity_id: climate.home_dining_room_heatpump
        data:
          temperature: 22
```

---

## Common Issues

### ❌ "Entity does not support action climate.turn_on"

**Problem:** Climate entities don't have `turn_on`/`turn_off` services.

**Solution:** Use `climate.set_hvac_mode` instead:

```yaml
# Wrong:
service: climate.turn_on

# Correct:
service: climate.set_hvac_mode
data:
  hvac_mode: heat
```

This is standard Home Assistant behavior for ALL climate integrations (Nest, Ecobee, etc.).

### ❌ Dashboard only shows temperature

**Problem:** You added the entity directly instead of using the thermostat card.

**Solution:** See [Dashboard Setup](#dashboard-setup) above.

### ❌ Integration not appearing

**Problem:** Integration files not in the correct location.

**Solution:**
1. Verify files are in `custom_components/melcloudhome/`
2. Restart Home Assistant
3. Check logs for errors: Configuration → Logs

---

## Supported Features

### HVAC Modes
- **Heat** - Heating mode
- **Cool** - Cooling mode
- **Auto** - Automatic mode (switches between heat/cool)
- **Dry** - Dehumidifier mode
- **Fan Only** - Fan without heating/cooling
- **Off** - Device off

### Temperature Control
- Range: 10-31°C
- Precision: 0.5°C increments
- Shows current and target temperature

### Fan Speeds
- Auto (device chooses optimal speed)
- One (lowest)
- Two
- Three
- Four
- Five (highest)

### Swing Modes (Vane Positions)
- Auto (device chooses optimal position)
- Swing (oscillating)
- One through Five (fixed positions)

---

## Device Information

Each heat pump appears as a device with:
- **Manufacturer:** Mitsubishi Electric
- **Model:** Air-to-Air Heat Pump (via MELCloud Home)
- **Suggested Area:** Building name from MELCloud
- **Identifiers:** Unit ID from MELCloud API

---

## Polling & Updates

- **Update Interval:** 60 seconds
- **Manual Refresh:** State updates after each control action
- **Authentication:** Automatically refreshes on session expiry
- **Offline Handling:** Entities become unavailable if device offline

---

## Troubleshooting

### Download Diagnostics

Get detailed diagnostic information for bug reports:

1. **Configuration → Integrations**
2. Find **"MELCloud Home"**
3. Click the **three dots menu** (⋮)
4. Select **"Download diagnostics"**
5. Save the JSON file

The diagnostics file contains:
- Integration configuration (with credentials redacted)
- Entity states and attributes
- Coordinator status
- Device information (units, buildings, capabilities)

**Privacy:** Email and password are automatically removed before export.

### View Logs

**Via UI:**
Configuration → Logs → Filter by "melcloudhome"

**Via SSH:**
```bash
ssh ha "sudo docker logs -f homeassistant" | grep melcloudhome
```

### Common Log Messages

**INFO: Authentication successful**
✅ Normal - Integration authenticated successfully

**WARNING: Update failed**
⚠️ Temporary network issue - will retry automatically

**ERROR: Authentication failed**
❌ Invalid credentials - check email/password

---

## Credits

- **Author:** @ablake
- **API:** Unofficial MELCloud Home API client
- **Hardware:** Mitsubishi Electric heat pumps
- **Platform:** Home Assistant

---

## Support

- **Issues:** Report bugs at [GitHub Issues](https://github.com/ablake/home-automation/issues)
- **Documentation:** See `_claude/` folder for API documentation
- **Updates:** Check GitHub for new releases

---

## Legal Notice

This is an **unofficial** third-party integration. It is not affiliated with, endorsed by, or supported by Mitsubishi Electric. Use at your own risk.

The integration uses the MELCloud Home web API in the same way the official web interface does. No reverse engineering or unauthorized access is performed.

---

## License

MIT License - See LICENSE file for details

---

## Version History

### v1.1.0 (2025-11-17)
- ✅ Added diagnostics support for troubleshooting
- ✅ Added custom integration icon (heat pump MDI icon)
- ✅ Updated documentation with diagnostics guide

### v1.0.0 (2025-11-17)
- ✅ Initial release
- ✅ Full climate control support
- ✅ Auto re-authentication
- ✅ Multi-device support
- ✅ Standard HA climate entity
