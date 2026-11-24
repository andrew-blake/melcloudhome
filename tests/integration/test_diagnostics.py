"""Tests for MELCloud Home diagnostics.

Tests cover diagnostics data structure, credential redaction, and data collection.
Follows HA best practices: test observable behavior through diagnostics API.

Reference: docs/testing-best-practices.md
Run with: make test-integration
"""

import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, PropertyMock, patch

import pytest
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.util import dt as dt_util

from custom_components.melcloudhome.api.models import Building, UserContext
from custom_components.melcloudhome.api.parsing import Reading
from custom_components.melcloudhome.const import CONF_ENABLE_WEBSOCKET, DOMAIN
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
from .ha_testing import (
    MockConfigEntry,
    async_fire_time_changed,
)

UNIT_1 = "1111aaaa-0000-4000-8000-00000000aaaa"
UNIT_2 = "2222bbbb-0000-4000-8000-00000000bbbb"
BUILDING_1 = "b1d61111-0000-4000-8000-000000000001"


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

        # Per-account energy storage keys (issue #290): the account hash is
        # one-way, so diagnostics is how a support request identifies its files
        storage_keys = diagnostics["coordinator"]["energy_storage_keys"]
        assert storage_keys["ata"].startswith("melcloudhome_energy_data_")
        assert storage_keys["atw"].startswith("melcloudhome_energy_data_atw_")


@pytest.mark.asyncio
async def test_diagnostics_includes_entity_states(hass: HomeAssistant) -> None:
    """Test diagnostics includes entity states for climate and sensors."""
    mock_context = create_mock_ata_user_context()
    entry, _ = await setup_ata_integration_custom(hass, mock_context)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert "entities" in diagnostics
    entities = diagnostics["entities"]

    # Keyed by domain + unique ID, the unit UUID replaced by its short ID.
    climate = entities["climate.melcloudhome_a1b2_9abc"]
    assert climate["state"] == "heat"
    assert "attributes" in climate

    temp_sensor = entities["sensor.melcloudhome_a1b2_9abc_room_temperature"]
    assert temp_sensor["state"] == "20.0"


