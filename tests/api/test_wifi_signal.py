"""Tests for get_wifi_signal (telemetry/actual, measure=rssi).

/context's rssi froze in September 2026 (#350, ADR-028). The vendor app charts
this series instead. Measured in a 24 h soak: stamps are UTC, every non-empty
response starts with the last reading before "from", values are integer dBm
strings, a value can be null, and a genuine reading can land on second 0.

Reference: docs/api/melcloudhome-telemetry-endpoints.md, ADR-028
Run with: make test-api
"""

from datetime import UTC, datetime
from typing import Any

import pytest
from freezegun import freeze_time

from custom_components.melcloudhome.api.client import MELCloudHomeClient
from custom_components.melcloudhome.api.parsing import Reading


def _response(*points: tuple[Any, Any]) -> dict[str, Any]:
    """A telemetry/actual response holding one rssi series."""
    return {
        "measureData": [
            {
                "deviceId": "unit-1",
                "type": "rssi",
                "values": [{"time": time, "value": value} for time, value in points],
            }
        ],
    }


@freeze_time("2026-10-05 10:17:42", real_asyncio=True)
@pytest.mark.asyncio
async def test_queries_one_hour_of_rssi_in_utc(mocker) -> None:
    """A 1 h UTC window ending now; the response covers only ~1 h from "from"."""
    client = MELCloudHomeClient()
    mock_request = mocker.patch.object(client, "_api_request", return_value=None)

    await client.get_wifi_signal("unit-1")

    mock_request.assert_called_once_with(
        "GET",
        "/telemetry/telemetry/actual/unit-1",
        params={
            "from": "2026-10-05 09:17",
            "to": "2026-10-05 10:17",
            "measure": "rssi",
        },
    )


@pytest.mark.asyncio
async def test_returns_the_newest_point_as_an_int_reading(mocker) -> None:
    """dBm are integers on the wire, and the sensor state must stay "-55"."""
    client = MELCloudHomeClient()
    mocker.patch.object(
        client,
        "_api_request",
        return_value=_response(
            ("2026-10-05 09:14:07.000000000", "-56"),
            ("2026-10-05 10:11:24.000000000", "-55"),
        ),
    )

    reading = await client.get_wifi_signal("unit-1")

    assert reading == Reading(-55, datetime(2026, 10, 5, 10, 11, 24, tzinfo=UTC))
    assert type(reading.value) is int


@pytest.mark.asyncio
async def test_newest_point_is_chosen_by_timestamp_not_position(mocker) -> None:
    """ADR-022: an out-of-order response must not send last_reading backwards."""
    client = MELCloudHomeClient()
    mocker.patch.object(
        client,
        "_api_request",
        return_value=_response(
            ("2026-10-05 10:11:24.000000000", "-55"),
            ("2026-10-05 09:14:07.000000000", "-56"),
        ),
    )

    reading = await client.get_wifi_signal("unit-1")

    assert reading == Reading(-55, datetime(2026, 10, 5, 10, 11, 24, tzinfo=UTC))


@pytest.mark.asyncio
async def test_parses_stamps_with_and_without_nine_digit_fractions_as_utc(
    mocker,
) -> None:
    """Both stamp forms parse, and as UTC: the unit's zone is never applied."""
    client = MELCloudHomeClient()
    mocker.patch.object(
        client,
        "_api_request",
        return_value=_response(
            ("2026-10-05 10:11:24.123456789", "-55"),
            ("2026-10-05 10:13:24", "-57"),
        ),
    )

    reading = await client.get_wifi_signal("unit-1")

    assert reading == Reading(-57, datetime(2026, 10, 5, 10, 13, 24, tzinfo=UTC))


@pytest.mark.asyncio
async def test_keeps_a_genuine_point_on_second_zero(mocker) -> None:
    """Measured: a 10-minute uploader's stamps drift onto :00. No synthetic filter."""
    client = MELCloudHomeClient()
    mocker.patch.object(
        client,
        "_api_request",
        return_value=_response(
            ("2026-10-05 17:16:59.000000000", "-60"),
            ("2026-10-05 17:27:00.000000000", "-61"),
        ),
    )

    reading = await client.get_wifi_signal("unit-1")

    assert reading == Reading(-61, datetime(2026, 10, 5, 17, 27, 0, tzinfo=UTC))


@pytest.mark.asyncio
async def test_skips_null_and_unparsable_points(mocker) -> None:
    """A bad point costs that point only (ADR-022). Nulls were measured live."""
    client = MELCloudHomeClient()
    mocker.patch.object(
        client,
        "_api_request",
        return_value=_response(
            ("2026-10-05 09:14:07.000000000", "-56"),
            ("2026-10-05 10:20:00.000000000", None),
            ("2026-10-05 10:21:00.000000000", "n/a"),
            ("not a time", "-40"),
            (None, "-41"),
        ),
    )

    reading = await client.get_wifi_signal("unit-1")

    assert reading == Reading(-56, datetime(2026, 10, 5, 9, 14, 7, tzinfo=UTC))


@pytest.mark.parametrize(
    "response",
    [
        None,  # 304 Not Modified
        {},
        {"measureData": []},
        _response(),
        _response(("2026-10-05 10:20:00.000000000", None)),
    ],
    ids=["304", "no-measure-data-key", "empty-measure-data", "no-values", "only-null"],
)
@pytest.mark.asyncio
async def test_nothing_usable_returns_none(mocker, response: Any) -> None:
    """No usable point is "no reading". The caller decides what that means (ADR-028)."""
    client = MELCloudHomeClient()
    mocker.patch.object(client, "_api_request", return_value=response)

    assert await client.get_wifi_signal("unit-1") is None


@pytest.mark.asyncio
async def test_propagates_exceptions(mocker) -> None:
    """A failed request raises, so it stays distinct from an empty one (ADR-020)."""
    client = MELCloudHomeClient()
    mocker.patch.object(client, "_api_request", side_effect=TimeoutError())

    with pytest.raises(TimeoutError):
        await client.get_wifi_signal("unit-1")
