"""ATW energy from the combined-energy report, tested through hass.states.

The client is mocked at the API boundary. get_energy_report's stand-in labels
each hour in the unit's TRUE zone (not the zone the tracker passes in) and then
runs the real parser with the tracker's zone, so a tracker that picks the wrong
zone produces the wrong keys and the tests fail.

Time is frozen at 2026-09-25 07:40 UTC (09:40 in Stockholm), clear of any
clock change, so every hour below lands in the same local days on every run.
The energy fetch runs in background tasks (startup fetch and timer), so every
wait uses wait_background_tasks=True, which in turn needs the WebSocket off.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest
from freezegun import freeze_time
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.melcloudhome.api.parsing import parse_energy_report
from custom_components.melcloudhome.const import CONF_ENABLE_WEBSOCKET

from .conftest import (
    TEST_ATW_UNIT_ID,
    TEST_SENSOR_ENERGY_CONSUMED,
    TEST_SENSOR_ENERGY_PRODUCED,
    create_mock_atw_building,
    create_mock_atw_unit,
    create_mock_atw_user_context,
    setup_atw_integration_custom,
)

MOCK_STORE_PATH = "custom_components.melcloudhome.energy_tracker_base.Store"
KEY = "%Y-%m-%d %H:%M:%S.000000000"
STOCKHOLM = "Europe/Stockholm"
LONDON = "Europe/London"
SECOND_UNIT_ID = "1eaf5678-1234-4abc-8def-0123456789ab"
FROZEN_NOW = "2026-09-25 07:40:00"


def _hour(hours_ago: int) -> datetime:
    """A UTC hour start relative to the frozen now (0 = the in-progress hour)."""
    return datetime.now(UTC).replace(minute=0, second=0, microsecond=0) - timedelta(
        hours=hours_ago
    )


def _key(hours_ago: int) -> str:
    return _hour(hours_ago).strftime(KEY)


def _raw_report(
    energy: dict[datetime, tuple[float, float]], label_tz: ZoneInfo
) -> list[dict]:
    """A raw combined-energy response, labels in the unit's true local time.

    Every hour is included; the parser's own window guard decides what counts.
    """
    consumed, produced = [], []
    for hour, (c, p) in sorted(energy.items()):
        label = hour.astimezone(label_tz).replace(tzinfo=None).isoformat()
        consumed.append({"x": label, "y": c})
        produced.append({"x": label, "y": p})
    return [
        {
            "datasets": [
                {"id": "interval_energy_consumed", "data": consumed},
                {"id": "interval_energy_produced", "data": produced},
            ]
        }
    ]


def _report_side_effect(
    energy: dict[datetime, tuple[float, float]],
    zones: dict[str, str],
    *,
    fake_point_for_multi_day: bool = False,
    fail_yesterday: bool = False,
):
    """get_energy_report stand-in: true-zone labels, real parser, tracker's tz."""

    async def side_effect(
        unit_id: str, from_utc: datetime, to_utc: datetime, tz: Any
    ) -> dict:
        label_tz = ZoneInfo(zones[unit_id])
        if fail_yesterday and to_utc <= datetime.now(UTC).astimezone(label_tz).replace(
            hour=0, minute=0, second=0, microsecond=0
        ).astimezone(UTC):
            raise RuntimeError("simulated failure for yesterday's window")
        raw = _raw_report(energy, label_tz)
        if fake_point_for_multi_day and to_utc - from_utc > timedelta(hours=25):
            # The real API's carry-forward artefact at the internal local midnight.
            midnight = (
                (from_utc + timedelta(days=1))
                .astimezone(label_tz)
                .replace(tzinfo=None)
                .isoformat()
            )
            for ds in raw[0]["datasets"]:
                ds["data"].append({"x": midnight, "y": 5.0})
        return parse_energy_report(raw, tz, from_utc, to_utc)

    return side_effect


def _storage(
    hours: dict[str, tuple[float, float]], consumed_total: float, produced_total: float
) -> dict:
    return {
        "cumulative": {
            TEST_ATW_UNIT_ID: {"consumed": consumed_total, "produced": produced_total}
        },
        "hour_values": {
            TEST_ATW_UNIT_ID: {
                "consumed": {k: c for k, (c, _) in hours.items()},
                "produced": {k: p for k, (_, p) in hours.items()},
            }
        },
    }


async def _setup(
    hass: HomeAssistant, units: list, side_effect, storage: dict | None
) -> None:
    context = create_mock_atw_user_context([create_mock_atw_building(units=units)])

    def configure(client: Any) -> None:
        client.atw = AsyncMock()
        client.atw.get_energy_report = AsyncMock(side_effect=side_effect)

    with patch(MOCK_STORE_PATH) as store_class:
        store = store_class.return_value
        store.async_load = AsyncMock(return_value=storage)
        store.async_save = AsyncMock()
        await setup_atw_integration_custom(
            hass,
            context,
            configure_client=configure,
            options={CONF_ENABLE_WEBSOCKET: False},
        )
        await hass.async_block_till_done(wait_background_tasks=True)


def _unit(time_zone: str | None = STOCKHOLM) -> Any:
    return create_mock_atw_unit(has_energy_meter=True, time_zone=time_zone)


