# LG ThinQ vs MELCloud Home Integration Comparison

This document compares the official Home Assistant LG ThinQ integration with our MELCloud Home custom integration to identify architectural patterns, best practices, and potential improvements.

**Last Updated:** 2025-11-19

---

## Quick Comparison Table

| Aspect | LG ThinQ (Official) | MELCloud Home (Custom) |
|--------|---------------------|------------------------|
| **Integration Type** | Core integration | Custom component |
| **API Client** | External PyPI package (`thinqconnect==1.0.8`) | Bundled in `api/` subfolder |
| **IoT Class** | `cloud_push` (MQTT + polling) | `cloud_polling` (polling only) |
| **Update Frequency** | Real-time via MQTT + periodic polling | 60-second polling (API rate limit) |
| **Coordinator Pattern** | One per device | Single coordinator for all devices |
| **Platforms** | 10 (climate, sensor, binary_sensor, switch, fan, number, select, event, vacuum, water_heater) | 3 (climate, sensor, binary_sensor) |
| **Authentication** | OAuth access token | Email/password with AWS Cognito |
| **Device Discovery** | DHCP discovery + cloud | Cloud only |
| **Preset Modes** | ✅ Yes | ❌ No (future) |
| **Horizontal Swing** | ✅ Yes (HA 2024.12+) | ✅ Yes (v1.2.0) |
| **Device-Specific Switches** | ✅ Yes (display light, jet mode, etc.) | ❌ No |

---

## Architecture Comparison

### API Client Management

**LG ThinQ:**
```python
# Uses external vendor-maintained SDK
requirements = ["thinqconnect==1.0.8"]

# SDK handles:
# - Token refresh
# - API endpoints
# - Error handling
# - Request/response models
```

**MELCloud Home:**
```python
# Bundled API client
custom_components/melcloudhome/
└── api/
    ├── auth.py        # AWS Cognito OAuth
    ├── client.py      # API client
    ├── models.py      # Data models
    ├── const.py       # Constants
    └── exceptions.py  # Custom exceptions

# No external dependencies
requirements = []
```

**Rationale:** We chose the bundled approach (see ADR-001) because:
- No official MELCloud Home SDK exists
- KISS/YAGNI principles
- Easier development and testing
- Can migrate to separate package later if needed

---

### Data Update Strategy

**LG ThinQ - Hybrid Push/Poll:**
```python
# Real-time MQTT updates
class ThinqData:
    coordinators: dict[str, DeviceDataUpdateCoordinator]
    mqtt: ThinQMQTTClient  # Push notifications

# Three update pathways:
# 1. Scheduled polling: _async_update_data()
# 2. MQTT push: handle_update_status()
# 3. Manual refresh: refresh_status()
```

**MELCloud Home - Polling Only:**
```python
# 60-second polling (API rate limit requirement)
class MELCloudHomeCoordinator(DataUpdateCoordinator[UserContext]):
    update_interval = timedelta(seconds=60)

    # Single update pathway:
    # 1. Scheduled polling: _async_update_data()
```

**Key Difference:**
- **LG**: Instant device state updates (< 1 second)
- **MELCloud**: Up to 60-second delay for state changes

**Future Enhancement:** Consider WebSocket/MQTT if MELCloud API supports it (see ADR-007).

---

### Coordinator Pattern

**LG ThinQ - Per-Device Coordinators:**
```python
# One coordinator per device
async def async_setup_coordinators(api: ThinQApi) -> dict[str, DeviceDataUpdateCoordinator]:
    coordinators = {}
    for device in await api.async_get_device_list():
        coordinator = DeviceDataUpdateCoordinator(hass, device, api)
        coordinators[device.device_id] = coordinator
    return coordinators

# Storage:
hass.data[DOMAIN][entry.entry_id] = ThinqData(
    coordinators=coordinators,
    mqtt=mqtt_client
)
```

