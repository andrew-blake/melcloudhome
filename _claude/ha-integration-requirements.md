# Home Assistant Integration Requirements

**Version:** 1.0
**Session:** 7
**Status:** Ready for Implementation

## Overview

Custom HA component for MELCloud Home air-to-air heat pumps as climate entities.

**v1.0 Goals:**

- Climate entity with full device control
- UI-based config flow (email/password)
- 60s polling with auto-reauth on session expiry
- Clean entity naming with future-proofing
- Comprehensive testing

## Component Structure

```
custom_components/melcloudhome/
├── manifest.json       # Metadata
├── strings.json        # UI translations
├── const.py           # HA constants & mode mappings
├── __init__.py        # Setup/teardown entry points
├── config_flow.py     # UI configuration wizard
├── coordinator.py     # Data update coordinator (60s polling)
├── climate.py         # Climate entity platform
└── api/               # Already complete (Sessions 1-4)
```

## Key Requirements

### 1. manifest.json

- Domain: `melcloudhome`
- `config_flow: true`, `iot_class: "cloud_polling"`
- No external requirements (bundled API)

### 2. config_flow.py

- Extend `ConfigFlow`, implement `async_step_user()`
- Prompt for email/password
- Validate with `client.login()`, handle errors: `invalid_auth`, `cannot_connect`, `unknown`
- Use `async_set_unique_id(email.lower())` to prevent duplicates
- Create entry: `"MELCloud Home ({email})"`

### 3. const.py

- `DOMAIN = "melcloudhome"`
- `UPDATE_INTERVAL = 60` (seconds)
- `PLATFORMS = ["climate"]`
- Mode mappings: `MELCLOUD_TO_HA_MODE`, `HA_TO_MELCLOUD_MODE`
  - ⚠️ MELCloud uses `"Automatic"` not `"Auto"`

### 4. coordinator.py

- Extend `DataUpdateCoordinator[UserContext]`
- Poll every 60s via `client.get_user_context()`
- Store `UserContext` in `self.data` (has `.buildings` property)
- Store credentials for auto re-login on `AuthenticationError`
- Raise `UpdateFailed` on `ApiError` (makes entities unavailable)
- Close client on unload
- Helper method: `get_building_for_unit(unit_id)` for entity lookups

### 5. **init**.py

- `async_setup_entry()`: Create client, login, create coordinator, forward to platforms
- `async_unload_entry()`: Unload platforms, close client
- Handle `ConfigEntryAuthFailed` (invalid creds) and `ConfigEntryNotReady` (temporary failure)

### 6. climate.py

**Platform Setup**:

```python
async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for building in coordinator.data.buildings:
        for unit in building.air_to_air_units:
            entities.append(MELCloudHomeClimate(coordinator, unit, building))
    async_add_entities(entities)
```

**Entity Naming (Modern HA Pattern)**:

- `unique_id`: Device UUID (`unit.id`) - permanent identifier
- Use `_attr_has_entity_name = True` with device info (not `self.entity_id`)
- Device name: `f"{building.name} {unit.name}"` (always include building)
- Entity name: `None` (uses device name) or specific like "Climate"
- Result: `climate.home_living_room_climate` or similar (HA generates)

**Class Structure**:

- Extend `CoordinatorEntity` + `ClimateEntity`
- Store `_unit_id` and `_building_id` for lookups
- `_device` property: Get current device, return None if not found
- `_building` property: Get current building, return None if not found

**Required Properties**:

- `available`: Check coordinator success, device exists, not in error
- `hvac_mode`: Return `OFF` if `!power`, else map from `MELCLOUD_TO_HA_MODE`
- `hvac_modes`: `[OFF, HEAT, COOL, AUTO, DRY, FAN_ONLY]`
- `current_temperature`, `target_temperature`: From `_device` (handle None)
- `fan_mode`, `fan_modes`: Strings "Auto", "One"-"Five"
- `swing_mode`, `swing_modes`: Vertical vane positions
- `min_temp`, `max_temp`, `target_temperature_step`: 10-31°C, 0.5° steps (Heat: 10°C, others: 16°C min)
- `supported_features`: Check `device.capabilities` before advertising features

**Required Methods** (validate input, call API, refresh):

