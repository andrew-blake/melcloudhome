"""Tests for outdoor temperature in ATA data model."""

from custom_components.melcloudhome.api.models_ata import AirToAirUnit


def test_air_to_air_unit_has_outdoor_temperature_field():
    """Test that AirToAirUnit has outdoor_temperature field with default None."""
    # Minimal data for AirToAirUnit.from_dict
    data = {
        "id": "test-unit-id",
        "givenDisplayName": "Test Unit",
        "settings": [],
        "capabilities": {},
    }

    unit = AirToAirUnit.from_dict(data)

    assert hasattr(unit, "outdoor_temperature")
    assert unit.outdoor_temperature is None


def test_air_to_air_unit_has_outdoor_temp_sensor_field():
    """Test that AirToAirUnit has has_outdoor_temp_sensor flag."""
    data = {
        "id": "test-unit-id",
        "givenDisplayName": "Test Unit",
        "settings": [],
        "capabilities": {},
    }

    unit = AirToAirUnit.from_dict(data)

    assert hasattr(unit, "has_outdoor_temp_sensor")
    assert unit.has_outdoor_temp_sensor is False
