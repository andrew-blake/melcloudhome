"""Tests for the deferred startup fetch of energy/telemetry data (ADR-021).

Reference: docs/testing-best-practices.md
Run with: make test-integration
"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from homeassistant.core import HomeAssistant

from .conftest import create_mock_ata_energy_context, setup_ata_integration_custom

CLIMATE_ENTITY_ID = "climate.melcloudhome_a1b2_9abc_climate"
ROOM_TEMP_ENTITY_ID = "sensor.melcloudhome_a1b2_9abc_room_temperature"


@pytest.mark.asyncio
async def test_entities_created_while_energy_fetch_is_still_running(
    hass: HomeAssistant,
) -> None:
    """Entity creation must not wait on the energy fetch.

    The fetch never returns. If setup were still awaiting it, this test
    would hang rather than fail - which is the point: a fetch that
    completes instantly is indistinguishable from one that never blocked.
    """

    def configure_client(mock_client: AsyncMock) -> None:
        async def hang(*_args, **_kwargs):
            await asyncio.Event().wait()

        mock_client.get_energy_data = AsyncMock(side_effect=hang)

    entry, _ = await setup_ata_integration_custom(
        hass,
        create_mock_ata_energy_context(),
        configure_client=configure_client,
    )

    assert hass.states.get(CLIMATE_ENTITY_ID) is not None, (
        "core climate entity must exist without waiting for the energy fetch"
    )
    assert hass.states.get(ROOM_TEMP_ENTITY_ID) is not None

    # Unload with the fetch still in flight: must not raise or hang, and
    # must not close the client underneath an in-flight request.
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.asyncio
async def test_energy_fetch_still_runs_after_setup(hass: HomeAssistant) -> None:
    """Deferring the fetch must not skip it.

    Without this, dropping the background task entirely still passes the
    test above.
    """
    _, mock_client = await setup_ata_integration_custom(
        hass, create_mock_ata_energy_context()
    )
    await hass.async_block_till_done()

    assert mock_client.get_energy_data.called, "energy fetch deferred but never ran"
