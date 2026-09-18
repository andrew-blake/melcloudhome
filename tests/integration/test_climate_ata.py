"""Tests for MELCloud Home ATA climate entity.

Tests cover climate entity behavior through Home Assistant core interfaces only.
Follows HA best practices: test observable behavior, not implementation details.

Reference: docs/testing-best-practices.md
Run with: make test-integration
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.climate import HVACAction, HVACMode
from homeassistant.core import HomeAssistant

from .conftest import (
    create_mock_ata_building,
    create_mock_ata_unit,
    create_mock_ata_user_context,
    setup_ata_integration_custom,
)

_CLIMATE_ENTITY = "climate.melcloudhome_a1b2_9abc_climate"


def _configure_ata_controls(client: Any) -> None:
    client.ata = MagicMock()
    client.ata.set_power = AsyncMock()
    client.ata.set_power_and_mode = AsyncMock()
    client.ata.set_temperature = AsyncMock()
    client.ata.set_fan_speed = AsyncMock()
    client.ata.set_vane_vertical = AsyncMock()
    client.ata.set_vane_horizontal = AsyncMock()


@pytest.mark.asyncio
async def test_climate_entity_state_reflects_device_data(hass: HomeAssistant) -> None:
    """Test that climate entity state correctly reflects device data."""
    mock_context = create_mock_ata_user_context()
    await setup_ata_integration_custom(
        hass, mock_context, configure_client=_configure_ata_controls
    )

    state = hass.states.get(_CLIMATE_ENTITY)
    assert state is not None
    assert state.state == HVACMode.HEAT
    assert state.attributes["current_temperature"] == 20.0
    assert state.attributes["temperature"] == 21.0
    assert state.attributes["fan_mode"] == "auto"
    assert state.attributes["swing_mode"] == "auto"


@pytest.mark.asyncio
async def test_set_hvac_mode_to_cool(hass: HomeAssistant) -> None:
    """Test changing HVAC mode to COOL via service call."""
    mock_context = create_mock_ata_user_context()
    await setup_ata_integration_custom(
        hass, mock_context, configure_client=_configure_ata_controls
    )

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": _CLIMATE_ENTITY, "hvac_mode": HVACMode.COOL},
        blocking=True,
    )


@pytest.mark.asyncio
async def test_set_hvac_mode_writes_even_when_already_matching(
    hass: HomeAssistant,
) -> None:
    """A redundant-looking power+mode command still reaches the API (#318).

    This asserted the opposite until the write-dedup was removed from the two
    power methods. Coordinator data is stale for the whole window between a
    write and the next completed refresh, so "already matches" could not be
    told apart from "was just commanded", and a real power-off issued inside
    that window was dropped while the unit kept running. ADR-018 pre-authorised
    the removal; the cost is one extra call per redundant scene application.
    """
    mock_unit = create_mock_ata_unit(power=True, operation_mode="Heat")
    mock_context = create_mock_ata_user_context(
        [create_mock_ata_building(units=[mock_unit])]
    )
    _, mock_client = await setup_ata_integration_custom(
        hass, mock_context, configure_client=_configure_ata_controls
    )

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": _CLIMATE_ENTITY, "hvac_mode": HVACMode.HEAT},
        blocking=True,
    )

    mock_client.ata.set_power_and_mode.assert_called_once()
    assert mock_client.ata.set_power_and_mode.call_args[0][1:] == (True, "Heat", None)
    mock_client.ata.set_power.assert_not_called()


@pytest.mark.asyncio
async def test_turn_on_uses_atomic_power_and_mode(hass: HomeAssistant) -> None:
    """Test that turn_on sends power+mode atomically, not power alone."""
    mock_unit = create_mock_ata_unit(power=False, operation_mode="Heat")
    mock_context = create_mock_ata_user_context(
        [create_mock_ata_building(units=[mock_unit])]
    )
    _, mock_client = await setup_ata_integration_custom(
        hass, mock_context, configure_client=_configure_ata_controls
    )

    await hass.services.async_call(
        "climate",
        "turn_on",
        {"entity_id": _CLIMATE_ENTITY},
        blocking=True,
    )

    mock_client.ata.set_power_and_mode.assert_called_once()
    mock_client.ata.set_power.assert_not_called()


@pytest.mark.asyncio
async def test_set_hvac_mode_off_turns_device_off(hass: HomeAssistant) -> None:
    """Test that setting HVAC mode to OFF powers down device."""
    mock_context = create_mock_ata_user_context()
    await setup_ata_integration_custom(
        hass, mock_context, configure_client=_configure_ata_controls
    )

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": _CLIMATE_ENTITY, "hvac_mode": HVACMode.OFF},
        blocking=True,
    )


@pytest.mark.asyncio
async def test_set_temperature_within_valid_range(hass: HomeAssistant) -> None:
    """Test setting temperature within valid range."""
    mock_context = create_mock_ata_user_context()
    await setup_ata_integration_custom(
        hass, mock_context, configure_client=_configure_ata_controls
    )

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": _CLIMATE_ENTITY, "temperature": 22.5},
        blocking=True,
    )


@pytest.mark.asyncio
async def test_set_temperature_out_of_range_rejected(hass: HomeAssistant) -> None:
    """Test that temperature out of range is rejected gracefully."""
    from contextlib import suppress

    from homeassistant.exceptions import ServiceValidationError

    mock_context = create_mock_ata_user_context()
    await setup_ata_integration_custom(
        hass, mock_context, configure_client=_configure_ata_controls
    )

    with suppress(ServiceValidationError):
        await hass.services.async_call(
            "climate",
            "set_temperature",
            {"entity_id": _CLIMATE_ENTITY, "temperature": 5.0},
            blocking=True,
        )

    with suppress(ServiceValidationError):
        await hass.services.async_call(
            "climate",
            "set_temperature",
            {"entity_id": _CLIMATE_ENTITY, "temperature": 35.0},
            blocking=True,
        )


@pytest.mark.asyncio
async def test_set_fan_mode(hass: HomeAssistant) -> None:
    """Test setting fan mode via service call."""
    mock_context = create_mock_ata_user_context()
    await setup_ata_integration_custom(
        hass, mock_context, configure_client=_configure_ata_controls
    )

    await hass.services.async_call(
        "climate",
        "set_fan_mode",
        {"entity_id": _CLIMATE_ENTITY, "fan_mode": "three"},
        blocking=True,
    )


@pytest.mark.asyncio
async def test_set_swing_mode_vertical_vanes(hass: HomeAssistant) -> None:
    """Test setting vertical vane position via swing mode."""
    mock_context = create_mock_ata_user_context()
    await setup_ata_integration_custom(
        hass, mock_context, configure_client=_configure_ata_controls
    )

    await hass.services.async_call(
        "climate",
        "set_swing_mode",
        {"entity_id": _CLIMATE_ENTITY, "swing_mode": "swing"},
        blocking=True,
    )


@pytest.mark.asyncio
async def test_set_swing_horizontal_mode(hass: HomeAssistant) -> None:
    """Test setting horizontal vane position."""
    mock_context = create_mock_ata_user_context()
    await setup_ata_integration_custom(
        hass, mock_context, configure_client=_configure_ata_controls
    )

    await hass.services.async_call(
        "climate",
        "set_swing_horizontal_mode",
        {"entity_id": _CLIMATE_ENTITY, "swing_horizontal_mode": "centre"},
        blocking=True,
    )


@pytest.mark.asyncio
async def test_hvac_action_heating_when_temp_below_target(hass: HomeAssistant) -> None:
    """Test HVAC action inference: HEATING when temp below target."""
    mock_unit = create_mock_ata_unit(
        operation_mode="Heat", set_temperature=21.0, room_temperature=19.0
    )
    mock_context = create_mock_ata_user_context(
        [create_mock_ata_building(units=[mock_unit])]
    )
    await setup_ata_integration_custom(hass, mock_context)

    state = hass.states.get(_CLIMATE_ENTITY)
    assert state is not None
    assert state.attributes["hvac_action"] == HVACAction.HEATING


@pytest.mark.asyncio
async def test_hvac_action_idle_when_temp_at_target(hass: HomeAssistant) -> None:
    """Test HVAC action inference: IDLE when temp at target."""
    mock_unit = create_mock_ata_unit(
        operation_mode="Heat", set_temperature=21.0, room_temperature=21.0
    )
    mock_context = create_mock_ata_user_context(
        [create_mock_ata_building(units=[mock_unit])]
    )
    await setup_ata_integration_custom(hass, mock_context)

    state = hass.states.get(_CLIMATE_ENTITY)
    assert state is not None
    assert state.attributes["hvac_action"] == HVACAction.IDLE


@pytest.mark.asyncio
async def test_hvac_action_cooling_when_temp_above_target(hass: HomeAssistant) -> None:
    """Test HVAC action inference: COOLING when temp above target."""
    mock_unit = create_mock_ata_unit(
        operation_mode="Cool", set_temperature=20.0, room_temperature=22.0
    )
    mock_context = create_mock_ata_user_context(
        [create_mock_ata_building(units=[mock_unit])]
    )
    await setup_ata_integration_custom(hass, mock_context)

    state = hass.states.get(_CLIMATE_ENTITY)
    assert state is not None
    assert state.attributes["hvac_action"] == HVACAction.COOLING


@pytest.mark.asyncio
async def test_device_unavailable_when_in_error_state(hass: HomeAssistant) -> None:
    """Test that device shows as unavailable when in error state."""
    mock_unit = create_mock_ata_unit(is_in_error=True)
    mock_context = create_mock_ata_user_context(
        [create_mock_ata_building(units=[mock_unit])]
    )
    await setup_ata_integration_custom(hass, mock_context)

    state = hass.states.get(_CLIMATE_ENTITY)
    assert state is not None
    assert state.state == "unavailable"


@pytest.mark.asyncio
async def test_device_power_off_shows_hvac_mode_off(hass: HomeAssistant) -> None:
    """Test that device power OFF maps to HVACMode.OFF."""
    mock_unit = create_mock_ata_unit(power=False, operation_mode="Heat")
    mock_context = create_mock_ata_user_context(
        [create_mock_ata_building(units=[mock_unit])]
    )
    await setup_ata_integration_custom(hass, mock_context)

    state = hass.states.get(_CLIMATE_ENTITY)
    assert state is not None
    assert state.state == HVACMode.OFF
    assert state.attributes["hvac_action"] == HVACAction.OFF


@pytest.mark.asyncio
async def test_turn_on_and_turn_off_services(hass: HomeAssistant) -> None:
    """Test turn_on and turn_off service calls."""
    mock_context = create_mock_ata_user_context()
    await setup_ata_integration_custom(
        hass, mock_context, configure_client=_configure_ata_controls
    )

    await hass.services.async_call(
        "climate", "turn_off", {"entity_id": _CLIMATE_ENTITY}, blocking=True
    )
    await hass.services.async_call(
        "climate", "turn_on", {"entity_id": _CLIMATE_ENTITY}, blocking=True
    )


@pytest.mark.asyncio
async def test_device_removal_entity_becomes_unavailable(hass: HomeAssistant) -> None:
    """Test that entity becomes unavailable when device is removed."""
    mock_context = create_mock_ata_user_context([create_mock_ata_building(units=[])])
    await setup_ata_integration_custom(hass, mock_context)

    state = hass.states.get(_CLIMATE_ENTITY)
    assert state is None  # Entity not created when no units


@pytest.mark.asyncio
async def test_climate_vocabularies_are_unchanged(hass: HomeAssistant) -> None:
    """Pin both vocabularies against a future tidy-up.

    ADR-025 rejected adding HomeKit's standard names to swing_modes: doing so
    requires swing_mode to report "vertical" instead of "swing", which breaks
    templates silently, and it builds a linked fan service on the Thermostat
    whose power button is rejected and visibly does nothing. The fan entity
    carries these controls instead. Read that ADR before changing this test.
    """
    mock_context = create_mock_ata_user_context()
    await setup_ata_integration_custom(
        hass, mock_context, configure_client=_configure_ata_controls
    )

    state = hass.states.get(_CLIMATE_ENTITY)
    assert state.attributes["fan_modes"] == [
        "auto",
        "one",
        "two",
        "three",
        "four",
        "five",
    ]
    assert state.attributes["swing_modes"] == [
        "auto",
        "swing",
        "one",
        "two",
        "three",
        "four",
        "five",
    ]


@pytest.mark.parametrize(
    ("service", "field", "value", "api_method"),
    [
        ("set_temperature", "temperature", 21.0, "set_temperature"),
        ("set_swing_mode", "swing_mode", "auto", "set_vane_vertical"),
        (
            "set_swing_horizontal_mode",
            "swing_horizontal_mode",
            "auto",
            "set_vane_horizontal",
        ),
        ("set_fan_mode", "fan_mode", "auto", "set_fan_speed"),
    ],
)
@pytest.mark.asyncio
async def test_a_command_matching_current_state_is_still_sent(
    hass: HomeAssistant,
    service: str,
    field: str,
    value: Any,
    api_method: str,
) -> None:
    """Every ATA field reaches the API when the unit already reads that value.

    `value` is the fixture's own starting value, sent twice. A check comparing
    the request against the coordinator's copy would skip both calls, so two
    calls is the witness for its absence, one case per field so a check
    reintroduced on one setter fails alone.
    """
    mock_context = create_mock_ata_user_context()
    _, mock_client = await setup_ata_integration_custom(
        hass, mock_context, configure_client=_configure_ata_controls
    )

    for _ in range(2):
        await hass.services.async_call(
            "climate",
            service,
            {"entity_id": _CLIMATE_ENTITY, field: value},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert getattr(mock_client.ata, api_method).call_count == 2
