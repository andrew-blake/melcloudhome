"""parse_api_timestamp interprets naive report stamps in the unit's timezone.

The /report/v1/ endpoints stamp points in the unit's own local time, not UTC
(measured 2026-08-24; see _claude/BACKLOG.md). These tests pin the conversion,
and pin the UTC default so a caller that has no zone keeps today's behaviour.
"""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from custom_components.melcloudhome.api.parsing import parse_api_timestamp


def test_naive_stamp_is_interpreted_in_the_given_timezone():
    # Europe/Stockholm is UTC+2 in August (CEST).
    result = parse_api_timestamp("2026-08-24T09:59:22", ZoneInfo("Europe/Stockholm"))
    assert result == datetime(2026, 8, 24, 7, 59, 22, tzinfo=UTC)


def test_naive_stamp_defaults_to_utc():
    # The default is the no-zone-known fallback: a unit whose /context omits
    # timeZone must keep behaving exactly as it does today, not shift silently.
    result = parse_api_timestamp("2026-08-24T09:59:22")
    assert result == datetime(2026, 8, 24, 9, 59, 22, tzinfo=UTC)


def test_london_offset_applied():
    # Europe/London is UTC+1 in August (BST).
    result = parse_api_timestamp("2026-08-24T08:21:14", ZoneInfo("Europe/London"))
    assert result == datetime(2026, 8, 24, 7, 21, 14, tzinfo=UTC)


def test_aware_stamp_ignores_the_timezone_argument():
    result = parse_api_timestamp(
        "2026-08-24T09:59:22+00:00", ZoneInfo("Europe/Stockholm")
    )
    assert result == datetime(2026, 8, 24, 9, 59, 22, tzinfo=UTC)


def test_seconds_survive_conversion():
    # _latest_genuine_reading rejects points with second == 0 as synthetic, so
    # the conversion must not disturb the seconds field.
    result = parse_api_timestamp("2026-08-23T21:41:16", ZoneInfo("Europe/Stockholm"))
    assert result.second == 16
