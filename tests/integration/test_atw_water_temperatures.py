"""Tests for ATW water temperatures fed by report/v1/internaltemperatures.

One request per unit returns every measure as a dataset, so these cover what
the tracker keeps from it: the capability filter, per-unit failure isolation,
and the zone-2 warning (ADR-023).

Reference: docs/testing-best-practices.md
Run with: make test-integration
"""

import logging
from datetime import UTC, datetime, timedelta, tzinfo
from typing import Any
from unittest.mock import AsyncMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.melcloudhome.api.parsing import Reading
from custom_components.melcloudhome.const import CONF_ENABLE_WEBSOCKET

from .conftest import (
    create_mock_atw_building,
    create_mock_atw_unit,
    create_mock_atw_user_context,
    setup_atw_integration_custom,
)

SECOND_UNIT_ID = "22221234-5678-9abc-def0-123456789999"

STAMP = datetime(2026, 8, 22, 14, 12, 16, tzinfo=UTC)

BASE_PAIR = {
    "flow_temperature": Reading(45.2, STAMP),
    "return_temperature": Reading(41.8, STAMP),
}
ZONE_SUFFIXED = {
    "flow_temperature_zone1": Reading(44.0, STAMP),
    "return_temperature_zone1": Reading(40.5, STAMP),
    "flow_temperature_zone2": Reading(38.0, STAMP),
    "return_temperature_zone2": Reading(35.0, STAMP),
}
# The report serves datasets for hardware the unit lacks as a constant 25
PLACEHOLDERS = {
    "flow_temperature_boiler": Reading(25.0, STAMP),
    "return_temperature_boiler": Reading(25.0, STAMP),
}


def _entity(unit_suffix: str, measure: str) -> str:
    return f"sensor.melcloudhome_{unit_suffix}_{measure}"


async def _setup(hass: HomeAssistant, units: list, readings) -> Any:
    """Set up ATW units whose water-temp fetch returns/raises `readings`."""

    def configure_client(mock_client: AsyncMock) -> None:
        # An exception or a per-unit callable both belong on side_effect
        if isinstance(readings, BaseException) or callable(readings):
            mock_client.get_atw_water_temperatures = AsyncMock(side_effect=readings)
        else:
            mock_client.get_atw_water_temperatures = AsyncMock(return_value=readings)

    _, mock_client = await setup_atw_integration_custom(
        hass,
        create_mock_atw_user_context([create_mock_atw_building(units=units)]),
        configure_client=configure_client,
        options={CONF_ENABLE_WEBSOCKET: False},
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    return mock_client


@pytest.mark.asyncio
async def test_readings_land_on_their_own_entities(hass: HomeAssistant) -> None:
    """Dataset ids are the measure names, so dispatch is an identity mapping."""
    await _setup(hass, [create_mock_atw_unit()], BASE_PAIR)

    assert (
        float(hass.states.get(_entity("0efc_9abc", "flow_temperature")).state) == 45.2
    )
    assert (
        float(hass.states.get(_entity("0efc_9abc", "return_temperature")).state) == 41.8
    )


@pytest.mark.asyncio
async def test_placeholders_for_absent_hardware_reach_no_entity(
    hass: HomeAssistant,
) -> None:
    """The 25s the report always sends are dropped by the capability filter.

    A single-zone boilerless unit gets ten datasets and keeps two. #266's
    creation gating means the boiler entities do not exist at all; this asserts
    the filter as well, so a future gating change cannot let a 25 through.
    """
    await _setup(hass, [create_mock_atw_unit()], BASE_PAIR | PLACEHOLDERS)

    assert hass.states.get(_entity("0efc_9abc", "flow_temperature_boiler")) is None
    for state in hass.states.async_all("sensor"):
        assert state.state != "25.0", f"{state.entity_id} took a placeholder"


@pytest.mark.asyncio
async def test_one_unit_failing_leaves_its_sibling_alone(hass: HomeAssistant) -> None:
    """Per-unit isolation: one unit's failure is one unit's failure.

    Blast radius grew with batching - a failure now costs every measure for
    that unit's cycle - so the boundary that still has to hold is the unit.
    """
    calls: list[str] = []

    async def per_unit(unit_id: str, tz: tzinfo = UTC) -> dict[str, Reading]:
        calls.append(unit_id)
        if unit_id == SECOND_UNIT_ID:
            raise OSError("endpoint down")
        return BASE_PAIR

    await _setup(
        hass,
        [
            create_mock_atw_unit(),
            create_mock_atw_unit(unit_id=SECOND_UNIT_ID, name="Second ATW"),
        ],
        per_unit,
    )

    assert len(calls) == 2, "both units must be polled"
    assert (
        float(hass.states.get(_entity("0efc_9abc", "flow_temperature")).state) == 45.2
    )
    assert hass.states.get(_entity("2222_9999", "flow_temperature")).state == "unknown"


@pytest.mark.asyncio
async def test_zone2_unit_gets_its_zone2_readings(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """A two-zone unit keeps the suffixed measures, and nothing warns.

    This is the assumption holding. The zone-1 pair comes with it: on a
    two-zone system those datasets are real, and the unsuffixed pair is the
    whole-system flow and return.
    """
    caplog.set_level(logging.WARNING)

    await _setup(
        hass, [create_mock_atw_unit(has_zone2=True)], BASE_PAIR | ZONE_SUFFIXED
    )

    for measure, expected in (
        ("flow_temperature_zone_1", 44.0),
        ("flow_temperature_zone_2", 38.0),
        ("return_temperature_zone_2", 35.0),
    ):
        assert float(hass.states.get(_entity("0efc_9abc", measure)).state) == expected

    assert not [
        record for record in caplog.records if "no zone-2 datasets" in record.message
    ]


@pytest.mark.asyncio
async def test_missing_zone2_datasets_warn_once_per_unit(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """The zone-2 assumption's only named safety net.

    Zone-2 datasets have never been observed on this endpoint, so shipping them
    for a two-zone unit is an assumption (ADR-023). If it is wrong the sensors
    read unknown; this warning names the cause, once per unit per run rather
    than once an hour forever.
    """
    caplog.set_level(logging.WARNING)

    mock_client = await _setup(hass, [create_mock_atw_unit(has_zone2=True)], BASE_PAIR)

    warnings = [
        record for record in caplog.records if "no zone-2 datasets" in record.message
    ]
    assert len(warnings) == 1
    assert warnings[0].levelno == logging.WARNING

    assert hass.states.get(_entity("0efc_9abc", "flow_temperature_zone_2")).state == (
        "unknown"
    )

    # A second poll must not repeat it
    mock_client.get_atw_water_temperatures = AsyncMock(return_value=BASE_PAIR)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=61))
    await hass.async_block_till_done(wait_background_tasks=True)

    warnings = [
        record for record in caplog.records if "no zone-2 datasets" in record.message
    ]
    assert len(warnings) == 1, "the warning must not repeat every poll"


@pytest.mark.asyncio
async def test_single_zone_unit_never_warns(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """No zone 2, no warning - the response is correct for that hardware."""
    caplog.set_level(logging.WARNING)

    await _setup(hass, [create_mock_atw_unit()], BASE_PAIR)

    assert not [
        record for record in caplog.records if "no zone-2 datasets" in record.message
    ]
