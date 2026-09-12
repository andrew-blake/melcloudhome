"""Tests for the MELCloud Home ATA fan entity.

Behaviour through Home Assistant core interfaces only.
Reference: docs/testing-best-practices.md
Run with: make test-integration
"""

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.melcloudhome.const import DOMAIN

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
    client.ata.set_power_and_mode = AsyncMock()
    client.ata.set_fan_speed = AsyncMock()
    client.ata.set_vane_vertical = AsyncMock()


async def _setup(hass: HomeAssistant, **unit_kw: Any) -> tuple[Any, Any]:
    """Set up the integration with one ATA unit, returning (entry, mock_client)."""
    context = create_mock_ata_user_context(
        buildings=[create_mock_ata_building(units=[create_mock_ata_unit(**unit_kw)])]
    )
    return await setup_ata_integration_custom(
        hass, context, configure_client=_configure_ata_controls
    )


async def _set_percentage(hass: HomeAssistant, percentage: int) -> None:
    await hass.services.async_call(
        "fan",
        "set_percentage",
        {"entity_id": _FAN_ENTITY, "percentage": percentage},
        blocking=True,
    )


async def _let_the_speed_write_land(hass: HomeAssistant) -> None:
    """Advance HA's clock past the fan's speed debounce window.

    The write is scheduled with async_call_later, so firing the loop's timers is
    enough - no real time passes and nothing here is timing-dependent.
    """
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=2))
    await hass.async_block_till_done()


@pytest.mark.asyncio
async def test_fan_entity_created_for_ata_unit(hass: HomeAssistant) -> None:
    """A unit with fan speeds gets a fan entity."""
    await _setup(hass)

    assert hass.states.get(_FAN_ENTITY) is not None


@pytest.mark.asyncio
async def test_percentage_reflects_commanded_speed(hass: HomeAssistant) -> None:
    """Speed three of five reports as 60 percent."""
    await _setup(hass, power=True, set_fan_speed="Three")

    assert hass.states.get(_FAN_ENTITY).attributes["percentage"] == 60


@pytest.mark.asyncio
async def test_percentage_is_none_before_any_numbered_speed_seen(
    hass: HomeAssistant,
) -> None:
    """Auto with nothing remembered yet leaves percentage unknown.

    The unit starts in auto, so there is no numbered speed to resume; today's
    behaviour (the HomeKit bridge falling back to its own hard-coded 50%) is
    the correct graceful degradation here. See
    test_percentage_reports_last_numbered_speed_in_auto for the case where a
    speed *has* been seen.
    """
    await _setup(hass, power=True, set_fan_speed="Auto")

    state = hass.states.get(_FAN_ENTITY)
    assert state.attributes["percentage"] is None
    assert state.attributes["preset_mode"] == "auto"


@pytest.mark.asyncio
async def test_percentage_reports_last_numbered_speed_in_auto(
    hass: HomeAssistant,
) -> None:
    """Switching to auto from a numbered speed keeps reporting that speed.

    Regression test for #318: HomeKit's bridge reads back our percentage when
    the user leaves Auto for Manual, and falls back to a hard-coded 50% if it
    finds None -- moving the unit to a speed the user never chose. Reporting
    the last numbered speed we saw instead of None lets leaving auto resume
    it.
    """
    _, mock_client = await _setup(hass, power=True, set_fan_speed="Three")

    updated_unit = create_mock_ata_unit(power=True, set_fan_speed="Auto")
    updated_context = create_mock_ata_user_context(
        [create_mock_ata_building(units=[updated_unit])]
    )
    mock_client.get_user_context = AsyncMock(return_value=updated_context)
    await hass.services.async_call(DOMAIN, "force_refresh", {}, blocking=True)
    await hass.async_block_till_done()

    state = hass.states.get(_FAN_ENTITY)
    assert state.attributes["percentage"] == 60
    assert state.attributes["preset_mode"] == "auto"


@pytest.mark.asyncio
async def test_set_percentage_sends_matching_speed(hass: HomeAssistant) -> None:
    """Forty percent of five speeds is speed two."""
    _, mock_client = await _setup(hass)

    await _set_percentage(hass, 40)
    await _let_the_speed_write_land(hass)

    mock_client.ata.set_fan_speed.assert_called_once()
    assert mock_client.ata.set_fan_speed.call_args[0][1] == "Two"


@pytest.mark.asyncio
async def test_set_percentage_zero_powers_the_unit_off(hass: HomeAssistant) -> None:
    """Zero means unit power off, and sends no speed."""
    _, mock_client = await _setup(hass)

    await _set_percentage(hass, 0)
    await _let_the_speed_write_land(hass)

    assert mock_client.ata.set_power.call_args[0][1] is False
    mock_client.ata.set_fan_speed.assert_not_called()


@pytest.mark.asyncio
async def test_set_preset_mode_auto(hass: HomeAssistant) -> None:
    """The auto preset sends the API's Auto fan speed.

    The unit must start on a numbered speed: the control client skips the call
    when the device already holds the requested value (ADR-018), and the mock
    helper defaults to "Auto".
    """
    _, mock_client = await _setup(hass, power=True, set_fan_speed="Three")

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
    _, mock_client = await _setup(hass)

    await hass.services.async_call(
        "fan", "turn_off", {"entity_id": _FAN_ENTITY}, blocking=True
    )

    assert mock_client.ata.set_power.call_args[0][1] is False


