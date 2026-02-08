"""Tests for outdoor temperature API client methods."""

from typing import Any

import pytest

from custom_components.melcloudhome.api.client import MELCloudHomeClient


class TestParseOutdoorTemp:
    """Tests for _parse_outdoor_temp method."""

    def test_parse_outdoor_temperature_success(self):
        """Test parsing outdoor temperature from valid response."""
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
                        {"x": "2026-02-03T11:00:00", "y": 11.0},
                        {"x": "2026-02-03T12:00:00", "y": 12.0},
                    ],
                },
            ]
        }

        result = client._parse_outdoor_temp(response)

        assert result == 12.0  # Latest value

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

        assert result is None

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

        assert result is None

    def test_parse_outdoor_temperature_malformed(self):
        """Test with malformed response structure."""
        client = MELCloudHomeClient()
        response: dict[str, Any] = {}

        result = client._parse_outdoor_temp(response)

        assert result is None


@pytest.mark.asyncio
async def test_get_outdoor_temperature_calls_api_correctly(mocker):
    """Test that get_outdoor_temperature calls API with correct parameters."""
    client = MELCloudHomeClient()

    # Mock _api_request to capture params
    mock_request = mocker.patch.object(
        client,
        "_api_request",
        return_value={
            "datasets": [
                {
                    "label": "REPORT.TREND_SUMMARY_REPORT.DATASET.LABELS.OUTDOOR_TEMPERATURE",
                    "data": [{"x": "2026-02-03T12:00:00", "y": 12.0}],
                }
            ]
        },
    )

    result = await client.get_outdoor_temperature("test-unit-id")

    # Verify request was called with correct params
    mock_request.assert_called_once()
    call_args = mock_request.call_args
    assert call_args[0][0] == "GET"
    assert call_args[0][1] == "/api/report/trendsummary"

    params = call_args[1]["params"]
    assert params["unitId"] == "test-unit-id"
    # Verify timestamp format (7 zeros for nanoseconds)
    assert params["from"].endswith(".0000000")
    assert params["to"].endswith(".0000000")

    # Verify result
    assert result == 12.0


@pytest.mark.asyncio
async def test_get_outdoor_temperature_api_returns_none(mocker):
    """Test when API returns None."""
    client = MELCloudHomeClient()

    # Mock _api_request to return None
    mocker.patch.object(client, "_api_request", return_value=None)

    result = await client.get_outdoor_temperature("test-unit-id")

    assert result is None


@pytest.mark.asyncio
async def test_get_outdoor_temperature_exception_handling(mocker):
    """Test exception handling returns None and logs debug."""
    client = MELCloudHomeClient()

    # Mock _api_request to raise an exception
    mocker.patch.object(client, "_api_request", side_effect=Exception("API error"))

    result = await client.get_outdoor_temperature("test-unit-id")

    # Should return None on exception, not raise
    assert result is None
