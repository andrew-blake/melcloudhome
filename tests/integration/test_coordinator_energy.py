"""Tests for MELCloud Home coordinator energy data lifecycle.

Tests cover energy data management, accumulation, persistence, and polling.
Follows HA best practices: test observable behavior through hass.states, not internals.

Reference: docs/testing-best-practices.md
Run with: make test-integration
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.melcloudhome.const import DOMAIN, HOUR_VALUE_RETENTION_HOURS

from .conftest import (
    MOCK_CLIENT_PATH,
    TEST_ATA_BUILDING_ID,
    TEST_ATA_UNIT_ID,
    create_mock_ata_energy_context,
)

MOCK_STORE_PATH = "custom_components.melcloudhome.energy_tracker_base.Store"

# Aliases — used as dict keys in energy data assertions throughout this file
TEST_UNIT_ID = TEST_ATA_UNIT_ID
TEST_BUILDING_ID = TEST_ATA_BUILDING_ID


def create_mock_energy_response(
    hour_values: list[tuple[str, float]],
) -> dict:
    """Create a mock energy API response.

    Args:
        hour_values: List of (timestamp, watt-hours) tuples
            Example: [("2025-01-15T10:00:00Z", 500.0), ("2025-01-15T11:00:00Z", 600.0)]

    Returns:
        Mock API response matching MELCloud format
    """
    values = [{"time": timestamp, "value": wh} for timestamp, wh in hour_values]

    return {
        "measureData": [
            {
                "measure": "cumulative_energy_consumed_since_last_upload",
                "unit": "Wh",
                "values": values,
            }
        ]
    }


@asynccontextmanager
async def setup_energy_entry(
    hass: HomeAssistant, storage: dict | None, energy_data: dict
) -> AsyncGenerator[MagicMock]:
    """Set up the integration with mocked client and store.

    Yields the store mock for save-call assertions.
    """
    with (
        patch(MOCK_CLIENT_PATH) as mock_client_class,
        patch(MOCK_STORE_PATH) as mock_store_class,
    ):
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(
            return_value=create_mock_ata_energy_context()
        )
        mock_client.get_energy_data = AsyncMock(return_value=energy_data)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        mock_store = mock_store_class.return_value
        mock_store.async_load = AsyncMock(return_value=storage)
        mock_store.async_save = AsyncMock()

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        yield mock_store


@pytest.mark.asyncio
async def test_initial_energy_fetch_with_first_init(hass: HomeAssistant) -> None:
    """Test that initial energy fetch skips historical data.

    When coordinator starts for the first time (no stored data), it should:
    1. Fetch energy data from API
    2. Mark latest hour as processed (initialize tracking)
    3. Set cumulative total to 0.0 (don't count historical data)
    4. Create energy sensor with initial value 0.0

    Validates: First initialization behavior prevents inflating totals
    Tests through: hass.states (sensor entity state)
    """
    mock_context = create_mock_ata_energy_context()

    # Mock energy response with 2 hours of historical data (should be skipped)
    mock_energy_data = create_mock_energy_response(
        [
            ("2025-01-15T10:00:00Z", 500.0),  # Historical - skip
            (
                "2025-01-15T11:00:00Z",
                600.0,
            ),  # Latest - mark as processed but don't count
        ]
    )

    with (
        patch(MOCK_CLIENT_PATH) as mock_client_class,
        patch(MOCK_STORE_PATH) as mock_store_class,
    ):
        # Set up mock client
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        mock_client.get_energy_data = AsyncMock(return_value=mock_energy_data)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        # Mock storage to return no stored data (first init)
        mock_store = mock_store_class.return_value
        mock_store.async_load = AsyncMock(return_value=None)
        mock_store.async_save = AsyncMock()

        # Set up integration
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # ✅ CORRECT: Assert through state machine
        state = hass.states.get("sensor.melcloudhome_a1b2_9abc_energy")
        assert state is not None
        assert state.state == "0.0"  # Should start at 0, not include historical data
        assert state.attributes["unit_of_measurement"] == "kWh"

        # Verify API was called for initial fetch
        mock_client.get_energy_data.assert_called()


@pytest.mark.asyncio
async def test_energy_accumulation_cumulative_totals(hass: HomeAssistant) -> None:
    """Test that energy accumulates correctly over time.

    When periodic energy updates occur, the coordinator should:
    1. Fetch new hourly data from API
    2. Add new hours to cumulative total (in kWh)
    3. Update sensor state with new total
    4. Save cumulative data to storage

    Validates: Energy accumulation logic works correctly
    Tests through: hass.states (sensor shows accumulated total)
    """
    mock_context = create_mock_ata_energy_context()

    # Initial state: 1 hour already processed
    initial_storage = {
        "cumulative": {TEST_UNIT_ID: 0.5},  # 0.5 kWh already accumulated
        "hour_values": {
            TEST_UNIT_ID: {
                "2025-01-15T10:00:00Z": 0.5
            }  # Track the processed hour value
        },
    }

    # New energy data: 2 new hours (should add both)
    mock_energy_data = create_mock_energy_response(
        [
            ("2025-01-15T10:00:00Z", 500.0),  # Already processed - skip
            ("2025-01-15T11:00:00Z", 600.0),  # NEW - add 0.6 kWh
            ("2025-01-15T12:00:00Z", 700.0),  # NEW - add 0.7 kWh
        ]
    )

    with (
        patch(MOCK_CLIENT_PATH) as mock_client_class,
        patch(MOCK_STORE_PATH) as mock_store_class,
    ):
        # Set up mock client
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        mock_client.get_energy_data = AsyncMock(return_value=mock_energy_data)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        # Mock storage with initial data
        mock_store = mock_store_class.return_value
        mock_store.async_load = AsyncMock(return_value=initial_storage)
        mock_store.async_save = AsyncMock()

        # Set up integration
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # ✅ CORRECT: Assert through state machine
        state = hass.states.get("sensor.melcloudhome_a1b2_9abc_energy")
        assert state is not None

        # Expected: 0.5 (initial) + 0.6 (11:00) + 0.7 (12:00) = 1.8 kWh
        assert float(state.state) == pytest.approx(1.8, rel=0.01)

        # Verify storage was updated with new cumulative total
        # Note: Both ATA and ATW trackers call async_save, check first call (ATA tracker)
        mock_store.async_save.assert_called()
        saved_data_ata = mock_store.async_save.call_args_list[0][0][0]  # First call
        # New multi-measure format: cumulative[unit_id][measure] = value
        assert saved_data_ata["cumulative"][TEST_UNIT_ID]["consumed"] == pytest.approx(
            1.8, rel=0.01
        )
        assert "hour_values" in saved_data_ata
        # New format: hour_values[unit_id][measure][timestamp] = value
        assert saved_data_ata["hour_values"][TEST_UNIT_ID]["consumed"][
            "2025-01-15T12:00:00Z"
        ] == pytest.approx(0.7, rel=0.01)


@pytest.mark.asyncio
async def test_corrupt_hourly_energy_value_rejected(hass: HomeAssistant) -> None:
    """Test that an implausible hourly energy value from the cloud is rejected.

    Reproduces GitHub issue #161: the MELCloud cloud API occasionally returns
    a corrupt hourly value of ~6,553,600 Wh (~65536 * 100 Wh, consistent with
    a 16-bit counter wrap) for a single hour. Without a sanity check, this
    delta is added straight into the cumulative total, permanently inflating
    it by ~6553.6 kWh.

    Validates: GitHub issue #161 - corrupt energy value accepted without check
    Tests through: hass.states (sensor total excludes the corrupt spike)
    """
    # Initial state: 12:00 hour already fully processed (3100 Wh = 3.1 kWh),
    # matching the issue's reported baseline before the corrupt spike.
    initial_storage = {
        "cumulative": {TEST_UNIT_ID: 3.1},
        "hour_values": {TEST_UNIT_ID: {"2026-06-30T12:00:00Z": 3.1}},
    }

    # New energy data includes the corrupt spike reported in the issue
    mock_energy_data = create_mock_energy_response(
        [
            ("2026-06-30T12:00:00Z", 3100.0),  # Already processed - skip
            ("2026-06-30T13:00:00Z", 6553300.0),  # CORRUPT - must be rejected
            ("2026-06-30T14:00:00Z", 800.0),  # NEW - add 0.8 kWh (legitimate)
        ]
    )

    async with setup_energy_entry(
        hass, initial_storage, mock_energy_data
    ) as mock_store:
        state = hass.states.get("sensor.melcloudhome_a1b2_9abc_energy")
        assert state is not None

        # Expected: 3.1 (initial, 12:00 already seen) + 0.8 (14:00, legitimate)
        # = 3.9 kWh. The corrupt 13:00 spike (~6553.3 kWh) must NOT be added.
        assert float(state.state) == pytest.approx(3.9, rel=0.01)

        saved_data = mock_store.async_save.call_args_list[0][0][0]
        assert saved_data["cumulative"][TEST_UNIT_ID]["consumed"] == pytest.approx(
            3.9, rel=0.01
        )
        # Corrupt hour must not be persisted as a seen value either, so a
        # later corrected reading for that hour can still be accepted.
        assert (
            "2026-06-30T13:00:00Z"
            not in saved_data["hour_values"][TEST_UNIT_ID]["consumed"]
        )


@pytest.mark.asyncio
async def test_corrupt_reading_rejection_warns_only_once(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that a re-sent corrupt reading is only warned about once.

    The cloud re-sends the same corrupt hour on every poll (observed for
    days after the event), which produced an identical WARNING every 30
    minutes. The first rejection must warn; repeats of the same
    (unit, measure, hour) must stay silent.

    Validates: GitHub issue #161 follow-up - rejection log spam
    Tests through: caplog (log output is the observable behavior here)
    """
    initial_storage = {
        "cumulative": {TEST_UNIT_ID: 3.1},
        "hour_values": {TEST_UNIT_ID: {"2026-06-30T12:00:00Z": 3.1}},
    }
    mock_energy_data = create_mock_energy_response(
        [
            ("2026-06-30T12:00:00Z", 3100.0),  # Already processed - skip
            ("2026-06-30T13:00:00Z", 6553300.0),  # CORRUPT - rejected every poll
        ]
    )

    async with setup_energy_entry(hass, initial_storage, mock_energy_data):
        assert caplog.text.count("exceeds sanity ceiling") == 1

        # Advance past the energy update interval - the mock re-sends the
        # same corrupt hour, mirroring observed cloud behavior.
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=31))
        await hass.async_block_till_done()

        assert caplog.text.count("exceeds sanity ceiling") == 1