**MELCloud Home - Single Coordinator:**
```python
# One coordinator for all devices
coordinator = MELCloudHomeCoordinator(hass, client, email, password)

# Single API call fetches all devices
context = await client.get_user_context()  # Returns all buildings + units

# O(1) cached lookups
coordinator._units[unit_id]
coordinator._unit_to_building[unit_id]

# Storage:
hass.data[DOMAIN][entry.entry_id] = coordinator
```

**Why Different:**
- **LG**: Per-device makes sense with MQTT (devices update independently)
- **MELCloud**: Single coordinator optimal for bulk API endpoint (`/user-context`)

---

### Error Handling & Authentication

**LG ThinQ:**
```python
# Setup
try:
    api = ThinQApi(entry.data[CONF_ACCESS_TOKEN])
except ThinQAPIException:
    raise ConfigEntryNotReady("API unavailable")

# Coordinator
try:
    data = await self.api.fetch_data()
except ThinQAPIException as e:
    raise UpdateFailed(e) from e

# Token refresh handled by thinqconnect SDK automatically
```

**MELCloud Home:**
```python
# Setup
try:
    await coordinator.async_config_entry_first_refresh()
except ConfigEntryAuthFailed:
    # Invalid credentials
    await client.close()
    raise
except Exception:
    raise ConfigEntryNotReady("Failed to fetch initial data")

# Coordinator - Automatic re-authentication
try:
    if not self.client.is_authenticated:
        await self.client.login(email, password)
    return await self.client.get_user_context()
except AuthenticationError:
    # Session expired - try once to re-authenticate
    await self.client.login(email, password)
    return await self.client.get_user_context()
```

**Key Difference:** We handle session expiration proactively with transparent retry (see ADR-002).

---

### Climate Entity Implementation

**LG ThinQ - Dynamic Features:**
```python
class ThinQClimateEntity(ThinQEntity, ClimateEntity):
    def __init__(self, coordinator, device):
        # Dynamic feature detection based on device capabilities
        self._attr_supported_features = 0
        if device.has_target_temp:
            self._attr_supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE
        if device.has_fan_mode:
            self._attr_supported_features |= ClimateEntityFeature.FAN_MODE
        # ... etc

        # Bidirectional mode conversion
        STR_TO_HVAC = {"cool": HVACMode.COOL, "heat": HVACMode.HEAT, ...}
        HVAC_TO_STR = {HVACMode.COOL: "cool", HVACMode.HEAT: "heat", ...}

    async def async_set_hvac_mode(self, hvac_mode):
        # Must turn on device first
        if hvac_mode != HVACMode.OFF:
            await self.coordinator.api.set_power(True)
        await self.coordinator.api.set_hvac_mode(HVAC_TO_STR[hvac_mode])
```

**MELCloud Home - Static Features:**
```python
class MELCloudHomeClimate(CoordinatorEntity, ClimateEntity):
    def __init__(self, coordinator, unit, building):
        # Static feature set (all Mitsubishi units similar)
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.SWING_MODE
            | ClimateEntityFeature.SWING_HORIZONTAL_MODE  # v1.2.0
        )

        # Static HVAC modes
        self._attr_hvac_modes = [
            HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL,
            HVACMode.AUTO, HVACMode.DRY, HVACMode.FAN_ONLY
        ]

    @property
    def hvac_action(self) -> HVACAction | None:
        """Infer HVAC action with hysteresis (±0.5°C)."""
        # Computed from temperature difference + mode
        # See climate.py:139-183 for full implementation
```

**Key Differences:**
1. **Presets:** LG supports preset modes (away, eco, boost) - we don't yet
2. **Feature Detection:** LG detects dynamically - we assume consistent hardware
3. **HVAC Action:** We infer heating/cooling/idle state - LG likely gets from API
4. **Horizontal Swing:** Both support vertical + horizontal swing modes (HA 2024.12+)
5. **Device-Specific Switches:** LG exposes device features as switches (display light, jet mode) - we don't yet

---

### Device Organization

**LG ThinQ:**
```python
# Flat structure: All devices at top level
devices = [
    "Washing Machine",
    "Dryer",
    "Refrigerator",
    "Air Conditioner",
    ...
]

# No explicit building/location hierarchy
# Each device is independent
```

