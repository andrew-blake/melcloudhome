"""Shared parsing utilities for MELCloud Home API models.

These utilities handle the conversion of API string values to Python types.
The API returns many values as strings (e.g., "True", "20.5") that need
proper type conversion.
"""

import logging
from datetime import UTC, datetime, timedelta, tzinfo
from itertools import pairwise
from typing import Any, NamedTuple

_LOGGER = logging.getLogger(__name__)


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
    needs the neighbouring points' ordering; not worth it for a reading age,
    and accepted for ATW energy keys too (at most about one hour a year lost,
    never double-counted, ADR-027).

    Raises ValueError on an unparsable value, same as fromisoformat.
    """
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=tz).astimezone(UTC)
    return parsed.astimezone(UTC)


_ENERGY_DATASETS = {
    "interval_energy_consumed": "consumed",
    "interval_energy_produced": "produced",
}
# Byte-identical to the telemetry endpoint's hour labels, so stored hour_values
# stay valid whichever endpoint produced them (ADR-027).
_ENERGY_HOUR_KEY_FORMAT = "%Y-%m-%d %H:%M:%S.000000000"


def energy_report_windows(now: datetime, tz: tzinfo) -> list[tuple[datetime, datetime]]:
    """Return yesterday's and today's local days in `tz` as UTC [from, to) bounds.

    Built by wall-clock arithmetic, so a clock-change day is 25 or 23 hours.
    Never widen a window past one local day: a two-day combined-energy
    request adds a fake point at the internal local midnight (ADR-027).
    """
    today = now.astimezone(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    days = (today - timedelta(days=1), today, today + timedelta(days=1))
    return list(pairwise(d.astimezone(UTC) for d in days))


def parse_energy_report(
    response: Any, tz: tzinfo, from_utc: datetime, to_utc: datetime
) -> dict[str, list[dict[str, str]]]:
    """Turn a combined-energy response into telemetry-shaped hour values.

    Labels are the unit's local hour starts (ADR-022); each becomes the UTC key
    the telemetry endpoint used for the same hour, so the base tracker's stored
    hour_values carry on unchanged (ADR-027). Points outside [from_utc, to_utc)
    are dropped as boundary artefacts, and a malformed point is skipped rather
    than costing the whole day.
    """
    result: dict[str, list[dict[str, str]]] = {"consumed": [], "produced": []}
    report = response[0] if isinstance(response, list) and response else response
    if not isinstance(report, dict):
        return result
    for dataset in report.get("datasets") or []:
        measure = (
            _ENERGY_DATASETS.get(dataset.get("id") or "")
            if isinstance(dataset, dict)
            else None
        )
        if measure is None:
            continue
        for point in dataset.get("data") or []:
            try:
                hour = parse_api_timestamp(str(point["x"]), tz)
                value = float(point["y"])
            except (KeyError, TypeError, ValueError, OverflowError):
                _LOGGER.debug("Skipping malformed energy report point: %r", point)
                continue
            if from_utc <= hour < to_utc:
                result[measure].append(
                    {
                        "time": hour.strftime(_ENERGY_HOUR_KEY_FORMAT),
                        "value": str(value),
                    }
                )
    return result


def strip_line_breaks(value: object) -> str:
    """Flatten CR/LF out of a server-supplied string.

    Applied to every name and value the API hands us that can reach a log line
    or a Home Assistant entity name. A device name is chosen by whoever owns the
    device in the MELCloud app, and on a shared building that is somebody else's
    account, so a name carrying CR/LF could forge log lines in a reader's own
    log (CWE-117) - which matters most when that log is being read to diagnose a
    fault, or pasted into an issue.

    Covers the separators `str.splitlines()` honours, not just CR/LF, because a
    browser log viewer or log shipper splits on those too. Every one becomes a
    space rather than vanishing: the same string is a Home Assistant device
    name, where dropping a character would silently corrupt what a user sees.

    Unconditional and written as a chain on purpose: CodeQL's `py/log-injection`
    recognizes a helper as a barrier only when every path through it strips, and
    it matches chained `.replace()` calls, so a branch or a loop here would
    silently stop this working for every caller.
    """
    return (
        str(value)
        .replace("\r\n", " ")
        .replace("\n", " ")
        .replace("\r", " ")
        .replace("\u2028", " ")
        .replace("\u2029", " ")
        .replace("\x85", " ")
    )


class Reading(NamedTuple):
    """A measured value with the time the unit actually recorded it.

    Sensors fed by slow-cadence polls can hold a value for hours after their
    upstream stops updating, and HA's own timestamps cannot show it: an
    identical rewrite advances only last_reported (issue #200, ADR-022).
    """

    value: float
    recorded_at: datetime
