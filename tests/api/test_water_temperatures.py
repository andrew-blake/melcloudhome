"""Tests for get_atw_water_temperatures (report/v1/internaltemperatures).

The report carries every ATW water-temperature series in one response, keyed by
dataset id, mixing genuine unit readings (arbitrary-second timestamps) with the
synthetic chart points the server appends - bucket-aligned repeats and a final
echo of the query's own "to".

Reference: docs/api/atw-api-reference.md, ADR-023
Run with: make test-api
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from freezegun import freeze_time

from custom_components.melcloudhome.api.client import MELCloudHomeClient
from custom_components.melcloudhome.api.parsing import Reading


def _dataset(dataset_id: str, points: list[dict[str, Any]]) -> dict[str, Any]:
    """One report dataset."""
    return {"id": dataset_id, "label": dataset_id.upper(), "data": points}


def _report(
    *datasets: dict[str, Any], to: str = "2026-08-22T14:30:00"
) -> list[dict[str, Any]]:
    """A response in the mobile BFF's list-wrapped shape, carrying its "to"."""
    return [{"datasets": list(datasets), "annotations": [], "to": to}]


@freeze_time("2026-08-22 14:30:00", real_asyncio=True)
@pytest.mark.asyncio
async def test_queries_hourly_over_an_8h_window(mocker) -> None:
    """One request, period=Hourly, 8h window, whole-minute "to"."""
    client = MELCloudHomeClient()
    mock_request = mocker.patch.object(
        client,
        "_api_request",
        return_value=_report(
            _dataset("flow_temperature", [{"x": "2026-08-22T14:12:16", "y": 45.2}])
        ),
    )

    result = await client.get_atw_water_temperatures("unit-1")

    mock_request.assert_called_once()
    args, kwargs = mock_request.call_args
    assert args[0] == "GET"
    assert args[1] == "/report/v1/internaltemperatures"

    params = kwargs["params"]
    assert params["unitId"] == "unit-1"
    assert params["period"] == "Hourly"
    to_dt = datetime.strptime(params["to"], "%Y-%m-%dT%H:%M:%S.0000000Z")
    from_dt = datetime.strptime(params["from"], "%Y-%m-%dT%H:%M:%S.0000000Z")
    assert to_dt == datetime(2026, 8, 22, 14, 30, 0)
    assert to_dt.second == 0
    # 8h always lands inside the server's 2-calendar-day ceiling, whatever
    # time of day it runs at (docs/api/atw-api-reference.md)
    assert to_dt - from_dt == timedelta(hours=8)

    assert result == {
        "flow_temperature": Reading(45.2, datetime(2026, 8, 22, 14, 12, 16, tzinfo=UTC))
    }


@pytest.mark.asyncio
async def test_strips_the_to_echo_and_keeps_the_newest_genuine_point(mocker) -> None:
    """The final point repeats the previous value stamped with the query "to"."""
    client = MELCloudHomeClient()
    mocker.patch.object(
        client,
        "_api_request",
        return_value=_report(
            _dataset(
                "return_temperature",
                [
                    {"x": "2026-08-22T12:04:11", "y": 40.0},
                    {"x": "2026-08-22T13:07:52", "y": 41.5},
                    {"x": "2026-08-22T14:00:00", "y": 41.5},  # bucket repeat
                    {"x": "2026-08-22T14:30:00", "y": 41.5},  # to-echo
                ],
            )
        ),
    )

    result = await client.get_atw_water_temperatures("unit-1")

    assert result == {
        "return_temperature": Reading(
            41.5, datetime(2026, 8, 22, 13, 7, 52, tzinfo=UTC)
        )
    }


@pytest.mark.asyncio
async def test_omits_a_dataset_with_only_synthetic_points(mocker) -> None:
    """A dataset the unit never uploaded to is absent from the result.

    Absent means "the endpoint answered and had nothing for this measure",
    which the tracker turns into an unknown sensor (ADR-020). It is distinct
    from a raise, which means the request failed.
    """
    client = MELCloudHomeClient()
    mocker.patch.object(
        client,
        "_api_request",
        return_value=_report(
            _dataset("flow_temperature", [{"x": "2026-08-22T14:12:16", "y": 45.2}]),
            _dataset(
                "flow_temperature_boiler", [{"x": "2026-08-22T14:30:00", "y": 25.0}]
            ),
        ),
    )

    result = await client.get_atw_water_temperatures("unit-1")

    assert set(result) == {"flow_temperature"}


@pytest.mark.asyncio
async def test_parses_the_bare_dict_response_shape(mocker) -> None:
    """The mobile BFF list-wraps reports; parse an unwrapped one too."""
    client = MELCloudHomeClient()
    mocker.patch.object(
        client,
        "_api_request",
        return_value={
            "to": "2026-08-22T14:30:00",
            "datasets": [
                _dataset("flow_temperature", [{"x": "2026-08-22T14:12:16", "y": 45.2}])
            ],
        },
    )

    result = await client.get_atw_water_temperatures("unit-1")

    assert result["flow_temperature"].value == 45.2


@pytest.mark.asyncio
async def test_one_unparsable_point_costs_only_that_point(mocker) -> None:
    """A bad datapoint must not abort the measure for a whole lookback window.

    The newest point here is unparsable, so the next older genuine reading is
    returned rather than the dataset being lost.
    """
    client = MELCloudHomeClient()
    mocker.patch.object(
        client,
        "_api_request",
        return_value=_report(
            _dataset(
                "flow_temperature",
                [
                    {"x": "2026-08-22T13:07:52", "y": 44.0},
                    {"x": "not-a-timestamp", "y": 99.9},
                ],
            )
        ),
    )

    result = await client.get_atw_water_temperatures("unit-1")

    assert result == {
        "flow_temperature": Reading(44.0, datetime(2026, 8, 22, 13, 7, 52, tzinfo=UTC))
    }


