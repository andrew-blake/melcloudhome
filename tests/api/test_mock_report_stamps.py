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

Naive is necessary but not sufficient. The real server stamps in the unit's own
zone, so naive UTC would still be wrong - the conversion would run on the wrong
input and every age would be out by the offset. These tests pin the zone too.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from aiohttp.test_utils import TestClient, TestServer

from tools.mock_melcloud_server import MockMELCloudServer

BEARER = {"Authorization": "Bearer mock-token"}

# The mock's buildings: "My Home" is Europe/London, the guest "Shared Building"
# is Europe/Madrid. In August that is BST (+1) and CEST (+2) - two different
# offsets, which is what makes a wrong-zone bug visible at all.
ATW_UNIT = "bf2d256c-42ac-4799-a6d8-c6ab433e5666"  # Europe/London
ATA_UNIT = "0efc1234-5678-9abc-def0-1234567887db"  # Europe/London
GUEST_ATW_UNIT = "aed21234-5678-9abc-def0-123456789abc"  # Europe/Madrid

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


@pytest.mark.parametrize(
    ("unit_id", "zone"),
    [(ATW_UNIT, "Europe/London"), (GUEST_ATW_UNIT, "Europe/Madrid")],
)
async def test_report_stamps_are_in_the_units_own_zone(mock_client, unit_id, zone):
    """Stamps must be unit-local wall-clock time, not UTC.

    Asserted as an offset from the request's own `to` bound rather than against
    the clock, so the test does not depend on when it runs. `to` goes out as
    UTC; the newest stamp must come back shifted ahead of it by exactly the
    unit's offset, which is what the real backend does.
    """
    resp = await mock_client.get(
        "/report/v1/internaltemperatures",
        params={"unitId": unit_id, **WINDOW},
        headers=BEARER,
    )
    assert resp.status == 200

    to_utc = datetime.fromisoformat(WINDOW["to"].replace(".0000000", ""))
    expected_offset = to_utc.astimezone(ZoneInfo(zone)).utcoffset()

    # The to-echo point: the query's own `to`, restamped in the unit's zone.
    newest = max(
        datetime.fromisoformat(s) for s in _stamps(await resp.json(content_type=None))
    )
    actual_offset = newest - to_utc.replace(tzinfo=None)

    assert actual_offset == expected_offset, (
        f"{zone} unit stamped {newest.isoformat()} for a `to` of "
        f"{to_utc.isoformat()}: shifted by {actual_offset}, expected "
        f"{expected_offset}. A shift of 0 means the mock is stamping in UTC, "
        "so every reading age it produces is wrong by the unit's offset."
    )


async def test_the_two_zones_disagree_by_an_hour(mock_client):
    """The London and Madrid units must not agree on the same instant.

    This is the discriminator that caught the original bug: two units at
    different offsets reporting one identical stamp is physically impossible if
    each is being stamped in its own zone. It fails for BOTH ways of getting
    this wrong - aware stamps and naive UTC - which no other test does.
    """
    stamps = {}
    for unit_id in (ATW_UNIT, GUEST_ATW_UNIT):
        resp = await mock_client.get(
            "/report/v1/internaltemperatures",
            params={"unitId": unit_id, **WINDOW},
            headers=BEARER,
        )
        assert resp.status == 200
        stamps[unit_id] = max(
            datetime.fromisoformat(s)
            for s in _stamps(await resp.json(content_type=None))
        )

    delta = stamps[GUEST_ATW_UNIT] - stamps[ATW_UNIT]
    assert delta == timedelta(hours=1), (
        f"Europe/Madrid stamp {stamps[GUEST_ATW_UNIT].isoformat()} and "
        f"Europe/London stamp {stamps[ATW_UNIT].isoformat()} differ by {delta}, "
        "expected exactly 1h (CEST vs BST in August)"
    )
