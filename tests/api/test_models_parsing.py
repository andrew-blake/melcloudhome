"""Tests for MELCloud Home API models parsing and normalization.

Tests focus on edge cases in helper functions that could cause real bugs:
- Type coercion (str → bool/float)
- None/empty value handling
- Numeric string → word mappings
- British/American spelling normalization

Avoids theatre: Only tests non-trivial logic with real edge cases.
"""

from typing import Any

from custom_components.melcloudhome.api.models_ata import AirToAirUnit
from custom_components.melcloudhome.api.parsing import (
    parse_bool,
    parse_int,
)


class TestParsingUtilities:
    """Test parsing utility functions directly (covers missing lines)."""

    def test_parse_bool_with_bool_input(self) -> None:
        """Test parse_bool passes through bool values unchanged (line 22)."""
        assert parse_bool(True) is True
        assert parse_bool(False) is False

    def test_parse_int_with_none(self) -> None:
        """Test parse_int handles None (line 60)."""
        assert parse_int(None) is None

    def test_parse_int_with_empty_string(self) -> None:
        """Test parse_int handles empty string (line 60)."""
        assert parse_int("") is None

    def test_parse_int_with_valid_string(self) -> None:
        """Test parse_int converts valid strings."""
        assert parse_int("42") == 42
        assert parse_int("0") == 0
        assert parse_int("-5") == -5

    def test_parse_int_with_invalid_string(self) -> None:
        """Test parse_int handles invalid strings (lines 62-65)."""
        assert parse_int("invalid") is None
        assert parse_int("12.5") is None  # Not an int
        assert parse_int("abc123") is None

    def test_parse_int_with_int_input(self) -> None:
        """Test parse_int handles int input directly."""
        assert parse_int(42) == 42
        assert parse_int(0) == 0


class TestBooleanParsing:
    """Test parse_bool helper edge cases via model integration."""

    def test_parse_bool_handles_none_as_false(self) -> None:
        """Test that None values are parsed as False (defensive programming)."""
        # Create unit with Power=None in settings
        data = {
            "id": "test-unit",
            "givenDisplayName": "Test",
            "settings": [{"name": "Power", "value": None}],
            "capabilities": {},
            "schedule": [],
        }
        unit = AirToAirUnit.from_dict(data)
        assert unit.power is False

    def test_parse_bool_handles_string_true_case_insensitive(self) -> None:
        """Test that 'true' in any case is parsed correctly."""
        test_cases = ["true", "True", "TRUE", "TrUe"]
        for value in test_cases:
            data = {
                "id": "test-unit",
                "givenDisplayName": "Test",
                "settings": [{"name": "Power", "value": value}],
                "capabilities": {},
                "schedule": [],
            }
            unit = AirToAirUnit.from_dict(data)
            assert unit.power is True, f"Failed for value: {value}"

    def test_parse_bool_non_true_strings_return_false(self) -> None:
        """Test that non-'true' strings return False."""
        test_cases = ["false", "False", "0", "1", "yes", "no", ""]
        for value in test_cases:
            data = {
                "id": "test-unit",
                "givenDisplayName": "Test",
                "settings": [{"name": "Power", "value": value}],
                "capabilities": {},
                "schedule": [],
            }
            unit = AirToAirUnit.from_dict(data)
            assert unit.power is False, f"Failed for value: {value}"


class TestErrorCodeParsing:
    """Test ErrorCode setting parsing on ATA units."""

    def test_error_code_parsed_when_present(self) -> None:
        """Test that a non-empty ErrorCode is exposed on the unit."""
        data = {
            "id": "test-unit",
            "givenDisplayName": "Test",
            "settings": [
                {"name": "IsInError", "value": "True"},
                {"name": "ErrorCode", "value": "E6"},
            ],
            "capabilities": {},
            "schedule": [],
        }
        unit = AirToAirUnit.from_dict(data)
        assert unit.is_in_error is True
        assert unit.error_code == "E6"

    def test_error_code_empty_string_becomes_none(self) -> None:
        """Test that an empty ErrorCode (no error) is normalized to None."""
        data = {
            "id": "test-unit",
            "givenDisplayName": "Test",
            "settings": [
                {"name": "IsInError", "value": "False"},
                {"name": "ErrorCode", "value": ""},
            ],
            "capabilities": {},
            "schedule": [],
        }
        unit = AirToAirUnit.from_dict(data)
        assert unit.error_code is None

    def test_error_code_missing_becomes_none(self) -> None:
        """Test that a missing ErrorCode setting is normalized to None."""
        data = {
            "id": "test-unit",
            "givenDisplayName": "Test",
            "settings": [],
            "capabilities": {},
            "schedule": [],
        }
        unit = AirToAirUnit.from_dict(data)
        assert unit.error_code is None


