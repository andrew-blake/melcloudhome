"""Tests for MELCloud Home integration setup.

These tests need an HA test package (pytest-homeassistant on the latest HA,
pytest-homeassistant-custom-component on the floor),
which provides mock Home Assistant fixtures. They run in Docker or CI.

Run with: make test-integration
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from custom_components.melcloudhome.const import DOMAIN

from .conftest import (
    create_mock_ata_unit,
    create_mock_atw_unit,
    create_mock_entry,
    patched_client,
)
from .ha_testing import MockConfigEntry

# Mock where the name is looked up, not where it's defined
# __init__.py IS the melcloudhome module (not __init__ submodule)
MOCK_CLIENT_PATH = "custom_components.melcloudhome.MELCloudHomeClient"


def _create_mock_user_context() -> MagicMock:
    """Create a mock UserContext with empty buildings."""
    context = MagicMock()
    context.buildings = []
    return context


@pytest.mark.asyncio
async def test_force_refresh_service_registered(
    hass: HomeAssistant,
) -> None:
    """Test force refresh service is registered on setup."""
    with patch(MOCK_CLIENT_PATH) as mock_client:
        client = mock_client.return_value
        client.get_wifi_signal = AsyncMock(return_value=None)
        client.login = AsyncMock()
        client.close = AsyncMock()
        client.get_user_context = AsyncMock(return_value=_create_mock_user_context())
        # is_authenticated is a @property - use PropertyMock
        type(client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Verify service registered
        assert hass.services.has_service(DOMAIN, "force_refresh")


@pytest.mark.asyncio
async def test_force_refresh_service_unregistered_on_last_unload(
    hass: HomeAssistant,
) -> None:
    """Test force refresh service is unregistered when last entry unloaded."""
    with patch(MOCK_CLIENT_PATH) as mock_client:
        client = mock_client.return_value
        client.get_wifi_signal = AsyncMock(return_value=None)
        client.login = AsyncMock()
        client.close = AsyncMock()
        client.get_user_context = AsyncMock(return_value=_create_mock_user_context())
        # is_authenticated is a @property - use PropertyMock
        type(client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert hass.services.has_service(DOMAIN, "force_refresh")

        # Unload entry
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

        # Verify service unregistered
        assert not hass.services.has_service(DOMAIN, "force_refresh")


@pytest.mark.asyncio
async def test_token_only_data_updates_do_not_reload(
    hass: HomeAssistant,
) -> None:
    """A token-only data write must not reload the entry.

    Regression guard: an update listener fires on any entry change, so
    persisting refreshed tokens (``_persist_tokens`` writes ``entry.data``) used
    to reload the whole integration on every token refresh. The integration
    must not register update listeners (options reloads go through
    ``OptionsFlowWithReload`` instead).
    """
    from custom_components.melcloudhome.const import CONF_ENABLE_WEBSOCKET

    with patch(MOCK_CLIENT_PATH) as mock_client:
        client = mock_client.return_value
        client.get_wifi_signal = AsyncMock(return_value=None)
        client.login = AsyncMock()
        client.close = AsyncMock()
        client.get_user_context = AsyncMock(return_value=_create_mock_user_context())
        type(client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            options={CONF_ENABLE_WEBSOCKET: False},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # No update listener may be registered: HA fires them on data writes
        # too, and OptionsFlowWithReload refuses to work alongside them.
        assert not entry.update_listeners

        with patch.object(
            hass.config_entries, "async_reload", new=AsyncMock()
        ) as mock_reload:
            # Simulate _persist_tokens: options unchanged, only data changes.
            hass.config_entries.async_update_entry(
                entry, data={**entry.data, "access_token": "rotated"}
            )
            await hass.async_block_till_done()

            mock_reload.assert_not_called()


@pytest.mark.asyncio
async def test_options_flow_change_reloads_entry(
    hass: HomeAssistant,
) -> None:
    """Completing the options flow with a change must reload the entry."""
    from custom_components.melcloudhome.const import CONF_ENABLE_WEBSOCKET

    with patch(MOCK_CLIENT_PATH) as mock_client:
        client = mock_client.return_value
        client.get_wifi_signal = AsyncMock(return_value=None)
        client.login = AsyncMock()
        client.close = AsyncMock()
        client.get_user_context = AsyncMock(return_value=_create_mock_user_context())
        type(client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            options={CONF_ENABLE_WEBSOCKET: False},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        with patch.object(
            hass.config_entries, "async_reload", new=AsyncMock()
        ) as mock_reload:
            result = await hass.config_entries.options.async_init(entry.entry_id)
            await hass.config_entries.options.async_configure(
                result["flow_id"], user_input={CONF_ENABLE_WEBSOCKET: True}
            )
            await hass.async_block_till_done()

            assert entry.options == {CONF_ENABLE_WEBSOCKET: True}
            mock_reload.assert_called_once_with(entry.entry_id)


@pytest.mark.asyncio
async def test_websocket_runs_by_default(hass: HomeAssistant) -> None:
    """An entry with no options starts the WebSocket accelerator (default on).

    Observed at the API boundary: the listener's first act is fetching the WS
    hash from the client.
    """
    with patch(MOCK_CLIENT_PATH) as mock_client:
        client = mock_client.return_value
        client.get_wifi_signal = AsyncMock(return_value=None)
        client.login = AsyncMock()
        client.close = AsyncMock()
        client.get_user_context = AsyncMock(return_value=_create_mock_user_context())
        # Fail the hash fetch so the listener parks in backoff instead of
        # flailing against the mock; the await itself proves it started.
        client.async_get_ws_hash = AsyncMock(side_effect=RuntimeError("stop"))
        type(client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        client.async_get_ws_hash.assert_awaited()


@pytest.mark.asyncio
async def test_websocket_opt_out_respected(hass: HomeAssistant) -> None:
    """An explicit enable_websocket=False keeps the listener off."""
    from custom_components.melcloudhome.const import CONF_ENABLE_WEBSOCKET

    with patch(MOCK_CLIENT_PATH) as mock_client:
        client = mock_client.return_value
        client.get_wifi_signal = AsyncMock(return_value=None)
        client.login = AsyncMock()
        client.close = AsyncMock()
        client.get_user_context = AsyncMock(return_value=_create_mock_user_context())
        client.async_get_ws_hash = AsyncMock()
        type(client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            options={CONF_ENABLE_WEBSOCKET: False},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        client.async_get_ws_hash.assert_not_awaited()


# =============================================================================
# Device names (#403, ADR-030): the unit's name, written once at creation.
# The integration never writes name_by_user; the label is the user's.
# =============================================================================

DINING_ID = "abc12345-1234-5678-9abc-def123456789"


def _context_with(*buildings: Any) -> Any:
    from custom_components.melcloudhome.api.models import UserContext

    return UserContext(buildings=list(buildings))


def _building(name: str, ata: list, atw: list | None = None) -> Any:
    from custom_components.melcloudhome.api.models import Building

    return Building(
        id=f"building-{name.lower().replace(' ', '-')}",
        name=name,
        air_to_air_units=ata,
        air_to_water_units=atw or [],
    )


def _device(hass: HomeAssistant, entry: Any, unit_id: str) -> Any:
    from homeassistant.helpers import device_registry as dr

    return next(
        d
        for d in dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
        if (DOMAIN, unit_id) in d.identifiers
    )


async def _set_up(hass: HomeAssistant, entry: Any) -> None:
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def _reload(hass: HomeAssistant, entry: Any) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.asyncio
async def test_new_devices_are_named_after_their_units(hass: HomeAssistant) -> None:
    """Each new device gets its unit's name and no label (ATA and ATW)."""
    ids = {
        "11111111-1111-1111-1111-111111111111": "Dining Room",
        "22222222-2222-2222-2222-222222222222": "Living Room",
        "33333333-3333-3333-3333-333333333333": "Heat Pump",
    }
    ata = [create_mock_ata_unit(unit_id=u, name=n) for u, n in list(ids.items())[:2]]
    atw = [
        create_mock_atw_unit(
            unit_id="33333333-3333-3333-3333-333333333333", name="Heat Pump"
        )
    ]
    with patched_client(_context_with(_building("Test Home", ata, atw))):
        entry = create_mock_entry()
        entry.add_to_hass(hass)
        await _set_up(hass, entry)

    for unit_id, name in ids.items():
        device = _device(hass, entry, unit_id)
        assert (device.name, device.name_by_user) == (name, None)


