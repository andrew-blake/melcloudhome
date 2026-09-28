"""VCR test for the ATW combined-energy report (real response shape).

Recording: pick a local day inside the ~91-day history the API returns, set
RECORD_DAY below, then `source .env && uv run pytest tests/api/test_energy_report_vcr.py -v`.
The query string is part of VCR matching, so the window must stay fixed.
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from custom_components.melcloudhome.api.client import MELCloudHomeClient

RECORD_DAY = datetime(2026, 9, 24)  # a local day with ATW energy at recording time


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_get_energy_report_one_day(
    authenticated_client: MELCloudHomeClient,
) -> None:
    context = await authenticated_client.get_user_context()
    unit = next(
        u for b in context.buildings for u in b.air_to_water_units if u.time_zone
    )
    assert unit.time_zone is not None
    tz = ZoneInfo(unit.time_zone)
    day_from = RECORD_DAY.replace(tzinfo=tz).astimezone(UTC)
    day_to = (RECORD_DAY + timedelta(days=1)).replace(tzinfo=tz).astimezone(UTC)

    result = await authenticated_client.atw.get_energy_report(
        unit.id, day_from, day_to, tz
    )

    assert result is not None
    assert set(result) == {"consumed", "produced"}
    points = result["consumed"] + result["produced"]
    assert points, "recorded day must contain ATW energy; pick another RECORD_DAY"
    for point in points:
        hour = datetime.strptime(point["time"], "%Y-%m-%d %H:%M:%S.000000000").replace(
            tzinfo=UTC
        )
        assert hour.minute == 0 and hour.second == 0
        assert day_from <= hour < day_to
        assert float(point["value"]) >= 0
