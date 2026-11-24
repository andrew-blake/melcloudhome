"""Tests for tools/dump_sensor_readings.py --redact.

Run with: make test-api
"""

from tools.dump_sensor_readings import redact_entity_id

SERIAL = "melcloudhome_a1b2_9abc"


def test_new_install_id_is_keyed_like_diagnostics() -> None:
    """HA-native ID: serial number plus the entity's own name, no device name."""
    assert (
        redact_entity_id(
            "sensor.living_room_ac_room_temperature",
            "Living Room AC Room temperature",
            SERIAL,
            "Living Room AC",
        )
        == f"sensor.{SERIAL}_room_temperature"
    )


def test_labelled_device_drops_the_label() -> None:
    assert (
        redact_entity_id(
            "sensor.my_home_my_home_living_room_ac_energy",
            "My Home Living Room AC Energy",
            SERIAL,
            "My Home Living Room AC",
        )
        == f"sensor.{SERIAL}_energy"
    )


def test_renamed_entity_prints_no_name() -> None:
    redacted = redact_entity_id(
        "sensor.granny_flat", "Granny Flat", SERIAL, "Living Room AC"
    )
    assert redacted == f"sensor.{SERIAL}_renamed"


def test_device_without_serial_keeps_the_marker_rule() -> None:
    """Devices from before the serial number: keep the short ID in the ID."""
    assert (
        redact_entity_id(
            "sensor.my_home_melcloudhome_a1b2_9abc_energy", "x", None, "My Home AC"
        )
        == f"sensor.{SERIAL}_energy"
    )
    assert redact_entity_id("sensor.lounge", "Lounge", None, "x") == "sensor.redacted"