@pytest.mark.asyncio
async def test_all_corrupt_first_init_completes_and_does_not_loop(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that first init with only implausible readings completes.

    If every reading in the lookback window is corrupt, nothing was stored,
    so the tracker re-ran first initialization on every poll - re-warning
    for every hour, forever, and never starting delta tracking. Init must
    complete by keeping a 0.0 placeholder (mirroring the all-corrupt
    self-heal strategy), so the next poll takes the throttled rejection
    path instead of re-initializing.

    Validates: GitHub issue #161 follow-up - all-corrupt first init loop
    Tests through: hass.states + caplog (init must not repeat)
    """
    mock_energy_data = create_mock_energy_response(
        [
            ("2026-06-30T12:00:00Z", 6553300.0),  # CORRUPT
            ("2026-06-30T13:00:00Z", 6553400.0),  # CORRUPT
        ]
    )

    async with setup_energy_entry(hass, None, mock_energy_data):
        state = hass.states.get("sensor.melcloudhome_a1b2_9abc_energy")
        assert state is not None
        assert float(state.state) == 0.0
        assert caplog.text.count("Initializing consumed tracking") == 1

        # Second poll re-sends the same all-corrupt window.
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=31))
        await hass.async_block_till_done()

        # Init must not run again, and the re-sent corrupt hours must go
        # through the warn-once rejection path, not the init path.
        assert caplog.text.count("Initializing consumed tracking") == 1
        assert caplog.text.count("- skipping") == 2  # once per hour, init only


@pytest.mark.asyncio
async def test_corrupt_historical_value_self_heals_on_load(
    hass: HomeAssistant,
) -> None:
    """Test that a previously-persisted corrupt value is purged on load.

    Reproduces the "already polluted" half of GitHub issue #161: installs
    that hit the corrupt cloud reading before the sanity check existed have
    it permanently baked into their stored cumulative total. On upgrade,
    the tracker should detect the implausible historical hour_value entry,
    drop it, and reset the cumulative total to 0.0. Resetting (rather than
    subtracting back to the true total) matters because HA's
    total_increasing reset handling records the post-revision state as new
    consumption - landing on 0.0 records nothing, while landing on the true
    total would record a phantom consumption of that entire amount.

    Note: this only heals the integration's own persisted counter. Home
    Assistant's Long-Term Statistics (Energy Dashboard history) are
    recorded separately and are not touched by this - the user still needs
    HA's built-in "Adjust statistics" tool for the affected day.

    Validates: GitHub issue #161 - fixing already-polluted stored totals
    Tests through: hass.states (sensor total is corrected after setup)
    """
    # Simulates a pre-fix install: the corrupt 13:00 spike was already
    # added in full to the cumulative total and recorded in hour_values.
    polluted_storage = {
        "cumulative": {
            TEST_UNIT_ID: {"consumed": 6556.4}
        },  # 3.1 + 6553.3 legit+corrupt
        "hour_values": {
            TEST_UNIT_ID: {
                "consumed": {
                    "2026-06-30T12:00:00Z": 3.1,
                    "2026-06-30T13:00:00Z": 6553.3,  # corrupt - must be purged
                }
            }
        },
    }

    # No new data this poll - just verifying the load-time self-heal
    mock_energy_data = create_mock_energy_response(
        [
            ("2026-06-30T12:00:00Z", 3100.0),
            ("2026-06-30T13:00:00Z", 6553300.0),
        ]
    )

    async with setup_energy_entry(
        hass, polluted_storage, mock_energy_data
    ) as mock_store:
        state = hass.states.get("sensor.melcloudhome_a1b2_9abc_energy")
        assert state is not None

        # Expected: cumulative reset to 0.0 after the purge. The 12:00 and
        # 13:00 hours were already seen (same values in this poll), so no
        # new delta is added.
        assert float(state.state) == pytest.approx(0.0, abs=1e-9)

        # The purge should have persisted immediately during async_setup,
        # before any new energy poll ran - check the earliest ATA save.
        saved_data = mock_store.async_save.call_args_list[0][0][0]
        assert saved_data["cumulative"][TEST_UNIT_ID]["consumed"] == pytest.approx(
            0.0, abs=1e-9
        )
        assert (
            "2026-06-30T13:00:00Z"
            not in saved_data["hour_values"][TEST_UNIT_ID]["consumed"]
        )


@pytest.mark.asyncio
async def test_all_corrupt_hour_values_self_heal_keeps_delta_tracking(
    hass: HomeAssistant,
) -> None:
    """Test self-heal when EVERY persisted hour_values entry is corrupt.

    Edge case of GitHub issue #161's self-heal: if a unit's entire persisted
    hour_values consists of implausible entries (e.g. a device whose very
    first tracked hour was the corrupt reading), purging them all would
    empty the dict. _is_first_initialization() would then treat the device
    as brand-new on the next poll, silently absorbing that poll's real
    energy as "historical" instead of counting it.

    The purge must instead keep the most recent corrupt entry's timestamp
    as a 0.0 placeholder: the cumulative total is still fully healed, and
    the next poll's legitimate values are counted as normal deltas.

    Validates: GitHub issue #161 - self-heal must never empty hour_values
    Tests through: hass.states (next poll's real energy is counted)
    """
    now = datetime.now(UTC)
    corrupt_ts = (now - timedelta(hours=3)).isoformat()
    new_hour_1 = (now - timedelta(hours=2)).isoformat()
    new_hour_2 = (now - timedelta(hours=1)).isoformat()

    # Pre-fix install where the ONLY entry ever recorded is the corrupt one.
    polluted_storage = {
        "cumulative": {TEST_UNIT_ID: {"consumed": 6553.3}},
        "hour_values": {TEST_UNIT_ID: {"consumed": {corrupt_ts: 6553.3}}},
    }

    # Next poll: API re-sends the corrupt hour (rejected by the ceiling)
    # plus two legitimate new hours that MUST be counted.
    mock_energy_data = create_mock_energy_response(
        [
            (corrupt_ts, 6553300.0),  # corrupt - rejected
            (new_hour_1, 500.0),  # NEW - add 0.5 kWh
            (new_hour_2, 800.0),  # NEW - add 0.8 kWh
        ]
    )

    async with setup_energy_entry(
        hass, polluted_storage, mock_energy_data
    ) as mock_store:
        state = hass.states.get("sensor.melcloudhome_a1b2_9abc_energy")
        assert state is not None

        # Cumulative healed to 0.0, then the poll's two legitimate hours
        # counted as normal deltas: 0.5 + 0.8 = 1.3 kWh. If hour_values had
        # been emptied, the poll would be absorbed as first-init and the
        # sensor would wrongly read 0.0.
        assert float(state.state) == pytest.approx(1.3, rel=0.01)

        # The self-heal save (earliest): cumulative healed, and the corrupt
        # hour kept as a 0.0 placeholder rather than the dict going empty.
        saved_data = mock_store.async_save.call_args_list[0][0][0]
        assert saved_data["cumulative"][TEST_UNIT_ID]["consumed"] == pytest.approx(
            0.0, abs=1e-9
        )
        assert saved_data["hour_values"][TEST_UNIT_ID]["consumed"] == {corrupt_ts: 0.0}


@pytest.mark.asyncio
async def test_stale_hour_values_pruned_on_load(hass: HomeAssistant) -> None:
    """Test that hour_values entries older than the retention window are pruned.

    hour_values only needs to cover the API's polling lookback window
    (DATA_LOOKBACK_HOURS_ENERGY) - once an hour falls outside
    HOUR_VALUE_RETENTION_HOURS, the API will never return that timestamp
    again, so the entry can never be looked up again. Without pruning,
    this dict grows unbounded for the lifetime of the install.

    Validates: bounded hour_values retention (companion to GitHub issue #161)
    Tests through: hass.states + persisted storage (stale entry removed,
    cumulative total and recent entry left untouched by pruning alone)
    """
    now = datetime.now(UTC)
    stale_timestamp = (
        now - timedelta(hours=HOUR_VALUE_RETENTION_HOURS + 24)
    ).isoformat()
    recent_timestamp = (now - timedelta(hours=1)).isoformat()

    initial_storage = {
        "cumulative": {TEST_UNIT_ID: {"consumed": 5.0}},
        "hour_values": {
            TEST_UNIT_ID: {
                "consumed": {
                    stale_timestamp: 1.0,  # outside retention window - pruned
                    recent_timestamp: 0.5,  # inside retention window - kept
                }
            }
        },
    }

    # Same recent hour, same value - already seen, no new delta
    mock_energy_data = create_mock_energy_response([(recent_timestamp, 500.0)])

    async with setup_energy_entry(
        hass, initial_storage, mock_energy_data
    ) as mock_store:
        state = hass.states.get("sensor.melcloudhome_a1b2_9abc_energy")
        assert state is not None
        # Pruning stale entries alone must not touch the cumulative total -
        # only implausible-value purging does that.
        assert float(state.state) == pytest.approx(5.0, rel=0.01)

        # The pruning save happens during async_setup, before the energy
        # poll runs - check the earliest ATA save.
        saved_data = mock_store.async_save.call_args_list[0][0][0]
        hour_values = saved_data["hour_values"][TEST_UNIT_ID]["consumed"]
        assert stale_timestamp not in hour_values
        assert recent_timestamp in hour_values


@pytest.mark.asyncio
async def test_double_hour_prevention(hass: HomeAssistant) -> None:
    """Test that same hour is never counted twice.

    When energy data is fetched multiple times with overlapping hours:
    1. Coordinator tracks last processed hour timestamp
    2. Only processes hours AFTER the last processed hour
    3. Cumulative total doesn't increase for already-processed hours

    Validates: Double-counting prevention works correctly
    Tests through: hass.states (total doesn't increase on duplicate)
    """
    mock_context = create_mock_ata_energy_context()

    # Timestamps must be recent (within HOUR_VALUE_RETENTION_HOURS) - the
    # real API only ever reports hours within its lookback window, so a
    # "duplicate old hour" scenario using stale timestamps isn't realistic
    # and would be pruned by _clean_hour_values before this test's poll runs.
    hour_10 = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    hour_11 = (datetime.now(UTC) - timedelta(hours=1)).isoformat()

    # Initial state: 2 hours already processed
    initial_storage = {
        "cumulative": {TEST_UNIT_ID: 1.1},  # 1.1 kWh already
        "hour_values": {
            TEST_UNIT_ID: {
                hour_10: 0.5,  # Already processed
                hour_11: 0.6,  # Already processed
            }
        },
    }

    # Energy response has SAME hours again with SAME values (should skip all)
    mock_energy_data_duplicate = create_mock_energy_response(
        [
            (hour_10, 500.0),  # Same value - skip
            (hour_11, 600.0),  # Same value - skip
        ]
    )

    with (
        patch(MOCK_CLIENT_PATH) as mock_client_class,
        patch(MOCK_STORE_PATH) as mock_store_class,
    ):
        # Set up mock client
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        mock_client.get_energy_data = AsyncMock(return_value=mock_energy_data_duplicate)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        # Mock storage
        mock_store = mock_store_class.return_value
        mock_store.async_load = AsyncMock(return_value=initial_storage)
        mock_store.async_save = AsyncMock()

        # Set up integration
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # ✅ CORRECT: Assert through state machine
        state = hass.states.get("sensor.melcloudhome_a1b2_9abc_energy")
        assert state is not None

        # Should still be 1.1 kWh (no new hours added)
        assert float(state.state) == pytest.approx(1.1, rel=0.01)

        # Verify hour_values unchanged (no deltas) - new multi-measure format
        saved_data = mock_store.async_save.call_args_list[0][0][
            0
        ]  # First call (ATA tracker)
        assert saved_data["hour_values"][TEST_UNIT_ID]["consumed"][
            hour_11
        ] == pytest.approx(0.6, rel=0.01)


@pytest.mark.asyncio
async def test_energy_topping_up_progressive_updates(hass: HomeAssistant) -> None:
    """Test that hour values are topped up as they increase (PROGRESSIVE UPDATES).

    Real API behavior: Same hour value increases progressively as device uploads data
    - Poll 1 at 09:05: 09:00 = 100 Wh (5 mins into hour, partial data)
    - Poll 2 at 09:39: 09:00 = 300 Wh (39 mins, increased by 200 Wh)
    - Poll 3 at 10:03: 09:00 = 400 Wh (past hour end, final value, increased by 100 Wh)

    Integration MUST track per-hour values and add deltas when values increase.
    Current bug: Only processes each hour once (timestamp comparison), missing increases.

    This test uses real data pattern from tools/energy_recording_dining_room.json

    Expected behavior:
    - Poll 1: Add 0.1 kWh → cumulative = 10.1 kWh
    - Poll 2: Add delta 0.2 kWh (0.3 - 0.1) → cumulative = 10.3 kWh
    - Poll 3: Add delta 0.1 kWh (0.4 - 0.3) + new hour 0.1 kWh → cumulative = 10.5 kWh

    Current bug behavior:
    - Poll 1: Add 0.1 kWh → cumulative = 10.1 kWh
    - Poll 2: Skip (not "newer" than 09:00) → cumulative = 10.1 kWh ✗
    - Poll 3: Skip 09:00, add 10:00 → cumulative = 10.2 kWh ✗

    Result: 60-75% energy undercount (tracks 0.2 kWh instead of 0.5 kWh)

    Validates: GitHub issue #23 - Wrong amount of consumed energy
    Tests through: hass.states (sensor shows correct accumulated total)
    """
    mock_context = create_mock_ata_energy_context()

    # Initial state: 10.0 kWh already accumulated, no hour tracking yet
    initial_storage = {
        "cumulative": {TEST_UNIT_ID: 10.0},
        "hour_values": {TEST_UNIT_ID: {}},  # Empty - using new format
    }

    with (
        patch(MOCK_CLIENT_PATH) as mock_client_class,
        patch(MOCK_STORE_PATH) as mock_store_class,
    ):
        # Set up mock client
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        # Mock storage
        mock_store = mock_store_class.return_value
        mock_store.async_load = AsyncMock(return_value=initial_storage)
        mock_store.async_save = AsyncMock()

        # Set up integration
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)

        # === POLL 1 at 09:05: 09:00 hour shows 100 Wh (partial) ===
        mock_client.get_energy_data = AsyncMock(
            return_value=create_mock_energy_response(
                [("2025-12-09 09:00:00.000000000", 100.0)]
            )
        )
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # ✅ Should be 10.0 + 0.1 = 10.1 kWh
        state = hass.states.get("sensor.melcloudhome_a1b2_9abc_energy")
        assert state is not None
        assert float(state.state) == pytest.approx(10.1, rel=0.01)

        # === POLL 2 at 09:39: 09:00 hour increased to 300 Wh ===
        coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        mock_client.get_energy_data = AsyncMock(
            return_value=create_mock_energy_response(
                [("2025-12-09 09:00:00.000000000", 300.0)]  # Increased from 100!
            )
        )
        await coordinator.energy_tracker.async_update_energy_data()
        coordinator.energy_tracker.update_unit_energy_data(coordinator._units)
        coordinator.async_update_listeners()
        await hass.async_block_till_done()

        # ✅ Should add delta: 0.3 - 0.1 = 0.2 kWh → 10.1 + 0.2 = 10.3 kWh
        state = hass.states.get("sensor.melcloudhome_a1b2_9abc_energy")
        assert float(state.state) == pytest.approx(10.3, rel=0.01)
        # ❌ WILL FAIL with current code: stays at 10.1 (skips "old" hour)

        # === POLL 3 at 10:03: 09:00 finalized at 400 Wh, new 10:00 hour ===
        mock_client.get_energy_data = AsyncMock(
            return_value=create_mock_energy_response(
                [
                    ("2025-12-09 09:00:00.000000000", 400.0),  # Increased to 400
                    ("2025-12-09 10:00:00.000000000", 100.0),  # New hour
                ]
            )
        )
        await coordinator.energy_tracker.async_update_energy_data()
        coordinator.energy_tracker.update_unit_energy_data(coordinator._units)
        coordinator.async_update_listeners()
        await hass.async_block_till_done()

        # ✅ Should add: delta 09:00 (0.1) + new 10:00 (0.1) = 0.2 kWh
        # 10.3 + 0.2 = 10.5 kWh
        state = hass.states.get("sensor.melcloudhome_a1b2_9abc_energy")
        assert float(state.state) == pytest.approx(10.5, rel=0.01)
        # ❌ WILL FAIL with current code: would be 10.2 (skips 09:00 delta, adds 10:00)

        # Verify storage has hour values tracking (new multi-measure format)
        # Check the last ATA tracker save (after poll 3)
        # Saves in this test: setup_ata (0), setup_atw (1), poll2_ata (2), poll3_ata (3)
        # Manual coordinator calls don't trigger ATW saves, only ATA
        # Last ATA save is index 3
        saved_data = mock_store.async_save.call_args_list[3][0][0]

        assert "hour_values" in saved_data
        assert saved_data["hour_values"][TEST_UNIT_ID]["consumed"][
            "2025-12-09 09:00:00.000000000"
        ] == pytest.approx(0.4, rel=0.001)
        assert saved_data["hour_values"][TEST_UNIT_ID]["consumed"][
            "2025-12-09 10:00:00.000000000"
        ] == pytest.approx(0.1, rel=0.001)


@pytest.mark.asyncio
async def test_energy_persistence_across_restarts(hass: HomeAssistant) -> None:
    """Test that energy data persists across Home Assistant restarts.

    When HA restarts:
    1. Coordinator loads cumulative totals from storage
    2. Coordinator loads last processed hour timestamps
    3. Sensors show correct accumulated values immediately
    4. New energy data continues accumulation from stored values

    Validates: Storage persistence works correctly
    Tests through: hass.states (sensor shows persisted value)
    """
    mock_context = create_mock_ata_energy_context()

    # Simulated persisted data from previous session
    persisted_storage = {
        "cumulative": {TEST_UNIT_ID: 25.7},  # 25.7 kWh total
        "hour_values": {
            TEST_UNIT_ID: {
                "2025-01-14T23:00:00Z": 0.8  # Last processed value
            }
        },
    }

    # New energy data after restart (1 new hour)
    mock_energy_data = create_mock_energy_response(
        [
            ("2025-01-14T23:00:00Z", 800.0),  # Same value - skip
            ("2025-01-15T00:00:00Z", 900.0),  # NEW - add 0.9 kWh
        ]
    )

    with (
        patch(MOCK_CLIENT_PATH) as mock_client_class,
        patch(MOCK_STORE_PATH) as mock_store_class,
    ):
        # Set up mock client
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        mock_client.get_energy_data = AsyncMock(return_value=mock_energy_data)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        # Mock storage with persisted data
        mock_store = mock_store_class.return_value
        mock_store.async_load = AsyncMock(return_value=persisted_storage)
        mock_store.async_save = AsyncMock()

        # Set up integration (simulates restart)
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # ✅ CORRECT: Assert through state machine
        state = hass.states.get("sensor.melcloudhome_a1b2_9abc_energy")
        assert state is not None

        # Expected: 25.7 (persisted) + 0.9 (new hour) = 26.6 kWh
        assert float(state.state) == pytest.approx(26.6, rel=0.01)

        # Verify storage saved new total (new multi-measure format)
        saved_data = mock_store.async_save.call_args_list[0][0][
            0
        ]  # First call (ATA tracker)
        assert saved_data["cumulative"][TEST_UNIT_ID]["consumed"] == pytest.approx(
            26.6, rel=0.01
        )


@pytest.mark.asyncio
async def test_storage_migration_from_v1_3_4_to_v2_0(hass: HomeAssistant) -> None:
    """Test migration from v1.3.4 single-measure to v2.0 multi-measure format.

    When upgrading from v1.3.4 stable to v2.0:
    1. Storage contains v1.3.4 format: {unit_id: float}
    2. Migration detects legacy format and converts to multi-measure
    3. Data is preserved under "consumed" measure
    4. Hour values are also migrated correctly
    5. Proper log message indicates migration occurred

    v1.3.4 format:
        cumulative: {unit_id: cumulative_kwh}
        hour_values: {unit_id: {timestamp: kwh}}

    v2.0 format:
        cumulative: {unit_id: {measure: cumulative_kwh}}
        hour_values: {unit_id: {measure: {timestamp: kwh}}}

    Validates: Backward compatibility migration works correctly
    Tests through: Storage format conversion and functionality
    """
    mock_context = create_mock_ata_energy_context()

    # Timestamps must be recent (within HOUR_VALUE_RETENTION_HOURS) - the
    # real API only ever reports hours within its lookback window, so a
    # "duplicate old hour" scenario using stale timestamps isn't realistic
    # and would be pruned by _clean_hour_values before this test's poll runs.
    hour_10 = (datetime.now(UTC) - timedelta(hours=3)).isoformat()
    hour_11 = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    hour_12 = (datetime.now(UTC) - timedelta(hours=1)).isoformat()

    # v1.3.4 storage format (single-measure)
    v1_3_4_storage = {
        "cumulative": {
            TEST_UNIT_ID: 15.3  # Single float value (v1.3.4 format)
        },
        "hour_values": {
            TEST_UNIT_ID: {
                hour_10: 0.5,  # Direct timestamp mapping (v1.3.4)
                hour_11: 0.6,
            }
        },
    }

    # New energy data after migration (1 new hour to verify accumulation still works)
    mock_energy_data = create_mock_energy_response(
        [
            (hour_10, 500.0),  # Already tracked - skip
            (hour_11, 600.0),  # Already tracked - skip
            (hour_12, 700.0),  # NEW - add 0.7 kWh
        ]
    )

    with (
        patch(MOCK_CLIENT_PATH) as mock_client_class,
        patch(MOCK_STORE_PATH) as mock_store_class,
    ):
        # Set up mock client
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        mock_client.get_energy_data = AsyncMock(return_value=mock_energy_data)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        # Mock storage with v1.3.4 format
        mock_store = mock_store_class.return_value
        mock_store.async_load = AsyncMock(return_value=v1_3_4_storage)
        mock_store.async_save = AsyncMock()

        # Set up integration (triggers migration)
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # ✅ Verify sensor exists and shows migrated value + new accumulation
        state = hass.states.get("sensor.melcloudhome_a1b2_9abc_energy")
        assert state is not None
        # Expected: 15.3 (migrated from v1.3.4) + 0.7 (new hour) = 16.0 kWh
        assert float(state.state) == pytest.approx(16.0, rel=0.01)

        # ✅ Verify saved data is in v2.0 multi-measure format
        mock_store.async_save.assert_called()
        saved_data = mock_store.async_save.call_args_list[0][0][0]  # First call (ATA)

        # Check cumulative is now multi-measure format
        assert isinstance(saved_data["cumulative"][TEST_UNIT_ID], dict)
        assert "consumed" in saved_data["cumulative"][TEST_UNIT_ID]
        assert saved_data["cumulative"][TEST_UNIT_ID]["consumed"] == pytest.approx(
            16.0, rel=0.01
        )

        # Check hour_values is now multi-measure format
        assert isinstance(saved_data["hour_values"][TEST_UNIT_ID], dict)
        assert "consumed" in saved_data["hour_values"][TEST_UNIT_ID]
        assert saved_data["hour_values"][TEST_UNIT_ID]["consumed"][
            hour_10
        ] == pytest.approx(0.5, rel=0.01)
        assert saved_data["hour_values"][TEST_UNIT_ID]["consumed"][
            hour_12
        ] == pytest.approx(0.7, rel=0.01)


@pytest.mark.asyncio
async def test_storage_no_migration_for_v2_0_format(hass: HomeAssistant) -> None:
    """Test that v2.0 format is loaded without migration.

    When storage already contains v2.0 multi-measure format:
    1. Migration logic detects v2.0 format
    2. Data is restored as-is without conversion
    3. Proper log message indicates restoration (not migration)

    Validates: v2.0 → v2.0 upgrade path works correctly
    Tests through: Storage format detection and loading
    """
    mock_context = create_mock_ata_energy_context()

    # Timestamps must be recent (within HOUR_VALUE_RETENTION_HOURS) - the
    # real API only ever reports hours within its lookback window, so a
    # "duplicate old hour" scenario using stale timestamps isn't realistic
    # and would be pruned by _clean_hour_values before this test's poll runs.
    hour_10 = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    hour_11 = (datetime.now(UTC) - timedelta(hours=1, minutes=30)).isoformat()
    hour_12 = (datetime.now(UTC) - timedelta(hours=1)).isoformat()

    # v2.0 storage format (multi-measure)
    v2_0_storage = {
        "cumulative": {
            TEST_UNIT_ID: {
                "consumed": 20.5,  # Multi-measure format (v2.0)
                "produced": 5.2,  # Multiple measures supported
            }
        },
        "hour_values": {
            TEST_UNIT_ID: {
                "consumed": {
                    hour_10: 0.5,
                    hour_11: 0.6,
                },
                "produced": {
                    hour_10: 0.2,
                    hour_11: 0.3,
                },
            }
        },
    }

    # New energy data (1 new hour)
    mock_energy_data = create_mock_energy_response(
        [
            (hour_11, 600.0),  # Already tracked - skip
            (hour_12, 700.0),  # NEW - add 0.7 kWh
        ]
    )

    with (
        patch(MOCK_CLIENT_PATH) as mock_client_class,
        patch(MOCK_STORE_PATH) as mock_store_class,
    ):
        # Set up mock client
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        mock_client.get_energy_data = AsyncMock(return_value=mock_energy_data)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        # Mock storage with v2.0 format
        mock_store = mock_store_class.return_value
        mock_store.async_load = AsyncMock(return_value=v2_0_storage)
        mock_store.async_save = AsyncMock()

        # Set up integration (no migration should occur)
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # ✅ Verify sensor exists and shows restored value + new accumulation
        state = hass.states.get("sensor.melcloudhome_a1b2_9abc_energy")
        assert state is not None
        # Expected: 20.5 (restored from v2.0) + 0.7 (new hour) = 21.2 kWh
        assert float(state.state) == pytest.approx(21.2, rel=0.01)

        # ✅ Verify saved data remains in v2.0 format
        mock_store.async_save.assert_called()
        saved_data = mock_store.async_save.call_args_list[0][0][0]  # First call (ATA)

        # Check cumulative is still multi-measure format
        assert isinstance(saved_data["cumulative"][TEST_UNIT_ID], dict)
        assert saved_data["cumulative"][TEST_UNIT_ID]["consumed"] == pytest.approx(
            21.2, rel=0.01
        )

        # Check hour_values structure preserved
        assert isinstance(saved_data["hour_values"][TEST_UNIT_ID]["consumed"], dict)
        assert saved_data["hour_values"][TEST_UNIT_ID]["consumed"][
            hour_12
        ] == pytest.approx(0.7, rel=0.01)


@pytest.mark.asyncio
async def test_energy_update_failure_recovery(hass: HomeAssistant) -> None:
    """Test that energy update failures don't crash the integration.

    When energy API call fails during initial setup:
    1. Coordinator logs error but doesn't crash
    2. Integration continues to function normally
    3. Sensor is created but shows as unavailable (no data fetched yet)
    4. Stored cumulative totals are preserved in coordinator state

    Note: Current behavior shows sensor as unavailable when initial fetch fails.
    This is because unit.energy_consumed is only set after successful API fetch.

    Validates: Error handling prevents integration crash
    Tests through: hass.states (sensor exists but unavailable)
    """
    mock_context = create_mock_ata_energy_context()

    # Initial state with some accumulated energy (simulating previous session)
    initial_storage = {
        "cumulative": {TEST_UNIT_ID: 5.5},
        "last_hour": {TEST_UNIT_ID: "2025-01-15T10:00:00Z"},
    }

    with (
        patch(MOCK_CLIENT_PATH) as mock_client_class,
        patch(MOCK_STORE_PATH) as mock_store_class,
    ):
        # Set up mock client - energy fetch will fail
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        # Simulate API error on energy fetch
        mock_client.get_energy_data = AsyncMock(side_effect=Exception("API timeout"))
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        # Mock storage
        mock_store = mock_store_class.return_value
        mock_store.async_load = AsyncMock(return_value=initial_storage)
        mock_store.async_save = AsyncMock()

        # Set up integration
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # ✅ CORRECT: Assert through state machine
        state = hass.states.get("sensor.melcloudhome_a1b2_9abc_energy")
        assert state is not None

        # Current behavior: sensor shows unavailable when initial fetch fails
        # This is because unit.energy_consumed is None (not populated from storage)
        assert state.state == "unavailable"

        # Verify integration didn't crash - other sensors still work
        climate_state = hass.states.get("climate.melcloudhome_a1b2_9abc_climate")
        assert climate_state is not None
        assert climate_state.state == "heat"  # Climate entity still functional


@pytest.mark.asyncio
async def test_energy_polling_cancellation_on_shutdown(hass: HomeAssistant) -> None:
    """Test that energy polling is properly cancelled on shutdown.

    When integration is unloaded:
    1. Coordinator's async_shutdown() is called
    2. Energy polling task is cancelled
    3. No further energy updates occur
    4. Client is closed properly

    Validates: Clean shutdown prevents resource leaks
    Tests through: Integration setup/teardown
    """
    mock_context = create_mock_ata_energy_context()

    # Mock energy data (will only be called during initial setup)
    mock_energy_data = create_mock_energy_response([("2025-01-15T10:00:00Z", 500.0)])

    with (
        patch(MOCK_CLIENT_PATH) as mock_client_class,
        patch(MOCK_STORE_PATH) as mock_store_class,
    ):
        # Set up mock client
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        mock_client.get_energy_data = AsyncMock(return_value=mock_energy_data)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        # Mock storage
        mock_store = mock_store_class.return_value
        mock_store.async_load = AsyncMock(return_value=None)
        mock_store.async_save = AsyncMock()

        # Set up integration
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Verify sensor exists
        state = hass.states.get("sensor.melcloudhome_a1b2_9abc_energy")
        assert state is not None

        # Reset call count after setup
        initial_calls = mock_client.get_energy_data.call_count

        # ✅ CORRECT: Unload through core interface
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

        # Verify client.close() was called (part of shutdown)
        mock_client.close.assert_called()

        # Verify no additional energy fetches after unload
        # (Polling task should be cancelled)
        assert mock_client.get_energy_data.call_count == initial_calls