@pytest.mark.asyncio
async def test_diagnostics_includes_user_context_data(hass: HomeAssistant) -> None:
    """Test diagnostics includes detailed user context with buildings and units."""
    unit1 = create_mock_ata_unit(
        unit_id=UNIT_1,
        name="Living Room",
        power=True,
        operation_mode="Heat",
        set_temperature=22.0,
        room_temperature=20.5,
        has_energy_meter=True,
    )
    unit2 = create_mock_ata_unit(
        unit_id=UNIT_2,
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
                building_id=BUILDING_1, name="Home", units=[unit1, unit2]
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
    # sha256 pseudonym, shaped like tests/conftest.py:pseudonymize_uuid
    assert building_data["id"] == (
        "aaaaaaaa-aaaa-aaaa-aaaa-"
        + hashlib.sha256(BUILDING_1.encode()).hexdigest()[:12]
    )
    assert building_data["name"] == "Building-1"
    assert building_data["ata_unit_count"] == 2
    assert building_data["atw_unit_count"] == 0

    units = building_data["ata_units"]
    assert len(units) == 2

    assert units[0]["id"] == "melcloudhome_1111_aaaa"
    assert units[0]["name"] == "***REDACTED***"
    assert units[0]["power"] is True
    assert units[0]["operation_mode"] == "Heat"
    assert units[0]["set_temperature"] == 22.0
    assert units[0]["room_temperature"] == 20.5
    assert units[0]["has_energy_consumed_meter"] is True
    assert "wifi_signal_last_poll_at" in units[0]  # shared Wi-Fi serialiser

    assert units[1]["id"] == "melcloudhome_2222_bbbb"
    assert units[1]["name"] == "***REDACTED***"
    assert units[1]["power"] is False
    assert units[1]["operation_mode"] == "Cool"
    assert units[1]["set_temperature"] == 19.0
    assert units[1]["room_temperature"] == 21.0
    assert units[1]["has_energy_consumed_meter"] is False

    blob = json.dumps(diagnostics, default=str)
    for raw in (UNIT_1, UNIT_2, BUILDING_1):
        assert raw not in blob


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
        outdoor_temp_reading=Reading(
            16.0, datetime(2026, 8, 17, 8, 57, 11, tzinfo=UTC)
        ),
        has_outdoor_temp_sensor=True,
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
    assert atw_unit["outdoor_temp_recorded_at"] == "2026-08-17T08:57:11+00:00"
    assert (
        atw_unit["outdoor_temp_last_error"]
        == "ValueError: MELCloud service unavailable (HTTP 500)"
    )
    assert atw_unit["outdoor_temp_last_error_at"] is not None


@pytest.mark.asyncio
async def test_diagnostics_carry_no_names_and_no_full_ids(hass: HomeAssistant) -> None:
    """No entity ID, name, label, area, email or full unit/building ID in a dump.

    Entity IDs are HA's and the user's (ADR-030): they can hold any building,
    unit or area name, so diagnostics key entities by unique ID instead, with
    the unit's UUID replaced by its short ID.
    """
    ata_id = "11112222-3333-4444-5555-666677778888"
    atw_id = "aaaa1111-2222-3333-4444-555566667777"
    cottage_id = "c0771a9e-0000-4000-8000-00000000c071"
    barn_id = "ba4b0000-0000-4000-8000-00000000ba4b"
    context = UserContext(
        buildings=[
            Building(
                id=cottage_id,
                name="Test Cottage",
                air_to_air_units=[
                    create_mock_ata_unit(unit_id=ata_id, name="Bathroom")
                ],
            ),
            Building(
                id=barn_id,
                name="Holiday Barn",
                air_to_water_units=[
                    create_mock_atw_unit(unit_id=atw_id, name="Heat Pump")
                ],
            ),
        ]
    )
    entry, _ = await setup_ata_integration_custom(hass, context)

    devices = dr.async_get(hass)
    entities = er.async_get(hass)
    area = ar.async_get(hass).async_get_or_create("Conservatory")
    ata_device = _device(hass, entry, ata_id)
    devices.async_update_device(
        ata_device.id, name_by_user="Granny Flat AC", area_id=area.id
    )
    for domain, unique_id, new_id in (
        ("climate", ata_id, "climate.test_cottage_bathroom_climate"),
        (
            "sensor",
            f"{ata_id}_room_temperature",
            "sensor.conservatory_granny_flat_ac_room",
        ),
        ("climate", f"{atw_id}_zone_1", "climate.lounge_ac"),
        ("water_heater", f"{atw_id}_tank", "water_heater.holiday_barn_heat_pump_tank"),
    ):
        entity_id = entities.async_get_entity_id(domain, DOMAIN, unique_id)
        entities.async_update_entity(entity_id, new_entity_id=new_id)
    await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    blob = json.dumps(diagnostics, default=str).lower()

    registered = er.async_entries_for_config_entry(entities, entry.entry_id)
    # Every entity ID, except the nameless short-ID form older versions gave
    # (climate.melcloudhome_1111_8888), which is also its diagnostics key.
    nameless = re.compile(r"^[a-z_]+\.melcloudhome_[0-9a-f]{4}_[0-9a-f]{4}(_|$)")
    forbidden = [e.entity_id for e in registered if not nameless.match(e.entity_id)] + [
        "test cottage",
        "test_cottage",
        "holiday barn",
        "holiday_barn",
        "bathroom",
        "heat pump",
        "heat_pump",
        "granny flat",
        "granny_flat",
        "conservatory",
        "lounge",
        "test@example.com",
        ata_id,
        atw_id,
        cottage_id,
        barn_id,
    ]
    assert [f for f in forbidden if f.lower() in blob] == []

    with_state = [e for e in registered if hass.states.get(e.entity_id)]
    assert len(diagnostics["entities"]) == len(with_state)
    assert "climate.melcloudhome_1111_8888" in diagnostics["entities"]
    assert "climate.melcloudhome_aaaa_7777_zone_1" in diagnostics["entities"]


def _device(hass: HomeAssistant, entry, unit_id: str) -> dr.DeviceEntry:
    """The entry's device for `unit_id`.

    dr.async_get_device is deprecated from HA 2026.11; this lookup exists
    unchanged from the 2025.8 floor on.
    """
    devices = [
        d
        for d in dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
        if (DOMAIN, unit_id) in d.identifiers
    ]
    assert len(devices) == 1
    return devices[0]


@pytest.mark.asyncio
async def test_diagnostics_separates_a_quiet_unit_from_a_failing_wifi_fetch(
    hass: HomeAssistant,
) -> None:
    """ADR-028: last_reading alone can't tell a steady signal from a failing fetch."""
    stamp = datetime(2026, 10, 5, 10, 41, 24, tzinfo=UTC)
    get_wifi_signal = AsyncMock(return_value=Reading(-56, stamp))

    def configure(client):
        client.get_wifi_signal = get_wifi_signal

    entry, _ = await setup_atw_integration_custom(
        hass,
        create_mock_atw_user_context(
            [create_mock_atw_building(units=[create_mock_atw_unit()])]
        ),
        configure_client=configure,
        options={CONF_ENABLE_WEBSOCKET: False},
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    unit = diagnostics["user_context"]["buildings"][0]["atw_units"][0]
    assert unit["wifi_signal"] == -56
    assert unit["wifi_signal_recorded_at"] == "2026-10-05T10:41:24+00:00"
    assert unit["wifi_signal_last_poll_at"] is not None
    assert unit["wifi_signal_last_error"] is None
    assert unit["wifi_signal_last_error_at"] is None

    get_wifi_signal.side_effect = TimeoutError("timed out")
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=31))
    await hass.async_block_till_done(wait_background_tasks=True)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    unit = diagnostics["user_context"]["buildings"][0]["atw_units"][0]
    assert unit["wifi_signal"] == -56
    assert unit["wifi_signal_last_error"] == "TimeoutError: timed out"
    assert unit["wifi_signal_last_error_at"] is not None
    # A failed poll is still a poll: last_poll_at moves with the error
    assert unit["wifi_signal_last_poll_at"] == unit["wifi_signal_last_error_at"]

    get_wifi_signal.side_effect = None
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=62))
    await hass.async_block_till_done(wait_background_tasks=True)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    unit = diagnostics["user_context"]["buildings"][0]["atw_units"][0]
    assert unit["wifi_signal"] == -56
    assert unit["wifi_signal_last_error"] is None
    assert unit["wifi_signal_last_error_at"] is None