@pytest.mark.asyncio
async def test_ignores_a_dataset_with_no_id(mocker) -> None:
    """Dispatch is an identity mapping on `id`; without one there is nothing to key."""
    client = MELCloudHomeClient()
    mocker.patch.object(
        client,
        "_api_request",
        return_value=_report(
            {"label": "MYSTERY", "data": [{"x": "2026-08-22T14:12:16", "y": 45.2}]}
        ),
    )

    assert await client.get_atw_water_temperatures("unit-1") == {}


@pytest.mark.asyncio
async def test_empty_response_yields_no_readings(mocker) -> None:
    """A 200 with nothing in it is not an error, and is not a reading either."""
    client = MELCloudHomeClient()
    mocker.patch.object(client, "_api_request", return_value=None)

    assert await client.get_atw_water_temperatures("unit-1") == {}


@pytest.mark.asyncio
async def test_propagates_exceptions(mocker) -> None:
    """Same contract as the outdoor-temperature reports (issue #251).

    A failed request must stay distinguishable from a successful one holding no
    reading: the tracker keeps its cached readings on the former and clears the
    measure on the latter.
    """
    client = MELCloudHomeClient()
    mocker.patch.object(client, "_api_request", side_effect=ValueError("boom"))

    with pytest.raises(ValueError, match="boom"):
        await client.get_atw_water_temperatures("unit-1")


@pytest.mark.asyncio
async def test_newest_point_is_chosen_by_timestamp_not_position(mocker) -> None:
    """Trust the datapoints' own stamps over the response ordering.

    Responses arrive ascending, but last_reading is user-visible and an
    out-of-order response would send a timestamp backwards (ADR-022). This is
    the rule the per-measure parser carried before the switch.
    """
    client = MELCloudHomeClient()
    mocker.patch.object(
        client,
        "_api_request",
        return_value=_report(
            _dataset(
                "flow_temperature",
                [
                    {"x": "2026-08-22T12:04:11", "y": 40.0},
                    {"x": "2026-08-22T14:12:16", "y": 45.2},
                    {"x": "2026-08-22T13:07:52", "y": 41.5},
                ],
            )
        ),
    )

    result = await client.get_atw_water_temperatures("unit-1")

    assert result == {
        "flow_temperature": Reading(45.2, datetime(2026, 8, 22, 14, 12, 16, tzinfo=UTC))
    }


_ISSUE_394 = json.loads(
    (
        Path(__file__).parent / "fixtures" / "issue394_internaltemperatures.json"
    ).read_text()
)


@pytest.mark.asyncio
async def test_genuine_readings_on_zero_seconds_are_kept(mocker) -> None:
    """A unit whose upload phase drifted onto :00 seconds still updates (#394).

    Trimmed from a real response: genuine 2-minute readings stamped
    06:58:00, hourly repeats at 07:00:00 and the echo at 07:06:00. The old
    seconds == 0 rule kept only the stragglers on :59 (06:53:59) and froze
    flow for hours.
    """
    client = MELCloudHomeClient()
    mocker.patch.object(client, "_api_request", return_value=_ISSUE_394)

    result = await client.get_atw_water_temperatures("unit-1")

    assert result["flow_temperature"] == Reading(
        27.0, datetime(2026, 11, 13, 6, 58, 0, tzinfo=UTC)
    )
    assert result["return_temperature"] == Reading(
        26.5, datetime(2026, 11, 13, 7, 3, 59, tzinfo=UTC)
    )
    assert client._parse_outdoor_temp(_ISSUE_394) == Reading(
        0.0, datetime(2026, 11, 13, 6, 28, 0, tzinfo=UTC)
    )


@pytest.mark.asyncio
async def test_echo_is_matched_in_the_units_local_time(mocker) -> None:
    """The request's "to" is UTC; the echo comes back in unit-local time.

    Measured on the VCR cassette: to=06:00Z was echoed as 08:00 on a
    Europe/Stockholm unit. Matching the request's own "to" would publish the
    echo as a fresh reading (the #224 failure), so the response's "to" is used.
    """
    client = MELCloudHomeClient()
    mocker.patch.object(
        client,
        "_api_request",
        return_value=_report(
            _dataset(
                "flow_temperature",
                [
                    {"x": "2026-08-22T16:12:16", "y": 45.2},
                    {"x": "2026-08-22T16:30:00", "y": 45.2},  # echo
                ],
            ),
            to="2026-08-22T16:30:00",
        ),
    )

    result = await client.get_atw_water_temperatures(
        "unit-1", ZoneInfo("Europe/Stockholm")
    )

    assert result == {
        "flow_temperature": Reading(45.2, datetime(2026, 8, 22, 14, 12, 16, tzinfo=UTC))
    }


def test_without_a_response_to_the_final_point_is_the_echo() -> None:
    """No top-level "to": treat the final point as the echo.

    Every measured response carries "to". Without it, losing one genuine
    point is cheaper than publishing an echo as a fresh reading.
    """
    client = MELCloudHomeClient()
    data = [
        {"x": "2026-08-22T14:12:16", "y": 45.2},
        {"x": "2026-08-22T14:28:31", "y": 46.0},
    ]

    assert client._latest_genuine_reading(data) == Reading(
        45.2, datetime(2026, 8, 22, 14, 12, 16, tzinfo=UTC)
    )