@pytest.mark.asyncio
async def test_user_label_survives_reloads(hass: HomeAssistant) -> None:
    """A label the user sets stays through reloads.

    This only guards against a one-way label write: the old erase-and-restore
    also put labels back, so it is not evidence that the erase is gone.
    """
    from homeassistant.helpers import device_registry as dr

    context = _context_with(
        _building(
            "Test Home", [create_mock_ata_unit(unit_id=DINING_ID, name="Dining Room")]
        )
    )
    with patched_client(context):
        entry = create_mock_entry()
        entry.add_to_hass(hass)
        await _set_up(hass, entry)
        device = _device(hass, entry, DINING_ID)
        dr.async_get(hass).async_update_device(device.id, name_by_user="My Custom Name")
        await _reload(hass, entry)
        await _reload(hass, entry)

    device = _device(hass, entry, DINING_ID)
    assert (device.name, device.name_by_user) == ("Dining Room", "My Custom Name")


@pytest.mark.asyncio
async def test_reset_label_shows_the_device_name(hass: HomeAssistant) -> None:
    """A label the user clears stays clear: entities show the device name."""
    from homeassistant.helpers import device_registry as dr, entity_registry as er

    context = _context_with(
        _building(
            "Test Home", [create_mock_ata_unit(unit_id=DINING_ID, name="Dining Room")]
        )
    )
    with patched_client(context):
        entry = create_mock_entry()
        entry.add_to_hass(hass)
        await _set_up(hass, entry)
        devices = dr.async_get(hass)
        device = _device(hass, entry, DINING_ID)
        devices.async_update_device(device.id, name_by_user="Temporary")
        devices.async_update_device(device.id, name_by_user=None)
        await _reload(hass, entry)

    assert _device(hass, entry, DINING_ID).name_by_user is None
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{DINING_ID}_room_temperature"
    )
    state = hass.states.get(entity_id)
    assert state.attributes["friendly_name"] == "Dining Room Room temperature"


