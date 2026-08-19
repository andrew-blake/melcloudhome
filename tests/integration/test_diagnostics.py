"""Tests for MELCloud Home diagnostics.

Tests cover diagnostics data structure, credential redaction, and data collection.
Follows HA best practices: test observable behavior through diagnostics API.

Reference: docs/testing-best-practices.md
Run with: make test-integration
"""

import json
from datetime import datetime
from unittest.mock import AsyncMock, PropertyMock, patch

import pytest
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.melcloudhome.const import DOMAIN
from custom_components.melcloudhome.diagnostics import (
    async_get_config_entry_diagnostics,
)

from .conftest import (
    MOCK_CLIENT_PATH,
    create_mock_ata_building,
    create_mock_ata_unit,
    create_mock_ata_user_context,
    create_mock_atw_building,
    create_mock_atw_unit,
    create_mock_atw_user_context,
    setup_ata_integration_custom,
    setup_atw_integration_custom,
    wire_connected_ws,
    ws_text_frame,
)


@pytest.mark.asyncio
async def test_diagnostics_includes_websocket_state(hass: HomeAssistant) -> None:
    """A connected socket reports its full state; the hash never leaks."""
    entry, _ = await setup_ata_integration_custom(
        hass,
        create_mock_ata_user_context(),
        configure_client=lambda client: wire_connected_ws(
            client, [ws_text_frame("unit-1")]
        ),
    )
    await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    ws = diagnostics["websocket"]
    assert ws["enabled"] is True
    assert ws["connected"] is True
    assert ws["last_delta_at"] is not None
    assert ws["reconnect_count"] == 0
    assert ws["current_backoff"] is not None
    # The WS hash credential must never appear anywhere in the dump.
    assert "HASH123" not in json.dumps(diagnostics, default=str)


@pytest.mark.asyncio
async def test_diagnostics_websocket_disabled(hass: HomeAssistant) -> None:
    """Opted-out entries still report the section, marked disabled."""
    from custom_components.melcloudhome.const import CONF_ENABLE_WEBSOCKET

    entry, _ = await setup_ata_integration_custom(
        hass,
        create_mock_ata_user_context(),
        options={CONF_ENABLE_WEBSOCKET: False},
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    ws = diagnostics["websocket"]
    assert ws["enabled"] is False
    assert ws["connected"] is False


@pytest.mark.asyncio
async def test_diagnostics_basic_structure(hass: HomeAssistant) -> None:
    """Test diagnostics returns correct basic structure with redacted credentials."""
    mock_context = create_mock_ata_user_context()

    # Non-standard entry: title + non-default password — keep inline
    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "secret_password"},
            unique_id="test@example.com",
            title="MELCloud Home",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        diagnostics = await async_get_config_entry_diagnostics(hass, entry)

        assert "entry" in diagnostics
        assert "coordinator" in diagnostics
        assert "entities" in diagnostics
        assert "user_context" in diagnostics

        assert diagnostics["entry"]["title"] == "***REDACTED***"
        assert diagnostics["entry"]["version"] == 2
        assert diagnostics["entry"]["data"][CONF_EMAIL] == "**REDACTED**"
        assert diagnostics["entry"]["data"][CONF_PASSWORD] == "**REDACTED**"

        assert diagnostics["coordinator"]["last_update_success"] is True
        assert diagnostics["coordinator"]["update_interval"] == 60.0


@pytest.mark.asyncio
async def test_diagnostics_includes_entity_states(hass: HomeAssistant) -> None:
    """Test diagnostics includes entity states for climate and sensors."""
    mock_context = create_mock_ata_user_context()
    entry, _ = await setup_ata_integration_custom(hass, mock_context)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert "entities" in diagnostics
    entities = diagnostics["entities"]

    climate_entity_id = "climate.melcloudhome_a1b2_9abc_climate"
    assert climate_entity_id in entities
    assert entities[climate_entity_id]["state"] == "heat"
    assert "attributes" in entities[climate_entity_id]

    temp_sensor_id = "sensor.melcloudhome_a1b2_9abc_room_temperature"
    assert temp_sensor_id in entities
    assert entities[temp_sensor_id]["state"] == "20.0"