async def _poll(hass: HomeAssistant) -> None:
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=31))
    await hass.async_block_till_done(wait_background_tasks=True)


def _state(hass: HomeAssistant, entity_id: str) -> float:
    return float(hass.states.get(entity_id).state)


@freeze_time(FROZEN_NOW, real_asyncio=True)
@pytest.mark.asyncio
async def test_sensor_rises_during_the_hour(hass: HomeAssistant) -> None:
    energy = {_hour(2): (0.4, 1.2), _hour(1): (0.5, 1.5), _hour(0): (0.1, 0.3)}
    stored = {_key(2): (0.4, 1.2), _key(1): (0.5, 1.5)}
    await _setup(
        hass,
        [_unit()],
        _report_side_effect(energy, {TEST_ATW_UNIT_ID: STOCKHOLM}),
        _storage(stored, 10.0, 30.0),
    )

    assert _state(hass, TEST_SENSOR_ENERGY_CONSUMED) == pytest.approx(10.1)
    assert _state(hass, TEST_SENSOR_ENERGY_PRODUCED) == pytest.approx(30.3)

    energy[_hour(0)] = (0.3, 0.9)  # the in-progress hour grows
    await _poll(hass)

    assert _state(hass, TEST_SENSOR_ENERGY_CONSUMED) == pytest.approx(10.3)
    assert _state(hass, TEST_SENSOR_ENERGY_PRODUCED) == pytest.approx(30.9)


@freeze_time(FROZEN_NOW, real_asyncio=True)
@pytest.mark.asyncio
async def test_upgrade_with_telemetry_keys_does_not_double_count(
    hass: HomeAssistant,
) -> None:
    stored = {_key(3): (0.2, 0.6), _key(2): (0.4, 1.2), _key(1): (0.5, 1.5)}
    energy = {
        _hour(3): (0.2, 0.6),
        _hour(2): (0.4, 1.2),
        _hour(1): (0.5, 1.5),
        _hour(0): (0.1, 0.3),
    }
    await _setup(
        hass,
        [_unit()],
        _report_side_effect(energy, {TEST_ATW_UNIT_ID: STOCKHOLM}),
        _storage(stored, 10.0, 30.0),
    )

    # Stored hours unchanged; only the partial in-progress hour is new.
    assert _state(hass, TEST_SENSOR_ENERGY_CONSUMED) == pytest.approx(10.1)
    assert _state(hass, TEST_SENSOR_ENERGY_PRODUCED) == pytest.approx(30.3)

    await _poll(hass)  # same values again: counted once, not twice

    assert _state(hass, TEST_SENSOR_ENERGY_CONSUMED) == pytest.approx(10.1)
    assert _state(hass, TEST_SENSOR_ENERGY_PRODUCED) == pytest.approx(30.3)


@freeze_time(FROZEN_NOW, real_asyncio=True)
@pytest.mark.asyncio
async def test_young_install_does_not_count_energy_from_before_tracking(
    hass: HomeAssistant,
) -> None:
    # Tracking began two hours ago; the report also holds six older active hours.
    energy = {_hour(h): (0.5, 1.5) for h in range(8, 0, -1)}
    stored = {_key(2): (0.5, 1.5), _key(1): (0.5, 1.5)}
    await _setup(
        hass,
        [_unit()],
        _report_side_effect(energy, {TEST_ATW_UNIT_ID: STOCKHOLM}),
        _storage(stored, 1.0, 3.0),
    )

    assert _state(hass, TEST_SENSOR_ENERGY_CONSUMED) == pytest.approx(1.0)
    assert _state(hass, TEST_SENSOR_ENERGY_PRODUCED) == pytest.approx(3.0)


@freeze_time(FROZEN_NOW, real_asyncio=True)
@pytest.mark.asyncio
async def test_single_day_windows_never_see_the_multi_day_fake_point(
    hass: HomeAssistant,
) -> None:
    energy = {_hour(26): (0.4, 1.2), _hour(2): (0.4, 1.2), _hour(1): (0.5, 1.5)}
    stored = {_key(26): (0.4, 1.2), _key(2): (0.4, 1.2), _key(1): (0.5, 1.5)}
    await _setup(
        hass,
        [_unit()],
        _report_side_effect(
            energy, {TEST_ATW_UNIT_ID: STOCKHOLM}, fake_point_for_multi_day=True
        ),
        _storage(stored, 10.0, 30.0),
    )
    await _poll(hass)

    assert _state(hass, TEST_SENSOR_ENERGY_CONSUMED) == pytest.approx(10.0)
    assert _state(hass, TEST_SENSOR_ENERGY_PRODUCED) == pytest.approx(30.0)


