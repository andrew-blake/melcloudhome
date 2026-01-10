# Session 9: Research Findings

## Pre-v1.2 Review - MELCloud, Climate Best Practices, and HACS

**Date:** 2025-11-17
**Session:** 9 of project development
**Status:** Research Complete

---

## Executive Summary

### Critical Insights

1. **Your implementation is MORE modern than the official MELCloud integration**
   - Official uses deprecated `@Throttle` decorator
   - Official lacks `DataUpdateCoordinator`
   - Your architecture is objectively superior

2. **Adopt sensor patterns, NOT architecture from MELCloud**
   - ✅ Entity description pattern - Adopt
   - ✅ Sensor types - Reference for ideas
   - ❌ Overall architecture - Don't copy

3. **HACS requires separate repository**
   - Current monorepo structure incompatible
   - Need dedicated `melcloudhome` repository
   - 7-9 hours setup time

### Top Recommendations

| Priority | Recommendation | Effort | Impact |
|----------|---------------|--------|---------|
| HIGH | Add sensor platform with entity descriptions | 4-6h | Statistics & history |
| HIGH | Implement WebSocket with event-driven updates | 4-6h | Real-time control |
| HIGH | Create HACS-compatible repository | 7-9h | User adoption |
| MEDIUM | Add binary sensors for errors | 2h | Automation triggers |
| LOW | Create brand assets for HA | 2-4h | Professional appearance |

---

## Part 1: Legacy MELCloud Integration Analysis

### Repository Location
<https://github.com/home-assistant/core/tree/master/homeassistant/components/melcloud>

### Architecture Assessment

**MELCloud Official:**

```
❌ Uses @Throttle decorator (deprecated since 2021)
❌ No DataUpdateCoordinator
❌ Individual entity updates (O(n) per update cycle)
❌ No centralized error handling
⚠️ Partially uses entity descriptions
✅ Good sensor platform structure
✅ Proper device classes
```

**Your Implementation:**

```
✅ DataUpdateCoordinator (modern pattern)
✅ Centralized updates (single API call)
✅ O(1) cached device lookups
✅ Proper error handling with ConfigEntryAuthFailed
✅ Full type hints with mypy
✅ ADR documentation
✅ Lazy imports documented
```

**Verdict:** **Your architecture is objectively better. Do NOT adopt MELCloud's patterns.**

### What to Adopt: Sensor Entity Descriptions

MELCloud uses a clean pattern for sensor definitions:

```python
@dataclass
class MelcloudSensorEntityDescription(SensorEntityDescription):
    """Sensor entity description with value extraction."""
    value_fn: Callable[[Device], float | None]
    enabled: Callable[[Device], bool] = lambda x: True

SENSOR_TYPES = [
    MelcloudSensorEntityDescription(
        key="room_temperature",
        translation_key="room_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.room_temperature,
    ),
]
```

**Adoption Plan:**

- ✅ Use this exact pattern for v1.2 sensors
- ✅ Create `sensor.py` with entity descriptions
- ✅ Add room temperature sensor (for statistics)
- ✅ Add energy consumption sensor (if API supports)

### What to Avoid: Custom Services

MELCloud provides custom services for vane control:

```yaml
set_vane_horizontal:
  description: "Set horizontal vane position"
```

**Assessment:**

- ❌ Duplicates climate entity functionality
- ❌ Legacy pattern (modern approach uses climate entity features)
- ❌ No compelling user value

**Decision:** Do NOT add custom vane services.

### Sensors from MELCloud

| Sensor | Device Class | State Class | Priority for v1.2 |
|--------|-------------|-------------|-------------------|
| Room Temperature | TEMPERATURE | MEASUREMENT | HIGH |
| Energy Consumed | ENERGY | TOTAL_INCREASING | MEDIUM |
| WiFi Signal | SIGNAL_STRENGTH | MEASUREMENT | LOW |

---

## Part 2: Modern Climate Integration Best Practices

### Research Sources

- Ecobee Integration (Gold-tier)
- Nest Integration (Platinum-tier)
- Home Assistant Climate Entity Documentation
- Integration Quality Scale Guidelines

