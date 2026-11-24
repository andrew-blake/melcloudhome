"""The names Home Assistant builds new entity IDs from (#403, ADR-030).

HA owns entity IDs: it builds a new one from the area, the device name and the
entity name, following the user's ID-format setting. Other tests look entities
up by unique_id. This file pins what the integration controls: each device's
registry name (the unit's name, set once when the device is created), its
serial number, and each entity's own name. It also pins that an existing
install keeps every entity ID, device name, label and saved entity label.
"""

from typing import Any

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import slugify

from custom_components.melcloudhome.api.models import Building, UserContext
from custom_components.melcloudhome.const import DOMAIN

from .conftest import (
    TEST_ATA_UNIT_ID,
    TEST_ATW_UNIT_ID,
    create_mock_ata_unit,
    create_mock_ata_user_context,
    create_mock_atw_unit,
    create_mock_atw_user_context,
    create_mock_entry,
    patched_client,
    setup_ata_integration_custom,
    setup_atw_integration_custom,
)

# compat_name (and the own-area rule) arrived in HA 2026.11.
HAS_COMPAT = hasattr(er, "async_preserve_compat_name_as_alias")

ATA_SERIAL = "melcloudhome_a1b2_9abc"
ATW_SERIAL = "melcloudhome_0efc_9abc"

_ACCOUNT = {("binary_sensor", "MELCloud Home", "Real-time updates")}

_ATA = _ACCOUNT | {
    ("binary_sensor", "Test Unit", "Connection state"),
    ("binary_sensor", "Test Unit", "Error state"),
    ("climate", "Test Unit", "Climate"),
    ("fan", "Test Unit", "A/C fan"),
    ("sensor", "Test Unit", "Actual fan speed"),
    ("sensor", "Test Unit", "Outdoor temperature"),
    ("sensor", "Test Unit", "Room temperature"),
    ("sensor", "Test Unit", "WiFi signal"),
}

