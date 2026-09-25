"""In-process tests for the mock's combined-energy route (no Docker)."""

from datetime import datetime

import pytest
from aiohttp import ClientResponse
from aiohttp.test_utils import TestClient, TestServer

from tools.mock_melcloud_server import MockMELCloudServer

BEARER = {"Authorization": "Bearer mock-token"}
ATW_UNIT = "bf2d256c-42ac-4799-a6d8-c6ab433e5666"  # Europe/London
ATA_UNIT = "0efc1234-5678-9abc-def0-1234567887db"  # Europe/London
# 24 Aug 2026, London local day (BST, UTC+1), as the integration sends it.
DAY = {
    "period": "Daily",
    "from": "2026-08-23T23:00:00.0000000Z",
    "to": "2026-08-24T23:00:00.0000000Z",
}


@pytest.fixture(autouse=True)
def _disable_rate_limiting(monkeypatch):
    monkeypatch.setattr("tools.mock_melcloud_server.ENABLE_RATE_LIMITING", False)


@pytest.fixture
async def mock_client():
    server = MockMELCloudServer()
    client = TestClient(TestServer(server.create_app()))
    await client.start_server()
    yield client
    await client.close()


async def _get(client: TestClient, params: dict[str, str]) -> ClientResponse:
    return await client.get("/report/v1/combined-energy", params=params, headers=BEARER)


@pytest.mark.asyncio
async def test_atw_day_has_local_hourly_labels_inside_the_day(mock_client) -> None:
    resp = await _get(mock_client, {**DAY, "unitId": ATW_UNIT})
    assert resp.status == 200
    report = (await resp.json(content_type=None))[0]
    ids = {d["id"] for d in report["datasets"]}
    assert {"interval_energy_consumed", "interval_energy_produced"} <= ids
    for dataset in report["datasets"]:
        if not dataset["id"].startswith("interval_energy_"):
            continue
        for point in dataset["data"]:
            stamp = datetime.fromisoformat(point["x"])
            assert stamp.tzinfo is None  # naive, device-local like the real server
            assert (stamp.minute, stamp.second) == (0, 0)
            assert stamp.date().isoformat() == "2026-08-24"  # inside the local day


@pytest.mark.asyncio
async def test_completed_hours_are_stable_across_requests(mock_client) -> None:
    first = (
        await (await _get(mock_client, {**DAY, "unitId": ATW_UNIT})).json(
            content_type=None
        )
    )[0]
    second = (
        await (await _get(mock_client, {**DAY, "unitId": ATW_UNIT})).json(
            content_type=None
        )
    )[0]
    assert first["datasets"] == second["datasets"]


@pytest.mark.asyncio
async def test_ata_unit_gets_500(mock_client) -> None:
    assert (await _get(mock_client, {**DAY, "unitId": ATA_UNIT})).status == 500


@pytest.mark.asyncio
async def test_missing_and_unknown_unit(mock_client) -> None:
    assert (await _get(mock_client, DAY)).status == 400
    assert (
        await _get(
            mock_client, {**DAY, "unitId": "00000000-0000-0000-0000-000000000000"}
        )
    ).status == 404