### Pattern: DataUpdateCoordinator ✅

**Modern Standard:**

```python
class MyCoordinator(DataUpdateCoordinator[MyDataType]):
    async def _async_update_data(self) -> MyDataType:
        try:
            return await self.client.get_data()
        except AuthError as err:
            raise ConfigEntryAuthFailed from err
        except ApiError as err:
            raise UpdateFailed(f"Error: {err}") from err
```

**Your Status:** ✅ Already using this pattern correctly

### Pattern: Event-Driven Updates (Nest)

**WebSocket Pattern:**

```python
def __init__(self, device):
    self._device = device
    # Subscribe to device updates
    self._device.add_update_listener(self.async_write_ha_state)
```

**Benefits:**

- Instant updates (< 1 second latency)
- No polling delay
- Lower API load
- Better user experience

**v1.2 Application:**

```python
async def _handle_websocket_message(self, message: dict):
    """Handle WebSocket message."""
    # Update coordinator data
    self.coordinator.async_set_updated_data(new_data)
    # All entities auto-update via coordinator
```

### Pattern: Feature Detection ✅

**Dynamic Capabilities:**

```python
@property
def supported_features(self) -> ClimateEntityFeature:
    features = ClimateEntityFeature.TARGET_TEMPERATURE

    if device.capabilities.has_fan:
        features |= ClimateEntityFeature.FAN_MODE

    return features
```

**Your Status:** ✅ Already doing this correctly (climate.py:169)

### Climate Entity Requirements Compliance

**Mandatory Implementation:**

- ✅ `hvac_mode` - Current operation mode (climate.py:128)
- ✅ `hvac_modes` - Available modes (climate.py:89-96)
- ✅ `temperature_unit` - Celsius/Fahrenheit (climate.py:53)
- ✅ `current_temperature` - Current reading (climate.py:137)
- ✅ `target_temperature` - Setpoint (climate.py:143)
- ✅ `async_set_hvac_mode()` - Change mode (climate.py:189)
- ✅ `async_set_temperature()` - Change setpoint (climate.py:203)

**Optional but Implemented:**

- ✅ `fan_mode` / `async_set_fan_mode()` (climate.py:149, 225)
- ✅ `swing_mode` / `async_set_swing_mode()` (climate.py:155, 236)
- ✅ `supported_features` - Feature flags (climate.py:169)
- ✅ `min_temp` / `max_temp` - Limits (climate.py:55, 161)

**Verdict:** ✅ Your climate implementation is fully compliant and modern

### Best Practice: Timeout Protection

**Recommendation:** Add timeout protection to API calls:

```python
from homeassistant.helpers import aiohttp_client

# In API client
self._session = aiohttp_client.async_get_clientsession(hass)
timeout = aiohttp.ClientTimeout(total=10)
```

**Status:** ⚠️ Not currently implemented - consider for v1.2

---

## Part 3: HACS Distribution Requirements

### Critical Finding: Monorepo Not Supported

**Current Structure:** ❌ Not HACS compatible

```
home-automation/
├── custom_components/melcloudhome/
├── tests/
├── docs/
├── _claude/
└── [HA config files]
```

**Required Structure:** ✅ HACS compatible

```
melcloudhome/                      # Dedicated repo
├── .github/workflows/
│   ├── validate.yml               # HACS + Hassfest
│   └── lint.yml
├── custom_components/
│   └── melcloudhome/             # Single integration
├── hacs.json                     # REQUIRED
├── README.md                     # REQUIRED
└── LICENSE                       # REQUIRED
```

### Required Files

#### 1. `hacs.json` (Root Directory)

```json
{
  "name": "MELCloud Home",
  "homeassistant": "2024.1.0",
  "hacs": "2.0.0"
}
```

#### 2. `manifest.json` Updates

Your current manifest is already compliant! Just update URLs:

```json
{
  "domain": "melcloudhome",
  "name": "MELCloud Home",
  "codeowners": ["@ablake"],
  "config_flow": true,
  "documentation": "https://github.com/andrew-blake/melcloudhome",
  "issue_tracker": "https://github.com/andrew-blake/melcloudhome/issues",
  "version": "1.1.2"
}
```

