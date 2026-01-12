"""Tests for MELCloud Home ATW climate entity.

Tests cover climate entity behavior through Home Assistant core interfaces only.
Follows HA best practices: test observable behavior, not implementation details.

Reference: docs/testing-best-practices.md
Run with: make test-ha
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
    TEST_CLIMATE_ZONE1_ENTITY_ID,
    create_mock_atw_building,
    create_mock_atw_unit,
    create_mock_atw_user_context,
)

# Mock at API boundary (NOT coordinator)
MOCK_CLIENT_PATH = "custom_components.melcloudhome.MELCloudHomeClient"


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
        mock_client.atw.set_temperature_zone1 = AsyncMock()
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
                "entity_id": TEST_CLIMATE_ZONE1_ENTITY_ID,
                "temperature": 22.5,
            },
            blocking=True,
        )

        # Verify API was called correctly
        await hass.async_block_till_done()
        mock_client.atw.set_temperature_zone1.assert_called_once_with(
            TEST_ATW_UNIT_ID, 22.5
        )


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
        mock_client.atw = MagicMock()
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

        # Call set_hvac_mode service
        await hass.services.async_call(
            "climate",
            "set_hvac_mode",
            {
                "entity_id": TEST_CLIMATE_ZONE1_ENTITY_ID,
                "hvac_mode": HVACMode.HEAT,
            },
            blocking=True,
        )

        # Verify API was called correctly
        await hass.async_block_till_done()
        mock_client.atw.set_power.assert_called_once_with(TEST_ATW_UNIT_ID, True)


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
        mock_client.atw.set_mode_zone1 = AsyncMock()
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
        mock_client.atw.set_mode_zone1 = AsyncMock()
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
        operation_status="Heating",  # Real API returns simplified status
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
