"""E2E tests for get_atw_water_temperatures against the mock server.

The only coverage of the mock's /report/v1/internaltemperatures handler, and
the only place the two-zone dataset path runs at all - both prod ATW units are
single-zone, so the dual-zone mock unit models the ADR-023 assumption rather
than testing it.

Requires the mock server (make dev-up, or the docker-compose test stack).
Run with: make test-e2e
"""

import pytest

from custom_components.melcloudhome.api.client import MELCloudHomeClient
from custom_components.melcloudhome.const import (
    ATW_TELEMETRY_MEASURES,
    ATW_TELEMETRY_MEASURES_BOILER,
    ATW_TELEMETRY_MEASURES_ZONE1,
    ATW_TELEMETRY_MEASURES_ZONE2,
)

PLACEHOLDER = 25.0


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_single_zone_unit_gets_the_base_pair_and_placeholders() -> None:
    """A single-zone boilerless unit: 8 datasets, 2 of them wanted.

    The suffixed series arrive as the constant 25 the real server sends for
    absent hardware, which is what the caller's capability filter exists to
    drop.
    """
    client = MELCloudHomeClient(debug_mode=True)
    try:
        await client.login("test@example.com", "password")
        context = await client.get_user_context()
        unit = next(
            u
            for building in context.buildings
            for u in building.air_to_water_units
            if not (u.capabilities and u.capabilities.has_zone2)
        )

        readings = await client.get_atw_water_temperatures(unit.id)

        for measure in ATW_TELEMETRY_MEASURES:
            assert measure in readings, f"{measure} missing"
            assert 0 < readings[measure].value < 90
            assert readings[measure].recorded_at.tzinfo is not None
            assert readings[measure].recorded_at.second != 0, "to-echo not stripped"

        # Zone 2 is absent entirely on a single-zone unit; zone 1 and boiler
        # arrive as placeholders rather than being omitted.
        for measure in ATW_TELEMETRY_MEASURES_ZONE2:
            assert measure not in readings
        for measure in ATW_TELEMETRY_MEASURES_ZONE1 + ATW_TELEMETRY_MEASURES_BOILER:
            assert readings[measure].value == PLACEHOLDER
    finally:
        await client.close()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_two_zone_unit_gets_its_zone2_datasets() -> None:
    """The assumption ADR-023 ships on, exercised where it can be exercised."""
    client = MELCloudHomeClient(debug_mode=True)
    try:
        await client.login("test@example.com", "password")
        context = await client.get_user_context()
        unit = next(
            u
            for building in context.buildings
            for u in building.air_to_water_units
            if u.capabilities and u.capabilities.has_zone2
        )

        readings = await client.get_atw_water_temperatures(unit.id)

        wanted = (
            ATW_TELEMETRY_MEASURES
            + ATW_TELEMETRY_MEASURES_ZONE1
            + ATW_TELEMETRY_MEASURES_ZONE2
        )
        for measure in wanted:
            assert measure in readings, f"{measure} missing"
            assert readings[measure].value != PLACEHOLDER, (
                f"{measure} came back as an absent-hardware placeholder"
            )
    finally:
        await client.close()