@freeze_time(FROZEN_NOW, real_asyncio=True)
@pytest.mark.asyncio
async def test_unit_without_zone_tracks_on_utc_and_warns_once(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    energy = {_hour(1): (0.5, 1.5), _hour(0): (0.1, 0.3)}
    stored = {_key(1): (0.5, 1.5)}
    with caplog.at_level(logging.WARNING):
        # True label zone is UTC here: the design accepts the offset risk, so
        # this test only pins "keeps tracking" and "warns once".
        await _setup(
            hass,
            [_unit(time_zone=None)],
            _report_side_effect(energy, {TEST_ATW_UNIT_ID: "UTC"}),
            _storage(stored, 10.0, 30.0),
        )
        await _poll(hass)
        await _poll(hass)

    assert _state(hass, TEST_SENSOR_ENERGY_CONSUMED) == pytest.approx(10.1)
    warnings = [r for r in caplog.records if "no usable time zone" in r.getMessage()]
    assert len(warnings) == 1


@freeze_time(FROZEN_NOW, real_asyncio=True)
@pytest.mark.asyncio
async def test_failed_yesterday_request_still_counts_today(hass: HomeAssistant) -> None:
    energy = {_hour(1): (0.5, 1.5), _hour(0): (0.2, 0.6)}
    stored = {_key(1): (0.5, 1.5)}
    await _setup(
        hass,
        [_unit()],
        _report_side_effect(energy, {TEST_ATW_UNIT_ID: STOCKHOLM}, fail_yesterday=True),
        _storage(stored, 10.0, 30.0),
    )

    assert _state(hass, TEST_SENSOR_ENERGY_CONSUMED) == pytest.approx(10.2)


@freeze_time(FROZEN_NOW, real_asyncio=True)
@pytest.mark.asyncio
async def test_unit_with_no_energy_yet_stays_quiet(hass: HomeAssistant) -> None:
    await _setup(
        hass, [_unit()], _report_side_effect({}, {TEST_ATW_UNIT_ID: STOCKHOLM}), None
    )
    await _poll(hass)

    assert _state(hass, TEST_SENSOR_ENERGY_CONSUMED) == 0.0
    assert _state(hass, TEST_SENSOR_ENERGY_PRODUCED) == 0.0


@freeze_time(FROZEN_NOW, real_asyncio=True)
@pytest.mark.asyncio
async def test_two_units_in_different_zones_get_their_own_keys(
    hass: HomeAssistant,
) -> None:
    energy = {_hour(1): (0.5, 1.5), _hour(0): (0.1, 0.3)}
    storage = {
        "cumulative": {
            TEST_ATW_UNIT_ID: {"consumed": 10.0, "produced": 30.0},
            SECOND_UNIT_ID: {"consumed": 20.0, "produced": 60.0},
        },
        "hour_values": {
            TEST_ATW_UNIT_ID: {"consumed": {_key(1): 0.5}, "produced": {_key(1): 1.5}},
            SECOND_UNIT_ID: {"consumed": {_key(1): 0.5}, "produced": {_key(1): 1.5}},
        },
    }
    units = [
        _unit(STOCKHOLM),
        create_mock_atw_unit(
            unit_id=SECOND_UNIT_ID,
            name="Second ATW",
            has_energy_meter=True,
            time_zone=LONDON,
        ),
    ]
    zones = {TEST_ATW_UNIT_ID: STOCKHOLM, SECOND_UNIT_ID: LONDON}
    await _setup(hass, units, _report_side_effect(energy, zones), storage)

    assert _state(hass, TEST_SENSOR_ENERGY_CONSUMED) == pytest.approx(10.1)
    assert _state(
        hass, "sensor.melcloudhome_1eaf_89ab_energy_consumed"
    ) == pytest.approx(20.1)


@freeze_time("2026-09-24 22:05:00", real_asyncio=True)  # 00:05 on 25 Sep in Stockholm
@pytest.mark.asyncio
async def test_yesterdays_last_hour_keeps_updating_after_midnight(
    hass: HomeAssistant,
) -> None:
    # 23:00 local on 24 Sep = 21:00 UTC: stored at a partial value, now final in yesterday's window.
    last_hour = datetime(2026, 9, 24, 21, 0, tzinfo=UTC)
    energy = {last_hour: (0.5, 1.5)}
    stored = {last_hour.strftime(KEY): (0.2, 0.6)}
    await _setup(
        hass,
        [_unit()],
        _report_side_effect(energy, {TEST_ATW_UNIT_ID: STOCKHOLM}),
        _storage(stored, 10.0, 30.0),
    )

    assert _state(hass, TEST_SENSOR_ENERGY_CONSUMED) == pytest.approx(10.3)
    assert _state(hass, TEST_SENSOR_ENERGY_PRODUCED) == pytest.approx(30.9)


@pytest.mark.parametrize(
    ("time_zone", "expected_warnings"), [(STOCKHOLM, 0), ("Asia/Kolkata", 1)]
)
@freeze_time(FROZEN_NOW, real_asyncio=True)
@pytest.mark.asyncio
async def test_only_a_non_whole_hour_offset_warns(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    time_zone: str,
    expected_warnings: int,
) -> None:
    with caplog.at_level(logging.WARNING):
        await _setup(
            hass,
            [_unit(time_zone)],
            _report_side_effect({}, {TEST_ATW_UNIT_ID: time_zone}),
            None,
        )
        await _poll(hass)

    warnings = [r for r in caplog.records if "no usable time zone" in r.getMessage()]
    assert len(warnings) == expected_warnings
