"""VCR test for get_wifi_signal against the real telemetry/actual endpoint.

Recorded for one ATA and one ATW unit, so both device types are evidenced on
the same request shape (ADR-028).

Recording VCR cassettes:
1. Set credentials: set -a; . ./.env; set +a   (MELCLOUD_USER / MELCLOUD_PASSWORD)
2. Delete existing cassette: rm tests/api/cassettes/test_get_wifi_signal.yaml
3. Move the frozen clock below to within the last day: the endpoint serves
   recent history, and VCR matches on the query string, which comes from it.
4. Run test: uv run pytest tests/api/test_wifi_signal_vcr.py -v

Reference: docs/testing-best-practices.md
"""

from typing import TYPE_CHECKING

import pytest
from freezegun import freeze_time

if TYPE_CHECKING:
    from custom_components.melcloudhome.api.client import MELCloudHomeClient


@freeze_time("2026-10-06 10:00:00", real_asyncio=True)
@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_get_wifi_signal(authenticated_client: "MELCloudHomeClient") -> None:
    """Both device types return an integer dBm reading with a UTC stamp."""
    context = await authenticated_client.get_user_context()
    ata = next((u for b in context.buildings for u in b.air_to_air_units), None)
    atw = next((u for b in context.buildings for u in b.air_to_water_units), None)
    if ata is None or atw is None:
        pytest.skip("Recording needs one ATA and one ATW unit")

    assert ata is not None and atw is not None  # Type narrowing
    for unit in (ata, atw):
        reading = await authenticated_client.get_wifi_signal(unit.id)
        assert reading is not None, f"{unit.id}: no reading"
        assert type(reading.value) is int
        assert -100 < reading.value < 0
        assert reading.recorded_at.tzinfo is not None
