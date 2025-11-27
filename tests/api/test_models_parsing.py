"""Tests for MELCloud Home API models parsing and normalization.

Tests focus on edge cases in helper functions that could cause real bugs:
- Type coercion (str → bool/float)
- None/empty value handling
- Numeric string → word mappings
- British/American spelling normalization

Avoids theatre: Only tests non-trivial logic with real edge cases.
"""

from custom_components.melcloudhome.api.models import AirToAirUnit


class TestBooleanParsing:
    """Test parse_bool helper edge cases."""

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
