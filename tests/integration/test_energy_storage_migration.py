"""Tests for the one-shot migration to entry-scoped energy storage (issue #290).

The energy ledger used to live under one shared storage key, so two config
entries overwrote each other's totals. The fix keys storage per account
(hash of the entry's unique_id) and adopts the legacy shared file on first
load. These tests exercise that migration.

Unlike the rest of the energy suite these tests do NOT patch Store at class
level: one mock serving every key cannot express "legacy has data, new key
absent". They use PHACC's hass_storage fixture, a dict keyed by store key.
Entries must be seeded in the wrapper shape {"version": 1, "key": ..., "data":
{...}} - PHACC raises ValueError on a raw payload.

Run with: make test-integration
"""

import copy
import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.melcloudhome.const import DOMAIN

from .conftest import (
    MOCK_CLIENT_PATH,
    TEST_ATA_UNIT_ID,
    create_mock_ata_building,
    create_mock_ata_unit,
    create_mock_ata_user_context,
)

LEGACY_ATA_KEY = "melcloudhome_energy_data"
LEGACY_ATW_KEY = "melcloudhome_energy_data_atw"

UNIT_A = TEST_ATA_UNIT_ID  # -> sensor.melcloudhome_a1b2_9abc_energy
UNIT_B = (
    "e5f6a7b8-1234-5678-9def-aabbccdd1234"  # -> sensor.melcloudhome_e5f6_1234_energy
)
SENSOR_A = "sensor.melcloudhome_a1b2_9abc_energy"
SENSOR_B = "sensor.melcloudhome_e5f6_1234_energy"


def account_suffix(account_id: str) -> str:
    """Expected storage suffix, computed independently of the implementation."""
    return hashlib.sha256(account_id.encode()).hexdigest()[:12]


def ata_key(account_id: str) -> str:
    return f"{LEGACY_ATA_KEY}_{account_suffix(account_id)}"


def atw_key(account_id: str) -> str:
    return f"{LEGACY_ATW_KEY}_{account_suffix(account_id)}"


def recent_hour(hours_ago: int) -> str:
    """An hour timestamp in the API's format, recent enough that
    _clean_hour_values leaves it alone (keeps the migration save the ONLY
    write, which is what kills the save-made-conditional mutant)."""
    dt = (datetime.now(UTC) - timedelta(hours=hours_ago)).replace(
        minute=0, second=0, microsecond=0
    )
    return dt.strftime("%Y-%m-%d %H:00:00.000000000")


def stored(key: str, payload: dict) -> dict:
    """Wrap a payload in the shape hass_storage requires."""
    return {"version": 1, "key": key, "data": payload}


def v2_payload(unit_kwh: dict[str, float], sentinel_hour: str) -> dict:
    """v2.0-format storage payload with a clean, recent sentinel hour."""
    return {
        "cumulative": {uid: {"consumed": kwh} for uid, kwh in unit_kwh.items()},
        "hour_values": {uid: {"consumed": {sentinel_hour: 0.8}} for uid in unit_kwh},
    }


def energy_response(hour_values: list[tuple[str, float]]) -> dict:
    values = [{"time": ts, "value": wh} for ts, wh in hour_values]
    return {
        "measureData": [
            {
                "measure": "cumulative_energy_consumed_since_last_upload",
                "unit": "Wh",
                "values": values,
            }
        ]
    }


def make_mock_client(context: Any, energy_data: dict) -> MagicMock:
    client = MagicMock()
    client.login = AsyncMock()
    client.close = AsyncMock()
    client.get_user_context = AsyncMock(return_value=context)
    client.get_energy_data = AsyncMock(return_value=energy_data)
    type(client).is_authenticated = PropertyMock(return_value=True)
    return client


def context_for_unit(unit_id: str) -> Any:
    return create_mock_ata_user_context(
        [
            create_mock_ata_building(
                building_id=f"building-{unit_id[:4]}",
                units=[create_mock_ata_unit(unit_id=unit_id, has_energy_meter=True)],
            )
        ]
    )