- `async_set_hvac_mode()`: Handle `OFF` → `set_power(False)`, else `set_power(True)` + `set_mode()`
- `async_set_temperature()`: Validate range, call `client.set_temperature()`
- `async_set_fan_mode()`: Validate value, call `client.set_fan_speed()`
- `async_set_swing_mode()`: Call `client.set_vanes()` (horizontal from device or "Auto")
- All call `coordinator.async_request_refresh()` after

**Device Info** (required for modern naming):

```python
DeviceInfo(
    identifiers={(DOMAIN, unit.id)},
    name=f"{building.name} {unit.name}",
    manufacturer="Mitsubishi Electric",
    model="Air-to-Air Heat Pump",
    suggested_area=building.name,
    via_device=(DOMAIN, entry.entry_id),
)
```

### 7. strings.json

- Config step: "user" with email/password fields
- Errors: `invalid_auth`, `cannot_connect`, `unknown`
- Abort: `already_configured`

## Testing Strategy

### Dependencies

Add to `pyproject.toml`:

```toml
[tool.uv.dev-dependencies]
pytest-homeassistant-custom-component = "^0.13"  # Provides hass fixture
```

This provides:

- `hass` fixture: Mock Home Assistant instance
- `aioclient_mock`: Mock aiohttp client
- Async test support built-in

### Test Structure

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures
├── test_config_flow.py      # Config flow tests
├── test_init.py             # Integration setup/teardown
├── test_coordinator.py      # Coordinator logic
└── test_climate.py          # Climate entity tests
```

### Fixtures (conftest.py)

```python
@pytest.fixture
def mock_melcloud_client():
    """Mock API client to avoid real API calls."""
    with patch("custom_components.melcloudhome.api.MELCloudHomeClient") as mock:
        client = mock.return_value
        # Mock successful login
        client.login = AsyncMock()
        # Mock get_user_context with sample data
        client.get_user_context = AsyncMock(return_value=sample_user_context())
        # Mock control methods
        client.set_power = AsyncMock()
        client.set_temperature = AsyncMock()
        yield client

@pytest.fixture
def sample_user_context():
    """Return sample UserContext for testing."""
    return UserContext(
        buildings=[
            Building(
                id="building-1",
                name="Home",
                air_to_air_units=[sample_unit()]
            )
        ]
    )
```

### Unit Tests

**test_config_flow.py**:

- ✅ Test successful login and config entry creation
- ✅ Test invalid credentials error (`invalid_auth`)
- ✅ Test connection error (`cannot_connect`)
- ✅ Test duplicate account prevention (unique_id)
- ✅ Test abort on already configured

**test_init.py**:

- ✅ Test `async_setup_entry` creates coordinator and forwards platforms
- ✅ Test `async_unload_entry` cleans up and closes client
- ✅ Test `ConfigEntryAuthFailed` on invalid credentials
- ✅ Test `ConfigEntryNotReady` on connection failure
- ✅ Test coordinator stored in hass.data correctly

**test_coordinator.py**:

- ✅ Test successful data fetch returns UserContext
- ✅ Test auto re-login on `AuthenticationError`
- ✅ Test `UpdateFailed` raised on `ApiError`
- ✅ Test 60s update interval configured
- ✅ Test client closed on unload

**test_climate.py**:

- ✅ Test entity setup from coordinator data
- ✅ Test unique_id set to device UUID
- ✅ Test device_info includes building context
- ✅ Test `available` property (coordinator success, device exists, no error)
- ✅ Test `hvac_mode` mapping (power off = OFF, power on = mapped mode)
- ✅ Test `current_temperature` and `target_temperature` from device
- ✅ Test `fan_mode` and `swing_mode` properties
- ✅ Test `min_temp` varies by mode (Heat: 10°C, others: 16°C)
- ✅ Test `supported_features` based on capabilities
- ✅ Test `async_set_hvac_mode` (OFF → power false, others → power + mode)
- ✅ Test `async_set_temperature` validates and calls client
- ✅ Test `async_set_fan_mode` and `async_set_swing_mode`
- ✅ Test refresh called after each control method
- ✅ Test entity handles missing device gracefully (returns None)

### Testing Patterns

**Mock API Client**:

```python
async def test_climate_set_temperature(hass, mock_client):
    """Test setting temperature."""
    # Setup
    entity = create_climate_entity(hass, mock_client)

    # Execute
    await entity.async_set_temperature(temperature=22.0)

    # Assert
    mock_client.set_temperature.assert_called_once_with(UNIT_ID, 22.0)
    assert entity.coordinator.async_request_refresh.called
