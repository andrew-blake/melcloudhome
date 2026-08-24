"""The integration passes each unit's own timezone to the report endpoints.

Tested through hass.states only: a reading whose naive stamp is in the unit's
zone must surface as a UTC last_reading shifted by that zone's offset. Asserting
on the client call would be testing our mock, not the integration - so the
stand-in client parses the stamp with whatever tz it is handed, which means a
wiring failure (no tz passed, so the UTC default) changes the attribute.

Reference: docs/testing-best-practices.md
Run with: make test-integration
"""

from datetime import UTC, datetime, tzinfo
from typing import Any
from unittest.mock import AsyncMock

import pytest
from homeassistant.core import HomeAssistant

from custom_components.melcloudhome.api.parsing import Reading, parse_api_timestamp
from custom_components.melcloudhome.const import CONF_ENABLE_WEBSOCKET

from .conftest import (
    create_mock_atw_building,
    create_mock_atw_unit,
    create_mock_atw_user_context,
    setup_atw_integration_custom,
)

FLOW_TEMP_ENTITY_ID = "sensor.melcloudhome_0efc_9abc_flow_temperature"

# A naive stamp exactly as /report/v1/internaltemperatures sends it: wall-clock
# time in the unit's own zone, seconds != 0 so it is not the synthetic to-echo.
LOCAL_STAMP = "2026-08-24T10:30:17"


async def _setup_with_zone(hass: HomeAssistant, time_zone: str | None) -> Any:
    """Set up a single-zone ATW unit reporting `time_zone` from /context.

    The stand-in `get_atw_water_temperatures` does what the real client does:
    parse the naive payload stamp with the tz it was given. It therefore only
    produces the shifted instant if the integration resolved and passed the
    unit's zone.
    """

    def configure_client(mock_client: AsyncMock) -> None:
        async def fake_water_temps(
            unit_id: str, tz: tzinfo = UTC
        ) -> dict[str, Reading]:
            return {
                "flow_temperature": Reading(41.5, parse_api_timestamp(LOCAL_STAMP, tz))
            }

        mock_client.get_atw_water_temperatures = AsyncMock(side_effect=fake_water_temps)

    _, mock_client = await setup_atw_integration_custom(
        hass,
        create_mock_atw_user_context(
            [
                create_mock_atw_building(
                    units=[create_mock_atw_unit(time_zone=time_zone)]
                )
            ]
        ),
        configure_client=configure_client,
        options={CONF_ENABLE_WEBSOCKET: False},
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    return mock_client


@pytest.mark.asyncio
async def test_last_reading_is_converted_from_the_unit_zone(
    hass: HomeAssistant,
) -> None:
    """A Europe/Madrid unit stamping 10:30:17 local must read 08:30:17 UTC."""
    await _setup_with_zone(hass, "Europe/Madrid")

    state = hass.states.get(FLOW_TEMP_ENTITY_ID)
    assert state is not None
    assert float(state.state) == 41.5
    last_reading = datetime.fromisoformat(state.attributes["last_reading"])

    # THE point of this test: the exact instant, not merely that it is tz-aware.
    # Europe/Madrid is CEST (UTC+2) in August.
    assert last_reading == datetime(2026, 8, 24, 8, 30, 17, tzinfo=UTC)


@pytest.mark.asyncio
async def test_missing_zone_falls_back_to_utc(hass: HomeAssistant) -> None:
    """A unit whose /context omits timeZone still reads, interpreted as UTC.

    The fallback must degrade to today's behaviour rather than dropping the
    reading or shifting it by a guess.
    """
    await _setup_with_zone(hass, None)

    state = hass.states.get(FLOW_TEMP_ENTITY_ID)
    assert state is not None
    assert float(state.state) == 41.5
    last_reading = datetime.fromisoformat(state.attributes["last_reading"])
    assert last_reading == datetime(2026, 8, 24, 10, 30, 17, tzinfo=UTC)
