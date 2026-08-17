"""Integration tests for ATW outdoor temperature sensor.

ATW's live /context OutdoorTemperature can be silently wrong (issue #251) or
absent, with no way to tell which from the value alone, so outdoor
temperature is sourced exclusively from the coordinator's comfort-graph poll -
mirroring how ATA's outdoor temperature is sourced exclusively from
trendsummary. See tests/integration/test_outdoor_temperature_sensor.py for
the ATA equivalent this mirrors.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant

from custom_components.melcloudhome.const import DOMAIN

from .conftest import (
    create_mock_atw_building,
    create_mock_atw_unit,
    create_mock_atw_user_context,
    setup_atw_integration_custom,
)

ENTITY_ID = "sensor.melcloudhome_0efc_9abc_outdoor_temperature"


async def test_atw_outdoor_temperature_sensor_shows_polled_value(
    hass: HomeAssistant,
) -> None:
    """Sensor shows the comfort-graph poll result, not any live-context value."""
    mock_unit = create_mock_atw_unit()
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )

    def configure(client: Any) -> None:
        client.get_atw_outdoor_temperature = AsyncMock(
            return_value=(16.0, datetime(2026, 8, 17, 8, 57, 11, tzinfo=UTC))
        )

    await setup_atw_integration_custom(hass, mock_context, configure_client=configure)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "16.0"
    assert state.attributes["last_reading"] == "2026-08-17T08:57:11+00:00"
    assert state.attributes["unit_of_measurement"] == "°C"
    assert state.attributes["device_class"] == "temperature"


async def test_atw_outdoor_temperature_unknown_when_poll_returns_none(
    hass: HomeAssistant,
) -> None:
    """Sensor is always created; shows 'unknown' when the poll finds nothing,
    never a stale/wrong live-context value."""
    mock_unit = create_mock_atw_unit()
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )

    def configure(client: Any) -> None:
        client.get_atw_outdoor_temperature = AsyncMock(return_value=(None, None))

    await setup_atw_integration_custom(hass, mock_context, configure_client=configure)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "unknown"


async def test_atw_outdoor_temperature_updates_on_coordinator_refresh(
    hass: HomeAssistant,
) -> None:
    """Value updates when the coordinator's next poll returns a new reading."""
    mock_unit = create_mock_atw_unit()
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )

    def configure(client: Any) -> None:
        client.get_atw_outdoor_temperature = AsyncMock(
            return_value=(16.0, datetime(2026, 8, 17, 8, 57, 11, tzinfo=UTC))
        )

    entry, mock_client = await setup_atw_integration_custom(
        hass, mock_context, configure_client=configure
    )

    assert hass.states.get(ENTITY_ID).state == "16.0"

    mock_client.get_atw_outdoor_temperature = AsyncMock(
        return_value=(14.0, datetime(2026, 8, 17, 9, 27, 11, tzinfo=UTC))
    )
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    coordinator.reset_outdoor_temp_polling()

    await hass.services.async_call(DOMAIN, "force_refresh", {}, blocking=True)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == "14.0"
    assert state.attributes["last_reading"] == "2026-08-17T09:27:11+00:00"
