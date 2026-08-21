"""Integration tests for outdoor temperature sensor."""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from freezegun import freeze_time
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.melcloudhome.api.parsing import Reading
from custom_components.melcloudhome.const import DOMAIN

from .conftest import (
    create_mock_ata_building,
    create_mock_ata_unit,
    create_mock_ata_user_context,
    setup_ata_integration_custom,
)

# Test device UUIDs (match mock server IDs)
LIVING_ROOM_ID = "0efc1234-5678-9abc-def0-1234567887db"  # Has outdoor sensor
BEDROOM_ID = "5b3e4321-8765-cba9-fed0-abcdef987a9b"  # No outdoor sensor
STUDY_ID = "a1b2c3d4-e5f6-7890-abcd-ef0123456789"  # Has outdoor sensor (2nd unit)
TEST_BUILDING_ID = "building-test-id"


@pytest.fixture
async def setup_integration_with_outdoor_temp(hass: HomeAssistant) -> MockConfigEntry:
    """Set up integration with two devices - one with outdoor sensor, one without."""
    living_room = create_mock_ata_unit(
        unit_id=LIVING_ROOM_ID,
        name="Living Room AC",
        has_outdoor_sensor=True,
        outdoor_temp_reading=Reading(12.0, None),
    )
    bedroom = create_mock_ata_unit(
        unit_id=BEDROOM_ID,
        name="Bedroom AC",
        has_outdoor_sensor=False,
    )
    mock_context = create_mock_ata_user_context(
        [create_mock_ata_building(units=[living_room, bedroom])]
    )

    async def mock_get_outdoor_temp(unit_id: str) -> Reading | None:
        if unit_id == LIVING_ROOM_ID:
            return Reading(12.0, datetime(2026, 2, 7, 11, 55, 0, tzinfo=UTC))
        return None

    def configure(client: Any) -> None:
        client.get_outdoor_temperature = AsyncMock(side_effect=mock_get_outdoor_temp)
        client.ata = MagicMock()
        client.ata.set_power = AsyncMock()
        client.ata.set_temperature = AsyncMock()

    entry, _ = await setup_ata_integration_custom(
        hass, mock_context, configure_client=configure
    )
    return entry


async def test_outdoor_temperature_sensor_created_when_device_has_sensor(
    hass: HomeAssistant, setup_integration_with_outdoor_temp
):
    """Test outdoor temp sensor created for device with outdoor sensor."""
    entity_id = "sensor.melcloudhome_0efc_87db_outdoor_temperature"
    state = hass.states.get(entity_id)

    assert state is not None
    assert state.state == "12.0"
    assert state.attributes["unit_of_measurement"] == "°C"
    assert state.attributes["device_class"] == "temperature"
    assert state.attributes["state_class"] == "measurement"


async def test_outdoor_temperature_sensor_exposes_last_reading(
    hass: HomeAssistant, setup_integration_with_outdoor_temp
):
    """Test last_reading attribute shows when the value was recorded.

    Units stop uploading outdoor temperature while idle (issue #171), so the
    sensor exposes the datapoint timestamp to make stale values detectable.
    """
    entity_id = "sensor.melcloudhome_0efc_87db_outdoor_temperature"
    state = hass.states.get(entity_id)

    assert state is not None
    assert state.attributes["last_reading"] == "2026-02-07T11:55:00+00:00"


async def test_outdoor_temperature_sensor_created_but_unknown_when_no_sensor(
    hass: HomeAssistant, setup_integration_with_outdoor_temp
):
    """Outdoor temp sensor is always created; a unit with no reading shows
    'unknown', not dropped."""
    entity_id = "sensor.melcloudhome_5b3e_7a9b_outdoor_temperature"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "unknown"


async def test_outdoor_temperature_updates_on_coordinator_refresh(
    hass: HomeAssistant, setup_integration_with_outdoor_temp
):
    """Test outdoor temperature value updates when coordinator refreshes."""
    entity_id = "sensor.melcloudhome_0efc_87db_outdoor_temperature"

    state_before = hass.states.get(entity_id)
    assert state_before is not None
    assert state_before.state == "12.0"

    await hass.services.async_call(DOMAIN, "force_refresh", {}, blocking=True)
    await hass.async_block_till_done()

    state_after = hass.states.get(entity_id)
    assert state_after.state == "12.0"


async def test_outdoor_temperature_created_and_unknown_when_first_poll_fails(
    hass: HomeAssistant,
):
    """A failed outdoor poll at setup must not drop the sensor: the unit is
    reachable, so it is created and shows 'unknown' until a reading arrives."""
    living_room = create_mock_ata_unit(
        unit_id=LIVING_ROOM_ID,
        name="Living Room AC",
        has_outdoor_sensor=False,
    )
    mock_context = create_mock_ata_user_context(
        [create_mock_ata_building(units=[living_room])]
    )

    def configure(client: Any) -> None:
        client.get_outdoor_temperature = AsyncMock(side_effect=Exception("API error"))
        client.ata = MagicMock()
        client.ata.set_power = AsyncMock()

    await setup_ata_integration_custom(hass, mock_context, configure_client=configure)

    entity_id = "sensor.melcloudhome_0efc_87db_outdoor_temperature"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "unknown"


