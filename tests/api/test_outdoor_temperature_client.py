"""Tests for outdoor temperature API client methods."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from freezegun import freeze_time

from custom_components.melcloudhome.api.client import MELCloudHomeClient


class TestParseOutdoorTemp:
    """Tests for _parse_outdoor_temp method.

    Real trendsummary responses mix genuine unit readings (arbitrary-second
    timestamps like 07:15:24) with synthetic chart points the server appends:
    bucket-aligned repeats of the last value (08:00:00, 09:00:00) and a final
    point stamped with the query's own "to" parameter. Only points with
    non-zero seconds are real readings.
    """

    def test_parse_outdoor_temperature_success(self):
        """Test parsing returns the latest genuine reading."""
        client = MELCloudHomeClient()
        response = {
            "datasets": [
                {
                    "label": "REPORT.TREND_SUMMARY_REPORT.DATASET.LABELS.ROOM_TEMPERATURE",
                    "data": [{"x": "2026-02-03T12:00:00", "y": 20.5}],
                },
                {
                    "label": "REPORT.TREND_SUMMARY_REPORT.DATASET.LABELS.OUTDOOR_TEMPERATURE",
                    "data": [
                        {"x": "2026-02-03T11:00:23", "y": 11.0},
                        {"x": "2026-02-03T12:00:23", "y": 12.0},
                    ],
                },
            ]
        }

        result = client._parse_outdoor_temp(response)

        assert result == (12.0, datetime(2026, 2, 3, 12, 0, 23, tzinfo=UTC))  # Latest

    def test_parse_outdoor_temperature_skips_synthetic_points(self):
        """Synthetic points (second-aligned padding and the to-echo) are skipped.

        Mirrors a real prod response: genuine readings at 07:14:23/07:15:24,
        then hour-aligned padding repeating the last value, then a final point
        stamped with the query's truncated "to" time.
        """
        client = MELCloudHomeClient()
        response = {
            "datasets": [
                {
                    "label": "REPORT.TREND_SUMMARY_REPORT.DATASET.LABELS.OUTDOOR_TEMPERATURE",
                    "data": [
                        {"x": "2026-07-28T07:14:23", "y": 25.0},
                        {"x": "2026-07-28T07:15:24", "y": 26.0},
                        {"x": "2026-07-28T08:00:00", "y": 26.0},
                        {"x": "2026-07-28T09:00:00", "y": 26.0},
                        {"x": "2026-07-28T09:02:00", "y": 26.0},
                    ],
                }
            ]
        }

        result = client._parse_outdoor_temp(response)

        assert result == (26.0, datetime(2026, 7, 28, 7, 15, 24, tzinfo=UTC))

    def test_parse_outdoor_temperature_null_value_falls_back(self):
        """A genuine-looking point with a null value falls back to older readings."""
        client = MELCloudHomeClient()
        response = {
            "datasets": [
                {
                    "label": "REPORT.TREND_SUMMARY_REPORT.DATASET.LABELS.OUTDOOR_TEMPERATURE",
                    "data": [
                        {"x": "2026-07-28T07:14:23", "y": 25.0},
                        {"x": "2026-07-28T07:15:24", "y": None},
                    ],
                }
            ]
        }

        result = client._parse_outdoor_temp(response)

        assert result == (25.0, datetime(2026, 7, 28, 7, 14, 23, tzinfo=UTC))

    def test_parse_outdoor_temperature_only_synthetic_points(self):
        """A response containing only synthetic points has no genuine reading."""
        client = MELCloudHomeClient()
        response = {
            "datasets": [
                {
                    "label": "REPORT.TREND_SUMMARY_REPORT.DATASET.LABELS.OUTDOOR_TEMPERATURE",
                    "data": [
                        {"x": "2026-07-28T08:00:00", "y": 26.0},
                        {"x": "2026-07-28T09:00:00", "y": 26.0},
                    ],
                }
            ]
        }

        result = client._parse_outdoor_temp(response)

        assert result == (None, None)

    def test_parse_outdoor_temperature_missing_dataset(self):
        """Test when outdoor temperature dataset is missing."""
        client = MELCloudHomeClient()
        response = {
            "datasets": [
                {
                    "label": "REPORT.TREND_SUMMARY_REPORT.DATASET.LABELS.ROOM_TEMPERATURE",
                    "data": [{"x": "2026-02-03T12:00:00", "y": 20.5}],
                }
            ]
        }

        result = client._parse_outdoor_temp(response)

        assert result == (None, None)

    def test_parse_outdoor_temperature_empty_data(self):
        """Test when outdoor temperature dataset exists but data array empty."""
        client = MELCloudHomeClient()
        response = {
            "datasets": [
                {
                    "label": "REPORT.TREND_SUMMARY_REPORT.DATASET.LABELS.OUTDOOR_TEMPERATURE",
                    "data": [],
                }
            ]
        }

        result = client._parse_outdoor_temp(response)

        assert result == (None, None)

    def test_parse_outdoor_temperature_list_wrapped(self):
        """Test parsing when mobile BFF wraps response in a list."""
        client = MELCloudHomeClient()
        response = [
            {
                "datasets": [
                    {
                        "label": "REPORT.TREND_SUMMARY_REPORT.DATASET.LABELS.OUTDOOR_TEMPERATURE",
                        "data": [{"x": "2026-04-12T20:00:41", "y": 14.5}],
                    }
                ]
            }
        ]

        result = client._parse_outdoor_temp(response)

        assert result == (14.5, datetime(2026, 4, 12, 20, 0, 41, tzinfo=UTC))

    def test_parse_outdoor_temperature_malformed(self):
        """Test with malformed response structure."""
        client = MELCloudHomeClient()
        response: dict[str, Any] = {}

        result = client._parse_outdoor_temp(response)

        assert result == (None, None)


@freeze_time("2026-02-03 12:30:45", real_asyncio=True)
@pytest.mark.asyncio
async def test_get_outdoor_temperature_calls_api_correctly(mocker):
    """Test that get_outdoor_temperature queries Hourly with a 7-day window.

    The "to" timestamp must be truncated to whole seconds=0 so the server's
    to-echo point is recognisable as synthetic by the parser.
    """
    client = MELCloudHomeClient()

    # Mock _api_request to capture params
    mock_request = mocker.patch.object(
        client,
        "_api_request",
        return_value={
            "datasets": [
                {
                    "label": "REPORT.TREND_SUMMARY_REPORT.DATASET.LABELS.OUTDOOR_TEMPERATURE",
                    "data": [{"x": "2026-02-03T12:00:23", "y": 12.0}],
                }
            ]
        },
    )

    result = await client.get_outdoor_temperature("test-unit-id")

    # Verify request was called with correct params
    mock_request.assert_called_once()
    call_args = mock_request.call_args
    assert call_args[0][0] == "GET"
    assert call_args[0][1] == "/report/v1/trendsummary"

    params = call_args[1]["params"]
    assert params["unitId"] == "test-unit-id"
    assert params["period"] == "Hourly"
    # Verify timestamp format (7 zeros for nanoseconds)
    assert params["from"].endswith(".0000000")
    assert params["to"].endswith(".0000000")
    # "to" is now (12:30:45) truncated to seconds=0
    to_dt = datetime.strptime(params["to"], "%Y-%m-%dT%H:%M:%S.0000000").replace(
        tzinfo=UTC
    )
    from_dt = datetime.strptime(params["from"], "%Y-%m-%dT%H:%M:%S.0000000").replace(
        tzinfo=UTC
    )
    assert to_dt == datetime(2026, 2, 3, 12, 30, 0, tzinfo=UTC)
    # 7-day window so units idle for days still return their last readings
    assert to_dt - from_dt == timedelta(days=7)

    # Verify result
    assert result == (12.0, datetime(2026, 2, 3, 12, 0, 23, tzinfo=UTC))


@pytest.mark.asyncio
async def test_get_outdoor_temperature_api_returns_none(mocker):
    """Test when API returns None."""
    client = MELCloudHomeClient()

    # Mock _api_request to return None
    mocker.patch.object(client, "_api_request", return_value=None)

    result = await client.get_outdoor_temperature("test-unit-id")

    assert result == (None, None)


@pytest.mark.asyncio
async def test_get_outdoor_temperature_propagates_exceptions(mocker):
    """Errors propagate to the caller rather than being swallowed to (None,
    None) - the coordinator needs to see them to distinguish "endpoint
    failing" from "no genuine reading yet" (both would otherwise look
    identical, undermining any diagnostic signal for issue #251-style bugs).
    The coordinator's own per-unit exception isolation (_poll_outdoor_temperature)
    is what keeps this from destabilizing the overall update.
    """
    client = MELCloudHomeClient()

    mocker.patch.object(client, "_api_request", side_effect=ValueError("API error"))

    with pytest.raises(ValueError, match="API error"):
        await client.get_outdoor_temperature("test-unit-id")


@freeze_time("2026-08-17 09:30:00", real_asyncio=True)
@pytest.mark.asyncio
async def test_get_atw_outdoor_temperature_calls_api_correctly(mocker):
    """Test that get_atw_outdoor_temperature queries Hourly with a 24h window."""
    client = MELCloudHomeClient()

    mock_request = mocker.patch.object(
        client,
        "_api_request",
        return_value={
            "datasets": [
                {
                    "label": "REPORT.TREND_SUMMARY_REPORT.DATASET.LABELS.OUTDOOR_TEMPERATURE",
                    "data": [{"x": "2026-08-17T09:00:23", "y": 16.0}],
                }
            ]
        },
    )

    result = await client.get_atw_outdoor_temperature("test-atw-unit-id")

    mock_request.assert_called_once()
    call_args = mock_request.call_args
    assert call_args[0][0] == "GET"
    assert call_args[0][1] == "/report/v1/comfort-graph"

    params = call_args[1]["params"]
    assert params["unitId"] == "test-atw-unit-id"
    assert params["period"] == "Hourly"
    to_dt = datetime.strptime(params["to"], "%Y-%m-%dT%H:%M:%S.0000000").replace(
        tzinfo=UTC
    )
    from_dt = datetime.strptime(params["from"], "%Y-%m-%dT%H:%M:%S.0000000").replace(
        tzinfo=UTC
    )
    assert to_dt == datetime(2026, 8, 17, 9, 30, 0, tzinfo=UTC)
    # 24h window: comfort-graph's Hourly period hard-fails past ~4 days back
    assert to_dt - from_dt == timedelta(hours=24)

    assert result == (16.0, datetime(2026, 8, 17, 9, 0, 23, tzinfo=UTC))


@pytest.mark.asyncio
async def test_get_atw_outdoor_temperature_propagates_exceptions(mocker):
    """Same propagation contract as get_outdoor_temperature - see that test."""
    client = MELCloudHomeClient()

    mocker.patch.object(client, "_api_request", side_effect=ValueError("API error"))

    with pytest.raises(ValueError, match="API error"):
        await client.get_atw_outdoor_temperature("test-atw-unit-id")