@pytest.mark.asyncio
async def test_readd_restores_label_and_area_and_names_device_after_unit(
    hass: HomeAssistant,
) -> None:
    """Re-adding an entry whose devices came from an older version.

    HA keeps a deleted device's label and area (not its name) and restores
    them when the device comes back; the name becomes the unit's name.
    """
    from homeassistant.helpers import area_registry as ar, device_registry as dr

    context = _context_with(
        _building(
            "Test Home", [create_mock_ata_unit(unit_id=DINING_ID, name="Dining Room")]
        )
    )
    area = ar.async_get(hass).async_get_or_create("Dining")
    with patched_client(context):
        entry = create_mock_entry()
        entry.add_to_hass(hass)
        # What older versions left: a short-ID name, plus the user's label and area.
        devices = dr.async_get(hass)
        old = devices.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, DINING_ID)},
            name="melcloudhome_abc1_6789",
            manufacturer="Mitsubishi Electric",
        )
        devices.async_update_device(old.id, name_by_user="Dining AC", area_id=area.id)
        await _set_up(hass, entry)
        assert _device(hass, entry, DINING_ID).name == "melcloudhome_abc1_6789"

        await hass.config_entries.async_remove(entry.entry_id)
        await hass.async_block_till_done()

        entry = create_mock_entry()
        entry.add_to_hass(hass)
        await _set_up(hass, entry)

    device = _device(hass, entry, DINING_ID)
    assert (device.name, device.name_by_user, device.area_id) == (
        "Dining Room",
        "Dining AC",
        area.id,
    )
