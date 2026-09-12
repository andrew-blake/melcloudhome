"""Tests for the MELCloud Home ATA fan entity.

Behaviour through Home Assistant core interfaces only.
Reference: docs/testing-best-practices.md
Run with: make test-integration
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant

from .conftest import (
    create_mock_ata_building,
    create_mock_ata_unit,
    create_mock_ata_user_context,
    setup_ata_integration_custom,
)

# melcloudhome_<first4><last4> from create_device_info, plus the slug of
# _attr_name. Confirmed: slugify("melcloudhome_a1b2_9abc A/C fan", separator="_")
# gives this, and the same call on "... Climate" gives the climate constant.
_FAN_ENTITY = "fan.melcloudhome_a1b2_9abc_a_c_fan"


def _configure_ata_controls(client: Any) -> None:
    client.ata = MagicMock()
    client.ata.set_power = AsyncMock()
    client.ata.set_fan_speed = AsyncMock()
    client.ata.set_vane_vertical = AsyncMock()


@pytest.mark.asyncio
async def test_fan_entity_created_for_ata_unit(hass: HomeAssistant) -> None:
    """A unit with fan speeds gets a fan entity."""
    mock_context = create_mock_ata_user_context()
    await setup_ata_integration_custom(
        hass, mock_context, configure_client=_configure_ata_controls
    )

    assert hass.states.get(_FAN_ENTITY) is not None


@pytest.mark.asyncio
async def test_percentage_reflects_commanded_speed(hass: HomeAssistant) -> None:
    """Speed three of five reports as 60 percent."""
    mock_unit = create_mock_ata_unit(power=True, set_fan_speed="Three")
    mock_context = create_mock_ata_user_context(
        buildings=[create_mock_ata_building(units=[mock_unit])]
    )
    await setup_ata_integration_custom(
        hass, mock_context, configure_client=_configure_ata_controls
    )

    assert hass.states.get(_FAN_ENTITY).attributes["percentage"] == 60


@pytest.mark.asyncio
async def test_percentage_is_none_in_auto(hass: HomeAssistant) -> None:
    """No numbered speed is commanded in auto, so percentage is unknown."""
    mock_unit = create_mock_ata_unit(power=True, set_fan_speed="Auto")
    mock_context = create_mock_ata_user_context(
        buildings=[create_mock_ata_building(units=[mock_unit])]
    )
    await setup_ata_integration_custom(
        hass, mock_context, configure_client=_configure_ata_controls
    )

    state = hass.states.get(_FAN_ENTITY)
    assert state.attributes["percentage"] is None
    assert state.attributes["preset_mode"] == "auto"


@pytest.mark.asyncio
async def test_set_percentage_sends_matching_speed(hass: HomeAssistant) -> None:
    """Forty percent of five speeds is speed two."""
    mock_context = create_mock_ata_user_context()
    _, mock_client = await setup_ata_integration_custom(
        hass, mock_context, configure_client=_configure_ata_controls
    )

    await hass.services.async_call(
        "fan",
        "set_percentage",
        {"entity_id": _FAN_ENTITY, "percentage": 40},
        blocking=True,
    )

    mock_client.ata.set_fan_speed.assert_called_once()
    assert mock_client.ata.set_fan_speed.call_args[0][1] == "Two"


@pytest.mark.asyncio
async def test_set_percentage_zero_powers_the_unit_off(hass: HomeAssistant) -> None:
    """Zero means unit power off, and sends no speed."""
    mock_context = create_mock_ata_user_context()
    _, mock_client = await setup_ata_integration_custom(
        hass, mock_context, configure_client=_configure_ata_controls
    )

    await hass.services.async_call(
        "fan",
        "set_percentage",
        {"entity_id": _FAN_ENTITY, "percentage": 0},
        blocking=True,
    )

    assert mock_client.ata.set_power.call_args[0][1] is False
    mock_client.ata.set_fan_speed.assert_not_called()


@pytest.mark.asyncio
async def test_set_preset_mode_auto(hass: HomeAssistant) -> None:
    """The auto preset sends the API's Auto fan speed.

    The unit must start on a numbered speed: the control client skips the call
    when the device already holds the requested value (ADR-018), and the mock
    helper defaults to "Auto".
    """
    mock_unit = create_mock_ata_unit(power=True, set_fan_speed="Three")
    mock_context = create_mock_ata_user_context(
        buildings=[create_mock_ata_building(units=[mock_unit])]
    )
    _, mock_client = await setup_ata_integration_custom(
        hass, mock_context, configure_client=_configure_ata_controls
    )

    await hass.services.async_call(
        "fan",
        "set_preset_mode",
        {"entity_id": _FAN_ENTITY, "preset_mode": "auto"},
        blocking=True,
    )

    assert mock_client.ata.set_fan_speed.call_args[0][1] == "Auto"


@pytest.mark.asyncio
async def test_turn_off_powers_the_unit_down(hass: HomeAssistant) -> None:
    """An air conditioner has no fan-off state, so off means unit power off."""
    mock_context = create_mock_ata_user_context()
    _, mock_client = await setup_ata_integration_custom(
        hass, mock_context, configure_client=_configure_ata_controls
    )

    await hass.services.async_call(
        "fan", "turn_off", {"entity_id": _FAN_ENTITY}, blocking=True
    )

    assert mock_client.ata.set_power.call_args[0][1] is False


@pytest.mark.asyncio
async def test_speed_count_follows_device_capability(hass: HomeAssistant) -> None:
    """A three-speed unit gets three steps, not five."""
    mock_unit = create_mock_ata_unit(
        power=True, set_fan_speed="Three", number_of_fan_speeds=3
    )
    mock_context = create_mock_ata_user_context(
        buildings=[create_mock_ata_building(units=[mock_unit])]
    )
    await setup_ata_integration_custom(
        hass, mock_context, configure_client=_configure_ata_controls
    )

    state = hass.states.get(_FAN_ENTITY)
    assert state.attributes["percentage_step"] == pytest.approx(100 / 3)
    assert state.attributes["percentage"] == 100


@pytest.mark.asyncio
async def test_no_fan_entity_without_fan_speeds(hass: HomeAssistant) -> None:
    """A unit reporting no speeds gets no fan entity."""
    mock_unit = create_mock_ata_unit(number_of_fan_speeds=0)
    mock_context = create_mock_ata_user_context(
        buildings=[create_mock_ata_building(units=[mock_unit])]
    )
    await setup_ata_integration_custom(
        hass, mock_context, configure_client=_configure_ata_controls
    )

    assert hass.states.get(_FAN_ENTITY) is None


@pytest.mark.asyncio
async def test_oscillating_true_when_vane_swinging(hass: HomeAssistant) -> None:
    """The API's Swing is the only vane value that oscillates."""
    mock_unit = create_mock_ata_unit(power=True, vane_vertical="Swing")
    mock_context = create_mock_ata_user_context(
        buildings=[create_mock_ata_building(units=[mock_unit])]
    )
    await setup_ata_integration_custom(
        hass, mock_context, configure_client=_configure_ata_controls
    )

    assert hass.states.get(_FAN_ENTITY).attributes["oscillating"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("vane", ["Auto", "One", "Five"])
async def test_oscillating_false_for_fixed_positions(
    hass: HomeAssistant, vane: str
) -> None:
    """Auto is a fixed mode-dependent angle, not a sweep, per the vendor manual."""
    mock_unit = create_mock_ata_unit(power=True, vane_vertical=vane)
    mock_context = create_mock_ata_user_context(
        buildings=[create_mock_ata_building(units=[mock_unit])]
    )
    await setup_ata_integration_custom(
        hass, mock_context, configure_client=_configure_ata_controls
    )

    assert hass.states.get(_FAN_ENTITY).attributes["oscillating"] is False


@pytest.mark.asyncio
async def test_oscillate_on_sends_swing(hass: HomeAssistant) -> None:
    """Turning oscillation on sets the vane to Swing."""
    mock_context = create_mock_ata_user_context()
    _, mock_client = await setup_ata_integration_custom(
        hass, mock_context, configure_client=_configure_ata_controls
    )

    await hass.services.async_call(
        "fan",
        "oscillate",
        {"entity_id": _FAN_ENTITY, "oscillating": True},
        blocking=True,
    )

    assert mock_client.ata.set_vane_vertical.call_args[0][1] == "Swing"


@pytest.mark.asyncio
async def test_oscillate_off_sends_auto(hass: HomeAssistant) -> None:
    """Turning it off returns the vane to the unit's own positioning.

    The vane must start on "Swing", both because that is the only state you
    would switch oscillation off from, and because the control client skips a
    write matching the device's current value (ADR-018).
    """
    mock_unit = create_mock_ata_unit(power=True, vane_vertical="Swing")
    mock_context = create_mock_ata_user_context(
        buildings=[create_mock_ata_building(units=[mock_unit])]
    )
    _, mock_client = await setup_ata_integration_custom(
        hass, mock_context, configure_client=_configure_ata_controls
    )

    await hass.services.async_call(
        "fan",
        "oscillate",
        {"entity_id": _FAN_ENTITY, "oscillating": False},
        blocking=True,
    )

    assert mock_client.ata.set_vane_vertical.call_args[0][1] == "Auto"
