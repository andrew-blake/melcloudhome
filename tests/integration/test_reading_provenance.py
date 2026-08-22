"""Tests for reading provenance on slow-cadence ATW telemetry sensors (issue #200).

A telemetry sensor holds its last value for as long as the poll keeps failing,
and HA's own timestamps cannot show it - an identical rewrite advances only
`last_reported`, which records our write, not the unit's reading. These tests
cover the `last_reading` attribute that does.

Reference: docs/testing-best-practices.md
Run with: make test-integration
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.melcloudhome.const import CONF_ENABLE_WEBSOCKET
from custom_components.melcloudhome.sensor_ata import ATA_SENSOR_TYPES
from custom_components.melcloudhome.sensor_atw import ATW_SENSOR_TYPES

from .conftest import (
    create_mock_atw_building,
    create_mock_atw_unit,
    create_mock_atw_user_context,
    setup_atw_integration_custom,
)

FLOW_TEMP_ENTITY_ID = "sensor.melcloudhome_0efc_9abc_flow_temperature"

# Wall-clock format the telemetry endpoint uses: naive, 9 fractional digits.
API_TIME_FORMAT = "%Y-%m-%d %H:%M:%S.%f000"


def _telemetry_response(*points: dict[str, Any]) -> dict[str, Any]:
    """Build a /telemetry/telemetry/actual response body."""
    return {"measureData": [{"values": list(points)}]}


def _expected_last_reading(api_time: str) -> str:
    """The attribute value a given API timestamp should surface as."""
    return datetime.fromisoformat(api_time).replace(tzinfo=UTC).isoformat()


async def _setup_with_telemetry(
    hass: HomeAssistant, response: dict[str, Any] | None
) -> Any:
    """Set up a single-zone ATW device whose telemetry poll returns `response`.

    The first telemetry fetch runs as a background task (ADR-021), so it needs
    wait_background_tasks - and that in turn needs the WebSocket listener off,
    since its reconnect loop never finishes.
    """

    def configure_client(mock_client: AsyncMock) -> None:
        mock_client.get_telemetry_actual = AsyncMock(return_value=response)

    _, mock_client = await setup_atw_integration_custom(
        hass,
        create_mock_atw_user_context(
            [create_mock_atw_building(units=[create_mock_atw_unit()])]
        ),
        configure_client=configure_client,
        options={CONF_ENABLE_WEBSOCKET: False},
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    return mock_client


@pytest.mark.asyncio
async def test_successful_poll_reports_an_hours_old_datapoint(
    hass: HomeAssistant,
) -> None:
    """A poll can succeed and still return data recorded hours ago.

    This is the prod symptom (issue #200): the endpoint answers, the sensor
    takes the value, and nothing in the entity state says the reading is old.
    """
    stamp = (dt_util.utcnow() - timedelta(hours=3)).strftime(API_TIME_FORMAT)
    await _setup_with_telemetry(
        hass, _telemetry_response({"time": stamp, "value": 41.5})
    )

    state = hass.states.get(FLOW_TEMP_ENTITY_ID)
    assert state is not None
    assert float(state.state) == 41.5
    assert state.attributes["last_reading"] == _expected_last_reading(stamp)

    age = dt_util.utcnow() - datetime.fromisoformat(state.attributes["last_reading"])
    assert age > timedelta(hours=2, minutes=55), (
        "last_reading must expose the reading's real age, not the fetch time"
    )


@pytest.mark.asyncio
async def test_last_reading_is_the_payload_time_not_now(hass: HomeAssistant) -> None:
    """last_reading comes from the datapoint, never from the clock.

    Stamping it with utcnow() would make every sensor look permanently fresh,
    which is the exact failure this attribute exists to expose.
    """
    await _setup_with_telemetry(
        hass,
        _telemetry_response({"time": "2026-01-14 12:48:44.047000000", "value": 38.0}),
    )

    state = hass.states.get(FLOW_TEMP_ENTITY_ID)
    assert state is not None
    assert state.attributes["last_reading"] == "2026-01-14T12:48:44.047000+00:00"


@pytest.mark.asyncio
async def test_failed_poll_keeps_the_previous_reading_unrestamped(
    hass: HomeAssistant,
) -> None:
    """A failed poll must not restamp the value it carries forward.

    The tracker returns without writing on failure, so the sensor keeps its
    value; the point of last_reading is that the stamp keeps standing still
    while it does.
    """
    stamp = "2026-01-14 12:48:44.047000000"
    mock_client = await _setup_with_telemetry(
        hass, _telemetry_response({"time": stamp, "value": 38.0})
    )
    assert hass.states.get(FLOW_TEMP_ENTITY_ID).attributes[
        "last_reading"
    ] == _expected_last_reading(stamp)

    mock_client.get_telemetry_actual = AsyncMock(side_effect=OSError("endpoint down"))
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=61))
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(FLOW_TEMP_ENTITY_ID)
    assert state is not None
    assert float(state.state) == 38.0
    assert state.attributes["last_reading"] == _expected_last_reading(stamp)


@pytest.mark.asyncio
async def test_newest_datapoint_is_chosen_by_timestamp_not_position(
    hass: HomeAssistant,
) -> None:
    """Trust the datapoints' own stamps over the response ordering."""
    newest = "2026-01-14 13:02:43.927000000"
    await _setup_with_telemetry(
        hass,
        _telemetry_response(
            {"time": "2026-01-14 12:48:44.047000000", "value": 30.0},
            {"time": newest, "value": 44.0},
            {"time": "2026-01-14 12:58:43.944000000", "value": 35.0},
        ),
    )

    state = hass.states.get(FLOW_TEMP_ENTITY_ID)
    assert state is not None
    assert float(state.state) == 44.0
    assert state.attributes["last_reading"] == _expected_last_reading(newest)


@pytest.mark.asyncio
async def test_datapoint_without_a_time_keeps_the_value(hass: HomeAssistant) -> None:
    """A value with no usable time is still the freshest thing we have.

    Dropping it would silently hold an older value instead, so it is taken
    with no provenance.
    """
    await _setup_with_telemetry(hass, _telemetry_response({"value": 39.5}))

    state = hass.states.get(FLOW_TEMP_ENTITY_ID)
    assert state is not None
    assert float(state.state) == 39.5
    assert state.attributes["last_reading"] is None


@pytest.mark.asyncio
async def test_last_reading_present_but_null_before_any_reading(
    hass: HomeAssistant,
) -> None:
    """The key exists from the start so templates can rely on it."""
    await _setup_with_telemetry(hass, None)

    state = hass.states.get(FLOW_TEMP_ENTITY_ID)
    assert state is not None
    assert state.state == "unknown"
    assert "last_reading" in state.attributes
    assert state.attributes["last_reading"] is None


@pytest.mark.parametrize("description", ATA_SENSOR_TYPES + ATW_SENSOR_TYPES)
def test_exactly_one_value_accessor(description: Any) -> None:
    """Every sensor reads its state from exactly one accessor.

    Enforced here rather than as an import-time assert: a bare assert is
    stripped under -O, and if it ever fired it would take the whole sensor
    platform down on a user's install.
    """
    assert (description.value_fn is None) != (description.reading_fn is None), (
        f"{description.key}: set exactly one of value_fn/reading_fn"
    )
