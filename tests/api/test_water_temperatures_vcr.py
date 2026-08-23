"""VCR test for ATW water temperatures via the internaltemperatures report.

The only test that exercises this endpoint against the real server. It is
recorded against a single-zone unit, so it covers the eight-dataset shape and
the constant-25 placeholders for absent hardware; the two-zone path has never
been observable (see ADR-023).

Recording VCR cassettes:
1. Set credentials: export MELCLOUD_USER=email MELCLOUD_PASSWORD=password
2. Delete existing cassette: rm tests/api/cassettes/test_get_atw_water_temperatures.yaml
3. Run test: pytest tests/api/test_water_temperatures_vcr.py -v
4. Cassette will be recorded automatically

The frozen clock is load-bearing: VCR matches on the query string, and the
request carries a from/to window derived from the clock.

Reference: docs/testing-best-practices.md, docs/api/atw-api-reference.md
"""

from typing import TYPE_CHECKING

import pytest
from freezegun import freeze_time

if TYPE_CHECKING:
    from custom_components.melcloudhome.api.client import MELCloudHomeClient

# Every dataset a single-zone unit returns, whether its hardware exists or not
EXPECTED_DATASET_IDS = {
    "set_tank_water_temperature",
    "tank_water_temperature",
    "flow_temperature",
    "return_temperature",
    "flow_temperature_zone1",
    "return_temperature_zone1",
    "flow_temperature_boiler",
    "return_temperature_boiler",
}


@freeze_time("2026-08-23 06:00:00", real_asyncio=True)
@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_get_atw_water_temperatures(
    authenticated_client: "MELCloudHomeClient",
) -> None:
    """Every water temperature arrives in one request, keyed by dataset id."""
    context = await authenticated_client.get_user_context()

    unit = next(
        (
            atw_unit
            for building in context.buildings
            for atw_unit in building.air_to_water_units
        ),
        None,
    )
    if unit is None:
        pytest.skip("No ATW units found")

    assert unit is not None  # Type narrowing
    readings = await authenticated_client.get_atw_water_temperatures(unit.id)

    # A dataset with no genuine point is omitted, so this is a subset check
    assert set(readings) <= EXPECTED_DATASET_IDS, (
        f"unexpected dataset ids: {set(readings) - EXPECTED_DATASET_IDS}"
    )
    assert "flow_temperature" in readings or "return_temperature" in readings, (
        "the unsuffixed pair is the whole point of the endpoint"
    )

    for dataset_id, reading in readings.items():
        assert 0.0 <= reading.value <= 90.0, f"{dataset_id}: {reading.value}"
        assert reading.recorded_at.tzinfo is not None, f"{dataset_id}: naive stamp"
        assert reading.recorded_at.second != 0, (
            f"{dataset_id}: seconds-aligned stamp means a synthetic point survived"
        )
