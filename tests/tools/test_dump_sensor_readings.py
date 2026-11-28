"""Tests for tools/dump_sensor_readings.py --redact.

Run with: make test-api
"""

from tools.dump_sensor_readings import redacted_keys

SERIAL = "melcloudhome_a1b2_9abc"


def test_key_is_serial_and_device_class() -> None:
    rows = [("sensor.living_room_ac_wifi_signal", "signal_strength", SERIAL)]
    assert redacted_keys(rows) == {
        "sensor.living_room_ac_wifi_signal": f"sensor.{SERIAL}_signal_strength"
    }


def test_user_label_never_reaches_the_key() -> None:
    """HA 2026.11 shape: a user-renamed entity shows "{device} {label}".

    The friendly name and entity ID can both carry the label, so neither is used.
    """
    rows = [
        ("sensor.gran_s_outdoor_temp", "temperature", SERIAL),
        ("sensor.living_room_ac_room_temperature", "temperature", SERIAL),
    ]
    keys = redacted_keys(rows)
    assert not any("gran" in key or "living" in key for key in keys.values())
    assert sorted(keys.values()) == [
        f"sensor.{SERIAL}_temperature_1",
        f"sensor.{SERIAL}_temperature_2",
    ]


def test_device_without_serial_uses_the_short_id_in_its_old_id() -> None:
    rows = [
        ("sensor.my_home_melcloudhome_a1b2_9abc_energy", "energy", None),
        ("sensor.lounge", None, None),
    ]
    assert redacted_keys(rows) == {
        "sensor.my_home_melcloudhome_a1b2_9abc_energy": f"sensor.{SERIAL}_energy",
        "sensor.lounge": "sensor.redacted_sensor",
    }
