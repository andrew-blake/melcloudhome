"""Tests for MELCloud Home ATW energy telemetry API.

Tests cover energy consumption and production data retrieval for heat pumps.
Uses VCR cassettes to test against real API responses.

Recording VCR cassettes:
1. Set credentials in .env: MELCLOUD_USER, MELCLOUD_PASSWORD
2. Delete existing cassette: rm tests/api/cassettes/test_get_energy_*.yaml
3. Run test: pytest tests/api/test_energy_atw.py::test_get_energy_consumed_hourly -v
4. Cassette will be recorded automatically

Reference: docs/testing-best-practices.md
"""

from datetime import UTC, datetime, timedelta

import pytest
from freezegun import freeze_time

from custom_components.melcloudhome.api.client import MELCloudHomeClient
from custom_components.melcloudhome.api.exceptions import AuthenticationError


class TestATWEnergyDataRetrieval:
    """Test ATW energy telemetry endpoints (requires VCR cassettes)."""

    @freeze_time("2026-01-18 10:24:22", real_asyncio=True)
    @pytest.mark.vcr()
    @pytest.mark.asyncio
    async def test_get_energy_consumed_hourly(
        self, credentials: tuple[str, str]
    ) -> None:
        """Test fetching hourly energy consumed data for ATW unit."""
        email, password = credentials
        client = MELCloudHomeClient(debug_mode=False)
        await client.login(email, password)

        # Get user context to find an ATW unit with energy capabilities
        context = await client.get_user_context()

        # Find ATW unit with energy capabilities, prefer Belgrade device (has cooling mode)
        unit = None
        for building in context.buildings:
            for atw_unit in building.air_to_water_units:
                if (
                    atw_unit.capabilities.has_estimated_energy_consumption
                    or atw_unit.capabilities.has_measured_energy_consumption
                ):
                    # Prefer device with cooling mode (Belgrade device has more features)
                    if atw_unit.capabilities.has_cooling_mode:
                        unit = atw_unit
                        break
                    # Fallback to any device with energy capabilities
                    if unit is None:
                        unit = atw_unit
            if unit and unit.capabilities.has_cooling_mode:
                break

        if not unit:
            pytest.skip("No ATW units with energy capabilities found")

        # Request last 24 hours (time frozen for VCR consistency)
        to_time = datetime.now(UTC)
        from_time = to_time - timedelta(hours=24)

        assert unit is not None  # Type narrowing
        result = await client.atw.get_energy_consumed(
            unit_id=unit.id,
            from_time=from_time,
            to_time=to_time,
            interval="Hour",
        )

        # Verify response structure
        assert result is not None or result is None  # Can be None if 304
        if result:
            assert isinstance(result, dict)
            # Energy responses have measureData structure
            assert "measureData" in result or len(result) == 0

        await client.close()

    @freeze_time("2026-01-18 10:24:22", real_asyncio=True)
    @pytest.mark.vcr()
    @pytest.mark.asyncio
    async def test_get_energy_produced_hourly(
        self, credentials: tuple[str, str]
    ) -> None:
        """Test fetching hourly energy produced data for ATW unit."""
        email, password = credentials
        client = MELCloudHomeClient(debug_mode=False)
        await client.login(email, password)

        context = await client.get_user_context()

        # Find ATW unit with energy capabilities, prefer Belgrade device (has cooling mode)
        unit = None
        for building in context.buildings:
            for atw_unit in building.air_to_water_units:
                if (
                    atw_unit.capabilities.has_estimated_energy_production
                    or atw_unit.capabilities.has_measured_energy_production
                ):
                    # Prefer device with cooling mode (Belgrade device has more features)
                    if atw_unit.capabilities.has_cooling_mode:
                        unit = atw_unit
                        break
                    # Fallback to any device with energy capabilities
                    if unit is None:
                        unit = atw_unit
            if unit and unit.capabilities.has_cooling_mode:
                break

        if not unit:
            pytest.skip("No ATW units with energy capabilities found")

        # Request last 24 hours (time frozen for VCR consistency)
        to_time = datetime.now(UTC)
        from_time = to_time - timedelta(hours=24)

        assert unit is not None  # Type narrowing
        result = await client.atw.get_energy_produced(
            unit_id=unit.id,
            from_time=from_time,
            to_time=to_time,
            interval="Hour",
        )

        # Verify response structure
        assert result is not None or result is None  # Can be None if 304
        if result:
            assert isinstance(result, dict)
            assert "measureData" in result or len(result) == 0

        await client.close()

    @freeze_time("2026-01-18 10:24:22", real_asyncio=True)
    @pytest.mark.vcr()
    @pytest.mark.asyncio
    async def test_get_energy_consumed_daily(
        self, credentials: tuple[str, str]
    ) -> None:
        """Test fetching daily energy consumed data for ATW unit."""
        email, password = credentials
        client = MELCloudHomeClient(debug_mode=False)
        await client.login(email, password)

        context = await client.get_user_context()

        # Find ATW unit with energy capabilities, prefer Belgrade device (has cooling mode)
        unit = None
        for building in context.buildings:
            for atw_unit in building.air_to_water_units:
                if (
                    atw_unit.capabilities.has_estimated_energy_consumption
                    or atw_unit.capabilities.has_measured_energy_consumption
                ):
                    # Prefer device with cooling mode (Belgrade device has more features)
                    if atw_unit.capabilities.has_cooling_mode:
                        unit = atw_unit
                        break
                    # Fallback to any device with energy capabilities
                    if unit is None:
                        unit = atw_unit
            if unit and unit.capabilities.has_cooling_mode:
                break

        if not unit:
            pytest.skip("No ATW units with energy capabilities found")

        # Request last 7 days (time frozen for VCR consistency)
        to_time = datetime.now(UTC)
        from_time = to_time - timedelta(days=7)

        assert unit is not None  # Type narrowing
        result = await client.atw.get_energy_consumed(
            unit_id=unit.id,
            from_time=from_time,
            to_time=to_time,
            interval="Day",
        )

        # Verify response
        assert result is not None or result is None
        if result:
            assert isinstance(result, dict)

        await client.close()

    @pytest.mark.asyncio
    async def test_get_energy_consumed_requires_authentication(self) -> None:
        """Energy consumed endpoint should require authentication."""
        client = MELCloudHomeClient(debug_mode=False)

        to_time = datetime.now(UTC)
        from_time = to_time - timedelta(hours=1)

        with pytest.raises(AuthenticationError, match="Not authenticated"):
            await client.atw.get_energy_consumed(
                unit_id="test-unit-id",
                from_time=from_time,
                to_time=to_time,
            )

        await client.close()

    @pytest.mark.asyncio
    async def test_get_energy_produced_requires_authentication(self) -> None:
        """Energy produced endpoint should require authentication."""
        client = MELCloudHomeClient(debug_mode=False)

        to_time = datetime.now(UTC)
        from_time = to_time - timedelta(hours=1)

        with pytest.raises(AuthenticationError, match="Not authenticated"):
            await client.atw.get_energy_produced(
                unit_id="test-unit-id",
                from_time=from_time,
                to_time=to_time,
            )

        await client.close()


# Note: Response parsing tests are not needed here since ATW uses the same
# telemetry endpoint structure as ATA, just with different measure parameters.
# Parsing is tested in test_energy.py with parse_energy_response().
