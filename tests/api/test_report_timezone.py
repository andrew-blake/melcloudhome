"""Report requests and parsing use the unit's timezone, defaulting to UTC.

The server compares our naive `to` string against locally-stamped rows, so a
UTC `to` silently truncates the most recent offset-hours of data (measured
2026-08-24 with a to-shift sweep; see _claude/BACKLOG.md). These tests pin both
the request side and the parse side, and pin the UTC default.
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from freezegun import freeze_time

from custom_components.melcloudhome.api.client import MELCloudHomeClient

UNIT = "ec56aa3b-94ec-433d-9fb9-49b9d6b86442"
STOCKHOLM = ZoneInfo("Europe/Stockholm")


@pytest.fixture
def client() -> MELCloudHomeClient:
    return MELCloudHomeClient()


@freeze_time("2026-08-24 08:00:00")
def test_report_params_declare_utc_explicitly(client):
    # Without the Z the server reads these as unit-local and truncates the
    # newest offset-hours of data. With it, the server converts.
    params = client._report_params(UNIT, timedelta(hours=8))
    assert params["to"] == "2026-08-24T08:00:00.0000000Z"
    assert params["from"] == "2026-08-24T00:00:00.0000000Z"


@freeze_time("2026-08-24 08:00:00")
def test_report_params_still_truncate_seconds(client):
    # The to-echo point is identified by second == 0, so `to` must stay
    # seconds-aligned.
    params = client._report_params(UNIT, timedelta(hours=8))
    assert params["to"].endswith(":00.0000000Z")


def test_latest_genuine_reading_converts_from_the_unit_timezone(client):
    data = [
        {"x": "2026-08-24T09:00:00", "y": 17.5},  # synthetic: second == 0
        {"x": "2026-08-24T09:46:15", "y": 22.0},  # genuine
    ]
    reading = client._latest_genuine_reading(data, STOCKHOLM)
    assert reading is not None
    assert reading.value == 22.0
    assert reading.recorded_at == datetime(2026, 8, 24, 7, 46, 15, tzinfo=UTC)


def test_latest_genuine_reading_defaults_to_utc(client):
    data = [{"x": "2026-08-24T09:46:15", "y": 22.0}]
    reading = client._latest_genuine_reading(data)
    assert reading is not None
    assert reading.recorded_at == datetime(2026, 8, 24, 9, 46, 15, tzinfo=UTC)


def test_parse_outdoor_temp_converts_from_the_unit_timezone(client):
    response = [
        {
            "datasets": [
                {
                    "label": "REPORT.TREND_SUMMARY_REPORT.DATASET.LABELS.OUTDOOR_TEMPERATURE",
                    "data": [
                        {"x": "2026-08-24T08:00:00", "y": 16},  # synthetic
                        {"x": "2026-08-24T08:21:14", "y": 15},  # genuine
                    ],
                }
            ]
        }
    ]
    reading = client._parse_outdoor_temp(response, ZoneInfo("Europe/London"))
    assert reading is not None
    assert reading.value == 15
    # Europe/London is UTC+1 in August.
    assert reading.recorded_at == datetime(2026, 8, 24, 7, 21, 14, tzinfo=UTC)