#### 3. GitHub Actions Validation

**Required Workflow:** `.github/workflows/validate.yml`

```yaml
name: Validate
on: [push, pull_request]

jobs:
  validate-hassfest:
    runs-on: "ubuntu-latest"
    steps:
      - uses: "actions/checkout@v4"
      - uses: "home-assistant/actions/hassfest@master"

  validate-hacs:
    runs-on: "ubuntu-latest"
    steps:
      - uses: "actions/checkout@v4"
      - uses: "hacs/action@main"
        with:
          category: "integration"
          ignore: "brands"
```

### Release Requirements

**CRITICAL:** HACS requires **GitHub Releases**, not just tags.

```bash
# Create tag
git tag -a v1.1.2 -m "Release v1.1.2"
git push origin v1.1.2

# THEN create GitHub Release via UI
# - Choose tag: v1.1.2
# - Title: v1.1.2 - Description
# - Body: Changelog
# - Publish release
```

### HACS Submission Checklist

**Pre-submission:**

- [ ] Repository is public on GitHub
- [ ] At least one GitHub Release published
- [ ] `hacs.json` in repository root
- [ ] `manifest.json` includes all required fields
- [ ] README.md with installation instructions
- [ ] GitHub Actions passing (HACS + Hassfest)
- [ ] Test installation as custom repository

**Submission Process:**

1. Fork `hacs/default` repository
2. Edit `integration` file (add alphabetically):

   ```json
   "melcloudhome": "andrew-blake/melcloudhome"
   ```

3. Create PR
4. Wait for review (weeks to months)

### Brand Assets (Optional but Recommended)

Create PNG icons for professional appearance:

- `icon.png` - 256×256px
- `icon@2x.png` - 512×512px
- `logo.png` - 128-256px
- `logo@2x.png` - 256-512px

Submit to `home-assistant/brands` repository.

### Migration Timeline

| Task | Time |
|------|------|
| Create new repository | 30 min |
| Add HACS files | 1 hour |
| Update README | 1 hour |
| Set up GitHub Actions | 30 min |
| Test validation | 30 min |
| Create first release | 15 min |
| Test installation | 1 hour |
| Create brand assets | 2-4 hours |
| **Total** | **7-9 hours** |
| **Approval wait** | **Weeks-months** |

---

## Part 4: v1.2 Implementation Recommendations

### DO These Things ✅

#### 1. Add Sensor Platform (HIGH PRIORITY)

**Implementation:**

```python
# sensor.py
@dataclass
class MELCloudHomeSensorEntityDescription(SensorEntityDescription):
    value_fn: Callable[[AirToAirUnit], float | None]
    available_fn: Callable[[AirToAirUnit], bool] = lambda x: True

SENSOR_TYPES = (
    MELCloudHomeSensorEntityDescription(
        key="room_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda unit: unit.room_temperature,
    ),
    # Energy, WiFi signal, etc.
)
```

**Sensors to Add:**

| Sensor | Priority | Rationale |
|--------|----------|-----------|
| Room Temperature | HIGH | Statistics/history |
| Energy Consumed | MEDIUM | Energy tracking |
| WiFi Signal | LOW | Diagnostics |

**Effort:** 4-6 hours

#### 2. Implement WebSocket Updates (HIGH PRIORITY)

**Pattern:**

```python
# coordinator.py
async def _websocket_loop(self):
    while True:
        try:
            message = await self._websocket.receive_json()
            await self._handle_message(message)
        except Exception as err:
            _LOGGER.error("WebSocket error: %s", err)
            await asyncio.sleep(5)

async def _handle_message(self, message: dict):
    updated_data = self._merge_ws_update(self.data, message)
    self.async_set_updated_data(updated_data)
```

**Benefits:**

- < 1 second update latency
- Real-time state changes
- Lower API load

**Effort:** 4-6 hours

#### 3. Create HACS Repository (HIGH PRIORITY)

**Steps:**

1. Create `andrew-blake/melcloudhome` repository
2. Copy integration files
3. Add `hacs.json`, workflows, updated README
4. Create v1.1.2 release
5. Test as custom repository
6. Submit to HACS default

