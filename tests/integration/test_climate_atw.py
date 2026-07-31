"""Tests for MELCloud Home ATW climate entity.

Tests cover climate entity behavior through Home Assistant core interfaces only.
Follows HA best practices: test observable behavior, not implementation details.

Reference: docs/testing-best-practices.md
Run with: make test-integration
"""

from unittest.mock import AsyncMock

import pytest
from homeassistant.components.climate import HVACAction, HVACMode
from homeassistant.core import HomeAssistant

from .conftest import (
    TEST_ATW_UNIT_ID,
    TEST_CLIMATE_ZONE1_ENTITY_ID,
    create_mock_atw_building,
    create_mock_atw_unit,
    create_mock_atw_user_context,
    setup_atw_integration_custom,
)


@pytest.mark.asyncio
async def test_atw_climate_zone1_created(hass: HomeAssistant) -> None:
    """Test ATW Zone 1 climate entity is created."""
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[create_mock_atw_unit()])]
    )
    await setup_atw_integration_custom(hass, mock_context)

    state = hass.states.get("climate.melcloudhome_0efc_9abc_zone_1")
    assert state is not None
    assert state.state == HVACMode.HEAT
    assert state.attributes["current_temperature"] == 20.0
    assert state.attributes["temperature"] == 21.0


@pytest.mark.asyncio
async def test_atw_set_temperature_zone1(hass: HomeAssistant) -> None:
    """Test setting Zone 1 temperature via service."""
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[create_mock_atw_unit()])]
    )
    _, mock_client = await setup_atw_integration_custom(hass, mock_context)
    mock_client.atw.set_temperature_zone1 = AsyncMock()

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": TEST_CLIMATE_ZONE1_ENTITY_ID, "temperature": 22.5},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_client.atw.set_temperature_zone1.assert_called_once_with(
        TEST_ATW_UNIT_ID, 22.5
    )


@pytest.mark.asyncio
async def test_atw_hvac_mode_heat_powers_up_system(hass: HomeAssistant) -> None:
    """Test setting HVAC mode to HEAT powers up ATW system."""
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[create_mock_atw_unit(power=False)])]
    )
    _, mock_client = await setup_atw_integration_custom(hass, mock_context)
    mock_client.atw.set_power = AsyncMock()
    mock_client.atw.set_mode_zone1 = AsyncMock()

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": TEST_CLIMATE_ZONE1_ENTITY_ID, "hvac_mode": HVACMode.HEAT},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_client.atw.set_power.assert_called_once_with(TEST_ATW_UNIT_ID, True)
    mock_client.atw.set_mode_zone1.assert_called_once_with(
        TEST_ATW_UNIT_ID, "HeatRoomTemperature"
    )


@pytest.mark.asyncio
async def test_atw_preset_mode_reflects_zone_operation_mode(
    hass: HomeAssistant,
) -> None:
    """Test preset mode reflects Zone 1 operation mode."""
    mock_context = create_mock_atw_user_context(
        [
            create_mock_atw_building(
                units=[create_mock_atw_unit(operation_mode_zone1="HeatRoomTemperature")]
            )
        ]
    )
    await setup_atw_integration_custom(hass, mock_context)

    state = hass.states.get("climate.melcloudhome_0efc_9abc_zone_1")
    assert state.attributes["preset_mode"] == "room"


@pytest.mark.asyncio
async def test_atw_set_preset_mode_room_to_flow(hass: HomeAssistant) -> None:
    """Test changing preset mode from room to flow."""
    mock_context = create_mock_atw_user_context(
        [
            create_mock_atw_building(
                units=[create_mock_atw_unit(operation_mode_zone1="HeatRoomTemperature")]
            )
        ]
    )
    _, mock_client = await setup_atw_integration_custom(hass, mock_context)
    mock_client.atw.set_mode_zone1 = AsyncMock()

    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": "climate.melcloudhome_0efc_9abc_zone_1", "preset_mode": "flow"},
        blocking=True,
    )


@pytest.mark.asyncio
async def test_atw_set_preset_mode_flow_to_curve(hass: HomeAssistant) -> None:
    """Test changing preset mode from flow to curve."""
    mock_context = create_mock_atw_user_context(
        [
            create_mock_atw_building(
                units=[create_mock_atw_unit(operation_mode_zone1="HeatFlowTemperature")]
            )
        ]
    )
    _, mock_client = await setup_atw_integration_custom(hass, mock_context)
    mock_client.atw.set_mode_zone1 = AsyncMock()

    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": "climate.melcloudhome_0efc_9abc_zone_1", "preset_mode": "curve"},
        blocking=True,
    )