@pytest.mark.asyncio
async def test_diagnostics_includes_user_context_data(hass: HomeAssistant) -> None:
    """Test diagnostics includes detailed user context with buildings and units."""
    unit1 = create_mock_ata_unit(
        unit_id="unit-1",
        name="Living Room",
        power=True,
        operation_mode="Heat",
        set_temperature=22.0,
        room_temperature=20.5,
        has_energy_meter=True,
    )
    unit2 = create_mock_ata_unit(
        unit_id="unit-2",
        name="Bedroom",
        power=False,
        operation_mode="Cool",
        set_temperature=19.0,
        room_temperature=21.0,
        has_energy_meter=False,
    )
    mock_context = create_mock_ata_user_context(
        [
            create_mock_ata_building(
                building_id="building-1", name="Home", units=[unit1, unit2]
            )
        ]
    )
    entry, _ = await setup_ata_integration_custom(hass, mock_context)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert "user_context" in diagnostics
    user_context = diagnostics["user_context"]

    assert "buildings" in user_context
    assert len(user_context["buildings"]) == 1

    building_data = user_context["buildings"][0]
    assert building_data["id"] == "building-1"
    assert building_data["name"] == "Building-1"
    assert building_data["ata_unit_count"] == 2
    assert building_data["atw_unit_count"] == 0

    units = building_data["ata_units"]
    assert len(units) == 2

    assert units[0]["id"] == "unit-1"
    assert units[0]["name"] == "***REDACTED***"
    assert units[0]["power"] is True
    assert units[0]["operation_mode"] == "Heat"
    assert units[0]["set_temperature"] == 22.0
    assert units[0]["room_temperature"] == 20.5
    assert units[0]["has_energy_consumed_meter"] is True

    assert units[1]["id"] == "unit-2"
    assert units[1]["name"] == "***REDACTED***"
    assert units[1]["power"] is False
    assert units[1]["operation_mode"] == "Cool"
    assert units[1]["set_temperature"] == 19.0
    assert units[1]["room_temperature"] == 21.0
    assert units[1]["has_energy_consumed_meter"] is False


@pytest.mark.asyncio
async def test_diagnostics_redacts_tokens(hass: HomeAssistant) -> None:
    """Regression: access_token, refresh_token, token_expiry must not appear in diagnostics."""
    mock_context = create_mock_ata_user_context()

    # Non-standard entry: extra config fields — keep inline
    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "secret_password",
                "access_token": "mock-access-token-abc123",
                "refresh_token": "mock-refresh-token-xyz789",
                "token_expiry": 9999999999.0,
            },
            unique_id="test@example.com",
            title="MELCloud Home",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        diagnostics = await async_get_config_entry_diagnostics(hass, entry)
        blob = json.dumps(diagnostics)

        assert "mock-access-token-abc123" not in blob
        assert "mock-refresh-token-xyz789" not in blob
        assert "9999999999.0" not in blob