_ATW = _ACCOUNT | {
    ("binary_sensor", "Test ATW Unit", "Connection state"),
    ("binary_sensor", "Test ATW Unit", "Error state"),
    ("binary_sensor", "Test ATW Unit", "Forced DHW active"),
    ("climate", "Test ATW Unit", "Zone 1"),
    ("sensor", "Test ATW Unit", "Flow temperature"),
    ("sensor", "Test ATW Unit", "Operation status"),
    ("sensor", "Test ATW Unit", "Outdoor temperature"),
    ("sensor", "Test ATW Unit", "Return temperature"),
    ("sensor", "Test ATW Unit", "Tank temperature"),
    ("sensor", "Test ATW Unit", "WiFi signal"),
    ("sensor", "Test ATW Unit", "Zone 1 temperature"),
    ("switch", "Test ATW Unit", "System Power"),
    ("water_heater", "Test ATW Unit", "Tank"),
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


def _unit_device(hass: HomeAssistant, unit_id: str) -> dr.DeviceEntry:
    # Device lookups by identifier are deprecated on 2026.11; this works on both.
    (entry,) = hass.config_entries.async_entries(DOMAIN)
    return next(
        d
        for d in dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
        if (DOMAIN, unit_id) in d.identifiers
    )


def _entity_id(hass: HomeAssistant, domain: str, unique_id: str) -> str:
    entity_id: str | None = er.async_get(hass).async_get_entity_id(
        domain, DOMAIN, unique_id
    )
    assert entity_id is not None
    return entity_id


@pytest.mark.asyncio
async def test_ata_naming_inputs(hass: HomeAssistant) -> None:
    entry, _ = await setup_ata_integration_custom(hass, create_mock_ata_user_context())
    assert _naming_inputs(hass, entry.entry_id) == _ATA


@pytest.mark.asyncio
async def test_atw_naming_inputs(hass: HomeAssistant) -> None:
    entry, _ = await setup_atw_integration_custom(hass, create_mock_atw_user_context())
    assert _naming_inputs(hass, entry.entry_id) == _ATW


@pytest.mark.asyncio
async def test_fresh_install_names_each_device_after_its_unit(
    hass: HomeAssistant,
) -> None:
    """A new device is named after the unit: no label, no area, a serial number."""
    context = UserContext(
        buildings=[
            Building(
                id="b1",
                name="My Home",
                air_to_air_units=[create_mock_ata_unit(name="Living Room AC")],
                air_to_water_units=[create_mock_atw_unit(name="Heat Pump")],
            )
        ]
    )
    await setup_ata_integration_custom(hass, context)

    for unit_id, name, serial in (
        (TEST_ATA_UNIT_ID, "Living Room AC", ATA_SERIAL),
        (TEST_ATW_UNIT_ID, "Heat Pump", ATW_SERIAL),
    ):
        device = _unit_device(hass, unit_id)
        assert (device.name, device.name_by_user, device.area_id) == (name, None, None)
        assert device.serial_number == serial


@pytest.mark.parametrize(
    "context_factory", [create_mock_ata_user_context, create_mock_atw_user_context]
)
@pytest.mark.asyncio
async def test_fresh_install_ids_are_built_from_the_unit_name(
    hass: HomeAssistant, context_factory: Any
) -> None:
    """The device is named before its entities register, so IDs use the unit name.

    The formula is HA's default with no area and the default ID-format
    setting, on the floor and on 2026.11. Single-unit fixtures: a second unit
    with the same name would get HA's _2 suffix.
    """
    entry, _ = await setup_ata_integration_custom(hass, context_factory())
    devices = dr.async_get(hass)
    entities = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    assert entities
    for entity in entities:
        device = devices.async_get(entity.device_id)
        parts = filter(None, [device.name, entity.original_name])
        assert entity.entity_id == f"{entity.domain}.{slugify(' '.join(parts))}"


@pytest.mark.asyncio
async def test_same_named_units_in_two_buildings_share_a_name(
    hass: HomeAssistant,
) -> None:
    """Accepted cost (#403): identical device names, the second ID gets _2."""
    second_id = "b2c3d4e5-5678-9abc-def0-0000000000ab"
    context = UserContext(
        buildings=[
            Building(
                id="b1",
                name="My Home",
                air_to_air_units=[create_mock_ata_unit(name="Living Room AC")],
            ),
            Building(
                id="b2",
                name="Holiday Home",
                air_to_air_units=[
                    create_mock_ata_unit(unit_id=second_id, name="Living Room AC")
                ],
            ),
        ]
    )
    await setup_ata_integration_custom(hass, context)

    first = _unit_device(hass, TEST_ATA_UNIT_ID)
    second = _unit_device(hass, second_id)
    assert first.name == second.name == "Living Room AC"
    first_climate = _entity_id(hass, "climate", TEST_ATA_UNIT_ID)
    assert _entity_id(hass, "climate", second_id) == f"{first_climate}_2"


# ---------------------------------------------------------------------------
# Existing install: what main leaves in the registries, then this version.
# ---------------------------------------------------------------------------

# (domain, unique_id, original_name, translation_key, object id) as main
# writes them for the units below. Checked against a real main run on both HA
# versions (2026-11-24); test_existing_install_seed_matches_main pins it.
_MAIN_ENTITIES = (
    ("climate", TEST_ATA_UNIT_ID, "Climate", "melcloudhome", f"{ATA_SERIAL}_climate"),
    (
        "fan",
        f"{TEST_ATA_UNIT_ID}_ac_fan",
        "A/C fan",
        "melcloudhome",
        f"{ATA_SERIAL}_a_c_fan",
    ),
    (
        "climate",
        f"{TEST_ATW_UNIT_ID}_zone_1",
        "Zone 1",
        "melcloudhome",
        f"{ATW_SERIAL}_zone_1",
    ),
    (
        "climate",
        f"{TEST_ATW_UNIT_ID}_zone_2",
        "Zone 2",
        "melcloudhome",
        f"{ATW_SERIAL}_zone_2",
    ),
    ("water_heater", f"{TEST_ATW_UNIT_ID}_tank", "Tank", None, f"{ATW_SERIAL}_tank"),
    (
        "switch",
        f"{TEST_ATW_UNIT_ID}_system_power",
        "System Power",
        None,
        f"{ATW_SERIAL}_system_power",
    ),
)

# unique_id -> label the user gave it (what 2026.11's migration keeps as compat_name)
_RENAMES = {
    TEST_ATA_UNIT_ID: "Lounge AC",
    f"{TEST_ATA_UNIT_ID}_ac_fan": "Lounge Fan",
    f"{TEST_ATW_UNIT_ID}_zone_1": "Upstairs",
    f"{TEST_ATW_UNIT_ID}_tank": "Hot Water",
}


def _existing_context() -> UserContext:
    return UserContext(
        buildings=[
            Building(
                id="b1",
                name="My Home",
                air_to_air_units=[create_mock_ata_unit(name="Living Room AC")],
                air_to_water_units=[
                    create_mock_atw_unit(name="Heat Pump", has_zone2=True)
                ],
            )
        ]
    )


def _seed_main_install(hass: HomeAssistant, entry: Any) -> None:
    """Write the devices and entities main leaves, before this version sets up.

    main: device name melcloudhome_xxxx_xxxx, area from the building, label
    "{building} {unit}" written after platform setup; entity names hard-coded
    (climate, switch, tank, zones) or translated (fan).
    """
    devices = dr.async_get(hass)
    entities = er.async_get(hass)
    device_ids = {}
    for unit_id, serial, model, label in (
        (
            TEST_ATA_UNIT_ID,
            ATA_SERIAL,
            "Air-to-Air Heat Pump (via MELCloud Home)",
            "My Home Living Room AC",
        ),
        (
            TEST_ATW_UNIT_ID,
            ATW_SERIAL,
            "Air-to-Water Heat Pump (Ecodan via MELCloud Home)",
            "My Home Heat Pump",
        ),
    ):
        device = devices.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, unit_id)},
            name=serial,
            manufacturer="Mitsubishi Electric",
            model=model,
            suggested_area="My Home",
        )
        device_ids[unit_id] = (device.id, label)

    for domain, unique_id, original_name, translation_key, object_id in _MAIN_ENTITIES:
        extra: dict[str, Any] = {}
        if HAS_COMPAT:
            # 2026.11 builds the ID from the area, device and entity names.
            extra["object_id_base"] = original_name
        else:
            extra["suggested_object_id"] = object_id
        entities.async_get_or_create(
            domain,
            DOMAIN,
            unique_id,
            config_entry=entry,
            device_id=device_ids[unique_id[:36]][0],
            has_entity_name=True,
            original_name=original_name,
            translation_key=translation_key,
            **extra,
        )

    # main writes the label after platform setup, once the IDs are fixed.
    for device_id, label in device_ids.values():
        devices.async_update_device(device_id, name_by_user=label)


