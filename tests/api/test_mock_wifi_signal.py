"""In-process test that the mock serves the rssi telemetry series (no Docker).

Drives MELCloudHomeClient.get_wifi_signal against the mock's handler for every
mock unit, ATA and ATW, so the devserver's Wi-Fi sensors have values and the
mock keeps the real endpoint's shape: the last reading before "from" comes
first, values are integer strings, stamps are UTC (ADR-028).
"""

import json
from typing import Any

import pytest
from aiohttp.test_utils import TestClient, TestServer

from custom_components.melcloudhome.api.client import MELCloudHomeClient
from custom_components.melcloudhome.api.models import (
    AirToAirUnit,
    AirToWaterUnit,
    UserContext,
)
from tools.mock_melcloud_server import MockMELCloudServer

BEARER = {"Authorization": "Bearer mock-token"}


@pytest.fixture(autouse=True)
def _disable_rate_limiting(monkeypatch):
    """The mock's rate limiter is module state and bleeds across tests."""
    monkeypatch.setattr("tools.mock_melcloud_server.ENABLE_RATE_LIMITING", False)


@pytest.fixture
async def mock_server():
    client = TestClient(TestServer(MockMELCloudServer().create_app()))
    await client.start_server()
    yield client
    await client.close()


@pytest.mark.asyncio
async def test_every_mock_unit_gets_an_integer_wifi_signal_reading(
    mock_server: TestClient, mocker
) -> None:
    """Both device types, the client's own query, an int dBm with a UTC stamp."""

    async def via_mock(method: str, endpoint: str, **kwargs: Any) -> Any:
        resp = await mock_server.request(
            method, endpoint, params=kwargs.get("params"), headers=BEARER
        )
        assert resp.status == 200, f"{endpoint}: HTTP {resp.status}"
        return json.loads(await resp.text())

    client = MELCloudHomeClient()
    mocker.patch.object(client, "_api_request", side_effect=via_mock)

    context = UserContext.from_dict(await via_mock("GET", "/context"))
    units: list[AirToAirUnit | AirToWaterUnit] = []
    for building in context.buildings:
        units.extend(building.air_to_air_units)
        units.extend(building.air_to_water_units)
    assert any(b.air_to_air_units for b in context.buildings)
    assert any(b.air_to_water_units for b in context.buildings)

    for unit in units:
        reading = await client.get_wifi_signal(unit.id)
        assert reading is not None, unit.id
        assert type(reading.value) is int
        assert -100 < reading.value < 0
        assert reading.recorded_at.tzinfo is not None