```

**Test Data Builders**:

```python
def build_device(power=True, mode="Heat", temp=22.0):
    """Build test device with defaults."""
    return AirToAirUnit(
        id="test-unit-id",
        name="Living Room",
        power=power,
        operation_mode=mode,
        set_temperature=temp,
        # ... other fields
    )
```

**Snapshot Testing** (config flow):

```python
async def test_config_flow_user_step(hass):
    """Test user step shows form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert "email" in result["data_schema"].schema
```

### Integration Tests

**Full Flow Test**:

```python
async def test_full_setup_flow(hass, mock_client):
    """Test complete setup and entity creation."""
    # 1. Config flow
    result = await setup_config_entry(hass, mock_client)
    assert result["type"] == "create_entry"

    # 2. Integration setup
    entry = result["result"]
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # 3. Verify coordinator created
    assert DOMAIN in hass.data
    assert entry.entry_id in hass.data[DOMAIN]

    # 4. Verify entities created
    state = hass.states.get("climate.home_living_room_climate")
    assert state is not None
    assert state.state == "heat"
```

### Manual Testing Checklist

- [ ] Add integration via UI with valid credentials
- [ ] Verify all devices discovered across all buildings
- [ ] Test power on/off via UI
- [ ] Test temperature adjustment (up/down, 0.5° steps)
- [ ] Test all modes: Heat, Cool, Auto, Dry, Fan
- [ ] Test fan speeds: Auto, 1-5
- [ ] Test vane/swing positions
- [ ] Verify state updates after 60s poll
- [ ] Test with invalid credentials (see error message)
- [ ] Test re-adding same account (duplicate prevention)
- [ ] Restart HA, verify entities persist
- [ ] Rename device in MELCloud app, verify name updates in HA
- [ ] Test with 2+ buildings (verify names show building context)
- [ ] Disconnect internet, verify entities become unavailable
- [ ] Reconnect, verify entities recover

### Coverage Goals

- Config flow: 100% (simple, mockable)
- Coordinator: >90% (core logic)
- Climate entity: >85% (many properties/methods)
- Overall: >80%

## Success Criteria

**Functional**:

- UI setup with email/password ✓
- All devices auto-discovered ✓
- Full climate control ✓
- Auto re-auth on session expiry ✓
- Clean entity naming ✓

**Quality**:

- Type-safe (mypy passes) ✓
- Formatted (ruff) ✓
- Test coverage >80% ✓
- Graceful error handling ✓

## Future (v1.1+)

- Sensor platform (energy, errors, signal)
- OAuth refresh tokens (remove password storage)
- Schedule management
- Preset modes

## Critical Notes

**API Constraints**:

- ⚠️ 60s minimum polling (rate limiting)
- ⚠️ Mode is `"Automatic"` not `"Auto"`
- ⚠️ Fan speeds are strings ("One"-"Five") not integers
- ⚠️ Requires `x-csrf: 1` and `referer` headers (API client handles this)

**Entity Naming**:

- ⚠️ Use modern `_attr_has_entity_name = True` pattern (not `self.entity_id`)
- ⚠️ Always include building in device name (future-proof)
- ⚠️ Entity IDs generated by HA, stable after creation

**Error Handling**:

- ⚠️ Check `device.capabilities` before advertising features
- ⚠️ Handle None gracefully if device/building not found
- ⚠️ Implement `available` property (coordinator + device + not in error)
- ⚠️ Validate inputs before API calls

**Data Structure**:

- ⚠️ `coordinator.data` is `UserContext` (has `.buildings`)
- ⚠️ Each building has `.air_to_air_units`
- ⚠️ Use helper method to get building for a unit

**Testing**:

- ⚠️ Mock API client, don't call real API
- ⚠️ Test with `hass` fixture from pytest-homeassistant-custom-component
- ⚠️ Use `AsyncMock` for async methods
- ⚠️ Test both happy path and error cases
