"""Tests for the deferred startup fetch of energy/telemetry data.

The first energy/telemetry fetch after a restart is ~22 sequential paced
requests (ADR-021). It runs in a background task so entity creation isn't
blocked on it. These tests pin that behaviour by making the fetch hang
forever: entities must still appear, and unloading must still be clean.

Follows HA best practices: observable behaviour through hass.states only,
never coordinator internals. Reference: docs/testing-best-practices.md
Run with: make test-integration
"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from homeassistant.core import HomeAssistant

from .conftest import create_mock_ata_energy_context, setup_ata_integration_custom

# Entity ID convention (docs/entities.md): short_id = first 4 + last 4 chars
# of the unit UUID with hyphens removed. TEST_ATA_UNIT_ID dehyphenates to
# "a1b2c3d456789abcdef0123456789abc" -> "a1b2_9abc".
CLIMATE_ENTITY_ID = "climate.melcloudhome_a1b2_9abc_climate"
ROOM_TEMP_ENTITY_ID = "sensor.melcloudhome_a1b2_9abc_room_temperature"


@pytest.mark.asyncio
async def test_entities_created_while_energy_fetch_is_still_running(
    hass: HomeAssistant,
) -> None:
    """Entity creation must not wait on the energy fetch.

    The fetch blocks on an Event that is never set. If setup were still
    awaiting it, this test would hang rather than fail - which is the
    point: a fetch that completes instantly is indistinguishable from one
    that never blocked, so only a hanging fetch proves the deferral.
    """
    blocked = asyncio.Event()

    def configure_client(mock_client: AsyncMock) -> None:
        async def hang(*_args, **_kwargs):
            await blocked.wait()

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
    # must not leave the client closed underneath an in-flight request.
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.asyncio
async def test_energy_fetch_still_runs_after_setup(hass: HomeAssistant) -> None:
    """Deferring the fetch must not skip it - the requests still happen."""
    called = asyncio.Event()

    def configure_client(mock_client: AsyncMock) -> None:
        async def record(*_args, **_kwargs):
            called.set()
            return {}

        mock_client.get_energy_data = AsyncMock(side_effect=record)

    await setup_ata_integration_custom(
        hass,
        create_mock_ata_energy_context(),
        configure_client=configure_client,
    )
    await hass.async_block_till_done()

    assert called.is_set(), "energy fetch was deferred but never ran"
