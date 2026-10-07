"""Tests for the Wi-Fi signal sensors' telemetry source (issue #350, ADR-028).

/context's rssi froze in September 2026, so wifi_signal reads the telemetry
series through client.get_wifi_signal on a 30-minute timer, with the first
fetch in the startup background task (ADR-021). These tests mock that method,
the API boundary, and observe only hass.states.

Reference: docs/testing-best-practices.md
Run with: make test-integration
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.melcloudhome.api.exceptions import ServiceUnavailableError
from custom_components.melcloudhome.api.models import Building
from custom_components.melcloudhome.api.parsing import Reading
from custom_components.melcloudhome.const import CONF_ENABLE_WEBSOCKET, DOMAIN

from .conftest import (
    TEST_ATA_UNIT_ID,
    create_mock_ata_unit,
    create_mock_ata_user_context,
    create_mock_atw_unit,
    setup_ata_integration_custom,
)

ATA_WIFI = "sensor.melcloudhome_a1b2_9abc_wifi_signal"
ATW_WIFI = "sensor.melcloudhome_0efc_9abc_wifi_signal"
STAMP = datetime(2026, 10, 5, 10, 41, 24, tzinfo=UTC)


def _context() -> Any:
    """One building with one ATA and one ATW unit, as fresh objects each call.

    Fresh objects matter: every real /context poll builds new units, and a
    reading survives only if the coordinator re-applies it.
    """
    return create_mock_ata_user_context(
        [
            Building(
                id="building-mixed",
                name="Home",
                air_to_air_units=[create_mock_ata_unit()],
                air_to_water_units=[create_mock_atw_unit()],
            )
        ]
    )


async def _setup(hass: HomeAssistant, get_wifi_signal: AsyncMock) -> tuple[Any, Any]:
    """Set up the mixed context and let the startup fetch finish."""

    def configure(client: Any) -> None:
        client.get_user_context = AsyncMock(side_effect=lambda: _context())
        client.get_wifi_signal = get_wifi_signal

    entry, mock_client = await setup_ata_integration_custom(
        hass,
        _context(),
        configure_client=configure,
        options={CONF_ENABLE_WEBSOCKET: False},
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry, mock_client


async def _advance(hass: HomeAssistant, minutes: int) -> None:
    """Fire every timer due within `minutes` of setup and let fetches finish."""
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=minutes))
    await hass.async_block_till_done(wait_background_tasks=True)


@pytest.mark.asyncio
async def test_both_device_types_show_the_newest_reading_as_an_integer(
    hass: HomeAssistant,
) -> None:
    """Same series, same handling for ATA and ATW. The state is "-56", never "-56.0"."""
    await _setup(hass, AsyncMock(return_value=Reading(-56, STAMP)))

    for entity_id in (ATA_WIFI, ATW_WIFI):
        state = hass.states.get(entity_id)
        assert state is not None, entity_id
        assert state.state == "-56", entity_id
        assert state.attributes["last_reading"] == STAMP.isoformat(), entity_id
        assert state.attributes["unit_of_measurement"] == "dBm"
        assert state.attributes["device_class"] == "signal_strength"


@pytest.mark.asyncio
async def test_unknown_with_null_last_reading_before_any_reading(
    hass: HomeAssistant,
) -> None:
    """The entity exists and the key exists, with nothing to show yet."""
    await _setup(hass, AsyncMock(return_value=None))

    for entity_id in (ATA_WIFI, ATW_WIFI):
        state = hass.states.get(entity_id)
        assert state is not None, f"{entity_id} was not created"
        assert state.state == "unknown"
        assert "last_reading" in state.attributes
        assert state.attributes["last_reading"] is None


@pytest.mark.asyncio
async def test_the_timer_fetches_again_after_30_minutes_and_not_before(
    hass: HomeAssistant,
) -> None:
    """30-minute cadence (ADR-028)."""
    get_wifi_signal = AsyncMock(return_value=Reading(-56, STAMP))
    await _setup(hass, get_wifi_signal)
    newer = Reading(-61, STAMP + timedelta(minutes=20))
    get_wifi_signal.return_value = newer

    await _advance(hass, 29)
    assert hass.states.get(ATA_WIFI).state == "-56"

    await _advance(hass, 31)
    state = hass.states.get(ATA_WIFI)
    assert state.state == "-61"
    assert state.attributes["last_reading"] == newer.recorded_at.isoformat()


@pytest.mark.asyncio
async def test_failed_fetch_keeps_the_value_and_its_stamp(hass: HomeAssistant) -> None:
    """The stamp standing still is how a user sees the fetch failing."""
    get_wifi_signal = AsyncMock(return_value=Reading(-56, STAMP))
    await _setup(hass, get_wifi_signal)

    get_wifi_signal.side_effect = TimeoutError()
    await _advance(hass, 31)

    state = hass.states.get(ATA_WIFI)
    assert state.state == "-56"
    assert state.attributes["last_reading"] == STAMP.isoformat()


@pytest.mark.asyncio
async def test_empty_response_keeps_the_value_and_its_stamp(
    hass: HomeAssistant,
) -> None:
    """ADR-028's carve-out from ADR-020.

    Measured: the server intermittently withholds a reading it has already
    served, about one response in twenty. Clearing on that would blank the
    sensor several times a day on a healthy unit.
    """
    get_wifi_signal = AsyncMock(return_value=Reading(-56, STAMP))
    await _setup(hass, get_wifi_signal)

    get_wifi_signal.return_value = None
    await _advance(hass, 31)

    state = hass.states.get(ATA_WIFI)
    assert state.state == "-56"
    assert state.attributes["last_reading"] == STAMP.isoformat()


@pytest.mark.asyncio
async def test_reading_survives_a_context_poll_that_replaces_the_units(
    hass: HomeAssistant,
) -> None:
    """Every /context poll builds new unit objects; the reading is re-applied."""
    await _setup(hass, AsyncMock(return_value=Reading(-56, STAMP)))

    await hass.services.async_call(DOMAIN, "force_refresh", {}, blocking=True)
    await hass.async_block_till_done()

    for entity_id in (ATA_WIFI, ATW_WIFI):
        assert hass.states.get(entity_id).state == "-56", entity_id


@pytest.mark.asyncio
async def test_a_fetch_shows_while_context_polls_are_failing(
    hass: HomeAssistant,
) -> None:
    """A tolerated /context failure skips _rebuild_caches; the timer applies anyway."""
    get_wifi_signal = AsyncMock(return_value=Reading(-56, STAMP))
    _, mock_client = await _setup(hass, get_wifi_signal)

    mock_client.get_user_context = AsyncMock(side_effect=TimeoutError())
    get_wifi_signal.return_value = Reading(-61, STAMP + timedelta(minutes=20))
    await _advance(hass, 31)

    assert hass.states.get(ATA_WIFI).state == "-61"


@pytest.mark.asyncio
async def test_one_unit_failing_does_not_stop_the_others(hass: HomeAssistant) -> None:
    """The ATA unit is fetched first; its timeout must not cost the ATW unit."""

    async def by_unit(unit_id: str) -> Reading:
        if unit_id == TEST_ATA_UNIT_ID:
            raise TimeoutError
        return Reading(-61, STAMP)

    await _setup(hass, AsyncMock(side_effect=by_unit))

    assert hass.states.get(ATA_WIFI).state == "unknown"
    assert hass.states.get(ATW_WIFI).state == "-61"


@pytest.mark.parametrize(
    "error",
    [TimeoutError("timed out"), ServiceUnavailableError(503)],
    ids=["timeout", "503"],
)
@pytest.mark.asyncio
async def test_a_failing_unit_warns_once_and_again_on_recovery(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, error: Exception
) -> None:
    """The tracker's own contract: one WARNING per failure run per unit, one on recovery.

    Counts only messages naming "Wi-Fi signal". On a 503 the shared
    _execute_with_retry also warns every attempt ("service unavailable during
    get_wifi_signal(...)"), as it does for outdoor temperature; that is out of
    scope here and not counted.
    """
    caplog.set_level(logging.WARNING)
    get_wifi_signal = AsyncMock(side_effect=error)
    await _setup(hass, get_wifi_signal)  # startup fetch: both units fail
    await _advance(hass, 31)  # still failing: no new warning

    def wifi_warnings(text: str) -> int:
        return sum(
            1
            for record in caplog.records
            if record.levelno == logging.WARNING
            and "Wi-Fi signal" in record.getMessage()
            and text in record.getMessage()
        )

    assert wifi_warnings("failed") == 2

    get_wifi_signal.side_effect = None
    get_wifi_signal.return_value = Reading(-56, STAMP)
    await _advance(hass, 62)

    assert wifi_warnings("failed") == 2
    assert wifi_warnings("working again") == 2

    await _advance(hass, 93)  # healthy again: the recovery must not repeat
    assert wifi_warnings("working again") == 2


@pytest.mark.asyncio
async def test_a_rejected_login_stops_the_batch_and_says_so(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """After a password change, one rejected login ends the cycle, visibly.

    Without the stop, every remaining unit attempts its own full login on
    every tick until the user re-authenticates. The failure is still logged,
    because a 401 on this endpoint alone would start no reauth flow.
    """
    caplog.set_level(logging.WARNING)
    get_wifi_signal = AsyncMock(side_effect=ConfigEntryAuthFailed("auth"))
    await _setup(hass, get_wifi_signal)  # two units: ATA, then ATW

    assert get_wifi_signal.await_count == 1
    assert [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.WARNING and "Wi-Fi signal" in record.getMessage()
    ] == [
        "Wi-Fi signal for Test Unit failed and the sensor will keep its previous "
        "value until a fetch succeeds: ConfigEntryAuthFailed: auth"
    ]


@pytest.mark.asyncio
async def test_no_fetch_after_unload(hass: HomeAssistant) -> None:
    """The timer is cancelled with the entry; a later tick must not fetch."""
    get_wifi_signal = AsyncMock(return_value=Reading(-56, STAMP))
    entry, _ = await _setup(hass, get_wifi_signal)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    get_wifi_signal.reset_mock()

    await _advance(hass, 31)

    get_wifi_signal.assert_not_called()
