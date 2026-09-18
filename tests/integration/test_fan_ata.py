"""Tests for the MELCloud Home ATA fan entity.

Behaviour through Home Assistant core interfaces only.
Reference: docs/testing-best-practices.md
Run with: make test-integration
"""

import asyncio
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.melcloudhome import fan as fan_module
from custom_components.melcloudhome.api.exceptions import ApiError
from custom_components.melcloudhome.const import DOMAIN

from .conftest import (
    create_mock_ata_building,
    create_mock_ata_unit,
    create_mock_ata_user_context,
    setup_ata_integration_custom,
)

# The climate tests already mock every ATA control this platform can reach, and
# then some; a second copy here would only drift out of step with it.
from .test_climate_ata import _configure_ata_controls

# melcloudhome_<first4><last4> from create_device_info, plus the slug of
# _attr_name. Confirmed: slugify("melcloudhome_a1b2_9abc A/C fan", separator="_")
# gives this, and the same call on "... Climate" gives the climate constant.
_FAN_ENTITY = "fan.melcloudhome_a1b2_9abc_a_c_fan"


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


def _speeds_written(mock_client: Any) -> list[str]:
    """Every speed that reached the API, whichever call carried it.

    A power-on that knows the unit's mode sends the speed in the same request,
    so most speeds arrive as set_power_and_mode's fourth argument. A unit
    reporting no mode to preserve still sends the two separately. Asserting on
    this rather than on one mock keeps the test about the speed reaching the API
    rather than about which call carried it.
    """
    speeds = [
        c[0][3]
        for c in mock_client.ata.set_power_and_mode.call_args_list
        if len(c[0]) > 3 and c[0][3] is not None
    ]
    speeds += [c[0][1] for c in mock_client.ata.set_fan_speed.call_args_list]
    return speeds


async def _let_tasks_run() -> None:
    """Give already-created tasks room to reach their next suspension point.

    Yields to the event loop a fixed number of times. Nothing sleeps and no real
    time passes, so this stays deterministic: every mock in play completes
    without awaiting anything real, so the only thing that can still be holding a
    task afterwards is the test's own gate.
    """
    for _ in range(20):
        await asyncio.sleep(0)


async def _power_off_via_service(hass: HomeAssistant) -> None:
    """Tap the tile off."""
    await hass.services.async_call(
        "fan", "turn_off", {"entity_id": _FAN_ENTITY}, blocking=True
    )


async def _power_off_via_slider(hass: HomeAssistant) -> None:
    """Drag to the zero detent and leave it there, so the write actually lands."""
    await _set_percentage(hass, 0)
    await _let_the_speed_write_land(hass)


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

    assert _speeds_written(mock_client) == ["Two"]


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

    A bare power write can fault a multi-zone outdoor unit. What is under test
    is which method carries the write, not whether it is sent.
    """
    _, mock_client = await _setup(hass, power=False, operation_mode="Heat")

    await hass.services.async_call(
        "fan", "turn_on", {"entity_id": _FAN_ENTITY}, blocking=True
    )

    assert mock_client.ata.set_power_and_mode.call_args[0][1:] == (True, "Heat", None)
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

    assert _speeds_written(mock_client) == ["Five"]

    await _let_the_speed_write_land(hass)

    assert _speeds_written(mock_client) == ["Five"]


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

    assert mock_client.ata.set_power_and_mode.call_args[0][1:] == (
        True,
        "Heat",
        "Two",
    )


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

    assert mock_client.ata.set_power_and_mode.call_args[0][1:] == (
        True,
        "Heat",
        "Auto",
    )


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

    assert mock_client.ata.set_power_and_mode.call_args[0][1:] == (
        True,
        "Heat",
        "Three",
    )


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

    The power-on is not deferred with the speed. Verified on hardware: the unit
    must start the moment the drag begins, not half a second after it ends,
    hence the assertions before the clock is advanced as well as after.
    """
    _, mock_client = await _setup(
        hass, power=False, operation_mode="Heat", set_fan_speed="Auto"
    )

    for percentage in (20, 40, 60):
        await _set_percentage(hass, percentage)

    assert mock_client.ata.set_power_and_mode.call_count == 0
    mock_client.ata.set_fan_speed.assert_not_called()

    await _let_the_speed_write_land(hass)

    assert mock_client.ata.set_power_and_mode.call_count == 1
    assert mock_client.ata.set_power_and_mode.call_args[0][1:] == (
        True,
        "Heat",
        "Three",
    )
    assert _speeds_written(mock_client) == ["Three"]


