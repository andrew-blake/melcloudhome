"""Unit tests for the real-time WebSocket listener and its hash credential.

Covers ``MELCloudHomeWebSocket`` (frame parsing, connect/receive dispatch, the
reconnect/backoff loop) and ``MELCloudHomeClient.async_get_ws_hash`` /
``async_ws_session``. Everything is mocked at the client / aiohttp boundary — no
network and no Home Assistant.
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from custom_components.melcloudhome.api.client import MELCloudHomeClient
from custom_components.melcloudhome.api.exceptions import (
    ApiError,
    AuthenticationError,
)
from custom_components.melcloudhome.api.websocket import (
    _INITIAL_BACKOFF,
    _STABLE_SESSION_SECS,
    MELCloudHomeWebSocket,
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
class _AsyncCM:
    """Minimal async context manager wrapping a fixed object."""

    def __init__(self, obj: object) -> None:
        self._obj = obj

    async def __aenter__(self) -> object:
        return self._obj

    async def __aexit__(self, *_exc: object) -> bool:
        return False


class _FakeWS:
    """Async-iterable stand-in for an aiohttp WebSocket response."""

    def __init__(self, messages: list[object]) -> None:
        self._messages = list(messages)

    async def __aenter__(self) -> _FakeWS:
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        return False

    def __aiter__(self) -> _FakeWS:
        return self

    async def __anext__(self) -> object:
        if not self._messages:
            raise StopAsyncIteration
        return self._messages.pop(0)


def _msg(msg_type: aiohttp.WSMsgType, data: str | None = None) -> MagicMock:
    m = MagicMock()
    m.type = msg_type
    m.data = data
    return m


def _delta_frame(
    unit_id: str, settings: list[object], *, data_key: str = "Data"
) -> str:
    return json.dumps(
        [
            {
                "messageType": "unitStateChanged",
                data_key: {
                    "id": unit_id,
                    "unitType": "ata",
                    "settings": settings,
                },
            }
        ]
    )


def _make_ws(
    on_delta: AsyncMock | None = None,
) -> tuple[MELCloudHomeWebSocket, AsyncMock]:
    on_delta = on_delta or AsyncMock()
    ws = MELCloudHomeWebSocket(MagicMock(), on_delta)
    return ws, on_delta


# --------------------------------------------------------------------------- #
# Frame parsing (_handle_text)
# --------------------------------------------------------------------------- #
class TestHandleText:
    async def test_valid_delta_dispatches_changed_setting_names(self) -> None:
        ws, on_delta = _make_ws()
        raw = _delta_frame(
            "unit-1",
            [{"name": "Power", "value": True}, {"name": "SetTemperature", "value": 21}],
        )
        await ws._handle_text(raw)
        on_delta.assert_awaited_once_with("unit-1", ["Power", "SetTemperature"])

    async def test_single_object_payload_is_accepted(self) -> None:
        """The server sometimes sends a bare object rather than a list."""
        ws, on_delta = _make_ws()
        raw = json.dumps(
            {
                "messageType": "unitStateChanged",
                "Data": {"id": "unit-2", "settings": [{"name": "Power"}]},
            }
        )
        await ws._handle_text(raw)
        on_delta.assert_awaited_once_with("unit-2", ["Power"])

    async def test_lowercase_data_key_is_accepted(self) -> None:
        ws, on_delta = _make_ws()
        raw = _delta_frame("unit-3", [], data_key="data")
        await ws._handle_text(raw)
        on_delta.assert_awaited_once_with("unit-3", [])

    async def test_malformed_json_is_ignored(self) -> None:
        ws, on_delta = _make_ws()
        await ws._handle_text("{not json")
        on_delta.assert_not_awaited()

    async def test_non_dict_items_are_skipped(self) -> None:
        ws, on_delta = _make_ws()
        await ws._handle_text(json.dumps(["a string", 42, None]))
        on_delta.assert_not_awaited()

    async def test_other_message_types_are_ignored(self) -> None:
        ws, on_delta = _make_ws()
        raw = json.dumps([{"messageType": "somethingElse", "Data": {"id": "x"}}])
        await ws._handle_text(raw)
        on_delta.assert_not_awaited()

    async def test_missing_unit_id_is_skipped(self) -> None:
        ws, on_delta = _make_ws()
        raw = json.dumps(
            [{"messageType": "unitStateChanged", "Data": {"settings": [{"name": "P"}]}}]
        )
        await ws._handle_text(raw)
        on_delta.assert_not_awaited()

    async def test_setting_entries_without_name_are_filtered(self) -> None:
        ws, on_delta = _make_ws()
        raw = _delta_frame(
            "unit-4",
            [
                {"name": "Power", "value": False},
                {"value": 1},  # no name -> dropped
                "not-a-dict",  # non-dict -> dropped
                {"name": "", "value": 2},  # empty name -> dropped
            ],
        )
        await ws._handle_text(raw)
        on_delta.assert_awaited_once_with("unit-4", ["Power"])

    async def test_handler_exception_does_not_propagate(self) -> None:
        on_delta = AsyncMock(side_effect=RuntimeError("handler boom"))
        ws, _ = _make_ws(on_delta)
        # Must not raise — a misbehaving handler cannot kill the listen loop.
        await ws._handle_text(_delta_frame("unit-5", [{"name": "Power"}]))
        on_delta.assert_awaited_once()


# --------------------------------------------------------------------------- #
# Connect + receive (_connect_once)
# --------------------------------------------------------------------------- #
class TestConnectOnce:
    def _client_with_ws(self, messages: list[object]) -> tuple[MagicMock, MagicMock]:
        session = MagicMock()
        session.ws_connect = MagicMock(return_value=_FakeWS(messages))
        client = MagicMock()
        client.async_get_ws_hash = AsyncMock(return_value="HASH123")
        client.async_ws_session = AsyncMock(return_value=session)
        return client, session

    async def test_text_frame_is_dispatched_then_close_ends_session(self) -> None:
        on_delta = AsyncMock()
        raw = _delta_frame("unit-1", [{"name": "Power"}])
        client, session = self._client_with_ws(
            [_msg(aiohttp.WSMsgType.TEXT, raw), _msg(aiohttp.WSMsgType.CLOSE)]
        )
        ws = MELCloudHomeWebSocket(client, on_delta)

        await ws._connect_once()

        on_delta.assert_awaited_once_with("unit-1", ["Power"])
        # Connected to WS_HOST with the fetched hash in the query string.
        url = session.ws_connect.call_args.args[0]
        assert "hash=HASH123" in url

    async def test_non_text_non_close_frames_are_ignored(self) -> None:
        on_delta = AsyncMock()
        raw = _delta_frame("unit-9", [{"name": "Power"}])
        client, _ = self._client_with_ws(
            [
                _msg(aiohttp.WSMsgType.BINARY, "ignored"),
                _msg(aiohttp.WSMsgType.TEXT, raw),
                _msg(aiohttp.WSMsgType.ERROR),
            ]
        )
        ws = MELCloudHomeWebSocket(client, on_delta)

        await ws._connect_once()

        # BINARY ignored, TEXT dispatched, ERROR ends the session.
        on_delta.assert_awaited_once_with("unit-9", ["Power"])

    async def test_logs_connected_then_restored_at_info(self, caplog) -> None:
        client, _ = self._client_with_ws([_msg(aiohttp.WSMsgType.CLOSE)])
        ws = MELCloudHomeWebSocket(client, AsyncMock())

        with caplog.at_level("INFO"):
            await ws._connect_once()  # first session
            await ws._connect_once()  # session after a drop

        infos = [
            r.getMessage()
            for r in caplog.records
            if r.levelname == "INFO" and "WebSocket" in r.getMessage()
        ]
        assert infos == ["WebSocket connected", "WebSocket connection restored"]


# --------------------------------------------------------------------------- #
# Reconnect loop (run / stop)
# --------------------------------------------------------------------------- #
class TestRunLoop:
    async def test_returns_immediately_if_already_closing(self) -> None:
        ws, _ = _make_ws()
        ws._connect_once = AsyncMock()  # type: ignore[method-assign]
        ws.stop()
        await ws.run()
        ws._connect_once.assert_not_called()

    async def test_clean_session_then_stop_exits_without_backoff(self, mocker) -> None:
        sleep = mocker.patch("asyncio.sleep", new_callable=AsyncMock)
        ws, _ = _make_ws()
        calls: list[int] = []

        async def fake_connect() -> None:
            calls.append(1)
            ws.stop()

        ws._connect_once = fake_connect  # type: ignore[method-assign]
        await ws.run()

        assert len(calls) == 1
        sleep.assert_not_awaited()

    async def test_error_backs_off_and_retries_until_stopped(self, mocker) -> None:
        sleep = mocker.patch("asyncio.sleep", new_callable=AsyncMock)
        mocker.patch("random.uniform", return_value=1.0)
        ws, _ = _make_ws()
        attempts: list[int] = []

        async def fake_connect() -> None:
            attempts.append(1)
            if len(attempts) < 3:
                raise RuntimeError("boom")
            ws.stop()  # clean third session ends the loop

        ws._connect_once = fake_connect  # type: ignore[method-assign]
        await ws.run()

        assert len(attempts) == 3
        # Backoff doubles between failed attempts: 5s then 10s.
        waited = [c.args[0] for c in sleep.await_args_list]
        assert waited == [_INITIAL_BACKOFF, _INITIAL_BACKOFF * 2]

    async def test_short_clean_session_keeps_escalating(self, mocker) -> None:
        """Accept-then-immediately-close must not reset the backoff.

        A server that completes the 101 handshake and closes right away
        (expired/revoked hash, throttling) makes every cycle end "cleanly";
        resetting on that would mean reconnecting at the initial backoff
        forever, with a hash fetch per cycle.
        """
        sleep = mocker.patch("asyncio.sleep", new_callable=AsyncMock)
        mocker.patch("random.uniform", return_value=1.0)
        ws, _ = _make_ws()
        attempts: list[int] = []

        async def fake_connect() -> None:  # returns instantly and cleanly
            attempts.append(1)
            if len(attempts) >= 4:
                ws.stop()

        ws._connect_once = fake_connect  # type: ignore[method-assign]
        await ws.run()

        waited = [c.args[0] for c in sleep.await_args_list]
        assert waited == [
            _INITIAL_BACKOFF,
            _INITIAL_BACKOFF * 2,
            _INITIAL_BACKOFF * 4,
        ]

    async def test_backoff_resets_only_after_surviving_session(self, mocker) -> None:
        sleep = mocker.patch("asyncio.sleep", new_callable=AsyncMock)
        mocker.patch("random.uniform", return_value=1.0)
        clock = {"now": 0.0}
        mocker.patch(
            "custom_components.melcloudhome.api.websocket.time.monotonic",
            side_effect=lambda: clock["now"],
        )
        ws, _ = _make_ws()
        attempts: list[int] = []

        async def fake_connect() -> None:
            attempts.append(1)
            if len(attempts) == 3:
                # This session survives past the stability threshold.
                clock["now"] += _STABLE_SESSION_SECS
                return
            if len(attempts) >= 4:
                ws.stop()
                return
            raise RuntimeError("boom")

        ws._connect_once = fake_connect  # type: ignore[method-assign]
        await ws.run()

        waited = [c.args[0] for c in sleep.await_args_list]
        # attempt1 fails -> 5s (backoff now 10); attempt2 fails -> 10s
        # (backoff now 20); attempt3 survives >60s -> reset -> 5s.
        assert waited == [
            _INITIAL_BACKOFF,
            _INITIAL_BACKOFF * 2,
            _INITIAL_BACKOFF,
        ]

    async def test_reconnect_sleep_is_jittered(self, mocker) -> None:
        sleep = mocker.patch("asyncio.sleep", new_callable=AsyncMock)
        uniform = mocker.patch("random.uniform", return_value=0.9)
        ws, _ = _make_ws()
        attempts: list[int] = []

        async def fake_connect() -> None:
            attempts.append(1)
            if len(attempts) >= 2:
                ws.stop()
                return
            raise RuntimeError("boom")

        ws._connect_once = fake_connect  # type: ignore[method-assign]
        await ws.run()

        uniform.assert_called_with(0.8, 1.2)
        waited = [c.args[0] for c in sleep.await_args_list]
        assert waited == [_INITIAL_BACKOFF * 0.9]

    async def test_logs_info_on_connection_lost(self, mocker, caplog) -> None:
        """An established session that drops logs one INFO, retries stay DEBUG."""
        mocker.patch("asyncio.sleep", new_callable=AsyncMock)
        mocker.patch("random.uniform", return_value=1.0)
        ws, _ = _make_ws()
        attempts: list[int] = []

        async def fake_connect() -> None:
            attempts.append(1)
            if len(attempts) == 1:
                ws._connected = True  # handshake succeeded, then dropped
                raise RuntimeError("dropped")
            if len(attempts) >= 3:
                ws.stop()
                return
            raise RuntimeError("still down")  # retry failure: no INFO

        ws._connect_once = fake_connect  # type: ignore[method-assign]
        with caplog.at_level("INFO"):
            await ws.run()

        lost = [r for r in caplog.records if "connection lost" in r.getMessage()]
        assert len(lost) == 1
        assert lost[0].levelname == "INFO"

    async def test_cancellation_propagates(self) -> None:
        ws, _ = _make_ws()

        async def fake_connect() -> None:
            raise asyncio.CancelledError

        ws._connect_once = fake_connect  # type: ignore[method-assign]
        with pytest.raises(asyncio.CancelledError):
            await ws.run()


# --------------------------------------------------------------------------- #
# Client credential endpoints
# --------------------------------------------------------------------------- #
def _client_with_auth(
    *, status: int = 200, body: dict | None = None
) -> tuple[MELCloudHomeClient, MagicMock, MagicMock]:
    resp = MagicMock()
    resp.status = status
    resp.json = AsyncMock(return_value=body if body is not None else {"hash": "H"})
    session = MagicMock()
    session.get = MagicMock(return_value=_AsyncCM(resp))

    auth = MagicMock()
    auth.is_token_expired = False
    auth.refresh_token = "refresh-token"
    auth.access_token = "access-token"
    auth.get_session = AsyncMock(return_value=session)
    auth.refresh_access_token = AsyncMock()

    client = MELCloudHomeClient()
    client._auth = auth
    return client, auth, session


class TestAsyncGetWsHash:
    async def test_returns_hash_and_sends_bearer(self) -> None:
        client, auth, session = _client_with_auth(body={"hash": "abc", "userId": "u"})
        result = await client.async_get_ws_hash()
        assert result == "abc"
        auth.refresh_access_token.assert_not_awaited()
        headers = session.get.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer access-token"

    async def test_refreshes_expired_token_and_notifies(self) -> None:
        client, auth, _ = _client_with_auth(body={"hash": "abc"})
        auth.is_token_expired = True
        on_refresh = MagicMock()
        client.set_on_tokens_refreshed(on_refresh)

        await client.async_get_ws_hash()

        auth.refresh_access_token.assert_awaited_once()
        on_refresh.assert_called_once()

    async def test_does_not_refresh_without_refresh_token(self) -> None:
        client, auth, _ = _client_with_auth(body={"hash": "abc"})
        auth.is_token_expired = True
        auth.refresh_token = None

        await client.async_get_ws_hash()

        auth.refresh_access_token.assert_not_awaited()

    @pytest.mark.parametrize("status", [401, 403])
    async def test_rejected_bearer_raises_authentication_error(
        self, status: int
    ) -> None:
        client, _, _ = _client_with_auth(status=status)
        with pytest.raises(AuthenticationError):
            await client.async_get_ws_hash()

    async def test_other_error_status_raises_api_error(self) -> None:
        client, _, _ = _client_with_auth(status=500)
        with pytest.raises(ApiError):
            await client.async_get_ws_hash()

    async def test_missing_hash_field_raises_api_error(self) -> None:
        client, _, _ = _client_with_auth(body={"userId": "u"})
        with pytest.raises(ApiError, match="missing 'hash'"):
            await client.async_get_ws_hash()


class TestAsyncWsSession:
    async def test_returns_authenticated_session(self) -> None:
        client, auth, session = _client_with_auth()
        assert await client.async_ws_session() is session
        auth.get_session.assert_awaited_once()