class TestFloatParsing:
    """Test parse_float helper edge cases."""

    def test_parse_float_handles_none(self) -> None:
        """Test that None values return None."""
        data = {
            "id": "test-unit",
            "givenDisplayName": "Test",
            "settings": [{"name": "RoomTemperature", "value": None}],
            "capabilities": {},
            "schedule": [],
        }
        unit = AirToAirUnit.from_dict(data)
        assert unit.room_temperature is None

    def test_parse_float_handles_empty_string(self) -> None:
        """Test that empty strings return None."""
        data = {
            "id": "test-unit",
            "givenDisplayName": "Test",
            "settings": [{"name": "RoomTemperature", "value": ""}],
            "capabilities": {},
            "schedule": [],
        }
        unit = AirToAirUnit.from_dict(data)
        assert unit.room_temperature is None

    def test_parse_float_handles_invalid_string(self) -> None:
        """Test that non-numeric strings return None gracefully."""
        data = {
            "id": "test-unit",
            "givenDisplayName": "Test",
            "settings": [{"name": "RoomTemperature", "value": "invalid"}],
            "capabilities": {},
            "schedule": [],
        }
        unit = AirToAirUnit.from_dict(data)
        assert unit.room_temperature is None

    def test_parse_float_converts_valid_string(self) -> None:
        """Test that valid numeric strings are converted."""
        data = {
            "id": "test-unit",
            "givenDisplayName": "Test",
            "settings": [{"name": "RoomTemperature", "value": "20.5"}],
            "capabilities": {},
            "schedule": [],
        }
        unit = AirToAirUnit.from_dict(data)
        assert unit.room_temperature == 20.5


class TestFanSpeedNormalization:
    """Test normalize_fan_speed mapping edge cases."""

    def test_fan_speed_numeric_to_word_mapping(self) -> None:
        """Test that numeric strings are mapped to word strings."""
        mappings = {
            "0": "Auto",
            "1": "One",
            "2": "Two",
            "3": "Three",
            "4": "Four",
            "5": "Five",
        }
        for numeric, expected_word in mappings.items():
            data = {
                "id": "test-unit",
                "givenDisplayName": "Test",
                "settings": [{"name": "SetFanSpeed", "value": numeric}],
                "capabilities": {},
                "schedule": [],
            }
            unit = AirToAirUnit.from_dict(data)
            assert unit.set_fan_speed == expected_word

    def test_fan_speed_word_passthrough(self) -> None:
        """Test that word strings pass through unchanged."""
        for word in ["Auto", "One", "Two", "Three", "Four", "Five"]:
            data = {
                "id": "test-unit",
                "givenDisplayName": "Test",
                "settings": [{"name": "SetFanSpeed", "value": word}],
                "capabilities": {},
                "schedule": [],
            }
            unit = AirToAirUnit.from_dict(data)
            assert unit.set_fan_speed == word

    def test_fan_speed_unknown_value_passthrough(self) -> None:
        """Test that unknown values pass through unchanged (defensive)."""
        data = {
            "id": "test-unit",
            "givenDisplayName": "Test",
            "settings": [{"name": "SetFanSpeed", "value": "UnknownSpeed"}],
            "capabilities": {},
            "schedule": [],
        }
        unit = AirToAirUnit.from_dict(data)
        assert unit.set_fan_speed == "UnknownSpeed"


class TestVaneNormalization:
    """Test vane direction normalization edge cases."""

    def test_vertical_vane_numeric_to_word_mapping(self) -> None:
        """Test vertical vane numeric string mapping."""
        mappings = {
            "0": "Auto",
            "7": "Swing",
            "1": "One",
            "2": "Two",
            "3": "Three",
            "4": "Four",
            "5": "Five",
        }
        for numeric, expected_word in mappings.items():
            data = {
                "id": "test-unit",
                "givenDisplayName": "Test",
                "settings": [{"name": "VaneVerticalDirection", "value": numeric}],
                "capabilities": {},
                "schedule": [],
            }
            unit = AirToAirUnit.from_dict(data)
            assert unit.vane_vertical_direction == expected_word

    def test_horizontal_vane_american_to_british_spelling(self) -> None:
        """Test American → British spelling conversion (real API variance)."""
        mappings = {
            "CenterLeft": "LeftCentre",
            "Center": "Centre",
            "CenterRight": "RightCentre",
        }
        for american, british in mappings.items():
            data = {
                "id": "test-unit",
                "givenDisplayName": "Test",
                "settings": [{"name": "VaneHorizontalDirection", "value": american}],
                "capabilities": {},
                "schedule": [],
            }
            unit = AirToAirUnit.from_dict(data)
            assert unit.vane_horizontal_direction == british

    def test_horizontal_vane_british_spelling_passthrough(self) -> None:
        """Test that British spellings pass through unchanged."""
        for british in [
            "Auto",
            "Swing",
            "Left",
            "LeftCentre",
            "Centre",
            "RightCentre",
            "Right",
        ]:
            data = {
                "id": "test-unit",
                "givenDisplayName": "Test",
                "settings": [{"name": "VaneHorizontalDirection", "value": british}],
                "capabilities": {},
                "schedule": [],
            }
            unit = AirToAirUnit.from_dict(data)
            assert unit.vane_horizontal_direction == british