@freeze_time("2026-02-07 12:00:00", real_asyncio=True)
async def test_outdoor_temperature_all_units_polled_on_refresh(
    hass: HomeAssistant,
    freezer,
):
    """Test that ALL units with outdoor sensors get polled, not just the first.

    Regression test: a shared polling timer was consumed by the first unit
    in the loop, starving all subsequent units from ever updating.
    """
    living_room = create_mock_ata_unit(
        unit_id=LIVING_ROOM_ID,
        name="Living Room AC",
        has_outdoor_sensor=True,
        outdoor_temp_reading=Reading(8.0, None),
    )
    study = create_mock_ata_unit(
        unit_id=STUDY_ID,
        name="Study AC",
        has_outdoor_sensor=True,
        outdoor_temp_reading=Reading(3.0, None),
    )
    mock_context = create_mock_ata_user_context(
        [create_mock_ata_building(units=[living_room, study])]
    )

    async def mock_get_outdoor_temp(unit_id: str) -> Reading | None:
        if unit_id == LIVING_ROOM_ID:
            return Reading(8.0, datetime(2026, 2, 7, 11, 55, 0, tzinfo=UTC))
        if unit_id == STUDY_ID:
            return Reading(3.0, datetime(2026, 2, 7, 11, 56, 0, tzinfo=UTC))
        return None

    def configure(client: Any) -> None:
        client.get_outdoor_temperature = AsyncMock(side_effect=mock_get_outdoor_temp)
        client.ata = MagicMock()
        client.ata.set_power = AsyncMock()
        client.ata.set_temperature = AsyncMock()

    entry, mock_client = await setup_ata_integration_custom(
        hass, mock_context, configure_client=configure
    )

    living_room_entity = "sensor.melcloudhome_0efc_87db_outdoor_temperature"
    study_entity = "sensor.melcloudhome_a1b2_6789_outdoor_temperature"

    state_lr = hass.states.get(living_room_entity)
    state_study = hass.states.get(study_entity)

    assert state_lr is not None, "Living Room outdoor temp sensor not created"
    assert state_study is not None, "Study outdoor temp sensor not created"
    assert state_lr.state == "8.0"
    assert state_study.state == "3.0"

    async def mock_get_outdoor_temp_updated(unit_id: str) -> Reading | None:
        if unit_id == LIVING_ROOM_ID:
            return Reading(10.0, datetime(2026, 2, 7, 12, 5, 0, tzinfo=UTC))
        if unit_id == STUDY_ID:
            return Reading(1.0, datetime(2026, 2, 7, 12, 6, 0, tzinfo=UTC))
        return None

    # mock_client is the same instance the coordinator holds — update directly
    mock_client.get_outdoor_temperature = AsyncMock(
        side_effect=mock_get_outdoor_temp_updated
    )

    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    coordinator.reset_outdoor_temp_polling()

    await hass.services.async_call(DOMAIN, "force_refresh", {}, blocking=True)
    await hass.async_block_till_done()

    state_lr = hass.states.get(living_room_entity)
    state_study = hass.states.get(study_entity)

    assert state_lr.state == "10.0", f"Living Room stuck at {state_lr.state}"
    assert state_study.state == "1.0", f"Study stuck at {state_study.state}"


async def test_idle_unit_reprobed_after_polling_interval(
    hass: HomeAssistant,
):
    """Test that a unit with no outdoor sensor found is re-probed after 30 min."""
    living_room = create_mock_ata_unit(
        unit_id=LIVING_ROOM_ID, name="Living Room AC", has_outdoor_sensor=False
    )
    mock_context = create_mock_ata_user_context(
        [create_mock_ata_building(units=[living_room])]
    )

    def configure(client: Any) -> None:
        client.get_outdoor_temperature = AsyncMock(return_value=None)
        client.ata = MagicMock()
        client.ata.set_power = AsyncMock()

    entry, mock_client = await setup_ata_integration_custom(
        hass, mock_context, configure_client=configure
    )

    # Outdoor temp entities use should_create_fn at setup time and are not
    # dynamically added on coordinator updates — the coordinator model is the
    # only observable outcome of a re-probe short of an entry reload.
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    unit = coordinator.get_ata_device(LIVING_ROOM_ID)
    assert unit is not None
    assert unit.has_outdoor_temp_sensor is False
    assert unit.outdoor_temp_reading is None

    mock_client.get_outdoor_temperature = AsyncMock(
        return_value=Reading(15.0, datetime(2026, 2, 7, 12, 0, 0, tzinfo=UTC))
    )
    coordinator.reset_outdoor_temp_polling()

    await hass.services.async_call(DOMAIN, "force_refresh", {}, blocking=True)
    await hass.async_block_till_done()

    unit = coordinator.get_ata_device(LIVING_ROOM_ID)
    assert unit.has_outdoor_temp_sensor is True, (
        "Unit should have outdoor sensor flag set after re-probe"
    )
    assert unit.outdoor_temp_reading.value == 15.0, (
        f"Expected 15.0°C after re-probe, got {unit.outdoor_temp_reading}"
    )
