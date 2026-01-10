"""Shared parsing utilities for MELCloud Home API models.

These utilities handle the conversion of API string values to Python types.
The API returns many values as strings (e.g., "True", "20.5") that need
proper type conversion.
"""


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