class TestCapabilitiesEdgeCases:
    """Test DeviceCapabilities parsing edge cases."""

    def test_capabilities_empty_dict_returns_defaults(self) -> None:
        """Test that empty capabilities dict returns safe defaults."""
        data = {
            "id": "test-unit",
            "givenDisplayName": "Test",
            "settings": [],
            "capabilities": {},  # Empty capabilities
            "schedule": [],
        }
        unit = AirToAirUnit.from_dict(data)
        # Should not crash, should have sensible defaults
        assert unit.capabilities is not None
        assert isinstance(unit.capabilities.has_energy_consumed_meter, bool)

    def test_capabilities_missing_returns_defaults(self) -> None:
        """Test that missing capabilities key returns safe defaults."""
        data = {
            "id": "test-unit",
            "givenDisplayName": "Test",
            "settings": [],
            # capabilities key missing entirely
            "schedule": [],
        }
        unit = AirToAirUnit.from_dict(data)
        assert unit.capabilities is not None


class TestProtectionModeParsing:
    """Test frostProtection/overheatProtection/holidayMode parsing on ATA units.

    These are top-level keys on the unit dict (siblings of "settings" and
    "capabilities"), not entries in the settings name-value array.
    """

    def _base_data(self, **top_level: Any) -> dict[str, Any]:
        return {
            "id": "test-unit",
            "givenDisplayName": "Test",
            "settings": [],
            "capabilities": {},
            "schedule": [],
            **top_level,
        }

    def test_frost_protection_parsed_when_configured(self) -> None:
        """Test a fully-populated frostProtection object is parsed."""
        data = self._base_data(
            frostProtection={"enabled": True, "active": False, "min": 10, "max": 12}
        )
        unit = AirToAirUnit.from_dict(data)
        assert unit.frost_protection is not None
        assert unit.frost_protection.enabled is True
        assert unit.frost_protection.active is False
        assert unit.frost_protection.min == 10.0
        assert unit.frost_protection.max == 12.0

    def test_overheat_protection_parsed_when_configured(self) -> None:
        """Test a fully-populated overheatProtection object is parsed."""
        data = self._base_data(
            overheatProtection={"enabled": True, "active": True, "min": 35, "max": 37}
        )
        unit = AirToAirUnit.from_dict(data)
        assert unit.overheat_protection is not None
        assert unit.overheat_protection.enabled is True
        assert unit.overheat_protection.active is True
        assert unit.overheat_protection.min == 35.0
        assert unit.overheat_protection.max == 37.0

    def test_holiday_mode_parsed_with_dates(self) -> None:
        """Test holidayMode parses startDate/endDate instead of min/max."""
        data = self._base_data(
            holidayMode={
                "enabled": True,
                "active": False,
                "startDate": "2026-07-20T18:30:53.79",
                "endDate": "2026-07-22T12:00:00",
            }
        )
        unit = AirToAirUnit.from_dict(data)
        assert unit.holiday_mode is not None
        assert unit.holiday_mode.enabled is True
        assert unit.holiday_mode.start_date == "2026-07-20T18:30:53.79"
        assert unit.holiday_mode.end_date == "2026-07-22T12:00:00"

    def test_protection_modes_null_when_never_configured(self) -> None:
        """Test that a null value (never configured) becomes None, not an empty object."""
        data = self._base_data(
            frostProtection=None, overheatProtection=None, holidayMode=None
        )
        unit = AirToAirUnit.from_dict(data)
        assert unit.frost_protection is None
        assert unit.overheat_protection is None
        assert unit.holiday_mode is None

    def test_protection_modes_missing_keys_become_none(self) -> None:
        """Test that entirely absent keys also normalize to None."""
        data = self._base_data()
        unit = AirToAirUnit.from_dict(data)
        assert unit.frost_protection is None
        assert unit.overheat_protection is None
        assert unit.holiday_mode is None
