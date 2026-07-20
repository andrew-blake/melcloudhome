"""In-process tests for the mock server's WebSocket support (no Docker)."""

import asyncio
from time import time

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


ATA_ID = "0efc1234-5678-9abc-def0-123456787db"  # Living Room AC (seeded)


async def test_put_emits_typed_delta_to_all_sockets(mock_client):
    client, _ = mock_client
    ws1 = await client.ws_connect(f"/ws?hash={MOCK_WS_HASH}")
    ws2 = await client.ws_connect(f"/ws?hash={MOCK_WS_HASH}")

    # Living Room AC seeds power=True (see _init_ata_devices), so power=False
    # here is the field that actually changes — power=True would be a noop
    # and (correctly, per test_noop_put_emits_nothing) emit no delta for it.
    resp = await client.put(
        f"/monitor/ataunit/{ATA_ID}",
        json={"power": False, "setTemperature": 21.5, "operationMode": "Cool"},
        headers=BEARER,
    )
    assert resp.status == 200

    for ws in (ws1, ws2):
        frame = await ws.receive_json(timeout=2)
        assert isinstance(frame, list) and len(frame) == 1
        assert frame[0]["messageType"] == "unitStateChanged"
        data = frame[0]["Data"]
        assert data["id"] == ATA_ID
        by_name = {s["name"]: s["value"] for s in data["settings"]}
        # Typed values, per #175 capture — NOT the stringified REST forms
        assert by_name["Power"] is False
        assert by_name["SetTemperature"] == 21.5
        assert by_name["OperationMode"] == 3  # int enum: 3=Cool (captured)
    await ws1.close()
    await ws2.close()


async def test_noop_put_emits_nothing(mock_client):
    client, _ = mock_client
    # Set a known value, then re-send the identical value: no delta.
    await client.put(
        f"/monitor/ataunit/{ATA_ID}", json={"setTemperature": 22.0}, headers=BEARER
    )
    ws = await client.ws_connect(f"/ws?hash={MOCK_WS_HASH}")
    await client.put(
        f"/monitor/ataunit/{ATA_ID}", json={"setTemperature": 22.0}, headers=BEARER
    )
    with pytest.raises(asyncio.TimeoutError):
        await ws.receive_json(timeout=0.5)
    await ws.close()


async def test_put_fan_speed_word_value_emits_typed_int(mock_client):
    # Regression: fan speed is a word ("Auto".."Five"), not a numeric string.
    # int("Three") used to raise ValueError inside _broadcast_delta after the
    # PUT had already mutated state, 500ing the whole request.
    client, _ = mock_client
    ws = await client.ws_connect(f"/ws?hash={MOCK_WS_HASH}")
    resp = await client.put(
        f"/monitor/ataunit/{ATA_ID}", json={"setFanSpeed": "Three"}, headers=BEARER
    )
    assert resp.status == 200
    frame = await ws.receive_json(timeout=2)
    by_name = {s["name"]: s["value"] for s in frame[0]["Data"]["settings"]}
    assert by_name["SetFanSpeed"] == 3
    await ws.close()


async def test_atw_put_emits_assumed_shape_delta(mock_client):
    client, _ = mock_client
    atw_id = "bf2d256c-42ac-4799-a6d8-c6ab433e5666"  # House Heat Pump (seeded)
    ws = await client.ws_connect(f"/ws?hash={MOCK_WS_HASH}")
    await client.put(
        f"/monitor/atwunit/{atw_id}",
        json={"setTankWaterTemperature": 52.0},
        headers=BEARER,
    )
    frame = await ws.receive_json(timeout=2)
    by_name = {s["name"]: s["value"] for s in frame[0]["Data"]["settings"]}
    assert by_name["SetTankWaterTemperature"] == 52.0
    await ws.close()