**MELCloud Home:**
```python
# Hierarchical: Buildings → Units
class UserContext:
    buildings: list[Building]

class Building:
    id: str
    name: str
    air_to_air_units: list[AirToAirUnit]

# O(1) lookups via coordinator cache
coordinator.get_unit(unit_id)
coordinator.get_building_for_unit(unit_id)

# Device suggested_area = building.name
```

**Why Different:** MELCloud API provides explicit building hierarchy; LG devices are independent appliances.

---

### Platform Support

| Platform | LG ThinQ | MELCloud Home | Notes |
|----------|----------|---------------|-------|
| **Climate** | ✅ | ✅ | Core functionality |
| **Binary Sensor** | ✅ | ✅ (v1.2.0) | Error/connection monitoring |
| **Sensor** | ✅ | ✅ (v1.2.0) | Temperature, humidity, etc. |
| **Switch** | ✅ | ❌ | Could add power on/off switch |
| **Fan** | ✅ | ❌ | N/A (fan control via climate) |
| **Number** | ✅ | ❌ | Could add for fine-tune settings |
| **Select** | ✅ | ❌ | Alternative to dropdown modes |
| **Event** | ✅ | ❌ | No event-based notifications (polling) |
| **Vacuum** | ✅ | N/A | LG-specific device type |
| **Water Heater** | ✅ | N/A | LG-specific device type |

---

### Configuration Flow

**LG ThinQ:**
```python
# OAuth access token required
config_flow:
    step_user:
        - Get access token from LG portal
        - Select country code

# DHCP discovery support
dhcp:
    - macaddress: "34E6E6*"
```

**MELCloud Home:**
```python
# Email/password authentication
config_flow:
    step_user:
        - Email address
        - Password

# AWS Cognito OAuth handled transparently
# No DHCP discovery (cloud-only)
```

---

## Best Practices from LG ThinQ

### ✅ What We Should Consider Adopting

1. **Real-time Updates (High Priority)**
   - Current 60s polling feels sluggish
   - Investigate WebSocket/MQTT support in MELCloud API
   - See ADR-007 for research deferral rationale

2. **Preset Modes (Medium Priority)**
   - Common HVAC feature (away, eco, boost, sleep)
   - Check if MELCloud API supports presets
   - Would improve user experience

3. **Dynamic Feature Detection (Low Priority)**
   - More robust to device variations
   - Current static approach works for uniform hardware
   - Consider if expanding to different Mitsubishi models

4. **Additional Platforms (Low Priority)**
   - **Switch platform:** Simple power on/off
   - **Select platform:** Alternative to dropdown UI
   - **Number platform:** Fine-tune advanced settings

### ✅ What We're Already Doing Well

1. **Bundled API Client**
   - Simpler development
   - No external dependencies
   - Easier testing

2. **Building Hierarchy**
   - O(1) cached lookups
   - Better organization for multi-building setups
   - Automatic area suggestions

3. **Horizontal Swing Support**
   - Both integrations support vertical + horizontal swing (HA 2024.12+)
   - MELCloud and LG both expose independent vane controls
   - Both are early adopters of the new HA feature

4. **Transparent Session Management**
   - Automatic re-authentication
   - Seamless to users
   - Well-documented in ADR-002

5. **Single Coordinator**
   - Optimal for our API structure
   - Bulk fetch is more efficient
   - Simpler state management

---

## Performance Considerations

### Update Latency

| Event | LG ThinQ | MELCloud Home |
|-------|----------|---------------|
| User changes temp in app | < 1 second | Up to 60 seconds |
| HA automation runs | Instant | Instant (confirmed after action) |
| Device reaches target temp | < 1 second | Up to 60 seconds |

**Impact:** LG users get instant feedback; we have noticeable delay for external changes.

### Network Efficiency

**LG ThinQ:**
- MQTT persistent connection (minimal overhead)
- Polling only for fallback
- More network connections (MQTT + HTTP)

