"""Tests for the account-level real-time updates connectivity binary sensor.

One diagnostic binary sensor per config entry reports whether the WebSocket
accelerator is connected, with a ``last_delta_at`` attribute. Tests observe
behavior through hass.states only; the client is mocked at the API boundary.

Run with: make test-integration
"""

import asyncio
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
    OpenFakeWS,
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

        # Opt back in and reload — the sensor must come back.
        hass.config_entries.async_update_entry(
            entry, options={CONF_ENABLE_WEBSOCKET: True}
        )
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

        assert hass.states.get(WS_ENTITY_ID) is not None
        assert registry.async_get(WS_ENTITY_ID) is not None


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


@pytest.mark.asyncio
async def test_ws_delta_triggers_debounced_refresh(hass: HomeAssistant) -> None:
    """The headline seam: a pushed delta causes a real coordinator refresh.

    Regression guard for the flagship v2.4.0 behavior — without it, a break in
    the delta -> debounced-refresh wiring would silently degrade real-time
    updates back to 60s polling with every other test still green.
    """
    _entry, mock_client = await setup_atw_integration_custom(
        hass,
        create_mock_atw_user_context(),
        configure_client=lambda client: wire_connected_ws(
            client, [ws_text_frame("unit-1")]
        ),
    )
    # Let the delta's debounced refresh (2s) run to completion.
    await hass.async_block_till_done()

    # Setup itself polls /context exactly once; the delta's debounced refresh
    # is the second call.
    assert mock_client.get_user_context.await_count == 2


@pytest.mark.asyncio
async def test_ws_sensor_flips_off_when_socket_drops(hass: HomeAssistant) -> None:
    """A dropped socket flips the sensor OFF via the listener notification."""

    class ClosingFakeWS(OpenFakeWS):
        """Yields its frames, then closes instead of staying open."""

        async def __anext__(self):
            if self._frames:
                return self._frames.pop(0)
            raise StopAsyncIteration

    def wire(client: MagicMock) -> None:
        wire_connected_ws(client, [])
        session = MagicMock()
        # First session delivers one delta then closes; the reconnect attempt
        # fails so the listener stays down for the rest of the test.
        session.ws_connect = MagicMock(
            side_effect=[
                ClosingFakeWS([ws_text_frame("unit-1")]),
                RuntimeError("down"),
                RuntimeError("down"),
            ]
        )
        client.async_ws_session = AsyncMock(return_value=session)

    await setup_atw_integration_custom(
        hass, create_mock_atw_user_context(), configure_client=wire
    )

    # The connect -> delta -> drop cycle involves no timers, but runs in a
    # background task; poll until the drop has propagated to the entity.
    state = None
    for _ in range(100):
        await hass.async_block_till_done()
        state = hass.states.get(WS_ENTITY_ID)
        if state and state.attributes["last_delta_at"] and state.state == STATE_OFF:
            break
        await asyncio.sleep(0.01)

    assert state is not None
    # last_delta_at proves it connected and delivered before dropping — the
    # sensor being OFF is the drop, not a never-connected listener.
    assert state.attributes["last_delta_at"] is not None
    assert state.state == STATE_OFF


@pytest.mark.asyncio
async def test_unload_cancels_pending_debounced_refresh(hass: HomeAssistant) -> None:
    """A delta received just before unload must not refresh after unload.

    Regression: the pending 2s debounce task survived unload, fired against a
    closed client session, and resurrected a fresh ClientSession that nothing
    ever closed.
    """
    fake = OpenFakeWS([ws_text_frame("unit-1")])

    def wire(client: MagicMock) -> None:
        wire_connected_ws(client, [])
        session = MagicMock()
        session.ws_connect = MagicMock(return_value=fake)
        client.async_ws_session = AsyncMock(return_value=session)

    entry, mock_client = await setup_atw_integration_custom(
        hass, create_mock_atw_user_context(), configure_client=wire
    )

    # Wait until the listener consumed the frame (the debounce is now pending)
    # without block_till_done, which would wait out the debounce itself.
    for _ in range(100):
        if not fake._frames:
            break
        await asyncio.sleep(0.01)
    for _ in range(5):
        await asyncio.sleep(0)  # let the delta handler queue the debounce task

    # Unload before the 2s debounce fires, then wait past its deadline.
    assert await hass.config_entries.async_unload(entry.entry_id)
    baseline = mock_client.get_user_context.await_count
    await asyncio.sleep(2.5)
    await hass.async_block_till_done()

    assert mock_client.get_user_context.await_count == baseline
