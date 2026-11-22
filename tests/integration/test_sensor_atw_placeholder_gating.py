"""Tests that ATW telemetry sensors for absent hardware are not created.

MELCloud returns a constant 25 for the zone-1-suffixed and boiler-circuit
telemetry measures on devices that lack that hardware, rather than an error or an
empty series. Those sensors are therefore gated on capabilities: the zone-1 pair
on `has_zone2` (on a single-zone system the unsuffixed flow/return IS zone 1) and
the boiler pair on `has_boiler`.

Reference: docs/testing-best-practices.md
Run with: make test-integration
"""

import pytest
from homeassistant.core import HomeAssistant

from .conftest import (
    create_mock_atw_building,
    create_mock_atw_unit,
    create_mock_atw_user_context,
    entity_id_for,
    find_entity_id,
    setup_atw_integration_custom,
)

ZONE1_FLOW = ("sensor", "0efc1234-5678-9abc-def0-123456789abc_flow_temperature_zone1")
ZONE1_RETURN = (
    "sensor",
    "0efc1234-5678-9abc-def0-123456789abc_return_temperature_zone1",
)
BOILER_FLOW = ("sensor", "0efc1234-5678-9abc-def0-123456789abc_flow_temperature_boiler")
BOILER_RETURN = (
    "sensor",
    "0efc1234-5678-9abc-def0-123456789abc_return_temperature_boiler",
)
PLAIN_FLOW = ("sensor", "0efc1234-5678-9abc-def0-123456789abc_flow_temperature")
PLAIN_RETURN = ("sensor", "0efc1234-5678-9abc-def0-123456789abc_return_temperature")


async def _setup(hass: HomeAssistant, **unit_kwargs) -> None:
    context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[create_mock_atw_unit(**unit_kwargs)])]
    )
    await setup_atw_integration_custom(hass, context)


@pytest.mark.asyncio
async def test_single_zone_no_boiler_gets_neither_pair(hass: HomeAssistant) -> None:
    """A single-zone, boilerless device gets only the unsuffixed flow/return."""
    await _setup(hass)

    assert hass.states.get(entity_id_for(hass, PLAIN_FLOW)) is not None
    assert hass.states.get(entity_id_for(hass, PLAIN_RETURN)) is not None
    for key in (ZONE1_FLOW, ZONE1_RETURN, BOILER_FLOW, BOILER_RETURN):
        assert find_entity_id(hass, key) is None, f"{key} should not exist"


@pytest.mark.asyncio
async def test_zone2_device_gets_the_zone1_pair(hass: HomeAssistant) -> None:
    """With a second zone the zone-1-suffixed measures carry real readings."""
    await _setup(hass, has_zone2=True)

    assert hass.states.get(entity_id_for(hass, ZONE1_FLOW)) is not None
    assert hass.states.get(entity_id_for(hass, ZONE1_RETURN)) is not None
    # Still no boiler on this device.
    assert find_entity_id(hass, BOILER_FLOW) is None
    assert find_entity_id(hass, BOILER_RETURN) is None


@pytest.mark.asyncio
async def test_boiler_device_gets_the_boiler_pair(hass: HomeAssistant) -> None:
    """A device reporting hasBoiler keeps its boiler-circuit sensors."""
    await _setup(hass, has_boiler=True)

    assert hass.states.get(entity_id_for(hass, BOILER_FLOW)) is not None
    assert hass.states.get(entity_id_for(hass, BOILER_RETURN)) is not None
    # Single zone, so no zone-1-suffixed pair.
    assert find_entity_id(hass, ZONE1_FLOW) is None
    assert find_entity_id(hass, ZONE1_RETURN) is None
