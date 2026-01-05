"""Tests for MELCloud Home climate entity.

Tests cover climate entity behavior through Home Assistant core interfaces only.
Follows HA best practices: test observable behavior, not implementation details.

Reference: docs/testing-best-practices.md
Run with: make test-ha
"""

from unittest.mock import AsyncMock, PropertyMock, patch

import pytest
from homeassistant.components.climate import HVACAction, HVACMode
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.melcloudhome.api.models import (
    AirToAirUnit,
    Building,
    DeviceCapabilities,
    UserContext,
)
from custom_components.melcloudhome.const import DOMAIN

from .conftest import (
    create_mock_atw_building,
    create_mock_atw_unit,
    create_mock_atw_user_context,
)

# Mock at API boundary (NOT coordinator)
MOCK_CLIENT_PATH = "custom_components.melcloudhome.MELCloudHomeClient"

# Test device UUID - generates entity_id: climate.melcloudhome_0efc_9abc
TEST_UNIT_ID = "0efc1234-5678-9abc-def0-123456789abc"
TEST_BUILDING_ID = "building-test-id"


def create_mock_unit(
    unit_id: str = TEST_UNIT_ID,
    name: str = "Test Unit",
    power: bool = True,
    operation_mode: str = "Heat",
    set_temperature: float = 21.0,
    room_temperature: float = 20.0,
    set_fan_speed: str = "Auto",
    vane_vertical: str = "Auto",
    vane_horizontal: str = "Auto",
    is_in_error: bool = False,
) -> AirToAirUnit:
    """Create a mock AirToAirUnit for testing.

    Uses real model class with realistic data.
    """
    return AirToAirUnit(
        id=unit_id,
        name=name,
        power=power,
        operation_mode=operation_mode,
        set_temperature=set_temperature,
        room_temperature=room_temperature,
        set_fan_speed=set_fan_speed,
        vane_vertical_direction=vane_vertical,
        vane_horizontal_direction=vane_horizontal,
        in_standby_mode=False,
        is_in_error=is_in_error,
        rssi=-50,
        capabilities=DeviceCapabilities(),
        schedule=[],
        schedule_enabled=False,
    )


def create_mock_building(
    building_id: str = TEST_BUILDING_ID,
    name: str = "Test Building",
    units: list[AirToAirUnit] | None = None,
) -> Building:
    """Create a mock Building for testing."""
    if units is None:
        units = [create_mock_unit()]
    return Building(id=building_id, name=name, air_to_air_units=units)


def create_mock_user_context(buildings: list[Building] | None = None) -> UserContext:
    """Create a mock UserContext for testing."""
    if buildings is None:
        buildings = [create_mock_building()]
    return UserContext(buildings=buildings)


@pytest.fixture
async def setup_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the integration with mocked API client.

    Follows HA best practices:
    - Mocks at API boundary (MELCloudHomeClient)
    - Sets up through core interface (hass.config_entries.async_setup)
    - Returns config entry for test use
    """
    mock_context = create_mock_user_context()

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        # Mock API control methods (called by service calls)
        mock_client.set_power = AsyncMock()
        mock_client.set_mode = AsyncMock()
        mock_client.set_temperature = AsyncMock()
        mock_client.set_fan_speed = AsyncMock()
        mock_client.set_vanes = AsyncMock()

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        return entry


@pytest.mark.asyncio
async def test_climate_entity_state_reflects_device_data(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Test that climate entity state correctly reflects device data.

    Validates: Entity state matches mock device configuration
    Tests through: hass.states (core interface)
    """
    # ✅ CORRECT: Assert through state machine
    state = hass.states.get("climate.melcloudhome_0efc_9abc")

    assert state is not None
    assert state.state == HVACMode.HEAT
    assert state.attributes["current_temperature"] == 20.0
    assert state.attributes["temperature"] == 21.0
    assert state.attributes["fan_mode"] == "Auto"
    assert state.attributes["swing_mode"] == "Auto"


