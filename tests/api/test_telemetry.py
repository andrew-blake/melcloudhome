"""Tests for MELCloud Home telemetry API (ATW flow/return temperatures).

Tests cover telemetry data retrieval, parsing, and error handling.
Uses VCR cassettes to test against real API responses.

Recording VCR cassettes:
1. Set credentials in .env: MELCLOUD_USER, MELCLOUD_PASSWORD
2. Delete existing cassette: rm tests/api/cassettes/test_get_telemetry_*.yaml
3. Run test: pytest tests/api/test_telemetry.py -v --record-mode=once
4. Cassettes will be recorded automatically

Note: Tests will be skipped if no ATW units found in account.

Reference: docs/testing-best-practices.md
"""

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from freezegun import freeze_time

from custom_components.melcloudhome.api.client import MELCloudHomeClient
from custom_components.melcloudhome.api.exceptions import AuthenticationError

if TYPE_CHECKING:
    from custom_components.melcloudhome.api.client import MELCloudHomeClient

# Test all telemetry measures (6 temperature + 1 RSSI)
TEMPERATURE_MEASURES = [
    "flow_temperature",
    "return_temperature",
    "flow_temperature_zone1",
    "return_temperature_zone1",
    "flow_temperature_boiler",
    "return_temperature_boiler",
]


@freeze_time("2026-01-14 16:00:00", real_asyncio=True)
@pytest.mark.vcr()
@pytest.mark.asyncio
@pytest.mark.parametrize("measure", TEMPERATURE_MEASURES)
async def test_get_telemetry_measure(
    authenticated_client: "MELCloudHomeClient", atw_unit_id: str, measure: str
) -> None:
    """Test fetching telemetry for each temperature measure."""
    to_time = datetime.now(UTC)
    from_time = to_time - timedelta(hours=4)

    result = await authenticated_client.get_telemetry_actual(
        unit_id=atw_unit_id,
        from_time=from_time,
        to_time=to_time,
        measure=measure,
    )

    # Verify response structure
    assert result is not None
    assert isinstance(result, dict)
    assert "measureData" in result

    # Verify data if present (may be empty for boiler temps)
    if result["measureData"] and result["measureData"][0]["values"]:
        value = result["measureData"][0]["values"][0]
        assert "time" in value
        assert "value" in value
        temp = float(value["value"])
        assert 0 <= temp <= 100  # Reasonable range


@freeze_time("2026-01-14 16:00:00", real_asyncio=True)
@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_get_rssi_telemetry(
    authenticated_client: "MELCloudHomeClient", atw_unit_id: str
) -> None:
    """Test fetching RSSI (WiFi signal strength) telemetry."""
    to_time = datetime.now(UTC)
    from_time = to_time - timedelta(hours=4)

    result = await authenticated_client.get_telemetry_actual(
        unit_id=atw_unit_id,
        from_time=from_time,
        to_time=to_time,
        measure="rssi",
    )

    # Verify response structure
    assert result is not None
    assert isinstance(result, dict)
    assert "measureData" in result

    # Verify data if present
    if result["measureData"] and result["measureData"][0]["values"]:
        value = result["measureData"][0]["values"][0]
        assert "time" in value
        assert "value" in value
        rssi = float(value["value"])
        # RSSI range: -30 (excellent) to -90 (poor)
        assert -100 <= rssi <= 0


@freeze_time("2026-01-14 16:00:00", real_asyncio=True)
@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_get_telemetry_empty_response(
    authenticated_client: "MELCloudHomeClient", atw_unit_id: str
) -> None:
    """Test handling of empty telemetry response (old/inactive device)."""
    # Request very old data (likely empty)
    to_time = datetime.now(UTC) - timedelta(days=365)
    from_time = to_time - timedelta(hours=4)

    result = await authenticated_client.get_telemetry_actual(
        unit_id=atw_unit_id,
        from_time=from_time,
        to_time=to_time,
        measure="flow_temperature",
    )

    # Should still return valid structure
    assert result is not None
    assert isinstance(result, dict)
    assert "measureData" in result


@pytest.mark.asyncio
async def test_get_telemetry_unauthenticated() -> None:
    """Test telemetry request without authentication fails properly."""
    client = MELCloudHomeClient(debug_mode=False)

    to_time = datetime.now(UTC)
    from_time = to_time - timedelta(hours=4)

    with pytest.raises(AuthenticationError):
        await client.get_telemetry_actual(
            unit_id="fake-unit-id",
            from_time=from_time,
            to_time=to_time,
            measure="flow_temperature",
        )

    await client.close()


@freeze_time("2026-01-14 16:00:00", real_asyncio=True)
@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_parse_telemetry_values(
    authenticated_client: "MELCloudHomeClient", atw_unit_id: str
) -> None:
    """Test parsing telemetry values into usable format."""
    to_time = datetime.now(UTC)
    from_time = to_time - timedelta(hours=4)

    result = await authenticated_client.get_telemetry_actual(
        unit_id=atw_unit_id,
        from_time=from_time,
        to_time=to_time,
        measure="flow_temperature",
    )

    # Parse values like TelemetryTracker does
    if result and result.get("measureData"):
        values = result["measureData"][0].get("values", [])

        if values:
            # Get latest value
            latest = values[-1]
            latest_temp = float(latest["value"])

            # Verify temperature is reasonable
            assert isinstance(latest_temp, float)
            assert 0 <= latest_temp <= 100

            # Verify timestamp format
            time_str = latest["time"]
            assert isinstance(time_str, str)
            assert " " in time_str or "T" in time_str