async def test_control_reject_hash(mock_client):
    client, _ = mock_client
    await client.post("/_mock/ws", json={"action": "reject-hash"}, headers=BEARER)
    with pytest.raises(aiohttp.WSServerHandshakeError) as err:
        await client.ws_connect(f"/ws?hash={MOCK_WS_HASH}")
    assert err.value.status == 403
    await client.post("/_mock/ws", json={"action": "clear"}, headers=BEARER)
    ws = await client.ws_connect(f"/ws?hash={MOCK_WS_HASH}")  # works again
    await ws.close()


async def test_control_accept_then_close(mock_client):
    client, _ = mock_client
    await client.post("/_mock/ws", json={"action": "accept-then-close"}, headers=BEARER)
    ws = await client.ws_connect(f"/ws?hash={MOCK_WS_HASH}")  # 101 succeeds...
    msg = await ws.receive(timeout=2)  # ...then server closes immediately
    assert msg.type == aiohttp.WSMsgType.CLOSE
    await client.post("/_mock/ws", json={"action": "clear"}, headers=BEARER)


async def test_control_close_now(mock_client):
    client, server = mock_client
    ws = await client.ws_connect(f"/ws?hash={MOCK_WS_HASH}")
    await client.post("/_mock/ws", json={"action": "close-now"}, headers=BEARER)
    msg = await ws.receive(timeout=2)
    assert msg.type == aiohttp.WSMsgType.CLOSE
    assert server.ws_clients == set()


async def test_control_emit_delta_passive_push(mock_client):
    client, _ = mock_client
    ws = await client.ws_connect(f"/ws?hash={MOCK_WS_HASH}")
    # Canonical passive push observed on prod: RoomTemperature + ActualFanSpeed
    await client.post(
        "/_mock/ws",
        json={
            "action": "emit-delta",
            "unit_id": ATA_ID,
            "settings": [
                {"name": "RoomTemperature", "value": 22.5},
                {"name": "ActualFanSpeed", "value": "2"},  # string, per capture
            ],
        },
        headers=BEARER,
    )
    frame = await ws.receive_json(timeout=2)
    by_name = {s["name"]: s["value"] for s in frame[0]["Data"]["settings"]}
    assert by_name["RoomTemperature"] == 22.5
    assert by_name["ActualFanSpeed"] == "2"
    await ws.close()


async def test_control_unknown_action_400(mock_client):
    client, _ = mock_client
    resp = await client.post("/_mock/ws", json={"action": "explode"}, headers=BEARER)
    assert resp.status == 400


async def test_control_requires_bearer(mock_client):
    """The fault-injection endpoint is not auth-exempt (LAN-peer hardening)."""
    client, _ = mock_client
    resp = await client.post("/_mock/ws", json={"action": "status"})
    assert resp.status == 401


async def test_control_emit_delta_missing_fields_400(mock_client):
    client, _ = mock_client
    resp = await client.post("/_mock/ws", json={"action": "emit-delta"}, headers=BEARER)
    assert resp.status == 400


async def test_control_status_reports_client_count(mock_client):
    client, _ = mock_client
    resp = await client.post("/_mock/ws", json={"action": "status"}, headers=BEARER)
    assert (await resp.json())["clients"] == 0
    ws = await client.ws_connect(f"/ws?hash={MOCK_WS_HASH}")
    resp = await client.post("/_mock/ws", json={"action": "status"}, headers=BEARER)
    assert (await resp.json())["clients"] == 1
    await ws.close()


async def test_ws_paths_exempt_from_rate_limiting(mock_client, monkeypatch):
    """Regression: with the limiter live, the client hits /ws/token then
    immediately opens /ws — <50ms apart. Without the exemption this
    livelocks the listener (token 200 -> upgrade 429 -> backoff -> repeat).
    """
    client, _ = mock_client
    monkeypatch.setattr("tools.mock_melcloud_server.ENABLE_RATE_LIMITING", True)
    # Simulate a REST request having just consumed the rate limit window.
    monkeypatch.setattr("tools.mock_melcloud_server.last_request_time", time())

    resp = await client.get("/ws/token", headers=BEARER)
    assert resp.status == 200

    ws = await client.ws_connect(f"/ws/?hash={MOCK_WS_HASH}")
    await ws.close()
