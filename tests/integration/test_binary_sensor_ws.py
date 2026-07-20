"""Tests for the account-level real-time updates connectivity binary sensor.

One diagnostic binary sensor per config entry reports whether the WebSocket
accelerator is connected, with a ``last_delta_at`` attribute. Tests observe
behavior through hass.states only; the client is mocked at the API boundary.

Run with: make test-integration
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.melcloudhome.const import CONF_ENABLE_WEBSOCKET, DOMAIN

from .conftest import (
    MOCK_CLIENT_PATH,
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
async def test_ws_sensor_removed_on_opt_out_no_orphan(hass: HomeAssistant) -> None:
    """Opting out after it was created removes the entity (no restored orphan).

    Regression: a conditionally-created entity left in the registry surfaces as
    a `restored`/`unavailable` orphan on reload. Opt-out must clean it up.
    """
    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        client = mock_client_class.return_value
        client.login = AsyncMock()
        client.close = AsyncMock()
        client.get_user_context = AsyncMock(return_value=create_mock_atw_user_context())
        client.async_get_ws_hash = AsyncMock(side_effect=RuntimeError("down"))
        type(client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)

        # Enabled (default): entity created and registered.
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert hass.states.get(WS_ENTITY_ID) is not None
        registry = er.async_get(hass)
        assert registry.async_get(WS_ENTITY_ID) is not None

        # Opt out and reload — entity must be gone from states AND registry.
        hass.config_entries.async_update_entry(
            entry, options={CONF_ENABLE_WEBSOCKET: False}
        )
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

        assert hass.states.get(WS_ENTITY_ID) is None
        assert registry.async_get(WS_ENTITY_ID) is None


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
    # Exposed as an ISO 8601 string (consistent with the diagnostics section),
    # not a raw datetime object.
    last_delta_at = state.attributes["last_delta_at"]
    assert isinstance(last_delta_at, str)
    assert datetime.fromisoformat(last_delta_at)
