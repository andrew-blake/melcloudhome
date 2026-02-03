"""VCR tests for outdoor temperature API.

Tests outdoor temperature retrieval against real API responses.
Uses VCR cassettes to record/replay HTTP interactions.

Recording VCR cassettes:
1. Set credentials: export MELCLOUD_USER=email MELCLOUD_PASSWORD=password
2. Delete existing cassette: rm tests/api/cassettes/test_get_outdoor_temperature*.yaml
3. Run test: pytest tests/api/test_outdoor_temperature_vcr.py -v
4. Cassette will be recorded automatically

Reference: docs/testing-best-practices.md
"""

from typing import TYPE_CHECKING

import pytest
from freezegun import freeze_time

if TYPE_CHECKING:
    from custom_components.melcloudhome.api.client import MELCloudHomeClient


@freeze_time("2026-02-03 12:30:00", real_asyncio=True)
@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_get_outdoor_temperature(
    authenticated_client: "MELCloudHomeClient",
) -> None:
    """Test fetching outdoor temperature for ATA unit.

    Note: Outdoor temperature is discovered at runtime - response may be
    a float (device has outdoor sensor) or None (device lacks sensor).
    Both are valid responses and tested here.
    """
    # Get user context to find ATA units
    context = await authenticated_client.get_user_context()

    # Find first ATA unit
    unit = None
    for building in context.buildings:
        for ata_unit in building.air_to_air_units:
            unit = ata_unit
            break
        if unit:
            break

    if not unit:
        pytest.skip("No ATA units found")

    # Get outdoor temperature
    assert unit is not None  # Type narrowing
    result = await authenticated_client.get_outdoor_temperature(unit.id)

    # Verify response - either float or None (both valid)
    if result is not None:
        assert isinstance(result, float)
        assert -50.0 <= result <= 50.0  # Reasonable temperature range
    # else: None is valid (device lacks outdoor sensor)
