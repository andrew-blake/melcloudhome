"""The energy timer fires at this install's clock-aligned slots (ADR-027).

Tested through the API boundary: count get_energy_report calls as time moves.
Time is frozen at 10:00:00 UTC, so an interval timer would first fire at 10:30
and a slot at :20-:27 tells the two apart.
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from freezegun import freeze_time
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.melcloudhome.const import CONF_ENABLE_WEBSOCKET
from custom_components.melcloudhome.coordinator import energy_poll_slot

from .conftest import (
    create_mock_atw_building,
    create_mock_atw_unit,
    create_mock_atw_user_context,
    setup_atw_integration_custom,
)

MOCK_STORE_PATH = "custom_components.melcloudhome.energy_tracker_base.Store"
FROZEN_NOW = datetime(2026, 9, 26, 10, 0, 0, tzinfo=UTC)


def test_slots_spread_across_the_band() -> None:
    slots = {energy_poll_slot(f"entry-{i}") for i in range(200)}
    assert {m for m, _ in slots} == set(range(20, 28))
    assert all(0 <= s < 60 for _, s in slots)
    assert energy_poll_slot("same") == energy_poll_slot("same")


@freeze_time(FROZEN_NOW, real_asyncio=True)
@pytest.mark.asyncio
async def test_energy_polls_at_the_install_slot_only(hass: HomeAssistant) -> None:
    unit = create_mock_atw_unit(has_energy_meter=True, time_zone="Europe/Stockholm")
    context = create_mock_atw_user_context([create_mock_atw_building(units=[unit])])
    report = AsyncMock(return_value={"consumed": [], "produced": []})

    def configure(client: Any) -> None:
        client.atw = AsyncMock()
        client.atw.get_energy_report = report

    with patch(MOCK_STORE_PATH) as store_class:
        store_class.return_value.async_load = AsyncMock(return_value=None)
        store_class.return_value.async_save = AsyncMock()
        entry, _ = await setup_atw_integration_custom(
            hass,
            context,
            configure_client=configure,
            options={CONF_ENABLE_WEBSOCKET: False},
        )
        await hass.async_block_till_done(wait_background_tasks=True)

        minute, second = energy_poll_slot(entry.entry_id)
        slot = FROZEN_NOW.replace(minute=minute, second=second)
        startup_calls = report.await_count
        assert startup_calls > 0  # the startup fetch ran

        async_fire_time_changed(hass, slot - timedelta(seconds=5))
        await hass.async_block_till_done(wait_background_tasks=True)
        assert report.await_count == startup_calls  # not yet

        async_fire_time_changed(hass, slot + timedelta(seconds=1))
        await hass.async_block_till_done(wait_background_tasks=True)
        assert report.await_count > startup_calls  # the slot fired
