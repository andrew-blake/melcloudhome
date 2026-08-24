"""In-process test that the mock's report stamps stay naive (no Docker).

The integration sends `from`/`to` with an explicit `Z` (api/client.py
_report_params). The mock feeds those parsed bounds straight into the emitted
datapoints' "x" values, so if it parses them as timezone-aware, every stamp it
returns carries "+00:00" — and parse_api_timestamp then *converts* rather than
interpreting, silently bypassing the unit-timezone path the mock exists to
exercise.

That regression passed the entire suite, in both directions: the integration
test for the timezone wiring mocks at the client layer, so nothing downstream
noticed the mock had stopped modelling the real server's naive stamps. This
catches it at source instead.
"""

import pytest
from aiohttp.test_utils import TestClient, TestServer

from tools.mock_melcloud_server import MockMELCloudServer

BEARER = {"Authorization": "Bearer mock-token"}

# A single-zone ATW unit the mock always defines, and the two ATA units.
ATW_UNIT = "bf2d256c-42ac-4799-a6d8-c6ab433e5666"
ATA_UNIT = "0efc1234-5678-9abc-def0-1234567887db"

# The exact shape _report_params builds, including the trailing Z.
WINDOW = {
    "period": "Hourly",
    "from": "2026-08-24T04:00:00.0000000Z",
    "to": "2026-08-24T11:50:00.0000000Z",
}


@pytest.fixture(autouse=True)
def _disable_rate_limiting(monkeypatch):
    """The mock's rate limiter is module state and bleeds across in-process
    tests run back-to-back, same as in test_mock_ws_server.py.
    """
    monkeypatch.setattr("tools.mock_melcloud_server.ENABLE_RATE_LIMITING", False)


@pytest.fixture
async def mock_client():
    server = MockMELCloudServer()
    client = TestClient(TestServer(server.create_app()))
    await client.start_server()
    yield client
    await client.close()


def _stamps(payload) -> list[str]:
    """Every "x" value in the response, across every dataset."""
    report = payload[0] if isinstance(payload, list) and payload else payload
    return [
        str(point["x"])
        for dataset in report.get("datasets", [])
        for point in dataset.get("data", [])
        if "x" in point
    ]


@pytest.mark.parametrize(
    ("endpoint", "unit_id"),
    [
        ("/report/v1/internaltemperatures", ATW_UNIT),
        ("/report/v1/comfort-graph", ATW_UNIT),
        ("/report/v1/trendsummary", ATA_UNIT),
    ],
)
async def test_report_stamps_carry_no_offset(mock_client, endpoint, unit_id):
    """A Z-suffixed request window must not make the stamps timezone-aware.

    The real server answers a `Z` window with naive unit-local stamps, so an
    offset suffix here means the mock has stopped resembling it.
    """
    resp = await mock_client.get(
        endpoint, params={"unitId": unit_id, **WINDOW}, headers=BEARER
    )
    assert resp.status == 200
    # The mock serves reports as text/plain, matching the real server.
    stamps = _stamps(await resp.json(content_type=None))
    assert stamps, f"{endpoint} returned no datapoints to check"

    offending = [s for s in stamps if s.endswith("Z") or "+" in s[10:]]
    assert not offending, (
        f"{endpoint} returned timezone-aware stamps {offending[:3]}; "
        "parse_api_timestamp will convert these and ignore the unit's zone"
    )