@pytest.mark.asyncio
async def test_concurrent_set_percentage_calls_write_the_last_position(
    hass: HomeAssistant,
) -> None:
    """Overlapping set_percentage calls must still write the released position.

    The test above awaits each call to completion, which is the one dispatch
    pattern the HomeKit bridge never uses: it fires each service call as its own
    un-awaited task, and Home Assistant takes no per-entity lock, so a drag's
    calls really do interleave at every await. Here the power-on request is held
    open so they do, and the later calls arrive while the first is still in
    flight.

    The pending position and its timer are claimed on entry, so the last call to
    arrive wins whatever order the calls interleave in. A drag issues no request
    at all until its timer fires, so there is no in-flight write for the later
    calls to arrive during, and the burst collapses to one write of the released
    position.
    """
    _, mock_client = await _setup(
        hass, power=False, operation_mode="Heat", set_fan_speed="Auto"
    )

    tasks = []
    for percentage in (20, 40, 60):
        tasks.append(
            asyncio.create_task(
                hass.services.async_call(
                    "fan",
                    "set_percentage",
                    {"entity_id": _FAN_ENTITY, "percentage": percentage},
                    blocking=True,
                )
            )
        )
        await _let_tasks_run()

    # No request has gone out yet: each call replaced the previous pending
    # position and restarted its timer.
    assert mock_client.ata.set_power_and_mode.call_count == 0

    await asyncio.gather(*tasks)
    await _let_the_speed_write_land(hass)

    assert mock_client.ata.set_power_and_mode.call_count == 1
    assert _speeds_written(mock_client) == ["Three"]


@pytest.mark.asyncio
async def test_a_failed_power_on_does_not_suppress_the_retry(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Arming the guard before the request must not make a failure stick.

    The deadline goes up before the write is awaited so that a drag's
    overlapping calls collapse into one power-on rather than one each. If that
    write then fails the unit is still off, so the deadline has to come back
    down and let the next call try again.

    The guard window is widened out of the way for the same reason as in
    test_power_off_disarms_the_power_on_guard: it is measured on the real clock.
    """
    monkeypatch.setattr(fan_module, "_POWER_ON_GUARD_WINDOW", 3600.0)
    _, mock_client = await _setup(
        hass, power=False, operation_mode="Heat", set_fan_speed="Auto"
    )

    mock_client.ata.set_power_and_mode.side_effect = ApiError("upstream said no")
    await _set_percentage(hass, 40)
    await _let_the_speed_write_land(hass)

    mock_client.ata.set_power_and_mode.side_effect = None
    await _set_percentage(hass, 60)
    await _let_the_speed_write_land(hass)

    assert mock_client.ata.set_power_and_mode.call_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("power_off", [_power_off_via_service, _power_off_via_slider])
async def test_power_off_disarms_the_power_on_guard(
    hass: HomeAssistant, power_off: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Turning the unit off must not leave a drag's guard suppressing the restart.

    Reachable entirely from the Home app on a running unit: dragging the slider
    arms the guard whether or not the unit needed the power-on, and nothing
    about that write clears it. Tap the tile off (or drag to the zero detent),
    then drag straight
    back up: the bridge sends Active and RotationSpeed together and deliberately
    skips fan.turn_on, so it arrives as set_percentage alone. A surviving guard
    would suppress the power-on and leave the unit off with a speed write landing
    on it, contradicting docs/homekit.md.

    The guard window is
    widened out of the way because it is measured on the real clock, which
    async_fire_time_changed does not move: at its production three seconds the
    result would depend on how long the test itself took to run, and the only
    thing under test here is whether the power-off disarms the guard, not when
    it would have expired on its own.
    """
    monkeypatch.setattr(fan_module, "_POWER_ON_GUARD_WINDOW", 3600.0)
    _, mock_client = await _setup(
        hass, power=False, operation_mode="Heat", set_fan_speed="Auto"
    )

    await _set_percentage(hass, 40)
    await _let_the_speed_write_land(hass)
    assert mock_client.ata.set_power_and_mode.call_count == 1

    await power_off(hass)
    await _set_percentage(hass, 60)
    await _let_the_speed_write_land(hass)

    assert mock_client.ata.set_power_and_mode.call_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("power_off", [_power_off_via_service, _power_off_via_slider])
async def test_power_off_is_sent_to_a_unit_already_off(
    hass: HomeAssistant, power_off: Any
) -> None:
    """An off must reach the API even when the unit already reads off.

    Found on hardware while building #318's fan entity.

    Observed on hardware: from off, a drag up followed by a drag to zero left
    the air conditioner running while the Home app showed it off. The power-on
    had not reached coordinator data yet, so the off was compared against a
    copy still reading power=False and dropped.

    The same comparison is what a reintroduced check would make, so the witness
    is an off issued while the coordinator's copy already reads off: it has to
    go out anyway.
    """
    _, mock_client = await _setup(
        hass, power=False, operation_mode="Heat", set_fan_speed="Auto"
    )

    await power_off(hass)

    mock_client.ata.set_power.assert_called_once()
    assert mock_client.ata.set_power.call_args[0][1] is False


@pytest.mark.asyncio
async def test_dragging_through_zero_does_not_power_off(
    hass: HomeAssistant,
) -> None:
    """Passing the zero detent mid-drag must not stop the unit.

    Only the released position counts, so a drag from low through zero and back
    up sends one speed and no power-off. Nothing is deduplicated, so a
    power-off reaching the control client would reach the API too: the
    assertion below fails if the zero detent is applied mid-drag.
    """
    _, mock_client = await _setup(
        hass, power=True, operation_mode="Heat", set_fan_speed="Auto"
    )

    for percentage in (40, 0, 80):
        await _set_percentage(hass, percentage)
    await _let_the_speed_write_land(hass)

    mock_client.ata.set_power.assert_not_called()
    assert _speeds_written(mock_client) == ["Four"]


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

    assert mock_client.ata.set_power_and_mode.call_count == 1
    assert mock_client.ata.set_power_and_mode.call_args[0][1] is True


@pytest.mark.asyncio
async def test_no_oscillation_without_a_vane(hass: HomeAssistant) -> None:
    """A unit with neither swing nor air direction gets no oscillate control."""
    await _setup(hass, power=True, has_swing=False, has_air_direction=False)

    assert "oscillating" not in hass.states.get(_FAN_ENTITY).attributes


@pytest.mark.asyncio
async def test_the_same_speed_twice_is_sent_twice(hass: HomeAssistant) -> None:
    """A speed the unit already reads still reaches the API.

    The fixture starts on One and both writes ask for One. A check comparing
    the request against the coordinator's copy would skip both, so this is the
    witness for its absence; a change-and-change-back is not, because the copy
    is updated after every accepted write and never matches the next request.
    """
    _, mock_client = await _setup(
        hass, power=True, operation_mode="Heat", set_fan_speed="One"
    )

    for _ in range(2):
        await _set_percentage(hass, 20)
        await _let_the_speed_write_land(hass)

    assert _speeds_written(mock_client) == [
        "One",
        "One",
    ]


@pytest.mark.asyncio
async def test_entity_shows_a_written_speed_before_the_next_refresh(
    hass: HomeAssistant,
) -> None:
    """The value applied to the coordinator's copy reaches entities before any poll.

    The refresh is deliberately left in flight. _let_the_speed_write_land would
    drain it, and because the API mock returns one UserContext object forever,
    that refresh re-registers the very unit the setter mutated and pushes
    the value itself, which passes whether or not listeners were notified.
    Yielding to the loop instead lets the write land while the refresh is still
    on its debounce, so the only thing that can have updated hass.states is the
    notify.
    """
    await _setup(hass, power=True, operation_mode="Heat", set_fan_speed="One")

    await _set_percentage(hass, 80)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=2))
    await _let_tasks_run()

    assert hass.states.get(_FAN_ENTITY).attributes["percentage"] == 80