def _main_entity_id(domain: str, object_id: str) -> str:
    # 2026.11 prefixes the area main's devices were given; the floor doesn't.
    return f"{domain}.{'my_home_' if HAS_COMPAT else ''}{object_id}"


@pytest.mark.asyncio
async def test_existing_install_seed_matches_main(hass: HomeAssistant) -> None:
    """The seed is what main writes, or the upgrade test proves nothing."""
    entry = create_mock_entry()
    entry.add_to_hass(hass)
    _seed_main_install(hass, entry)
    registry = er.async_get(hass)
    for domain, unique_id, original_name, translation_key, object_id in _MAIN_ENTITIES:
        entity = registry.async_get(_entity_id(hass, domain, unique_id))
        assert entity.entity_id == _main_entity_id(domain, object_id)
        assert (
            entity.original_name,
            entity.translation_key,
            entity.has_entity_name,
        ) == (
            original_name,
            translation_key,
            True,
        )
    for unit_id, serial, label in (
        (TEST_ATA_UNIT_ID, ATA_SERIAL, "My Home Living Room AC"),
        (TEST_ATW_UNIT_ID, ATW_SERIAL, "My Home Heat Pump"),
    ):
        device = _unit_device(hass, unit_id)
        assert (device.name, device.name_by_user, device.area_id) == (
            serial,
            label,
            "my_home",
        )
        assert device.serial_number is None