@pytest.mark.asyncio
async def test_atw_hvac_action_idle_when_valve_on_dhw(hass: HomeAssistant) -> None:
    """Test HVAC action is IDLE when 3-way valve is on DHW (ATW-specific)."""
    mock_unit = create_mock_atw_unit(
        power=True,
        room_temperature_zone1=18.0,
        set_temperature_zone1=21.0,
        operation_mode_zone1="HeatRoomTemperature",
        operation_status="HotWater",
    )
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )
    await setup_atw_integration_custom(hass, mock_context)

    state = hass.states.get("climate.melcloudhome_0efc_9abc_zone_1")
    assert state.attributes["hvac_action"] == HVACAction.IDLE


@pytest.mark.asyncio
async def test_atw_hvac_action_heating_when_valve_on_zone1_and_below_target(
    hass: HomeAssistant,
) -> None:
    """Test HVAC action is HEATING when valve on Zone 1 and below target."""
    mock_unit = create_mock_atw_unit(
        power=True,
        room_temperature_zone1=18.0,
        set_temperature_zone1=21.0,
        operation_mode_zone1="HeatRoomTemperature",
        operation_status="Heating",
    )
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )
    await setup_atw_integration_custom(hass, mock_context)

    state = hass.states.get("climate.melcloudhome_0efc_9abc_zone_1")
    assert state.attributes["hvac_action"] == HVACAction.HEATING


@pytest.mark.asyncio
async def test_atw_extra_state_attributes_include_valve_status(
    hass: HomeAssistant,
) -> None:
    """Test extra state attributes include operation_status and valve info."""
    mock_unit = create_mock_atw_unit(
        operation_status="Heating", forced_hot_water_mode=False
    )
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )
    await setup_atw_integration_custom(hass, mock_context)

    state = hass.states.get("climate.melcloudhome_0efc_9abc_zone_1")
    assert state.attributes["operation_status"] == "Heating"
    assert "forced_dhw_active" in state.attributes
    assert "zone_heating_available" in state.attributes


@pytest.mark.asyncio
async def test_atw_climate_unavailable_when_device_in_error(
    hass: HomeAssistant,
) -> None:
    """Test ATW climate entity unavailable when device in error."""
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[create_mock_atw_unit(is_in_error=True)])]
    )
    await setup_atw_integration_custom(hass, mock_context)

    assert (
        hass.states.get("climate.melcloudhome_0efc_9abc_zone_1").state == "unavailable"
    )


@pytest.mark.asyncio
async def test_atw_climate_zone_naming_includes_zone_1_suffix(
    hass: HomeAssistant,
) -> None:
    """Test ATW climate entity ID includes zone_1 suffix."""
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[create_mock_atw_unit()])]
    )
    await setup_atw_integration_custom(hass, mock_context)

    state = hass.states.get("climate.melcloudhome_0efc_9abc_zone_1")
    assert state is not None
    assert "_zone_1" in state.entity_id


@pytest.mark.asyncio
async def test_atw_climate_off_when_power_false(hass: HomeAssistant) -> None:
    """Test ATW climate state is OFF when power is false."""
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[create_mock_atw_unit(power=False)])]
    )
    await setup_atw_integration_custom(hass, mock_context)

    assert (
        hass.states.get("climate.melcloudhome_0efc_9abc_zone_1").state == HVACMode.OFF
    )


# ==============================================================================
# Cooling Mode Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_atw_cooling_hvac_mode_available_when_capability_enabled(
    hass: HomeAssistant,
) -> None:
    """Test COOL hvac_mode available when has_cooling_mode=True."""
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[create_mock_atw_unit(has_cooling_mode=True)])]
    )
    await setup_atw_integration_custom(hass, mock_context)

    state = hass.states.get(TEST_CLIMATE_ZONE1_ENTITY_ID)
    assert HVACMode.COOL in state.attributes["hvac_modes"]
    assert HVACMode.HEAT in state.attributes["hvac_modes"]
    assert HVACMode.OFF in state.attributes["hvac_modes"]


@pytest.mark.asyncio
async def test_atw_cooling_hvac_mode_unavailable_without_capability(
    hass: HomeAssistant,
) -> None:
    """Test COOL hvac_mode unavailable when has_cooling_mode=False."""
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[create_mock_atw_unit(has_cooling_mode=False)])]
    )
    await setup_atw_integration_custom(hass, mock_context)

    state = hass.states.get(TEST_CLIMATE_ZONE1_ENTITY_ID)
    assert HVACMode.COOL not in state.attributes["hvac_modes"]
    assert HVACMode.HEAT in state.attributes["hvac_modes"]


