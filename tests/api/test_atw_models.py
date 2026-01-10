"""Tests for Air-to-Water (ATW) heat pump models.

Phase 1: Model parsing tests (TDD approach using HAR file fixtures).
These tests validate that models correctly parse real API responses.
"""

import logging
from typing import Any, cast

from custom_components.melcloudhome.api.models import Building, UserContext
from custom_components.melcloudhome.api.models_atw import (
    AirToWaterCapabilities,
    AirToWaterUnit,
)

from .fixtures.atw_fixtures import (
    ATW_UNIT_ERROR,
    ATW_UNIT_HALF_DEGREES,
    ATW_UNIT_HEATING_DHW,
    ATW_UNIT_HEATING_ZONE,
    ATW_UNIT_IDLE,
    ATW_UNIT_WITH_ZONE2,
    USER_CONTEXT_MIXED_UNITS,
    USER_CONTEXT_MULTIPLE_ATW_UNITS,
    USER_CONTEXT_NO_ATW_UNITS,
    USER_CONTEXT_SINGLE_ATW_UNIT,
)

# =============================================================================
# AirToWaterCapabilities Tests
# =============================================================================


class TestAirToWaterCapabilities:
    """Tests for AirToWaterCapabilities model."""

    def test_capabilities_from_dict_with_all_fields(self) -> None:
        """Test parsing capabilities with all fields present."""
        caps_data = cast(dict[str, Any], ATW_UNIT_HEATING_ZONE["capabilities"])

        caps = AirToWaterCapabilities.from_dict(caps_data)

        assert caps.has_hot_water is True
        assert caps.ftc_model == 3
        assert caps.has_zone2 is False
        assert caps.has_demand_side_control is True

    def test_capabilities_from_dict_with_missing_fields_uses_defaults(self) -> None:
        """Test that missing fields use default values."""
        caps_data: dict[str, Any] = {}

        caps = AirToWaterCapabilities.from_dict(caps_data)

        # Should use defaults
        assert caps.has_hot_water is True
        assert caps.ftc_model == 3
        assert caps.has_demand_side_control is True

    def test_capabilities_always_uses_safe_temperature_defaults(self) -> None:
        """Test that temperature ranges ALWAYS use hardcoded safe defaults.

        CRITICAL: API-reported ranges are unreliable. We ALWAYS use:
        - Zone: 10-30°C
        - DHW: 40-60°C
        """
        # Simulate API bug: inverted ranges
        caps_data = {
            "minSetTankTemperature": 0,  # Wrong
            "maxSetTankTemperature": 60,
            "minSetTemperature": 30,  # Wrong (inverted)
            "maxSetTemperature": 50,  # Wrong (inverted)
        }

        caps = AirToWaterCapabilities.from_dict(caps_data)

        # Should use HARDCODED safe defaults, NOT API values
        assert caps.min_set_tank_temperature == 40.0
        assert caps.max_set_tank_temperature == 60.0
        assert caps.min_set_temperature == 10.0
        assert caps.max_set_temperature == 30.0

    def test_capabilities_logs_warning_when_api_values_differ(self, caplog) -> None:
        """Test that capability parsing logs warning when overriding API values."""
        caps_data = {
            "minSetTankTemperature": 0,  # Different from safe default
            "maxSetTankTemperature": 60,
            "minSetTemperature": 30,  # Different from safe default
            "maxSetTemperature": 50,
        }

        with caplog.at_level(logging.DEBUG):
            _caps = AirToWaterCapabilities.from_dict(caps_data)

        # Should log when overriding
        log_messages = [record.message for record in caplog.records]
        assert any("DHW range" in msg and "safe default" in msg for msg in log_messages)
        assert any(
            "Zone range" in msg and "safe default" in msg for msg in log_messages
        )

    def test_capabilities_from_empty_dict_returns_defaults(self) -> None:
        """Test that empty dict returns default capabilities."""
        caps = AirToWaterCapabilities.from_dict({})

        # Safe defaults
        assert caps.min_set_tank_temperature == 40.0
        assert caps.max_set_tank_temperature == 60.0
        assert caps.min_set_temperature == 10.0
        assert caps.max_set_temperature == 30.0

        # Default flags
        assert caps.has_hot_water is True
        assert caps.ftc_model == 3