@pytest.mark.asyncio
async def test_a_write_landing_during_a_poll_still_shows_the_written_speed(
    hass: HomeAssistant,
) -> None:
    """The copy is fetched after the write, not before.

    While the speed PUT is in flight a poll completes and replaces every unit
    object with one parsed from a response that predates the write. A copy
    fetched before the write would be the discarded object, and the entity
    would keep reading the poll's speed. Fetched afterwards, the written speed
    lands on the object entities read.
    """
    _, mock_client = await _setup(
        hass, power=True, operation_mode="Heat", set_fan_speed="One"
    )

    async def _poll_completes_mid_write(*_args: Any, **_kwargs: Any) -> None:
        mock_client.get_user_context.return_value = create_mock_ata_user_context(
            buildings=[
                create_mock_ata_building(
                    units=[
                        create_mock_ata_unit(
                            power=True, operation_mode="Heat", set_fan_speed="One"
                        )
                    ]
                )
            ]
        )
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=61))
        await _let_tasks_run()

    mock_client.ata.set_fan_speed.side_effect = _poll_completes_mid_write

    await _set_percentage(hass, 80)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
    await _let_tasks_run()

    assert hass.states.get(_FAN_ENTITY).attributes["percentage"] == 80


@pytest.mark.asyncio
async def test_entity_reports_a_commanded_speed_before_its_write_lands(
    hass: HomeAssistant,
) -> None:
    """The power-on publishes this entity's state before the speed write exists.

    From off, set_percentage powers the unit on at once and defers the speed by
    _SPEED_DEBOUNCE_WINDOW. That power-on writes through and notifies listeners
    while the coordinator's copy still holds the old speed, so the entity would
    publish that old speed first. A HomeKit controller keeps the first value it
    is told for a characteristic and ignored the correction 0.7 s behind it,
    leaving the tile and the home screen reading the previous speed until the
    app was force-closed. Seen on hardware.
    """
    await _setup(hass, power=False, operation_mode="Cool", set_fan_speed="Three")

    await _set_percentage(hass, 100)

    assert hass.states.get(_FAN_ENTITY).attributes["percentage"] == 100


@pytest.mark.asyncio
@pytest.mark.parametrize("power_off", [_power_off_via_service, _power_off_via_slider])
async def test_a_power_off_drops_a_pending_speed(
    hass: HomeAssistant, power_off: Any
) -> None:
    """Cancelling a drag voids its value, not only its timer.

    Nothing reschedules a cancelled write, so a value left behind would be what
    the entity reports from then until a restart.
    """
    await _setup(hass, power=False, operation_mode="Cool", set_fan_speed="Three")

    await _set_percentage(hass, 100)
    await power_off(hass)

    assert hass.states.get(_FAN_ENTITY).attributes["percentage"] == 60