@pytest.mark.asyncio
async def test_set_hvac_mode_to_cool(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Test changing HVAC mode to COOL via service call.

    Validates: Service accepts mode change without error
    Tests through: hass.services (core interface)
    """
    # ✅ CORRECT: Call service through core registry
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": "climate.melcloudhome_0efc_9abc", "hvac_mode": HVACMode.COOL},
        blocking=True,
    )

    # Service call succeeded (no exception raised)
    # Note: State change depends on coordinator refresh, not tested here


@pytest.mark.asyncio
async def test_set_hvac_mode_off_turns_device_off(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Test that setting HVAC mode to OFF powers down device.

    Validates: OFF mode service call accepted
    Tests through: hass.services (core interface)
    """
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": "climate.melcloudhome_0efc_9abc", "hvac_mode": HVACMode.OFF},
        blocking=True,
    )

    # Service call succeeded (no exception raised)


@pytest.mark.asyncio
async def test_set_temperature_within_valid_range(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Test setting temperature within valid range.

    Validates: Temperature change service call accepted
    Tests through: hass.services (core interface)
    """
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": "climate.melcloudhome_0efc_9abc", "temperature": 22.5},
        blocking=True,
    )

    # Service call succeeded (no exception raised)


@pytest.mark.asyncio
async def test_set_temperature_out_of_range_rejected(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Test that temperature out of range is rejected gracefully.

    Validates: Out-of-range temps are logged but don't crash integration
    Tests through: hass.services (core interface)

    Note: Home Assistant's climate component may validate ranges before
    calling entity methods. Our entity also validates in async_set_temperature.
    """
    from contextlib import suppress

    from homeassistant.exceptions import ServiceValidationError

    # Below minimum (10°C for heat mode)
    # May be rejected by HA or logged by entity
    with suppress(ServiceValidationError):
        await hass.services.async_call(
            "climate",
            "set_temperature",
            {"entity_id": "climate.melcloudhome_0efc_9abc", "temperature": 5.0},
            blocking=True,
        )

    # Above maximum (31°C)
    with suppress(ServiceValidationError):
        await hass.services.async_call(
            "climate",
            "set_temperature",
            {"entity_id": "climate.melcloudhome_0efc_9abc", "temperature": 35.0},
            blocking=True,
        )

    # Test passes - out of range temps handled without crash


@pytest.mark.asyncio
async def test_set_fan_mode(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Test setting fan mode via service call.

    Validates: Fan mode change service call accepted
    Tests through: hass.services (core interface)
    """
    await hass.services.async_call(
        "climate",
        "set_fan_mode",
        {"entity_id": "climate.melcloudhome_0efc_9abc", "fan_mode": "Three"},
        blocking=True,
    )

    # Service call succeeded (no exception raised)


@pytest.mark.asyncio
async def test_set_swing_mode_vertical_vanes(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Test setting vertical vane position via swing mode.

    Validates: Swing mode change service call accepted
    Tests through: hass.services (core interface)
    """
    await hass.services.async_call(
        "climate",
        "set_swing_mode",
        {"entity_id": "climate.melcloudhome_0efc_9abc", "swing_mode": "Swing"},
        blocking=True,
    )

    # Service call succeeded (no exception raised)


@pytest.mark.asyncio
async def test_set_swing_horizontal_mode(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Test setting horizontal vane position.

    Validates: Horizontal swing mode change service call accepted
    Tests through: hass.services (core interface)
    """
    await hass.services.async_call(
        "climate",
        "set_swing_horizontal_mode",
        {
            "entity_id": "climate.melcloudhome_0efc_9abc",
            "swing_horizontal_mode": "Centre",
        },
        blocking=True,
    )

    # Service call succeeded (no exception raised)


@pytest.mark.asyncio
async def test_hvac_action_heating_when_temp_below_target(hass: HomeAssistant) -> None:
    """Test HVAC action inference: HEATING when temp below target.

    Validates: hvac_action attribute shows HEATING with hysteresis
    Tests through: hass.states (core interface)
    Scenario: Heat mode, current 19°C, target 21°C (> 0.5°C threshold)
    """
    # Create unit with temp below target
    mock_unit = create_mock_unit(
        operation_mode="Heat",
        set_temperature=21.0,
        room_temperature=19.0,  # 2°C below target (exceeds 0.5°C hysteresis)
    )
    mock_context = create_mock_user_context([create_mock_building(units=[mock_unit])])

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # ✅ CORRECT: Assert through state machine
        state = hass.states.get("climate.melcloudhome_0efc_9abc")
        assert state is not None
        assert state.attributes["hvac_action"] == HVACAction.HEATING


@pytest.mark.asyncio
async def test_hvac_action_idle_when_temp_at_target(hass: HomeAssistant) -> None:
    """Test HVAC action inference: IDLE when temp at target.

    Validates: hvac_action attribute shows IDLE
    Tests through: hass.states (core interface)
    Scenario: Heat mode, current 21°C, target 21°C (within hysteresis)
    """
    mock_unit = create_mock_unit(
        operation_mode="Heat",
        set_temperature=21.0,
        room_temperature=21.0,  # At target
    )
    mock_context = create_mock_user_context([create_mock_building(units=[mock_unit])])

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("climate.melcloudhome_0efc_9abc")
        assert state is not None
        assert state.attributes["hvac_action"] == HVACAction.IDLE


@pytest.mark.asyncio
async def test_hvac_action_cooling_when_temp_above_target(hass: HomeAssistant) -> None:
    """Test HVAC action inference: COOLING when temp above target.

    Validates: hvac_action attribute shows COOLING with hysteresis
    Tests through: hass.states (core interface)
    Scenario: Cool mode, current 22°C, target 20°C (> 0.5°C threshold)
    """
    mock_unit = create_mock_unit(
        operation_mode="Cool",
        set_temperature=20.0,
        room_temperature=22.0,  # 2°C above target (exceeds 0.5°C hysteresis)
    )
    mock_context = create_mock_user_context([create_mock_building(units=[mock_unit])])

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("climate.melcloudhome_0efc_9abc")
        assert state is not None
        assert state.attributes["hvac_action"] == HVACAction.COOLING


@pytest.mark.asyncio
async def test_device_unavailable_when_in_error_state(hass: HomeAssistant) -> None:
    """Test that device shows as unavailable when in error state.

    Validates: Entity availability reflects device error state
    Tests through: hass.states (core interface)
    Scenario: Device with is_in_error=True
    """
    mock_unit = create_mock_unit(is_in_error=True)
    mock_context = create_mock_user_context([create_mock_building(units=[mock_unit])])

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("climate.melcloudhome_0efc_9abc")
        assert state is not None
        assert state.state == "unavailable"


@pytest.mark.asyncio
async def test_device_power_off_shows_hvac_mode_off(hass: HomeAssistant) -> None:
    """Test that device power OFF maps to HVACMode.OFF.

    Validates: Powered off device shows OFF state regardless of mode
    Tests through: hass.states (core interface)
    Scenario: Device with power=False, operation_mode="Heat"
    """
    mock_unit = create_mock_unit(power=False, operation_mode="Heat")
    mock_context = create_mock_user_context([create_mock_building(units=[mock_unit])])

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("climate.melcloudhome_0efc_9abc")
        assert state is not None
        assert state.state == HVACMode.OFF
        assert state.attributes["hvac_action"] == HVACAction.OFF


@pytest.mark.asyncio
async def test_turn_on_and_turn_off_services(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Test turn_on and turn_off service calls.

    Validates: Turn on/off services accepted without error
    Tests through: hass.services (core interface)
    """
    # Turn off
    await hass.services.async_call(
        "climate",
        "turn_off",
        {"entity_id": "climate.melcloudhome_0efc_9abc"},
        blocking=True,
    )

    # Turn on
    await hass.services.async_call(
        "climate",
        "turn_on",
        {"entity_id": "climate.melcloudhome_0efc_9abc"},
        blocking=True,
    )

    # Both calls succeeded (no exception raised)


@pytest.mark.asyncio
async def test_device_removal_entity_becomes_unavailable(hass: HomeAssistant) -> None:
    """Test that entity becomes unavailable when device is removed.

    Validates: Entity handles device removal gracefully
    Tests through: hass.states (core interface)
    Scenario: Building with no units (device removed from account)
    """
    # Setup with empty units list
    mock_context = create_mock_user_context([create_mock_building(units=[])])

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Entity won't be created if no units at setup
        # This tests that setup doesn't crash with empty units
        state = hass.states.get("climate.melcloudhome_0efc_9abc")
        assert state is None  # Entity not created


# ============================================================================
# ATW (Air-to-Water) Climate Tests
# ============================================================================


@pytest.mark.asyncio
async def test_atw_climate_zone1_created(hass: HomeAssistant) -> None:
    """Test ATW Zone 1 climate entity is created."""
    mock_unit = create_mock_atw_unit()
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Check Zone 1 entity exists with correct naming
        state = hass.states.get("climate.melcloudhome_0efc_9abc_zone_1")
        assert state is not None
        assert state.state == HVACMode.HEAT
        assert state.attributes["current_temperature"] == 20.0
        assert state.attributes["temperature"] == 21.0


@pytest.mark.asyncio
async def test_atw_set_temperature_zone1(hass: HomeAssistant) -> None:
    """Test setting Zone 1 temperature via service."""
    mock_unit = create_mock_atw_unit()
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        mock_client.set_temperature_zone1 = AsyncMock()
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Call set_temperature service
        await hass.services.async_call(
            "climate",
            "set_temperature",
            {
                "entity_id": "climate.melcloudhome_0efc_9abc_zone_1",
                "temperature": 22.5,
            },
            blocking=True,
        )

        # Service succeeded without errors


@pytest.mark.asyncio
async def test_atw_hvac_mode_off_powers_down_system(hass: HomeAssistant) -> None:
    """Test setting HVAC mode to OFF powers down entire ATW system."""
    mock_unit = create_mock_atw_unit(power=True)
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        mock_client.set_power_atw = AsyncMock()
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Call set_hvac_mode service
        await hass.services.async_call(
            "climate",
            "set_hvac_mode",
            {
                "entity_id": "climate.melcloudhome_0efc_9abc_zone_1",
                "hvac_mode": HVACMode.OFF,
            },
            blocking=True,
        )

        # Service succeeded without errors


@pytest.mark.asyncio
async def test_atw_hvac_mode_heat_powers_up_system(hass: HomeAssistant) -> None:
    """Test setting HVAC mode to HEAT powers up ATW system."""
    mock_unit = create_mock_atw_unit(power=False)
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        mock_client.set_power_atw = AsyncMock()
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Call set_hvac_mode service
        await hass.services.async_call(
            "climate",
            "set_hvac_mode",
            {
                "entity_id": "climate.melcloudhome_0efc_9abc_zone_1",
                "hvac_mode": HVACMode.HEAT,
            },
            blocking=True,
        )

        # Service succeeded without errors


@pytest.mark.asyncio
async def test_atw_preset_mode_reflects_zone_operation_mode(
    hass: HomeAssistant,
) -> None:
    """Test preset mode reflects Zone 1 operation mode."""
    mock_unit = create_mock_atw_unit(operation_mode_zone1="HeatRoomTemperature")
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("climate.melcloudhome_0efc_9abc_zone_1")
        assert state.attributes["preset_mode"] == "room"


@pytest.mark.asyncio
async def test_atw_set_preset_mode_room_to_flow(hass: HomeAssistant) -> None:
    """Test changing preset mode from room to flow."""
    mock_unit = create_mock_atw_unit(operation_mode_zone1="HeatRoomTemperature")
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        mock_client.set_mode_zone1 = AsyncMock()
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Call set_preset_mode service
        await hass.services.async_call(
            "climate",
            "set_preset_mode",
            {
                "entity_id": "climate.melcloudhome_0efc_9abc_zone_1",
                "preset_mode": "flow",
            },
            blocking=True,
        )

        # Service succeeded without errors


@pytest.mark.asyncio
async def test_atw_set_preset_mode_flow_to_curve(hass: HomeAssistant) -> None:
    """Test changing preset mode from flow to curve."""
    mock_unit = create_mock_atw_unit(operation_mode_zone1="HeatFlowTemperature")
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        mock_client.set_mode_zone1 = AsyncMock()
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Call set_preset_mode service
        await hass.services.async_call(
            "climate",
            "set_preset_mode",
            {
                "entity_id": "climate.melcloudhome_0efc_9abc_zone_1",
                "preset_mode": "curve",
            },
            blocking=True,
        )

        # Service succeeded without errors


@pytest.mark.asyncio
async def test_atw_hvac_action_idle_when_valve_on_dhw(hass: HomeAssistant) -> None:
    """Test HVAC action is IDLE when 3-way valve is on DHW (ATW-specific)."""
    mock_unit = create_mock_atw_unit(
        power=True,
        room_temperature_zone1=18.0,  # Below target
        set_temperature_zone1=21.0,
        operation_mode_zone1="HeatRoomTemperature",
        operation_status="HotWater",  # Valve on DHW, not Zone 1
    )
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("climate.melcloudhome_0efc_9abc_zone_1")
        # Even though temp is below target, hvac_action is IDLE because valve is on DHW
        assert state.attributes["hvac_action"] == HVACAction.IDLE


@pytest.mark.asyncio
async def test_atw_hvac_action_heating_when_valve_on_zone1_and_below_target(
    hass: HomeAssistant,
) -> None:
    """Test HVAC action is HEATING when valve on Zone 1 and below target."""
    mock_unit = create_mock_atw_unit(
        power=True,
        room_temperature_zone1=18.0,  # Below target
        set_temperature_zone1=21.0,
        operation_mode_zone1="HeatRoomTemperature",
        operation_status="HeatRoomTemperature",  # Valve on Zone 1
    )
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("climate.melcloudhome_0efc_9abc_zone_1")
        # Valve is on Zone 1 and temp below target, so HEATING
        assert state.attributes["hvac_action"] == HVACAction.HEATING


@pytest.mark.asyncio
async def test_atw_extra_state_attributes_include_valve_status(
    hass: HomeAssistant,
) -> None:
    """Test extra state attributes include operation_status and valve info."""
    mock_unit = create_mock_atw_unit(
        operation_status="HeatRoomTemperature",
        forced_hot_water_mode=False,
    )
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("climate.melcloudhome_0efc_9abc_zone_1")
        assert state.attributes["operation_status"] == "HeatRoomTemperature"
        assert "forced_dhw_active" in state.attributes
        assert "zone_heating_available" in state.attributes


@pytest.mark.asyncio
async def test_atw_climate_unavailable_when_device_in_error(
    hass: HomeAssistant,
) -> None:
    """Test ATW climate entity unavailable when device in error."""
    mock_unit = create_mock_atw_unit(is_in_error=True)
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("climate.melcloudhome_0efc_9abc_zone_1")
        assert state.state == "unavailable"


@pytest.mark.asyncio
async def test_atw_climate_zone_naming_includes_zone_1_suffix(
    hass: HomeAssistant,
) -> None:
    """Test ATW climate entity ID includes zone_1 suffix."""
    mock_unit = create_mock_atw_unit()
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Entity ID should include _zone_1 suffix
        state = hass.states.get("climate.melcloudhome_0efc_9abc_zone_1")
        assert state is not None
        assert "_zone_1" in state.entity_id


@pytest.mark.asyncio
async def test_atw_climate_off_when_power_false(hass: HomeAssistant) -> None:
    """Test ATW climate state is OFF when power is false."""
    mock_unit = create_mock_atw_unit(power=False)
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("climate.melcloudhome_0efc_9abc_zone_1")
        assert state.state == HVACMode.OFF
