"""Tests for get_atw_water_temperatures (report/v1/internaltemperatures).

The report carries every ATW water-temperature series in one response, keyed by
dataset id, mixing genuine unit readings (arbitrary-second timestamps) with the
synthetic chart points the server appends - bucket-aligned repeats and a final
echo of the query's own "to".

Reference: docs/api/atw-api-reference.md, ADR-023
Run with: make test-api
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from freezegun import freeze_time

from custom_components.melcloudhome.api.client import MELCloudHomeClient
from custom_components.melcloudhome.api.parsing import Reading


def _dataset(dataset_id: str, points: list[dict[str, Any]]) -> dict[str, Any]:
    """One report dataset."""
    return {"id": dataset_id, "label": dataset_id.upper(), "data": points}


def _report(*datasets: dict[str, Any]) -> list[dict[str, Any]]:
    """A response in the mobile BFF's list-wrapped shape."""
    return [{"datasets": list(datasets), "annotations": []}]


@freeze_time("2026-08-22 14:30:00", real_asyncio=True)
@pytest.mark.asyncio
async def test_queries_hourly_over_an_8h_window(mocker) -> None:
    """One request, period=Hourly, 8h window, seconds-aligned "to".

    The seconds alignment is load-bearing: it is what makes the server's
    to-echo point identifiable as synthetic.
    """
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
    to_dt = datetime.strptime(params["to"], "%Y-%m-%dT%H:%M:%S.0000000")
    from_dt = datetime.strptime(params["from"], "%Y-%m-%dT%H:%M:%S.0000000")
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
            "datasets": [
                _dataset("flow_temperature", [{"x": "2026-08-22T14:12:16", "y": 45.2}])
            ]
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
