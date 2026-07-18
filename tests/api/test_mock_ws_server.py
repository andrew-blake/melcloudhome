"""In-process tests for the mock server's WebSocket support (no Docker)."""

import aiohttp
import pytest
from aiohttp.test_utils import TestClient, TestServer

from tools.mock_melcloud_server import MOCK_WS_HASH, MockMELCloudServer

BEARER = {"Authorization": "Bearer mock-token"}


@pytest.fixture(autouse=True)
def _disable_rate_limiting(monkeypatch):
    """The mock server's rate limiter tracks last-request time as module
    state, which bleeds across tests run back-to-back in the same process
    (no Docker, no real network delay between requests). Irrelevant to WS
    behavior — disable it here rather than in the server itself.
    """
    monkeypatch.setattr("tools.mock_melcloud_server.ENABLE_RATE_LIMITING", False)


@pytest.fixture
async def mock_client():
    server = MockMELCloudServer()
    client = TestClient(TestServer(server.create_app()))
    await client.start_server()
    yield client, server
    await client.close()


async def test_ws_token_returns_hash_equal_userid(mock_client):
    client, _ = mock_client
    resp = await client.get("/ws/token", headers=BEARER)
    assert resp.status == 200
    data = await resp.json()
    assert data["hash"] == MOCK_WS_HASH
    assert data["userId"] == data["hash"]


async def test_ws_token_requires_bearer(mock_client):
    client, _ = mock_client
    resp = await client.get("/ws/token")
    assert resp.status == 401


async def test_ws_upgrade_with_valid_hash_no_bearer(mock_client):
    client, server = mock_client
    ws = await client.ws_connect(f"/ws/?hash={MOCK_WS_HASH}")
    assert len(server.ws_clients) == 1
    await ws.close()


async def test_ws_upgrade_rejects_bad_hash(mock_client):
    client, _ = mock_client
    with pytest.raises(aiohttp.WSServerHandshakeError) as err:
        await client.ws_connect("/ws/?hash=wrong")
    assert err.value.status == 403


async def test_ws_inbound_frames_ignored_and_disconnect_cleans_up(mock_client):
    client, server = mock_client
    ws = await client.ws_connect(f"/ws?hash={MOCK_WS_HASH}")
    await ws.send_str("garbage the real client never sends")
    await ws.close()
    assert server.ws_clients == set()
