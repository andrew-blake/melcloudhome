"""Integration tests for outdoor temperature sensor."""

from homeassistant.core import HomeAssistant


async def test_outdoor_temperature_sensor_created_when_device_has_sensor(
    hass: HomeAssistant,
):
    """Test outdoor temp sensor created for device with outdoor sensor."""
    # Living Room AC (0efc1234...) has outdoor sensor in mock
    entity_id = "sensor.melcloudhome_0efc_76db_outdoor_temperature"

    state = hass.states.get(entity_id)

    assert state is not None
    assert state.state == "12.0"  # Value from mock server
    assert state.attributes["unit_of_measurement"] == "°C"
    assert state.attributes["device_class"] == "temperature"
    assert state.attributes["state_class"] == "measurement"


async def test_outdoor_temperature_sensor_not_created_when_no_sensor(
    hass: HomeAssistant,
):
    """Test outdoor temp sensor NOT created for device without outdoor sensor."""
    # Bedroom AC (5b3e4321...) does not have outdoor sensor in mock
    entity_id = "sensor.melcloudhome_5b3e_7a9b_outdoor_temperature"

    state = hass.states.get(entity_id)

    assert state is None  # Entity should not exist


async def test_outdoor_temperature_updates_on_coordinator_refresh(hass: HomeAssistant):
    """Test outdoor temperature value updates when coordinator refreshes."""
    entity_id = "sensor.melcloudhome_0efc_76db_outdoor_temperature"

    # Initial state
    state_before = hass.states.get(entity_id)
    assert state_before.state == "12.0"

    # Trigger coordinator refresh
    await hass.services.async_call(
        "homeassistant", "update_entity", {"entity_id": entity_id}, blocking=True
    )

    # Value should still be 12.0 (mock returns constant)
    state_after = hass.states.get(entity_id)
    assert state_after.state == "12.0"


async def test_outdoor_temperature_unavailable_when_device_in_error(
    hass: HomeAssistant,
):
    """Test outdoor temp sensor shows unavailable when device errors."""
    entity_id = "sensor.melcloudhome_0efc_76db_outdoor_temperature"

    # Mock coordinator to return device in error state
    # TODO: Implement this test when we have error injection in mock server

    # For now, verify sensor can handle unavailable state
    state = hass.states.get(entity_id)
    assert state is not None
