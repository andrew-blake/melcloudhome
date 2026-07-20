"""Tests for the account-level real-time updates connectivity binary sensor.

One diagnostic binary sensor per config entry reports whether the WebSocket
accelerator is connected, with a ``last_delta_at`` attribute. Tests observe
behavior through hass.states only; the client is mocked at the API boundary.

Run with: make test-integration
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.melcloudhome.const import CONF_ENABLE_WEBSOCKET

from .conftest import (
    create_mock_atw_user_context,
    setup_atw_integration_custom,
)

WS_ENTITY_ID = "binary_sensor.melcloud_home_real_time_updates"


class _OpenWS:
    """Fake aiohttp WebSocket: yields queued frames, then stays open."""

    def __init__(self, frames: list[object]) -> None:
        self._frames = list(frames)

    async def __aenter__(self) -> "_OpenWS":
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        return False

    def __aiter__(self) -> "_OpenWS":
        return self

    async def __anext__(self) -> object:
        if self._frames:
            return self._frames.pop(0)
        await asyncio.Event().wait()  # block until the task is cancelled
        raise StopAsyncIteration


def _text_frame(unit_id: str) -> MagicMock:
    msg = MagicMock()
    msg.type = aiohttp.WSMsgType.TEXT
    msg.data = json.dumps(
        [
            {
                "messageType": "unitStateChanged",
                "Data": {"id": unit_id, "settings": [{"name": "Power"}]},
            }
        ]
    )
    return msg


def _wire_connected_ws(client: MagicMock, frames: list[object]) -> None:
    """Make the mocked client's WS path connect successfully."""
    session = MagicMock()
    session.ws_connect = MagicMock(return_value=_OpenWS(frames))
    client.async_get_ws_hash = AsyncMock(return_value="HASH123")
    client.async_ws_session = AsyncMock(return_value=session)
    type(client).ws_host = "wss://example.invalid"


@pytest.mark.asyncio
async def test_ws_sensor_off_when_listener_cannot_connect(
    hass: HomeAssistant,
) -> None:
    """Default-on entry creates the sensor; unconnected listener reads off."""

    def fail_hash(client: MagicMock) -> None:
        client.async_get_ws_hash = AsyncMock(side_effect=RuntimeError("down"))

    await setup_atw_integration_custom(
        hass, create_mock_atw_user_context(), configure_client=fail_hash
    )

    state = hass.states.get(WS_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes["device_class"] == "connectivity"
    assert state.attributes["last_delta_at"] is None

    registry = er.async_get(hass)
    entity = registry.async_get(WS_ENTITY_ID)
    assert entity is not None
    assert entity.entity_category == er.EntityCategory.DIAGNOSTIC


@pytest.mark.asyncio
async def test_ws_sensor_absent_when_opted_out(hass: HomeAssistant) -> None:
    """Opting out of real-time updates creates no connectivity sensor."""
    await setup_atw_integration_custom(
        hass,
        create_mock_atw_user_context(),
        options={CONF_ENABLE_WEBSOCKET: False},
    )

    assert hass.states.get(WS_ENTITY_ID) is None


@pytest.mark.asyncio
async def test_ws_sensor_on_when_connected_and_tracks_deltas(
    hass: HomeAssistant,
) -> None:
    """A live socket reads on; a received delta stamps last_delta_at."""
    await setup_atw_integration_custom(
        hass,
        create_mock_atw_user_context(),
        configure_client=lambda client: _wire_connected_ws(
            client, [_text_frame("unit-1")]
        ),
    )
    # Let the listener task connect, consume the frame, and let the
    # debounced refresh from the delta run to completion.
    await hass.async_block_till_done()

    state = hass.states.get(WS_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes["last_delta_at"] is not None
