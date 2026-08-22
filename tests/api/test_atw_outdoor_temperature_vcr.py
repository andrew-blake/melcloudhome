"""VCR tests for ATW outdoor temperature via the comfort-graph report API.

Unlike ATA (whose live /context OutdoorTemperature is always absent), ATW's
live value can be present but silently wrong with no way to tell from the
value alone (issue #251) — so ATW always queries the comfort-graph report
instead of trusting the live value.

Recording VCR cassettes:
1. Set credentials: export MELCLOUD_USER=email MELCLOUD_PASSWORD=password
2. Delete existing cassette: rm tests/api/cassettes/test_get_atw_outdoor_temperature*.yaml
3. Run test: pytest tests/api/test_atw_outdoor_temperature_vcr.py -v
4. Cassette will be recorded automatically

Reference: docs/testing-best-practices.md
"""

from typing import TYPE_CHECKING

import pytest
from freezegun import freeze_time

if TYPE_CHECKING:
    from custom_components.melcloudhome.api.client import MELCloudHomeClient


@freeze_time("2026-08-17 09:30:00", real_asyncio=True)
@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_get_atw_outdoor_temperature(
    authenticated_client: "MELCloudHomeClient",
) -> None:
    """Test fetching outdoor temperature for ATW unit via comfort-graph."""
    context = await authenticated_client.get_user_context()

    unit = None
    for building in context.buildings:
        for atw_unit in building.air_to_water_units:
            unit = atw_unit
            break
        if unit:
            break

    if not unit:
        pytest.skip("No ATW units found")

    assert unit is not None  # Type narrowing
    reading = await authenticated_client.get_atw_outdoor_temperature(unit.id)

    # Verify response - either a Reading or None (both valid)
    if reading is not None:
        assert isinstance(reading.value, float)
        assert -50.0 <= reading.value <= 50.0  # Reasonable temperature range
    # else: None is valid (no genuine reading in the lookback window)
