"""Tests for MELCloud Home ATW Zone 2 climate entity.

Tests cover Zone 2 climate entity behavior through Home Assistant core interfaces only.
Follows HA best practices: test observable behavior, not implementation details.

Reference: docs/testing-best-practices.md
Run with: make test-integration
"""

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from homeassistant.components.climate import HVACAction, HVACMode
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.melcloudhome.const import DOMAIN

from .conftest import (
    TEST_ATW_UNIT_ID,
    TEST_CLIMATE_ZONE2_ENTITY_ID,
    TEST_SENSOR_ZONE2_TEMP,
    create_mock_atw_building,
    create_mock_atw_unit,
    create_mock_atw_user_context,
)

# Mock at API boundary (NOT coordinator)
MOCK_CLIENT_PATH = "custom_components.melcloudhome.MELCloudHomeClient"


@pytest.mark.asyncio
async def test_atw_climate_zone2_created_when_has_zone2(hass: HomeAssistant) -> None:
    """Test ATW Zone 2 climate entity is created when device has Zone 2."""
    mock_unit = create_mock_atw_unit(
        has_zone2=True,
        operation_mode_zone2="HeatFlowTemperature",
        set_temperature_zone2=21.0,
        room_temperature_zone2=20.0,
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

        state = hass.states.get(TEST_CLIMATE_ZONE2_ENTITY_ID)
        assert state is not None
        assert state.state == HVACMode.HEAT
        assert state.attributes["current_temperature"] == 20.0
        assert state.attributes["temperature"] == 21.0
        assert state.attributes["preset_mode"] == "flow"


@pytest.mark.asyncio
async def test_atw_climate_zone2_not_created_when_no_zone2(
    hass: HomeAssistant,
) -> None:
    """Test ATW Zone 2 climate entity is not created when device lacks Zone 2."""
    mock_unit = create_mock_atw_unit(has_zone2=False)
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

        state = hass.states.get(TEST_CLIMATE_ZONE2_ENTITY_ID)
        assert state is None


@pytest.mark.asyncio
async def test_atw_set_temperature_zone2(hass: HomeAssistant) -> None:
    """Test setting Zone 2 temperature via service."""
    mock_unit = create_mock_atw_unit(has_zone2=True)
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        mock_client.atw.set_temperature_zone2 = AsyncMock()
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
                "entity_id": TEST_CLIMATE_ZONE2_ENTITY_ID,
                "temperature": 22.5,
            },
            blocking=True,
        )

        # Verify API was called correctly
        await hass.async_block_till_done()
        mock_client.atw.set_temperature_zone2.assert_called_once_with(
            TEST_ATW_UNIT_ID, 22.5
        )


@pytest.mark.asyncio
async def test_atw_set_preset_mode_zone2(hass: HomeAssistant) -> None:
    """Test changing Zone 2 preset mode to flow."""
    mock_unit = create_mock_atw_unit(
        has_zone2=True,
        operation_mode_zone2="HeatRoomTemperature",
    )
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        mock_client.atw = MagicMock()
        mock_client.atw.set_mode_zone2 = AsyncMock()
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
                "entity_id": TEST_CLIMATE_ZONE2_ENTITY_ID,
                "preset_mode": "flow",
            },
            blocking=True,
        )

        # Verify API was called with correct ATW mode
        await hass.async_block_till_done()
        mock_client.atw.set_mode_zone2.assert_called_once_with(
            TEST_ATW_UNIT_ID, "HeatFlowTemperature"
        )