@pytest.mark.asyncio
async def test_atw_cooling_mode_detected_from_operation_mode(
    hass: HomeAssistant,
) -> None:
    """Test cooling mode detected from CoolRoomTemperature operation mode."""
    mock_unit = create_mock_atw_unit(
        has_cooling_mode=True, operation_mode_zone1="CoolRoomTemperature"
    )
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )
    await setup_atw_integration_custom(hass, mock_context)

    state = hass.states.get(TEST_CLIMATE_ZONE1_ENTITY_ID)
    assert state.state == HVACMode.COOL
    assert state.attributes["preset_mode"] == "room"


@pytest.mark.asyncio
async def test_atw_cooling_preset_modes_only_room_and_flow(
    hass: HomeAssistant,
) -> None:
    """Test cooling mode shows only room and flow presets (no curve)."""
    mock_unit = create_mock_atw_unit(
        has_cooling_mode=True, operation_mode_zone1="CoolRoomTemperature"
    )
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )
    await setup_atw_integration_custom(hass, mock_context)

    state = hass.states.get(TEST_CLIMATE_ZONE1_ENTITY_ID)
    preset_modes = state.attributes["preset_modes"]
    assert "room" in preset_modes
    assert "flow" in preset_modes
    assert "curve" not in preset_modes
    assert len(preset_modes) == 2


@pytest.mark.asyncio
async def test_atw_heating_preset_modes_all_three(hass: HomeAssistant) -> None:
    """Test heating mode shows all three presets (room, flow, curve)."""
    mock_unit = create_mock_atw_unit(
        has_cooling_mode=True, operation_mode_zone1="HeatRoomTemperature"
    )
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )
    await setup_atw_integration_custom(hass, mock_context)

    state = hass.states.get(TEST_CLIMATE_ZONE1_ENTITY_ID)
    preset_modes = state.attributes["preset_modes"]
    assert "room" in preset_modes
    assert "flow" in preset_modes
    assert "curve" in preset_modes
    assert len(preset_modes) == 3


@pytest.mark.asyncio
async def test_atw_cooling_temperature_step_always_one_degree(
    hass: HomeAssistant,
) -> None:
    """Test cooling mode always uses 1.0°C temperature step."""
    mock_unit = create_mock_atw_unit(
        has_cooling_mode=True, operation_mode_zone1="CoolRoomTemperature"
    )
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )
    await setup_atw_integration_custom(hass, mock_context)

    assert (
        hass.states.get(TEST_CLIMATE_ZONE1_ENTITY_ID).attributes["target_temp_step"]
        == 1.0
    )


@pytest.mark.asyncio
async def test_atw_set_preset_mode_in_cooling(hass: HomeAssistant) -> None:
    """Test setting preset mode from room to flow in cooling mode."""
    mock_unit = create_mock_atw_unit(
        has_cooling_mode=True, operation_mode_zone1="CoolRoomTemperature"
    )
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )
    _, mock_client = await setup_atw_integration_custom(hass, mock_context)
    mock_client.atw.set_mode_zone1 = AsyncMock()

    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": TEST_CLIMATE_ZONE1_ENTITY_ID, "preset_mode": "flow"},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_client.atw.set_mode_zone1.assert_called_once_with(
        TEST_ATW_UNIT_ID, "CoolFlowTemperature"
    )


@pytest.mark.asyncio
async def test_atw_set_hvac_mode_to_cool(hass: HomeAssistant) -> None:
    """Test setting HVAC mode to COOL."""
    mock_unit = create_mock_atw_unit(
        has_cooling_mode=True,
        power=False,
        operation_mode_zone1="HeatRoomTemperature",
    )
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )
    _, mock_client = await setup_atw_integration_custom(hass, mock_context)
    mock_client.atw.set_power = AsyncMock()
    mock_client.atw.set_mode_zone1 = AsyncMock()

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": TEST_CLIMATE_ZONE1_ENTITY_ID, "hvac_mode": HVACMode.COOL},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_client.atw.set_power.assert_called_once_with(TEST_ATW_UNIT_ID, True)
    mock_client.atw.set_mode_zone1.assert_called_once_with(
        TEST_ATW_UNIT_ID, "CoolRoomTemperature"
    )