**MELCloud Home:**
- HTTP polling every 60s
- Single `/user-context` call fetches all devices
- Fewer connections, but periodic overhead

---

## Recommendations

### Short Term (v1.3)

1. ✅ **Add Preset Modes** (if API supports)
   - Check API for preset/schedule functionality
   - Map to HA preset modes
   - Update climate entity

2. ✅ **Document Horizontal Swing**
   - Already implemented in v1.2.0
   - Update README with HA 2024.12+ requirements
   - Show example card configurations

### Medium Term (v1.4)

3. ✅ **Investigate WebSocket/Push**
   - Research MELCloud API for WebSocket support
   - Could reduce latency from 60s to < 1s
   - See ADR-007 for current deferral

4. ✅ **Add Switch Platform**
   - Simple on/off toggle
   - Easier for basic automations
   - Mirrors climate.set_hvac_mode(off/heat)

### Long Term (v2.0)

5. ✅ **Dynamic Feature Detection**
   - If expanding to other Mitsubishi models
   - More robust to device variations
   - Would require API capability discovery

6. ✅ **Per-Device Coordinators**
   - Only if we implement WebSocket/push updates
   - Would allow independent device updates
   - More complex, only worth it with push notifications

---

## Architecture Decision Alignment

Our architectural decisions remain sound compared to LG ThinQ:

- **ADR-001 (Bundled API):** ✅ Still appropriate (no official SDK)
- **ADR-002 (Auth Refresh):** ✅ Better than LG (more transparent)
- **ADR-003 (Entity Naming):** ✅ Stable, works well
- **ADR-004 (Refactoring):** ✅ Clean separation maintained
- **ADR-005 (Divergence from Official):** ✅ Confirmed - we target different API
- **ADR-007 (Defer WebSocket):** ✅ Still valid - defer until v1.3+

---

## Example: LG ThinQ Dashboard Configuration

For reference, here's a working LG ThinQ configuration showing advanced features:

```yaml
square: false
type: grid
columns: 1
cards:
  - type: thermostat
    entity: climate.office_a_c
    features:
      - type: climate-hvac-modes
        hvac_modes:
          - "off"
          - heat
          - dry
          - cool
          - fan_only
          - heat_cool
      - type: climate-fan-modes
        style: dropdown
      - type: climate-swing-modes
        style: dropdown
      - type: climate-swing-horizontal-modes
        style: dropdown
    show_current_as_primary: false
    name: Mode
  - type: entities
    entities:
      - entity: switch.office_a_c_display_light
        name: Display light
      - entity: switch.office_a_c_jet_mode
        name: Jet mode
    state_color: true
title: Aircon
```

**Notable Features:**
- Both vertical and horizontal swing modes (HA 2024.12+)
- Device-specific switches (display light, jet mode)
- Custom HVAC mode selection
- Dropdown style for multi-option controls

---

## Conclusion

The MELCloud Home integration follows similar patterns to official integrations like LG ThinQ while making appropriate choices for our specific API and use case:

**Strengths:**
- ✅ Clean architecture with bundled API client
- ✅ Efficient single-coordinator pattern
- ✅ Horizontal swing support (same as LG ThinQ)
- ✅ Transparent session management

**Opportunities:**
- 🔄 Real-time updates (if API supports WebSocket)
- 🔄 Preset modes (if API supports)
- 🔄 Additional platforms (switch for device features, select)
- 🔄 Device-specific switches (inspired by LG's display light, jet mode)

Overall, our integration is well-architected and compares favorably to official HA integrations. The main limitation is polling-based updates, which is an API constraint rather than an implementation issue.

---

## References

- LG ThinQ Integration: https://github.com/home-assistant/core/tree/dev/homeassistant/components/lg_thinq
- HA Climate Entity: https://developers.home-assistant.io/docs/core/entity/climate/
- HA 2024.12 Horizontal Swing: https://developers.home-assistant.io/blog/2024/12/03/climate-horizontal-swing/
- Our ADRs: `docs/decisions/`
