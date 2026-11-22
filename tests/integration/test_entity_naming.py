"""The names Home Assistant builds new entity IDs from.

Other tests look entities up by unique_id, because the ID's format depends on
the HA version and user settings (area prefix from 2026.6, #403). This file
pins what the integration controls: each device's registry name
(melcloudhome_{first4}_{last4}) and each entity's own name, which comes from
its translation_key (#240/#246). A change here changes the entity IDs of
every new install, so update the expected sets only on purpose.
"""

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import (
    create_mock_ata_user_context,
    create_mock_atw_user_context,
    setup_ata_integration_custom,
    setup_atw_integration_custom,
)

_ACCOUNT = {("binary_sensor", "MELCloud Home", "Real-time updates")}

_ATA = _ACCOUNT | {
    ("binary_sensor", "melcloudhome_a1b2_9abc", "Connection state"),
    ("binary_sensor", "melcloudhome_a1b2_9abc", "Error state"),
    ("climate", "melcloudhome_a1b2_9abc", "Climate"),
    ("fan", "melcloudhome_a1b2_9abc", "A/C fan"),
    ("sensor", "melcloudhome_a1b2_9abc", "Actual fan speed"),
    ("sensor", "melcloudhome_a1b2_9abc", "Outdoor temperature"),
    ("sensor", "melcloudhome_a1b2_9abc", "Room temperature"),
    ("sensor", "melcloudhome_a1b2_9abc", "WiFi signal"),
}

_ATW = _ACCOUNT | {
    ("binary_sensor", "melcloudhome_0efc_9abc", "Connection state"),
    ("binary_sensor", "melcloudhome_0efc_9abc", "Error state"),
    ("binary_sensor", "melcloudhome_0efc_9abc", "Forced DHW active"),
    ("climate", "melcloudhome_0efc_9abc", "Zone 1"),
    ("sensor", "melcloudhome_0efc_9abc", "Flow temperature"),
    ("sensor", "melcloudhome_0efc_9abc", "Operation status"),
    ("sensor", "melcloudhome_0efc_9abc", "Outdoor temperature"),
    ("sensor", "melcloudhome_0efc_9abc", "Return temperature"),
    ("sensor", "melcloudhome_0efc_9abc", "Tank temperature"),
    ("sensor", "melcloudhome_0efc_9abc", "WiFi signal"),
    ("sensor", "melcloudhome_0efc_9abc", "Zone 1 temperature"),
    ("switch", "melcloudhome_0efc_9abc", "System Power"),
    ("water_heater", "melcloudhome_0efc_9abc", "Tank"),
}


def _naming_inputs(hass: HomeAssistant, entry_id: str) -> set[tuple]:
    """(domain, device registry name, entity name) for each entity."""
    devices = dr.async_get(hass)
    inputs = set()
    for entity in er.async_entries_for_config_entry(er.async_get(hass), entry_id):
        device = devices.async_get(entity.device_id) if entity.device_id else None
        inputs.add(
            (entity.domain, device.name if device else None, entity.original_name)
        )
    return inputs


@pytest.mark.asyncio
async def test_ata_naming_inputs(hass: HomeAssistant) -> None:
    entry, _ = await setup_ata_integration_custom(hass, create_mock_ata_user_context())
    assert _naming_inputs(hass, entry.entry_id) == _ATA


@pytest.mark.asyncio
async def test_atw_naming_inputs(hass: HomeAssistant) -> None:
    entry, _ = await setup_atw_integration_custom(hass, create_mock_atw_user_context())
    assert _naming_inputs(hass, entry.entry_id) == _ATW


@pytest.mark.xfail(
    strict=True,
    reason="_clear_friendly_device_names/_restore_device_names wipe compat_name",
)
@pytest.mark.asyncio
async def test_reload_keeps_compat_name(hass: HomeAssistant) -> None:
    """A reload must not wipe the pre-2026.11 name HA keeps in compat_name.

    HA 2026.11's registry migration stores a user-renamed entity's old full
    name in compat_name; friendly_name and the Alexa/Google alias migrations
    read it. Any device_registry write to name_by_user clears it on every
    entity of that device.
    """
    if not hasattr(er, "async_preserve_compat_name_as_alias"):
        pytest.skip("compat_name arrived in HA 2026.11")

    from unittest.mock import AsyncMock, PropertyMock, patch

    from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

    from custom_components.melcloudhome.const import DOMAIN

    from .conftest import MOCK_CLIENT_PATH, TEST_ATA_UNIT_ID
    from .ha_testing import MockConfigEntry

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        client = mock_client_class.return_value
        client.login = AsyncMock()
        client.close = AsyncMock()
        client.get_user_context = AsyncMock(return_value=create_mock_ata_user_context())
        client.get_wifi_signal = AsyncMock(return_value=None)
        type(client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        registry = er.async_get(hass)
        entity_id = registry.async_get_entity_id("climate", DOMAIN, TEST_ATA_UNIT_ID)
        assert entity_id is not None
        # What the v1.24 migration leaves for an entity the user renamed to
        # a name that doesn't start with the device name. No public API sets it.
        registry._async_update_entity(
            entity_id, name="Lounge AC", compat_name="Lounge AC"
        )
        await hass.async_block_till_done()
        assert registry.async_get(entity_id).compat_name == "Lounge AC"

        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

        assert registry.async_get(entity_id).compat_name == "Lounge AC"
        assert hass.states.get(entity_id).attributes["friendly_name"] == "Lounge AC"
