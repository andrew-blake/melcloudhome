"""Pure tests for the combined-energy windows and parser (no network)."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from custom_components.melcloudhome.api.parsing import (
    energy_report_windows,
    parse_energy_report,
)

STOCKHOLM = ZoneInfo("Europe/Stockholm")

# Today's local day for Stockholm on 2026-09-24 (CEST, UTC+2), as UTC bounds.
DAY_FROM = datetime(2026, 9, 23, 22, 0, tzinfo=UTC)
DAY_TO = datetime(2026, 9, 24, 22, 0, tzinfo=UTC)


def _report(consumed: list[dict], produced: list[dict]) -> list[dict]:
    """The mobile API's real shape: a one-element list around the report."""
    return [
        {
            "reportPeriod": 1,
            "datasets": [
                {"id": "interval_energy_consumed", "data": consumed},
                {"id": "interval_energy_produced", "data": produced},
                {
                    "id": "outside_temperature",
                    "data": [{"x": "2026-09-24T06:00:00", "y": 11.5}],
                },
            ],
        }
    ]


def test_windows_normal_day() -> None:
    now = datetime(2026, 9, 25, 7, 40, tzinfo=UTC)
    assert energy_report_windows(now, STOCKHOLM) == [
        (
            datetime(2026, 9, 23, 22, 0, tzinfo=UTC),
            datetime(2026, 9, 24, 22, 0, tzinfo=UTC),
        ),
        (
            datetime(2026, 9, 24, 22, 0, tzinfo=UTC),
            datetime(2026, 9, 25, 22, 0, tzinfo=UTC),
        ),
    ]


def test_windows_autumn_day_is_25_hours() -> None:
    now = datetime(2026, 10, 25, 12, 0, tzinfo=UTC)
    _, (today_from, today_to) = energy_report_windows(now, STOCKHOLM)
    assert today_from == datetime(2026, 10, 24, 22, 0, tzinfo=UTC)
    assert today_to == datetime(2026, 10, 25, 23, 0, tzinfo=UTC)


def test_windows_spring_day_is_23_hours() -> None:
    now = datetime(2027, 3, 28, 12, 0, tzinfo=UTC)
    _, (today_from, today_to) = energy_report_windows(now, STOCKHOLM)
    assert today_from == datetime(2027, 3, 27, 23, 0, tzinfo=UTC)
    assert today_to == datetime(2027, 3, 28, 22, 0, tzinfo=UTC)


def test_windows_just_after_local_midnight() -> None:
    # 00:05 local on 25 Sep: yesterday is still 24 Sep, fetched in full.
    now = datetime(2026, 9, 24, 22, 5, tzinfo=UTC)
    (y_from, y_to), (t_from, _) = energy_report_windows(now, STOCKHOLM)
    assert (y_from, y_to) == (
        datetime(2026, 9, 23, 22, 0, tzinfo=UTC),
        datetime(2026, 9, 24, 22, 0, tzinfo=UTC),
    )
    assert t_from == datetime(2026, 9, 24, 22, 0, tzinfo=UTC)


def test_labels_become_telemetry_keys() -> None:
    result = parse_energy_report(
        _report(
            [
                {"x": "2026-09-24T06:00:00", "y": 0.1333},
                {"x": "2026-09-24T09:00:00", "y": 0.3833333333333333},
            ],
            [{"x": "2026-09-24T06:00:00", "y": 1.25}],
        ),
        STOCKHOLM,
        DAY_FROM,
        DAY_TO,
    )
    assert [p["time"] for p in result["consumed"]] == [
        "2026-09-24 04:00:00.000000000",
        "2026-09-24 07:00:00.000000000",
    ]
    assert [p["time"] for p in result["produced"]] == ["2026-09-24 04:00:00.000000000"]


def test_values_equal_telemetry_as_floats() -> None:
    # The same hour as telemetry sent it: "0.3833333333333333" (a string).
    result = parse_energy_report(
        _report([{"x": "2026-09-24T09:00:00", "y": 0.3833333333333333}], []),
        STOCKHOLM,
        DAY_FROM,
        DAY_TO,
    )
    assert float(result["consumed"][0]["value"]) == float("0.3833333333333333")


def test_int_value_parses() -> None:
    result = parse_energy_report(
        _report([{"x": "2026-09-24T09:00:00", "y": 0}], []), STOCKHOLM, DAY_FROM, DAY_TO
    )
    assert float(result["consumed"][0]["value"]) == 0.0


def test_points_outside_window_are_dropped() -> None:
    result = parse_energy_report(
        _report(
            [
                {
                    "x": "2026-09-23T23:00:00",
                    "y": 0.5,
                },  # 21:00 UTC on 23 Sep: before the window
                {
                    "x": "2026-09-24T00:00:00",
                    "y": 0.6,
                },  # 22:00 UTC: the window's first hour
                {
                    "x": "2026-09-25T00:00:00",
                    "y": 0.7,
                },  # 22:00 UTC on 24 Sep: the window's end, excluded
            ],
            [],
        ),
        STOCKHOLM,
        DAY_FROM,
        DAY_TO,
    )
    assert [p["time"] for p in result["consumed"]] == ["2026-09-23 22:00:00.000000000"]


def test_malformed_points_are_skipped() -> None:
    result = parse_energy_report(
        _report(
            [
                {"x": "not a time", "y": 0.5},
                {"y": 0.5},
                {"x": "2026-09-24T06:00:00"},
                {"x": "2026-09-24T06:00:00", "y": "abc"},
                {"x": "2026-09-24T07:00:00", "y": 0.2},
            ],
            [],
        ),
        STOCKHOLM,
        DAY_FROM,
        DAY_TO,
    )
    assert [p["time"] for p in result["consumed"]] == ["2026-09-24 05:00:00.000000000"]


def test_outside_temperature_is_ignored_and_empty_shapes_are_safe() -> None:
    assert parse_energy_report(_report([], []), STOCKHOLM, DAY_FROM, DAY_TO) == {
        "consumed": [],
        "produced": [],
    }
    assert parse_energy_report(None, STOCKHOLM, DAY_FROM, DAY_TO) == {
        "consumed": [],
        "produced": [],
    }
    assert parse_energy_report([], STOCKHOLM, DAY_FROM, DAY_TO) == {
        "consumed": [],
        "produced": [],
    }


def test_bare_object_response_parses() -> None:
    bare = _report([{"x": "2026-09-24T06:00:00", "y": 0.1}], [])[0]
    result = parse_energy_report(bare, STOCKHOLM, DAY_FROM, DAY_TO)
    assert [p["time"] for p in result["consumed"]] == ["2026-09-24 04:00:00.000000000"]