# =============================================================================
# AirToWaterUnit Tests
# =============================================================================


class TestAirToWaterUnit:
    """Tests for AirToWaterUnit model."""

    def test_unit_from_dict_parses_all_fields(self) -> None:
        """Test that unit parsing extracts all top-level fields."""
        unit = AirToWaterUnit.from_dict(ATW_UNIT_HEATING_DHW)

        # Identity
        assert unit.id == "unit-001"
        assert unit.name == "Heat pump"

        # Device info
        assert unit.ftc_model == 3
        assert unit.rssi == -45

        # Status
        assert unit.power is True
        assert unit.in_standby_mode is False

    def test_unit_from_dict_parses_settings_array(self) -> None:
        """Test that settings array is correctly parsed into typed fields."""
        unit = AirToWaterUnit.from_dict(ATW_UNIT_HEATING_DHW)

        # Settings array should be parsed and converted
        assert unit.power is True
        assert unit.operation_status == "HotWater"
        assert unit.operation_mode_zone1 == "HeatCurve"
        assert unit.forced_hot_water_mode is True

    def test_unit_from_dict_converts_string_booleans(self) -> None:
        """Test that string "True"/"False" are converted to bool."""
        unit = AirToWaterUnit.from_dict(ATW_UNIT_HEATING_DHW)

        # API returns string "True"/"False"
        assert isinstance(unit.power, bool)
        assert isinstance(unit.in_standby_mode, bool)
        assert isinstance(unit.forced_hot_water_mode, bool)
        assert isinstance(unit.is_in_error, bool)

        assert unit.power is True
        assert unit.in_standby_mode is False
        assert unit.forced_hot_water_mode is True
        assert unit.is_in_error is False

    def test_unit_from_dict_converts_string_floats(self) -> None:
        """Test that string numbers are converted to float."""
        unit = AirToWaterUnit.from_dict(ATW_UNIT_HEATING_DHW)

        # API returns string "20.5", "31", etc.
        assert isinstance(unit.room_temperature_zone1, float)
        assert isinstance(unit.set_temperature_zone1, float)
        assert isinstance(unit.tank_water_temperature, float)
        assert isinstance(unit.set_tank_water_temperature, float)

        assert unit.room_temperature_zone1 == 20.5
        assert unit.set_temperature_zone1 == 31.0
        assert unit.tank_water_temperature == 29.0
        assert unit.set_tank_water_temperature == 60.0

    def test_unit_from_dict_handles_missing_optional_fields(self) -> None:
        """Test that missing optional fields are handled gracefully."""
        minimal_unit = {
            "id": "unit-minimal",
            "givenDisplayName": "Minimal",
            "ftcModel": 3,
            "settings": [
                {"name": "Power", "value": "True"},
                {"name": "OperationMode", "value": "Stop"},
            ],
            "capabilities": {},
        }

        unit = AirToWaterUnit.from_dict(minimal_unit)

        # Should not raise, should use None for missing fields
        assert unit.id == "unit-minimal"
        assert unit.room_temperature_zone1 is None
        assert unit.set_temperature_zone1 is None

    def test_unit_from_dict_parses_zone2_when_present(self):
        """Test that Zone 2 fields are parsed when HasZone2=1."""
        unit = AirToWaterUnit.from_dict(ATW_UNIT_WITH_ZONE2)

        assert unit.has_zone2 is True
        assert unit.operation_mode_zone2 == "HeatRoomTemperature"
        assert unit.room_temperature_zone2 == 19.0
        assert unit.set_temperature_zone2 == 20.0

    def test_unit_from_dict_parses_zone2_when_absent(self):
        """Test that Zone 2 fields are None when HasZone2=0."""
        unit = AirToWaterUnit.from_dict(ATW_UNIT_HEATING_DHW)

        assert unit.has_zone2 is False
        assert unit.operation_mode_zone2 is None
        assert unit.room_temperature_zone2 is None
        assert unit.set_temperature_zone2 is None

    def test_unit_from_dict_parses_holiday_mode(self) -> None:
        """Test that holiday mode is parsed correctly."""
        unit = AirToWaterUnit.from_dict(ATW_UNIT_HEATING_DHW)

        # Holiday mode present but disabled
        assert unit.holiday_mode_enabled is False

    def test_unit_from_dict_parses_frost_protection(self) -> None:
        """Test that frost protection is parsed correctly."""
        unit = AirToWaterUnit.from_dict(ATW_UNIT_HEATING_DHW)

        # Frost protection is None in fixture
        assert unit.frost_protection_enabled is False

    def test_unit_from_dict_handles_error_state(self) -> None:
        """Test that error state is parsed correctly."""
        unit = AirToWaterUnit.from_dict(ATW_UNIT_ERROR)

        assert unit.is_in_error is True
        assert unit.error_code == "E4"

    def test_operation_status_vs_operation_mode_zone1_distinct(self):
        """Test that operation_status (API: OperationMode) is distinct from operation_mode_zone1.

        CRITICAL: These are DIFFERENT fields with DIFFERENT meanings:
        - operation_status: WHAT the 3-way valve is doing RIGHT NOW (read-only)
        - operation_mode_zone1: HOW to heat the zone (control setting)
        """
        unit = AirToWaterUnit.from_dict(ATW_UNIT_HEATING_DHW)

        # API has OperationMode="HotWater" (status)
        # API has OperationModeZone1="HeatCurve" (control)
        assert unit.operation_status == "HotWater"
        assert unit.operation_mode_zone1 == "HeatCurve"
        assert unit.operation_status != unit.operation_mode_zone1

    def test_unit_parses_capabilities_with_safe_defaults(self) -> None:
        """Test that unit's capabilities use safe temperature defaults."""
        unit = AirToWaterUnit.from_dict(ATW_UNIT_HEATING_DHW)

        # Even though API has wrong ranges, capabilities should use safe defaults
        assert unit.capabilities.min_set_tank_temperature == 40.0
        assert unit.capabilities.max_set_tank_temperature == 60.0
        assert unit.capabilities.min_set_temperature == 10.0
        assert unit.capabilities.max_set_temperature == 30.0