def make_entry(email: str, *, unique_id: str | None) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_EMAIL: email, CONF_PASSWORD: "password"},
        unique_id=unique_id,
    )


async def wait_for_startup_fetch(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Wait for the ADR-021 startup energy fetch.

    It runs as a background task, which async_block_till_done does not wait
    for (and wait_background_tasks=True hangs on the never-ending websocket
    task), so await the fetch task itself.
    """
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    if coordinator._startup_fetch_task is not None:
        await coordinator._startup_fetch_task
    await hass.async_block_till_done()


async def setup_entry(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await wait_for_startup_fetch(hass, entry)


EMAIL = "test@example.com"


@pytest.mark.asyncio
async def test_migration_does_not_rerun_when_new_key_present_but_empty(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Case 1: the guard is `is None`, not truthiness.

    An empty-but-present new key is normal steady state (ATA-only installs
    rewrite an empty ATW file every 30 minutes). Re-migrating from the legacy
    file would land its values as one upward jump that total_increasing books
    as real consumption.
    """
    sentinel = recent_hour(2)
    hass_storage[LEGACY_ATA_KEY] = stored(
        LEGACY_ATA_KEY, v2_payload({UNIT_A: 25.7}, sentinel)
    )
    hass_storage[ata_key(EMAIL)] = stored(
        ata_key(EMAIL), {"cumulative": {}, "hour_values": {}}
    )

    client = make_mock_client(
        context_for_unit(UNIT_A), energy_response([(sentinel, 800.0)])
    )
    with patch(MOCK_CLIENT_PATH, return_value=client):
        await setup_entry(hass, make_entry(EMAIL, unique_id=EMAIL))

    # Fresh tracker: first init marks history as seen, counts nothing.
    # 25.7 appearing here means the migration re-ran off the legacy file.
    state = hass.states.get(SENSOR_A)
    assert state is not None
    assert float(state.state) == 0.0
    assert hass_storage[ata_key(EMAIL)]["data"]["cumulative"].get(UNIT_A, {}).get(
        "consumed", 0.0
    ) == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_legacy_file_is_never_written(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Case 2: the legacy file is byte-identical after setup AND a poll.

    The legacy file is the only safety net for a one-shot irreversible
    migration; nothing else guards it. The post-poll half matters: at setup
    the adopted content equals what was just read, so a write-back to the
    legacy key would be invisible until new data arrives.
    """
    sentinel = recent_hour(2)
    hass_storage[LEGACY_ATA_KEY] = stored(
        LEGACY_ATA_KEY, v2_payload({UNIT_A: 25.7}, sentinel)
    )
    snapshot = copy.deepcopy(hass_storage[LEGACY_ATA_KEY])

    client = make_mock_client(
        context_for_unit(UNIT_A), energy_response([(sentinel, 800.0)])
    )
    with patch(MOCK_CLIENT_PATH, return_value=client):
        entry = make_entry(EMAIL, unique_id=EMAIL)
        await setup_entry(hass, entry)

        assert hass_storage[LEGACY_ATA_KEY] == snapshot

        # A poll cycle that accumulates new energy, then check again.
        client.get_energy_data = AsyncMock(
            return_value=energy_response([(sentinel, 800.0), (recent_hour(1), 500.0)])
        )
        coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        await coordinator.energy_tracker.async_update_energy_data()
        await hass.async_block_till_done()

        assert hass_storage[LEGACY_ATA_KEY] == snapshot
        # ... and the new energy landed under the new key, proving the poll ran
        assert hass_storage[ata_key(EMAIL)]["data"]["cumulative"][UNIT_A][
            "consumed"
        ] == pytest.approx(26.2, rel=0.01)


@pytest.mark.asyncio
async def test_single_entry_migrates_with_totals_unchanged(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Case 3: the path almost every real user is on."""
    sentinel = recent_hour(2)
    hass_storage[LEGACY_ATA_KEY] = stored(
        LEGACY_ATA_KEY, v2_payload({UNIT_A: 25.7}, sentinel)
    )

    client = make_mock_client(
        context_for_unit(UNIT_A), energy_response([(sentinel, 800.0)])
    )
    with patch(MOCK_CLIENT_PATH, return_value=client):
        await setup_entry(hass, make_entry(EMAIL, unique_id=EMAIL))

    state = hass.states.get(SENSOR_A)
    assert state is not None
    assert float(state.state) == pytest.approx(25.7, rel=0.01)

    new_data = hass_storage[ata_key(EMAIL)]["data"]
    assert new_data["cumulative"][UNIT_A]["consumed"] == pytest.approx(25.7)
    assert new_data["hour_values"][UNIT_A]["consumed"] == {sentinel: 0.8}
    # The ATW tracker migrated too (to an empty file - no legacy ATW data)
    assert hass_storage[atw_key(EMAIL)]["data"]["cumulative"] == {}


@pytest.mark.asyncio
async def test_two_entries_split_comingled_legacy_file(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Case 4: the #290 regression test.

    Two accounts whose units co-mingled in the shared legacy file. Each entry
    adopts the legacy contents wholesale under its own key, and across
    setup -> poll -> teardown -> setup no sensor's state decreases. The two
    contexts use disjoint unit ids: unique_id is unit-scoped, so shared ids
    would collide in the entity registry and the second entry's sensors
    would never exist - the assertion would observe only the entry that
    never regressed.
    """
    email_a, email_b = "a@example.com", "b@example.com"
    sentinel = recent_hour(2)
    new_hour = recent_hour(1)
    # Clean, recent fixture: nothing for _clean_hour_values to touch, so the
    # unconditional migration save is the only thing that writes the new key.
    hass_storage[LEGACY_ATA_KEY] = stored(
        LEGACY_ATA_KEY, v2_payload({UNIT_A: 25.7, UNIT_B: 40.0}, sentinel)
    )

    def fresh_clients() -> list[MagicMock]:
        return [
            make_mock_client(
                context_for_unit(UNIT_A),
                energy_response([(sentinel, 800.0), (new_hour, 500.0)]),
            ),
            make_mock_client(
                context_for_unit(UNIT_B),
                energy_response([(sentinel, 800.0), (new_hour, 300.0)]),
            ),
        ]

    entry_a = make_entry(email_a, unique_id=email_a)
    entry_b = make_entry(email_b, unique_id=email_b)

    with patch(MOCK_CLIENT_PATH, side_effect=fresh_clients()) as mock_client_class:
        await setup_entry(hass, entry_a)
        await setup_entry(hass, entry_b)

        state_a = hass.states.get(SENSOR_A)
        state_b = hass.states.get(SENSOR_B)
        assert state_a is not None and state_b is not None
        total_a = float(state_a.state)
        total_b = float(state_b.state)
        assert total_a == pytest.approx(25.7 + 0.5, rel=0.01)
        assert total_b == pytest.approx(40.0 + 0.3, rel=0.01)

        # Each new file holds the legacy contents wholesale (no ownership
        # filtering), under its own key.
        key_a, key_b = ata_key(email_a), ata_key(email_b)
        assert key_a != key_b
        for key in (key_a, key_b):
            cumulative = hass_storage[key]["data"]["cumulative"]
            assert UNIT_A in cumulative
            assert UNIT_B in cumulative
        # Each entry's own accumulation went to its own key, not the other's
        assert hass_storage[key_a]["data"]["cumulative"][UNIT_A][
            "consumed"
        ] == pytest.approx(26.2, rel=0.01)
        assert hass_storage[key_b]["data"]["cumulative"][UNIT_A][
            "consumed"
        ] == pytest.approx(25.7, rel=0.01)
        assert hass_storage[key_b]["data"]["cumulative"][UNIT_B][
            "consumed"
        ] == pytest.approx(40.3, rel=0.01)

        # teardown -> setup: the restart that used to reproduce #290
        assert await hass.config_entries.async_unload(entry_a.entry_id)
        assert await hass.config_entries.async_unload(entry_b.entry_id)
        await hass.async_block_till_done()

        mock_client_class.side_effect = fresh_clients()
        await hass.config_entries.async_setup(entry_a.entry_id)
        await hass.async_block_till_done()
        await wait_for_startup_fetch(hass, entry_a)
        await hass.config_entries.async_setup(entry_b.entry_id)
        await hass.async_block_till_done()
        await wait_for_startup_fetch(hass, entry_b)

    state_a = hass.states.get(SENSOR_A)
    state_b = hass.states.get(SENSOR_B)
    assert state_a is not None and state_b is not None
    assert float(state_a.state) >= total_a
    assert float(state_b.state) >= total_b


@pytest.mark.asyncio
async def test_entries_without_unique_id_do_not_collide(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Case 5: unique_id=None must not be stringified into a shared key.

    sha256("None") for every such entry would rebuild #290 under a nicer
    filename. The fallback is the entry_id, which is unique per entry.
    """
    entry_a = make_entry("a@example.com", unique_id=None)
    entry_b = make_entry("b@example.com", unique_id=None)

    clients = [
        make_mock_client(context_for_unit(UNIT_A), energy_response([])),
        make_mock_client(context_for_unit(UNIT_B), energy_response([])),
    ]
    with patch(MOCK_CLIENT_PATH, side_effect=clients):
        await setup_entry(hass, entry_a)
        await setup_entry(hass, entry_b)

    assert entry_a.state is ConfigEntryState.LOADED
    assert entry_b.state is ConfigEntryState.LOADED

    key_a = ata_key(entry_a.entry_id)
    key_b = ata_key(entry_b.entry_id)
    assert key_a != key_b
    assert key_a in hass_storage
    assert key_b in hass_storage


@pytest.mark.asyncio
async def test_v1_3_4_legacy_format_migrates_via_legacy_key(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Case 6: the v1.3.4 -> v2.0 format conversion lives inside the load
    path, so data arriving by the legacy key must still pass through it.
    A v1.3.4 payload adopted without it puts a bare float where a dict is
    expected and setup crashes."""
    sentinel = recent_hour(2)
    hass_storage[LEGACY_ATA_KEY] = stored(
        LEGACY_ATA_KEY,
        {
            "cumulative": {UNIT_A: 25.7},  # bare float: v1.3.4 single-measure
            "hour_values": {UNIT_A: {sentinel: 0.8}},
        },
    )

    client = make_mock_client(
        context_for_unit(UNIT_A), energy_response([(sentinel, 800.0)])
    )
    with patch(MOCK_CLIENT_PATH, return_value=client):
        await setup_entry(hass, make_entry(EMAIL, unique_id=EMAIL))

    state = hass.states.get(SENSOR_A)
    assert state is not None
    assert float(state.state) == pytest.approx(25.7, rel=0.01)

    # Saved under the new key in v2.0 multi-measure format
    new_data = hass_storage[ata_key(EMAIL)]["data"]
    assert new_data["cumulative"][UNIT_A] == {"consumed": pytest.approx(25.7)}


@pytest.mark.asyncio
async def test_clean_install_starts_fresh(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Case 7: no legacy file, no new file - crash guard only."""
    client = make_mock_client(
        context_for_unit(UNIT_A), energy_response([(recent_hour(2), 800.0)])
    )
    with patch(MOCK_CLIENT_PATH, return_value=client):
        await setup_entry(hass, make_entry(EMAIL, unique_id=EMAIL))

    state = hass.states.get(SENSOR_A)
    assert state is not None
    assert float(state.state) == 0.0
    # The new keys exist even with nothing migrated, so migration never retries
    assert ata_key(EMAIL) in hass_storage
    assert atw_key(EMAIL) in hass_storage
    assert LEGACY_ATA_KEY not in hass_storage