@pytest.mark.asyncio
async def test_speed_count_follows_device_capability(hass: HomeAssistant) -> None:
    """A three-speed unit gets three steps, not five."""
    await _setup(hass, power=True, set_fan_speed="Three", number_of_fan_speeds=3)

    state = hass.states.get(_FAN_ENTITY)
    assert state.attributes["percentage_step"] == pytest.approx(100 / 3)
    assert state.attributes["percentage"] == 100


@pytest.mark.asyncio
async def test_no_fan_entity_without_fan_speeds(hass: HomeAssistant) -> None:
    """A unit reporting no speeds gets no fan entity."""
    await _setup(hass, number_of_fan_speeds=0)

    assert hass.states.get(_FAN_ENTITY) is None


@pytest.mark.asyncio
async def test_oscillating_true_when_vane_swinging(hass: HomeAssistant) -> None:
    """The API's Swing is the only vane value that oscillates."""
    await _setup(hass, power=True, vane_vertical="Swing")

    assert hass.states.get(_FAN_ENTITY).attributes["oscillating"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("vane", ["Auto", "One", "Five"])
async def test_oscillating_false_for_fixed_positions(
    hass: HomeAssistant, vane: str
) -> None:
    """Auto is a fixed mode-dependent angle, not a sweep, per the vendor manual."""
    await _setup(hass, power=True, vane_vertical=vane)

    assert hass.states.get(_FAN_ENTITY).attributes["oscillating"] is False


@pytest.mark.asyncio
async def test_oscillate_on_sends_swing(hass: HomeAssistant) -> None:
    """Turning oscillation on sets the vane to Swing."""
    _, mock_client = await _setup(hass)

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
    _, mock_client = await _setup(hass, power=True, vane_vertical="Swing")

    await hass.services.async_call(
        "fan",
        "oscillate",
        {"entity_id": _FAN_ENTITY, "oscillating": False},
        blocking=True,
    )

    assert mock_client.ata.set_vane_vertical.call_args[0][1] == "Auto"


@pytest.mark.asyncio
async def test_turn_on_preserves_the_operation_mode(hass: HomeAssistant) -> None:
    """Power-on carries the mode, so no operationMode=null reaches the API.

    A bare power write can fault a multi-zone outdoor unit. The unit starts off
    because the control client skips a write the device already satisfies.
    """
    _, mock_client = await _setup(hass, power=False, operation_mode="Heat")

    await hass.services.async_call(
        "fan", "turn_on", {"entity_id": _FAN_ENTITY}, blocking=True
    )

    assert mock_client.ata.set_power_and_mode.call_args[0][1:] == (True, "Heat")
    mock_client.ata.set_power.assert_not_called()


@pytest.mark.asyncio
async def test_turn_on_with_percentage_supersedes_a_pending_drag_write(
    hass: HomeAssistant,
) -> None:
    """An explicit turn_on is a single deliberate command, not a drag.

    It writes without waiting on the debounce window, and the pending write from
    the drag it interrupted must not land afterwards and undo it.
    """
    _, mock_client = await _setup(
        hass, power=True, operation_mode="Heat", set_fan_speed="Auto"
    )

    await _set_percentage(hass, 20)
    await hass.services.async_call(
        "fan",
        "turn_on",
        {"entity_id": _FAN_ENTITY, "percentage": 100},
        blocking=True,
    )

    mock_client.ata.set_fan_speed.assert_called_once()
    assert mock_client.ata.set_fan_speed.call_args[0][1] == "Five"

    await _let_the_speed_write_land(hass)

    mock_client.ata.set_fan_speed.assert_called_once()


@pytest.mark.asyncio
async def test_turn_on_with_percentage_sets_power_and_speed(
    hass: HomeAssistant,
) -> None:
    """turn_on(percentage=40) powers on and commands speed two of five."""
    _, mock_client = await _setup(
        hass, power=False, operation_mode="Heat", set_fan_speed="Auto"
    )

    await hass.services.async_call(
        "fan",
        "turn_on",
        {"entity_id": _FAN_ENTITY, "percentage": 40},
        blocking=True,
    )

    assert mock_client.ata.set_power_and_mode.call_args[0][1:] == (True, "Heat")
    assert mock_client.ata.set_fan_speed.call_args[0][1] == "Two"


@pytest.mark.asyncio
async def test_turn_on_with_auto_preset_sets_power_and_speed(
    hass: HomeAssistant,
) -> None:
    """HomeKit's Auto toggle routes through turn_on, so it must power on too."""
    _, mock_client = await _setup(
        hass, power=False, operation_mode="Heat", set_fan_speed="Three"
    )

    await hass.services.async_call(
        "fan",
        "turn_on",
        {"entity_id": _FAN_ENTITY, "preset_mode": "auto"},
        blocking=True,
    )

    assert mock_client.ata.set_power_and_mode.call_args[0][1:] == (True, "Heat")
    assert mock_client.ata.set_fan_speed.call_args[0][1] == "Auto"


@pytest.mark.asyncio
async def test_set_percentage_powers_on_an_off_unit(hass: HomeAssistant) -> None:
    """Dragging the HomeKit slider up on an off tile must start the unit.

    The bridge sends Active=1 and RotationSpeed in one write and then skips
    fan.turn_on, so set_percentage alone has to power the unit on.
    """
    _, mock_client = await _setup(
        hass, power=False, operation_mode="Heat", set_fan_speed="Auto"
    )

    await _set_percentage(hass, 60)
    await _let_the_speed_write_land(hass)

    assert mock_client.ata.set_power_and_mode.call_args[0][1:] == (True, "Heat")
    assert mock_client.ata.set_fan_speed.call_args[0][1] == "Three"


@pytest.mark.asyncio
async def test_set_percentage_burst_writes_only_the_final_speed(
    hass: HomeAssistant,
) -> None:
    """Regression test for #318.

    A HomeKit slider drag issues several set_percentage calls in quick
    succession. Issuing a write per intermediate position let them overlap in
    flight, and the server applies overlapping writes in arrival order rather
    than issue order: a drag ending on Three was observed writing Two, Three,
    Three, Three and settling on Two. Only the position the user released on may
    reach the API, which also collapses the power-on burst to a single write.
    """
    _, mock_client = await _setup(
        hass, power=False, operation_mode="Heat", set_fan_speed="Auto"
    )

    for percentage in (20, 40, 60):
        await _set_percentage(hass, percentage)
    await _let_the_speed_write_land(hass)

    assert mock_client.ata.set_power_and_mode.call_count == 1
    assert mock_client.ata.set_power_and_mode.call_args[0][1:] == (True, "Heat")
    mock_client.ata.set_fan_speed.assert_called_once()
    assert mock_client.ata.set_fan_speed.call_args[0][1] == "Three"


@pytest.mark.asyncio
async def test_set_percentage_burst_powers_on_immediately(
    hass: HomeAssistant,
) -> None:
    """The power-on is not debounced along with the speed.

    Verified on hardware: the unit must start the moment the drag begins, not
    half a second after it ends. So before the clock advances, the power write
    has already gone and the speed write has not.
    """
    _, mock_client = await _setup(
        hass, power=False, operation_mode="Heat", set_fan_speed="Auto"
    )

    for percentage in (20, 40, 60):
        await _set_percentage(hass, percentage)

    assert mock_client.ata.set_power_and_mode.call_count == 1
    mock_client.ata.set_fan_speed.assert_not_called()


@pytest.mark.asyncio
async def test_dragging_through_zero_does_not_power_off(
    hass: HomeAssistant,
) -> None:
    """Passing the zero detent mid-drag must not stop the unit.

    Only the released position counts, so a drag from low through zero and back
    up sends one speed and no power-off. The unit starts on, so a power-off
    write would really be issued rather than skipped by the write-dedup.
    """
    _, mock_client = await _setup(
        hass, power=True, operation_mode="Heat", set_fan_speed="Auto"
    )

    for percentage in (40, 0, 80):
        await _set_percentage(hass, percentage)
    await _let_the_speed_write_land(hass)

    mock_client.ata.set_power.assert_not_called()
    mock_client.ata.set_fan_speed.assert_called_once()
    assert mock_client.ata.set_fan_speed.call_args[0][1] == "Four"


@pytest.mark.asyncio
async def test_pending_speed_write_is_dropped_when_the_entity_goes_away(
    hass: HomeAssistant,
) -> None:
    """Unloading the entry must leave no write scheduled behind it."""
    entry, mock_client = await _setup(
        hass, power=True, operation_mode="Heat", set_fan_speed="Auto"
    )

    await _set_percentage(hass, 60)
    await hass.config_entries.async_unload(entry.entry_id)
    await _let_the_speed_write_land(hass)

    mock_client.ata.set_fan_speed.assert_not_called()


@pytest.mark.asyncio
async def test_turn_on_still_powers_on_after_a_set_percentage_burst(
    hass: HomeAssistant,
) -> None:
    """The drag-burst guard must never make the documented turn_on service
    unreliable: an explicit fan.turn_on always powers on, even immediately
    after a set_percentage call already consumed the guard window.
    """
    _, mock_client = await _setup(
        hass, power=False, operation_mode="Heat", set_fan_speed="Auto"
    )

    await _set_percentage(hass, 20)
    await hass.services.async_call(
        "fan", "turn_on", {"entity_id": _FAN_ENTITY}, blocking=True
    )

    assert mock_client.ata.set_power_and_mode.call_count == 2


@pytest.mark.asyncio
async def test_no_oscillation_without_a_vane(hass: HomeAssistant) -> None:
    """A unit with neither swing nor air direction gets no oscillate control."""
    await _setup(hass, power=True, has_swing=False, has_air_direction=False)

    assert "oscillating" not in hass.states.get(_FAN_ENTITY).attributes