@pytest.mark.asyncio
async def test_diagnostics_includes_atw_outdoor_temp_source_fields(
    hass: HomeAssistant,
) -> None:
    """Diagnostics distinguishes a last-good reading from a fresh poll error."""
    unit = create_mock_atw_unit(
        outdoor_temperature=16.0,
        has_outdoor_temp_sensor=True,
        outdoor_temp_recorded_at=datetime(2026, 8, 17, 8, 57, 11),
    )
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[unit])]
    )

    def configure(client):
        client.get_atw_outdoor_temperature = AsyncMock(
            side_effect=ValueError("MELCloud service unavailable (HTTP 500)")
        )

    entry, _ = await setup_atw_integration_custom(
        hass, mock_context, configure_client=configure
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    atw_unit = diagnostics["user_context"]["buildings"][0]["atw_units"][0]

    assert atw_unit["outdoor_temperature"] == 16.0
    assert atw_unit["has_outdoor_temp_sensor"] is True
    assert atw_unit["outdoor_temp_recorded_at"] == "2026-08-17T08:57:11"
    assert (
        atw_unit["outdoor_temp_last_error"]
        == "ValueError: MELCloud service unavailable (HTTP 500)"
    )
    assert atw_unit["outdoor_temp_last_error_at"] is not None


@pytest.mark.asyncio
async def test_diagnostics_redacts_device_name_from_entity_id_key(
    hass: HomeAssistant,
) -> None:
    """A legacy/recreated entity_id with the real device name baked in gets redacted."""
    unit_id = "11112222-3333-4444-5555-666677778888"
    unit = create_mock_ata_unit(unit_id=unit_id, name="Bathroom")
    mock_context = create_mock_ata_user_context(
        [
            create_mock_ata_building(
                building_id="building-1", name="Test Cottage", units=[unit]
            )
        ]
    )
    entry, _ = await setup_ata_integration_custom(hass, mock_context)

    device_reg = dr.async_get(hass)
    device = device_reg.async_get_device(identifiers={(DOMAIN, unit_id)})
    assert device is not None
    assert device.name_by_user == "Test Cottage Bathroom"

    entity_reg = er.async_get(hass)
    leaked = entity_reg.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{unit_id}_leaked_sensor",
        suggested_object_id="test_cottage_bathroom_leaked_sensor",
        device_id=device.id,
        config_entry=entry,
    )
    hass.states.async_set(leaked.entity_id, "42")

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    entities = diagnostics["entities"]

    assert leaked.entity_id not in entities
    blob = json.dumps(entities)
    assert "test_cottage" not in blob
    assert "bathroom" not in blob

    redacted_keys = [k for k in entities if k.endswith("_leaked_sensor")]
    assert len(redacted_keys) == 1
    assert redacted_keys[0].startswith("sensor.redacted_device_")


@pytest.mark.asyncio
async def test_diagnostics_redacts_area_name_from_entity_id_key(
    hass: HomeAssistant,
) -> None:
    """A leaked entity_id matching only the (shorter) area slug, not the
    longer name_by_user slug, still gets redacted - this integration always
    sets name_by_user to "{building} {unit}", so a leaked entity_id using
    just the area/building name alone (the real-world case found live
    2026-08-19) would slip past a name_by_user-only check."""
    unit_id = "aaaa1111-2222-3333-4444-555566667777"
    unit = create_mock_ata_unit(unit_id=unit_id, name="Bathroom")
    mock_context = create_mock_ata_user_context(
        [
            create_mock_ata_building(
                building_id="building-2", name="Test Building", units=[unit]
            )
        ]
    )
    entry, _ = await setup_ata_integration_custom(hass, mock_context)

    device_reg = dr.async_get(hass)
    device = device_reg.async_get_device(identifiers={(DOMAIN, unit_id)})
    assert device is not None
    assert device.name_by_user == "Test Building Bathroom"

    area_reg = ar.async_get(hass)
    area = area_reg.async_get_or_create("Test Building")
    device_reg.async_update_device(device.id, area_id=area.id)
    device = device_reg.async_get_device(identifiers={(DOMAIN, unit_id)})
    assert device is not None and device.area_id == area.id

    entity_reg = er.async_get(hass)
    leaked = entity_reg.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{unit_id}_leaked_sensor",
        suggested_object_id="test_building_leaked_sensor",
        device_id=device.id,
        config_entry=entry,
    )
    hass.states.async_set(leaked.entity_id, "42")

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    entities = diagnostics["entities"]

    assert leaked.entity_id not in entities
    blob = json.dumps(entities)
    assert "test_building" not in blob

    redacted_keys = [k for k in entities if k.endswith("_leaked_sensor")]
    assert len(redacted_keys) == 1
    assert redacted_keys[0].startswith("sensor.redacted_device_")


@pytest.mark.asyncio
async def test_diagnostics_single_device_type_entity_ids_unaffected(
    hass: HomeAssistant,
) -> None:
    """Single-device accounts have no name prefix to redact - must be a no-op."""
    mock_context = create_mock_ata_user_context()
    entry, _ = await setup_ata_integration_custom(hass, mock_context)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    entities = diagnostics["entities"]

    assert "climate.melcloudhome_a1b2_9abc_climate" in entities
    assert "sensor.melcloudhome_a1b2_9abc_room_temperature" in entities
    assert not any("redacted_device_" in key for key in entities)
