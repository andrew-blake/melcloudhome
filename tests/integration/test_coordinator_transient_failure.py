"""One failed poll must not take every entity unavailable (issue #309).

A single /context request that times out or fails on the network used to mark
the whole integration failed, so all entities read "unavailable" until the next
poll succeeded 60 s later. The coordinator now carries the previous data across
one failed poll and only gives up on the second consecutive failure.

Tested through hass.states only.

Reference: docs/testing-best-practices.md
Run with: make test-integration
"""

import logging
from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from homeassistant.components.climate import HVACMode
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.melcloudhome.api.exceptions import ApiError
from custom_components.melcloudhome.const import CONF_ENABLE_WEBSOCKET

from .conftest import create_mock_ata_user_context, setup_ata_integration_custom

_CLIMATE_ENTITY = "climate.melcloudhome_a1b2_9abc_climate"
_ROOM_TEMP_ENTITY = "sensor.melcloudhome_a1b2_9abc_room_temperature"


async def _setup(hass: HomeAssistant):
    mock_context = create_mock_ata_user_context()
    _entry, mock_client = await setup_ata_integration_custom(
        hass, mock_context, options={CONF_ENABLE_WEBSOCKET: False}
    )
    assert hass.states.get(_CLIMATE_ENTITY).state == HVACMode.HEAT
    return mock_context, mock_client


async def _next_poll(hass: HomeAssistant) -> None:
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=61))
    await hass.async_block_till_done(wait_background_tasks=True)


@pytest.mark.asyncio
async def test_single_timed_out_poll_keeps_entities_available(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """One timeout keeps the last known values and says so in the log."""
    _context, mock_client = await _setup(hass)
    mock_client.get_user_context = AsyncMock(side_effect=TimeoutError())

    with caplog.at_level(logging.WARNING):
        await _next_poll(hass)

    assert hass.states.get(_CLIMATE_ENTITY).state == HVACMode.HEAT
    assert hass.states.get(_ROOM_TEMP_ENTITY).state == "20.0"
    warnings = [
        r.message
        for r in caplog.records
        if r.levelno == logging.WARNING and "keeping" in r.message.lower()
    ]
    assert warnings, "a tolerated failure must be visible in the log"
    # A bare TimeoutError has an empty str(); the line must still say what failed.
    assert "TimeoutError" in warnings[0]


@pytest.mark.asyncio
async def test_single_network_error_keeps_entities_available(
    hass: HomeAssistant,
) -> None:
    """A network error is tolerated the same way as a timeout."""
    _context, mock_client = await _setup(hass)
    mock_client.get_user_context = AsyncMock(
        side_effect=ApiError("Network error: connection reset")
    )

    await _next_poll(hass)

    assert hass.states.get(_CLIMATE_ENTITY).state == HVACMode.HEAT


@pytest.mark.asyncio
async def test_second_consecutive_failure_marks_unavailable_then_recovers(
    hass: HomeAssistant,
) -> None:
    """Two failures in a row is a real outage; the next success restores state."""
    mock_context, mock_client = await _setup(hass)
    mock_client.get_user_context = AsyncMock(side_effect=TimeoutError())

    await _next_poll(hass)
    assert hass.states.get(_CLIMATE_ENTITY).state == HVACMode.HEAT

    await _next_poll(hass)
    assert hass.states.get(_CLIMATE_ENTITY).state == STATE_UNAVAILABLE

    mock_client.get_user_context = AsyncMock(return_value=mock_context)
    await _next_poll(hass)
    assert hass.states.get(_CLIMATE_ENTITY).state == HVACMode.HEAT


@pytest.mark.asyncio
async def test_failure_tolerance_resets_after_a_good_poll(
    hass: HomeAssistant,
) -> None:
    """Fail, succeed, fail: the second failure is a fresh single failure."""
    mock_context, mock_client = await _setup(hass)

    mock_client.get_user_context = AsyncMock(side_effect=TimeoutError())
    await _next_poll(hass)
    mock_client.get_user_context = AsyncMock(return_value=mock_context)
    await _next_poll(hass)
    mock_client.get_user_context = AsyncMock(side_effect=TimeoutError())
    await _next_poll(hass)

    assert hass.states.get(_CLIMATE_ENTITY).state == HVACMode.HEAT