@pytest.mark.asyncio
async def test_atw_zone2_hvac_action_heating(hass: HomeAssistant) -> None:
    """Test Zone 2 HVAC action shows HEATING when operation_status is Heating."""
    mock_unit = create_mock_atw_unit(
        has_zone2=True,
        power=True,
        room_temperature_zone2=18.0,
        set_temperature_zone2=21.0,
        operation_mode_zone2="HeatRoomTemperature",
        operation_status="Heating",
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

        state = hass.states.get(TEST_CLIMATE_ZONE2_ENTITY_ID)
        assert state.attributes["hvac_action"] == HVACAction.HEATING


@pytest.mark.asyncio
async def test_atw_zone2_temperature_sensor_created(hass: HomeAssistant) -> None:
    """Test Zone 2 temperature sensor created when device has Zone 2."""
    mock_unit = create_mock_atw_unit(
        has_zone2=True,
        room_temperature_zone2=20.0,
        operation_mode_zone2="HeatRoomTemperature",
        set_temperature_zone2=21.0,
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

        state = hass.states.get(TEST_SENSOR_ZONE2_TEMP)
        assert state is not None
        assert float(state.state) == 20.0


@pytest.mark.asyncio
async def test_atw_zone2_temperature_sensor_not_created_without_zone2(
    hass: HomeAssistant,
) -> None:
    """Test Zone 2 temperature sensor NOT created without Zone 2."""
    mock_unit = create_mock_atw_unit(has_zone2=False)
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

        state = hass.states.get(TEST_SENSOR_ZONE2_TEMP)
        assert state is None


@pytest.mark.asyncio
async def test_atw_zone2_hvac_mode_off(hass: HomeAssistant) -> None:
    """Test setting Zone 2 HVAC mode to OFF powers down the system."""
    mock_unit = create_mock_atw_unit(
        has_zone2=True,
        power=True,
        operation_mode_zone2="HeatRoomTemperature",
    )
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        mock_client.atw.set_power = AsyncMock()
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Set HVAC mode to OFF
        await hass.services.async_call(
            "climate",
            "set_hvac_mode",
            {
                "entity_id": TEST_CLIMATE_ZONE2_ENTITY_ID,
                "hvac_mode": HVACMode.OFF,
            },
            blocking=True,
        )

        # Verify power off was called
        await hass.async_block_till_done()
        mock_client.atw.set_power.assert_called_once_with(TEST_ATW_UNIT_ID, False)


@pytest.mark.asyncio
async def test_atw_zone2_extra_state_attributes(hass: HomeAssistant) -> None:
    """Test Zone 2 climate entity exposes expected extra state attributes."""
    mock_unit = create_mock_atw_unit(
        has_zone2=True,
        power=True,
        operation_mode_zone2="HeatRoomTemperature",
        operation_status="Heating",
        forced_hot_water_mode=False,
        ftc_model=3,
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

        state = hass.states.get(TEST_CLIMATE_ZONE2_ENTITY_ID)
        assert state is not None

        # Verify extra state attributes (system-wide)
        assert state.attributes["operation_status"] == "Heating"
        assert state.attributes["forced_dhw_active"] is False
        assert state.attributes["ftc_model"] == 3
        # Note: zone_heating_available is True for both zones when system is heating
        assert state.attributes["zone_heating_available"] is True


@pytest.mark.asyncio
async def test_atw_zone2_zone_heating_not_available_when_stopped(
    hass: HomeAssistant,
) -> None:
    """Test zone_heating_available is False when system is idle (Stop)."""
    mock_unit = create_mock_atw_unit(
        has_zone2=True,
        power=True,
        operation_mode_zone2="HeatRoomTemperature",
        operation_status="Stop",  # System idle
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

        state = hass.states.get(TEST_CLIMATE_ZONE2_ENTITY_ID)
        assert state is not None
        assert state.attributes["zone_heating_available"] is False


@pytest.mark.asyncio
async def test_atw_zone2_preset_mode_transitions(hass: HomeAssistant) -> None:
    """Test Zone 2 preset mode transitions (flow to curve, curve to room)."""
    mock_unit = create_mock_atw_unit(
        has_zone2=True,
        operation_mode_zone2="HeatFlowTemperature",
    )
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        mock_client.atw = MagicMock()
        mock_client.atw.set_mode_zone2 = AsyncMock()
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Test flow -> curve
        await hass.services.async_call(
            "climate",
            "set_preset_mode",
            {
                "entity_id": TEST_CLIMATE_ZONE2_ENTITY_ID,
                "preset_mode": "curve",
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_client.atw.set_mode_zone2.assert_called_with(TEST_ATW_UNIT_ID, "HeatCurve")

        # Test curve -> room
        mock_client.atw.set_mode_zone2.reset_mock()
        await hass.services.async_call(
            "climate",
            "set_preset_mode",
            {
                "entity_id": TEST_CLIMATE_ZONE2_ENTITY_ID,
                "preset_mode": "room",
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_client.atw.set_mode_zone2.assert_called_with(
            TEST_ATW_UNIT_ID, "HeatRoomTemperature"
        )


@pytest.mark.asyncio
async def test_atw_zone2_cooling_mode_available(hass: HomeAssistant) -> None:
    """Test Zone 2 has COOL hvac_mode when device has cooling capability."""
    mock_unit = create_mock_atw_unit(
        has_zone2=True,
        has_cooling_mode=True,
        operation_mode_zone2="HeatRoomTemperature",
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

        state = hass.states.get(TEST_CLIMATE_ZONE2_ENTITY_ID)
        assert state is not None
        assert HVACMode.COOL in state.attributes["hvac_modes"]


@pytest.mark.asyncio
async def test_atw_zone2_cooling_mode_detected(hass: HomeAssistant) -> None:
    """Test Zone 2 HVAC mode detected as COOL from operation_mode_zone2."""
    mock_unit = create_mock_atw_unit(
        has_zone2=True,
        has_cooling_mode=True,
        power=True,
        operation_mode_zone2="CoolRoomTemperature",
        operation_status="Cooling",
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

        state = hass.states.get(TEST_CLIMATE_ZONE2_ENTITY_ID)
        assert state.state == HVACMode.COOL
        assert state.attributes["hvac_action"] == HVACAction.COOLING


@pytest.mark.asyncio
async def test_atw_zone2_set_cooling_mode(hass: HomeAssistant) -> None:
    """Test setting Zone 2 to COOL mode calls set_mode_zone2 with CoolRoomTemperature."""
    mock_unit = create_mock_atw_unit(
        has_zone2=True,
        has_cooling_mode=True,
        power=True,
        operation_mode_zone2="HeatRoomTemperature",
    )
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        mock_client.atw = MagicMock()
        mock_client.atw.set_mode_zone2 = AsyncMock()
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Set HVAC mode to COOL
        await hass.services.async_call(
            "climate",
            "set_hvac_mode",
            {
                "entity_id": TEST_CLIMATE_ZONE2_ENTITY_ID,
                "hvac_mode": HVACMode.COOL,
            },
            blocking=True,
        )

        await hass.async_block_till_done()
        mock_client.atw.set_mode_zone2.assert_called_once_with(
            TEST_ATW_UNIT_ID, "CoolRoomTemperature"
        )


@pytest.mark.asyncio
async def test_atw_zone2_cooling_preset_modes(hass: HomeAssistant) -> None:
    """Test Zone 2 preset modes in cooling (should only have room and flow, no curve)."""
    mock_unit = create_mock_atw_unit(
        has_zone2=True,
        has_cooling_mode=True,
        power=True,
        operation_mode_zone2="CoolRoomTemperature",
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

        state = hass.states.get(TEST_CLIMATE_ZONE2_ENTITY_ID)
        assert state is not None

        # In cooling mode, only room and flow presets available (no curve)
        preset_modes = state.attributes["preset_modes"]
        assert "room" in preset_modes
        assert "flow" in preset_modes
        assert "curve" not in preset_modes