**Effort:** 7-9 hours

#### 4. Add Binary Sensors (MEDIUM PRIORITY)

**Sensors:**

- Error state (device_class: PROBLEM)
- Connection state (device_class: CONNECTIVITY)

**Use Case:** Automation triggers when device errors occur

**Effort:** 2 hours

### DON'T Do These Things ❌

#### 1. Don't Refactor to Match MELCloud

- Their architecture is older/deprecated
- Your patterns are more modern
- No benefit to downgrading

#### 2. Don't Add Custom Vane Services

- Climate entity already handles vanes
- Unnecessary duplication
- No user value

#### 3. Don't Remove Coordinator

- MELCloud uses deprecated `@Throttle`
- Your approach is superior
- Better error handling

#### 4. Don't Change Entity Naming

- UUID-based IDs are stable
- Current strategy is optimal
- No need to match MELCloud

---

## Part 5: Architectural Decisions

### ADR-005: Divergence from Official MELCloud Integration

**Decision:** Maintain current modern architecture; do NOT adopt MELCloud patterns.

**Rationale:**

1. MELCloud uses deprecated `@Throttle` decorator (pre-2021 pattern)
2. MELCloud lacks `DataUpdateCoordinator` (introduced 2020)
3. Our architecture is objectively more modern and performant
4. MELCloud's individual entity updates are inefficient (O(n))
5. Our centralized coordinator provides better error handling

**Consequences:**

- ✅ Better performance (O(1) vs O(n) lookups)
- ✅ More reliable error handling
- ✅ Follows 2024 best practices
- ⚠️ Code diverges from official integration
- ✅ Better positioned for future HA versions

**References:**

- MELCloud: <https://github.com/home-assistant/core/tree/master/homeassistant/components/melcloud>
- DataUpdateCoordinator docs: <https://developers.home-assistant.io/docs/integration_fetching_data>

### ADR-006: Adopt Entity Description Pattern for Sensors

**Decision:** Use MELCloud's entity description pattern for v1.2 sensors.

**Rationale:**

1. Modern HA pattern (2022+)
2. Clean separation of metadata and logic
3. Type-safe with dataclasses
4. Widely adopted across integrations
5. Reduces boilerplate code

**Implementation:**

```python
@dataclass
class MELCloudHomeSensorEntityDescription(SensorEntityDescription):
    value_fn: Callable[[AirToAirUnit], Any]
    available_fn: Callable[[AirToAirUnit], bool] = lambda x: True
```

**Consequences:**

- ✅ Less boilerplate code
- ✅ Easier to add new sensors
- ✅ Better type safety
- ✅ Consistent with modern integrations
- ⚠️ Requires Python 3.10+ (already required)

---

## Part 6: v1.2 Implementation Plan

### Phase 1: Sensor Platform (4-6 hours)

**Tasks:**

1. Create `custom_components/melcloudhome/sensor.py`
2. Define sensor entity descriptions
3. Implement `MELCloudHomeSensor` class
4. Register sensor platform in `__init__.py`
5. Add tests for sensor platform
6. Update documentation

**Deliverables:**

- `sensor.py` with entity descriptions
- Room temperature sensor
- Energy consumption sensor (if API supports)
- Test coverage for sensors

### Phase 2: WebSocket Implementation (4-6 hours)

**Tasks:**

1. Research WebSocket message format
2. Implement WebSocket connection management
3. Add message parsing and handling
4. Update coordinator with WebSocket data
5. Implement fallback to polling
6. Add error handling and reconnection
7. Test real-time updates

**Deliverables:**

- WebSocket integration in coordinator
- Real-time state updates
- Graceful fallback mechanism
- Updated documentation

### Phase 3: Binary Sensors (2 hours)

**Tasks:**

1. Create `custom_components/melcloudhome/binary_sensor.py`
2. Implement error state sensor
3. Implement connection state sensor
4. Register binary sensor platform
5. Add tests

**Deliverables:**

- `binary_sensor.py`
- Error state sensor
- Connection state sensor

