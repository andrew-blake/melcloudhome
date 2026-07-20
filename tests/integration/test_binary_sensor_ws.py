"""Tests for the account-level real-time updates connectivity binary sensor.

One diagnostic binary sensor per config entry reports whether the WebSocket
accelerator is connected, with a ``last_delta_at`` attribute. Tests observe
behavior through hass.states only; the client is mocked at the API boundary.

Run with: make test-integration
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.melcloudhome.const import CONF_ENABLE_WEBSOCKET

from .conftest import (
    create_mock_atw_user_context,
    setup_atw_integration_custom,
    wire_connected_ws,
    ws_text_frame,
)

WS_ENTITY_ID = "binary_sensor.melcloud_home_real_time_updates"


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
        configure_client=lambda client: wire_connected_ws(
            client, [ws_text_frame("unit-1")]
        ),
    )
    # Let the listener task connect, consume the frame, and let the
    # debounced refresh from the delta run to completion.
    await hass.async_block_till_done()

    state = hass.states.get(WS_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes["last_delta_at"] is not None
