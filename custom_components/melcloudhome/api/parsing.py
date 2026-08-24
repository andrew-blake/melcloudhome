"""Shared parsing utilities for MELCloud Home API models.

These utilities handle the conversion of API string values to Python types.
The API returns many values as strings (e.g., "True", "20.5") that need
proper type conversion.
"""

from datetime import UTC, datetime, tzinfo
from typing import NamedTuple


def parse_bool(value: str | bool | None) -> bool:
    """Parse boolean from API string value.

    API returns booleans as string "True"/"False". This helper converts
    them to Python bool, handling edge cases.

    Args:
        value: String "True"/"False", bool, or None

    Returns:
        Parsed boolean (False if None)
    """
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).lower() == "true"


def parse_float(value: str | float | None) -> float | None:
    """Parse float from API string value.

    API returns numbers as strings. This helper converts them to float,
    handling edge cases like empty strings and invalid values.

    Args:
        value: String number, float, empty string, or None

    Returns:
        Parsed float or None if unparsable
    """
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def parse_int(value: str | int | None) -> int | None:
    """Parse int from API string value.

    API sometimes returns integers as strings (e.g., HasZone2="0").
    This helper converts them to int, handling edge cases.

    Args:
        value: String number, int, empty string, or None

    Returns:
        Parsed int or None if unparsable
    """
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def parse_api_timestamp(value: str, tz: tzinfo = UTC) -> datetime:
    """Parse an API timestamp into a UTC-aware datetime.

    MELCloud sends naive stamps in the *unit's own* local time, not UTC. Passing
    the unit's timezone is therefore how a report reading gets a correct age;
    `tz` defaults to UTC so a caller that has no timezone behaves as before
    (measured 2026-08-24, see docs/api/atw-api-reference.md). An offset that IS
    present is converted rather than overwritten, which would shift a
    user-visible last_reading.

    ponytail: a naive stamp inside a DST autumn fold is ambiguous and resolves
    to fold=0, so one hour twice a year can be an hour out. Disambiguating
    needs the neighbouring points' ordering; not worth it for a reading age.

    Raises ValueError on an unparsable value, same as fromisoformat.
    """
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=tz).astimezone(UTC)
    return parsed.astimezone(UTC)


class Reading(NamedTuple):
    """A measured value with the time the unit actually recorded it.

    Sensors fed by slow-cadence polls can hold a value for hours after their
    upstream stops updating, and HA's own timestamps cannot show it: an
    identical rewrite advances only last_reported (issue #200, ADR-022).
    """

    value: float
    recorded_at: datetime