def _record_registry_updates(hass: HomeAssistant) -> tuple[list, list]:
    entity_updates: list = []
    device_updates: list = []

    def on_entity(event: Any) -> None:
        if event.data["action"] == "update":
            entity_updates.append((event.data["entity_id"], set(event.data["changes"])))

    def on_device(event: Any) -> None:
        if event.data["action"] == "update":
            device_updates.append((event.data["device_id"], set(event.data["changes"])))

    hass.bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, on_entity)
    hass.bus.async_listen(dr.EVENT_DEVICE_REGISTRY_UPDATED, on_device)
    return entity_updates, device_updates


# Entity changes that wipe compat_name on 2026.11 (entity_registry.py:2185-2192).
_COMPAT_CLEARING = {"name", "device_id", "has_entity_name"}


@pytest.mark.asyncio
async def test_existing_install_upgrade_keeps_ids_names_and_labels(
    hass: HomeAssistant,
) -> None:
    """Upgrading from main changes no entity ID, device name, label or area.

    Each unit device gets exactly one update, adding its serial number; no
    entity update touches a field that clears compat_name. On 2026.11 the
    saved labels survive two boots.
    """
    entry = create_mock_entry()
    entry.add_to_hass(hass)
    _seed_main_install(hass, entry)
    registry = er.async_get(hass)
    if HAS_COMPAT:
        for unique_id, label in _RENAMES.items():
            domain = next(e[0] for e in _MAIN_ENTITIES if e[1] == unique_id)
            # No public API sets compat_name; this is what the 1.24 migration leaves.
            registry._async_update_entity(
                _entity_id(hass, domain, unique_id), name=label, compat_name=label
            )
    before_ids = {e[1]: _entity_id(hass, e[0], e[1]) for e in _MAIN_ENTITIES}
    devices_before = {
        unit_id: _unit_device(hass, unit_id)
        for unit_id in (TEST_ATA_UNIT_ID, TEST_ATW_UNIT_ID)
    }
    await hass.async_block_till_done()
    entity_updates, device_updates = _record_registry_updates(hass)

    with patched_client(_existing_context()):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        unit_device_ids = {d.id for d in devices_before.values()}
        assert sorted(
            (device_id, sorted(changes))
            for device_id, changes in device_updates
            if device_id in unit_device_ids
        ) == sorted((device_id, ["serial_number"]) for device_id in unit_device_ids)
        for unit_id, before in devices_before.items():
            after = _unit_device(hass, unit_id)
            assert (after.name, after.name_by_user, after.area_id) == (
                before.name,
                before.name_by_user,
                before.area_id,
            )
            assert after.serial_number == before.name  # melcloudhome_xxxx_xxxx

        for _, changes in entity_updates:
            assert not changes & _COMPAT_CLEARING, changes
        assert {
            u: _entity_id(hass, e[0], u) for e in _MAIN_ENTITIES for u in [e[1]]
        } == (before_ids)

        for _ in range(2):
            await hass.config_entries.async_reload(entry.entry_id)
            await hass.async_block_till_done()
        if HAS_COMPAT:
            for unique_id, label in _RENAMES.items():
                entity = registry.async_get(before_ids[unique_id])
                assert entity.compat_name == label
                state = hass.states.get(entity.entity_id)
                assert state.attributes["friendly_name"] == label


@pytest.mark.asyncio
async def test_reload_keeps_compat_name(hass: HomeAssistant) -> None:
    """A reload must not wipe the pre-2026.11 name HA keeps in compat_name.

    HA 2026.11's registry migration stores a user-renamed entity's old full
    name in compat_name; friendly_name and the Alexa/Google alias migrations
    read it. Any device_registry write to name_by_user clears it on every
    entity of that device.
    """
    if not HAS_COMPAT:
        pytest.skip("compat_name arrived in HA 2026.11")

    with patched_client(create_mock_ata_user_context()):
        entry = create_mock_entry()
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        registry = er.async_get(hass)
        entity_id = _entity_id(hass, "climate", TEST_ATA_UNIT_ID)
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