### Phase 4: HACS Repository (7-9 hours)

**Tasks:**

1. Create new `melcloudhome` repository
2. Copy integration files
3. Create `hacs.json`
4. Update README.md for HACS
5. Set up GitHub Actions
6. Create v1.2.0 release
7. Test as custom repository
8. Create brand assets
9. Submit to HACS default

**Deliverables:**

- Dedicated HACS-compatible repository
- GitHub Actions passing
- v1.2.0 release published
- Brand assets submitted
- HACS PR submitted

### Total Effort: 17-23 hours

**Breakdown:**

- Sensors: 4-6 hours
- WebSocket: 4-6 hours
- Binary sensors: 2 hours
- HACS: 7-9 hours

---

## Part 7: Quality Assessment

### Current Quality (v1.1.2)

| Tier | Status | Notes |
|------|--------|-------|
| Bronze | ✅ PASS | UI config, tests, docs, quality |
| Silver | ✅ PASS | Error recovery, maintenance |
| Gold | ⚠️ PARTIAL | Missing translations, discovery |
| Platinum | ⚠️ PARTIAL | Good async, needs full typing |

### Quality Comparison: MELCloud Home vs Official MELCloud

| Aspect | Official MELCloud | MELCloud Home | Winner |
|--------|-------------------|---------------|--------|
| Architecture | Legacy (@Throttle) | Modern (Coordinator) | **YOU** 🏆 |
| Performance | O(n) lookups | O(1) cached | **YOU** 🏆 |
| Error Handling | Basic | Comprehensive | **YOU** 🏆 |
| Code Quality | Good | Excellent | **YOU** 🏆 |
| Documentation | Minimal | Extensive (ADRs) | **YOU** 🏆 |
| Testing | Core tests | 82% coverage | **YOU** 🏆 |
| Type Safety | Partial | Full (mypy) | **YOU** 🏆 |

**Overall:** Your integration is objectively higher quality than the official MELCloud integration.

---

## Part 8: Next Steps

### Immediate (This Session)

- [x] Research MELCloud integration
- [x] Research climate best practices
- [x] Research HACS requirements
- [ ] Document findings (this file)
- [ ] Update ROADMAP.md with v1.2 plan
- [ ] Create ADR-005 (divergence from MELCloud)
- [ ] Create ADR-006 (entity description adoption)

### Session 10: v1.2 Implementation

**Order of Implementation:**

1. Sensor platform (highest value, enables statistics)
2. WebSocket updates (real-time control)
3. Binary sensors (automation triggers)
4. HACS repository (distribution)

**Decision Points:**

- ✅ WebSocket: Implement in v1.2
- ✅ Sensors: Implement in v1.2
- ✅ Architecture: Keep current (superior to MELCloud)
- ✅ HACS: Create separate repository
- ❌ Custom services: Not needed
- ❌ Refactoring: Not needed

---

## Part 9: References

### Documentation Reviewed

- [MELCloud Integration](https://github.com/home-assistant/core/tree/master/homeassistant/components/melcloud)
- [Ecobee Integration](https://github.com/home-assistant/core/tree/dev/homeassistant/components/ecobee)
- [Nest Integration](https://github.com/home-assistant/core/tree/dev/homeassistant/components/nest)
- [Climate Entity Docs](https://developers.home-assistant.io/docs/core/entity/climate/)
- [DataUpdateCoordinator Docs](https://developers.home-assistant.io/docs/integration_fetching_data/)
- [HACS Documentation](https://hacs.xyz/docs/publish/integration/)
- [Home Assistant Brands](https://github.com/home-assistant/brands)

### Key Insights Sources

- Integration Quality Scale
- Modern climate integration patterns (Nest, Ecobee)
- HACS validation requirements
- Entity description pattern evolution

---

## Conclusion

**Key Takeaway:** Your integration is already more modern than the official MELCloud integration. Focus on additive improvements (sensors, WebSocket, HACS) while maintaining your superior architecture.

**Confidence Level:** High - Research is comprehensive and findings are well-documented.

**Ready for v1.2 Implementation:** Yes - Clear plan with prioritized tasks and realistic time estimates.
