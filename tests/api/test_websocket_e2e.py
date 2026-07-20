"""Real-wire e2e: real client + real WS listener against the Docker mock.

Covers everything below the coordinator (hash fetch, handshake, frame
parsing, reconnect). The hass side (delta -> debounced refresh -> states) is
covered in tests/integration/ with a mocked client; the stitched seam was
verified on prod 2026-07-18 (design doc, section 5).

Requires: mock server running (make dev-up locally, or make test-e2e).
"""

import asyncio

import aiohttp
import pytest

from custom_components.melcloudhome.api.client import MELCloudHomeClient
from custom_components.melcloudhome.api.const_shared import MOCK_BASE_URL
from custom_components.melcloudhome.api.websocket import MELCloudHomeWebSocket

# The control endpoint requires a bearer like every other mock endpoint
# (any value passes — the mock only checks the scheme).
_BEARER = {"Authorization": "Bearer mock-token"}


async def _ws_control(action: str) -> None:
    async with (
        aiohttp.ClientSession() as session,
        session.post(
            f"{MOCK_BASE_URL}/_mock/ws", json={"action": action}, headers=_BEARER
        ) as resp,
    ):
        assert resp.status == 200


async def _ws_client_count() -> int:
    async with (
        aiohttp.ClientSession() as session,
        session.post(
            f"{MOCK_BASE_URL}/_mock/ws", json={"action": "status"}, headers=_BEARER
        ) as resp,
    ):
        return int((await resp.json())["clients"])


async def _wait_for_new_ws_client(baseline: int, timeout: float = 10.0) -> None:
    """Block until the mock reports more sockets than `baseline`."""

    async def poll() -> None:
        while await _ws_client_count() <= baseline:
            await asyncio.sleep(0.1)

    await asyncio.wait_for(poll(), timeout=timeout)


class TestWebSocketE2E:
    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_put_reaches_delta_handler_over_real_wire(self):
        client = MELCloudHomeClient(debug_mode=True)
        deltas: list[tuple[str, list[str]]] = []
        got_one = asyncio.Event()

        async def on_delta(unit_id: str, names: list[str]) -> None:
            deltas.append((unit_id, names))
            got_one.set()

        listener = MELCloudHomeWebSocket(client, on_delta=on_delta)
        task: asyncio.Task | None = None
        try:
            # Login before starting the listener task: async_get_ws_hash()
            # requires an authenticated session, and starting the task first
            # makes its first connect attempt fail (no token yet), forcing a
            # 5s backoff that reliably misses the PUT below. Matches
            # production ordering (coordinator starts the WS task only after
            # the client is already authenticated).
            await client.login("test@example.com", "password")
            baseline = await _ws_client_count()
            task = asyncio.create_task(listener.run())
            context = await client.get_user_context()
            unit = context.buildings[0].air_to_air_units[0]
            # Deterministic connect wait — a fixed sleep raced slow runners.
            await _wait_for_new_ws_client(baseline)

            await client.ata.set_temperature(unit.id, 23.5)

            await asyncio.wait_for(got_one.wait(), timeout=10)
            unit_ids = [d[0] for d in deltas]
            assert unit.id in unit_ids
            names = [n for d in deltas if d[0] == unit.id for n in d[1]]
            assert "SetTemperature" in names
        finally:
            listener.stop()
            if task is not None:
                task.cancel()
                # Reap without raising: swallows the expected CancelledError
                # and, unlike pytest.raises here in finally, can't mask the
                # test's own failure if the task had already finished.
                await asyncio.gather(task, return_exceptions=True)
            await client.close()

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_listener_survives_accept_then_close(self):
        await _ws_control("accept-then-close")
        client = MELCloudHomeClient(debug_mode=True)

        async def on_delta(unit_id: str, names: list[str]) -> None:
            pass

        listener = MELCloudHomeWebSocket(client, on_delta=on_delta)
        task: asyncio.Task | None = None
        try:
            # Login before starting the listener task (see comment in the
            # test above) so the connect/close/backoff cycle under test is
            # the accept-then-close one, not a pre-login auth failure.
            await client.login("test@example.com", "password")
            task = asyncio.create_task(listener.run())
            # Long enough for >1 connect/close/backoff cycle (initial 5s)
            await asyncio.sleep(8)
            assert not task.done(), "listener died instead of backing off"
        finally:
            await _ws_control("clear")
            listener.stop()
            if task is not None:
                task.cancel()
                # Reap without raising (see comment in the test above).
                await asyncio.gather(task, return_exceptions=True)
            await client.close()