# =============================================================================
# Building Tests
# =============================================================================


class TestBuilding:
    """Tests for Building model with ATW support."""

    def test_building_parses_both_a2a_and_a2w_units(self):
        """Test that Building parses both A2A and A2W units."""
        building_data = cast(dict[str, Any], USER_CONTEXT_MIXED_UNITS["buildings"][0])

        building = Building.from_dict(building_data)

        assert len(building.air_to_air_units) == 1
        assert len(building.air_to_water_units) == 1
        assert building.air_to_air_units[0].id == "a2a-001"
        assert building.air_to_water_units[0].id == "unit-002"

    def test_building_handles_no_atw_units(self) -> None:
        """Test that Building handles empty ATW units list."""
        building_data = cast(dict[str, Any], USER_CONTEXT_NO_ATW_UNITS["buildings"][0])

        building = Building.from_dict(building_data)

        assert len(building.air_to_air_units) == 1
        assert len(building.air_to_water_units) == 0


# =============================================================================
# UserContext Tests
# =============================================================================


class TestUserContext:
    """Tests for UserContext with ATW support."""

    def test_user_context_get_all_air_to_water_units(self) -> None:
        """Test that get_all_air_to_water_units returns flat list of all ATW units."""
        context = UserContext.from_dict(USER_CONTEXT_MULTIPLE_ATW_UNITS)

        atw_units = context.get_all_air_to_water_units()

        # Should have 3 units across 2 buildings
        assert len(atw_units) == 3
        unit_ids = {unit.id for unit in atw_units}
        assert unit_ids == {"unit-002", "unit-004", "unit-003"}

    def test_user_context_get_air_to_water_unit_by_id(self) -> None:
        """Test that get_air_to_water_unit_by_id finds specific unit."""
        context = UserContext.from_dict(USER_CONTEXT_SINGLE_ATW_UNIT)

        unit = context.get_air_to_water_unit_by_id("unit-001")

        assert unit is not None
        assert unit.id == "unit-001"
        assert unit.name == "Heat pump"

    def test_user_context_get_air_to_water_unit_by_id_not_found(self) -> None:
        """Test that get_air_to_water_unit_by_id returns None for unknown ID."""
        context = UserContext.from_dict(USER_CONTEXT_SINGLE_ATW_UNIT)

        unit = context.get_air_to_water_unit_by_id("unknown-id")

        assert unit is None

    def test_user_context_handles_no_atw_units(self) -> None:
        """Test that UserContext handles empty ATW units gracefully."""
        context = UserContext.from_dict(USER_CONTEXT_NO_ATW_UNITS)

        atw_units = context.get_all_air_to_water_units()

        assert len(atw_units) == 0

    def test_user_context_with_mixed_units(self) -> None:
        """Test that UserContext handles both A2A and A2W units."""
        context = UserContext.from_dict(USER_CONTEXT_MIXED_UNITS)

        a2a_units = context.get_all_air_to_air_units()
        a2w_units = context.get_all_air_to_water_units()

        assert len(a2a_units) == 1
        assert len(a2w_units) == 1


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_settings_array(self) -> None:
        """Test that empty settings array is handled."""
        unit_data = {
            "id": "unit-empty",
            "givenDisplayName": "Empty",
            "ftcModel": 3,
            "settings": [],  # Empty
            "capabilities": {},
        }

        unit = AirToWaterUnit.from_dict(unit_data)

        # Should use defaults for missing settings
        assert unit.id == "unit-empty"
        assert unit.power is False  # Default
        assert unit.operation_status == "Stop"  # Default

    def test_empty_string_converts_to_none(self) -> None:
        """Test that empty strings are converted to None."""
        # ErrorCode is empty string in IDLE fixture
        unit_idle = AirToWaterUnit.from_dict(ATW_UNIT_IDLE)
        assert unit_idle.error_code is None

    def test_string_zero_converts_to_false_for_haszone2(self):
        """Test that string "0" for HasZone2 converts to False."""
        unit = AirToWaterUnit.from_dict(ATW_UNIT_HEATING_DHW)

        # HasZone2 is "0" (string)
        assert unit.has_zone2 is False

    def test_string_one_converts_to_true_for_haszone2(self):
        """Test that string "1" for HasZone2 converts to True."""
        unit = AirToWaterUnit.from_dict(ATW_UNIT_WITH_ZONE2)

        # HasZone2 is "1" (string)
        assert unit.has_zone2 is True

    def test_half_degree_temperatures(self) -> None:
        """Test that half-degree temperatures are parsed correctly."""
        unit = AirToWaterUnit.from_dict(ATW_UNIT_HALF_DEGREES)

        assert unit.room_temperature_zone1 == 21.5
        assert unit.set_temperature_zone1 == 22.5
        assert unit.capabilities.has_half_degrees is True


# =============================================================================
# API Bug Validation Tests
# =============================================================================


class TestAPIBugValidation:
    """Tests that validate known API bugs are handled correctly."""

    def test_api_bug_inverted_temperature_ranges(self) -> None:
        """Test that inverted API temperature ranges are corrected.

        Known bug: API sometimes reports minSetTemperature=30, maxSetTemperature=50
        which is backwards for underfloor heating (should be 10-30).
        """
        # This is the ACTUAL data from HAR file with the bug
        unit = AirToWaterUnit.from_dict(ATW_UNIT_HEATING_DHW)

        # Capabilities should use SAFE DEFAULTS, not buggy API values
        assert unit.capabilities.min_set_temperature == 10.0
        assert unit.capabilities.max_set_temperature == 30.0

    def test_api_bug_zero_min_tank_temperature(self) -> None:
        """Test that zero minSetTankTemperature is corrected to 40°C."""
        unit = AirToWaterUnit.from_dict(ATW_UNIT_HEATING_DHW)

        # API reports 0, we use 40
        assert unit.capabilities.min_set_tank_temperature == 40.0
