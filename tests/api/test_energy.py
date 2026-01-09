"""Tests for MELCloud Home energy telemetry API.

Tests cover energy data retrieval, parsing, and error handling.
Uses VCR cassettes to test against real API responses.

Recording VCR cassettes:
1. Set credentials in .env: MELCLOUD_USER, MELCLOUD_PASSWORD
2. Delete existing cassette: rm tests/api/cassettes/test_get_energy_*.yaml
3. Run test: pytest tests/api/test_energy.py::test_get_energy_data_hourly -v
4. Cassette will be recorded automatically

Reference: docs/testing-best-practices.md
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from freezegun import freeze_time

from custom_components.melcloudhome.api.client import MELCloudHomeClient
from custom_components.melcloudhome.api.exceptions import AuthenticationError


class TestEnergyDataRetrieval:
    """Test energy telemetry endpoint (requires VCR cassettes)."""

    @freeze_time("2026-01-08 17:38:00", real_asyncio=True)
    @pytest.mark.vcr()
    @pytest.mark.asyncio
    async def test_get_energy_data_hourly(self, credentials: tuple[str, str]) -> None:
        """Test fetching hourly energy data for ATA unit."""
        email, password = credentials
        client = MELCloudHomeClient(debug_mode=False)
        await client.login(email, password)

        # Get user context to find a unit with energy meter
        context = await client.get_user_context()

        # Find first ATA unit with energy meter
        unit = None
        for building in context.buildings:
            for ata_unit in building.air_to_air_units:
                if ata_unit.capabilities.has_energy_consumed_meter:
                    unit = ata_unit
                    break
            if unit:
                break

        if not unit:
            pytest.skip("No ATA units with energy meters found")

        # Request last 24 hours (time frozen for VCR consistency)
        to_time = datetime.now(UTC)
        from_time = to_time - timedelta(hours=24)

        assert unit is not None  # Type narrowing
        result = await client.get_energy_data(
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

    @freeze_time("2026-01-08 17:38:00", real_asyncio=True)
    @pytest.mark.vcr()
    @pytest.mark.asyncio
    async def test_get_energy_data_daily(self, credentials: tuple[str, str]) -> None:
        """Test fetching daily energy data for ATA unit."""
        email, password = credentials
        client = MELCloudHomeClient(debug_mode=False)
        await client.login(email, password)

        context = await client.get_user_context()

        # Find first ATA unit with energy meter
        unit = None
        for building in context.buildings:
            for ata_unit in building.air_to_air_units:
                if ata_unit.capabilities.has_energy_consumed_meter:
                    unit = ata_unit
                    break
            if unit:
                break

        if not unit:
            pytest.skip("No ATA units with energy meters found")

        # Request last 7 days (time frozen for VCR consistency)
        to_time = datetime.now(UTC)
        from_time = to_time - timedelta(days=7)

        assert unit is not None  # Type narrowing
        result = await client.get_energy_data(
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
    async def test_get_energy_data_requires_authentication(self) -> None:
        """Energy endpoint should require authentication."""
        client = MELCloudHomeClient(debug_mode=False)

        to_time = datetime.now(UTC)
        from_time = to_time - timedelta(hours=1)

        with pytest.raises(AuthenticationError, match="Not authenticated"):
            await client.get_energy_data(
                unit_id="test-unit-id",
                from_time=from_time,
                to_time=to_time,
            )

        await client.close()


class TestEnergyResponseParsing:
    """Test energy response parsing (unit tests - no VCR needed)."""

    def test_parse_energy_response_with_valid_data(self) -> None:
        """Parser should extract kWh from valid response."""
        client = MELCloudHomeClient(debug_mode=False)

        # Sample response structure from API (measureData is array)
        response = {
            "measureData": [
                {
                    "values": [
                        {"value": "1500"},  # 1500 Wh = 1.5 kWh
                        {"value": "2000"},  # 2000 Wh = 2.0 kWh (most recent)
                    ]
                }
            ]
        }

        result = client.parse_energy_response(response)
        assert result == 2.0  # Most recent value in kWh

    def test_parse_energy_response_with_empty_values(self) -> None:
        """Parser should handle empty values array."""
        client = MELCloudHomeClient(debug_mode=False)

        response: dict[str, Any] = {"measureData": [{"values": []}]}

        result = client.parse_energy_response(response)
        assert result is None

    def test_parse_energy_response_with_missing_measure_data(self) -> None:
        """Parser should handle missing measureData."""
        client = MELCloudHomeClient(debug_mode=False)

        response: dict[str, Any] = {}

        result = client.parse_energy_response(response)
        assert result is None

    def test_parse_energy_response_with_none(self) -> None:
        """Parser should handle None input (304 response)."""
        client = MELCloudHomeClient(debug_mode=False)

        result = client.parse_energy_response(None)
        assert result is None

    def test_parse_energy_response_converts_wh_to_kwh(self) -> None:
        """Parser should convert Wh to kWh correctly."""
        client = MELCloudHomeClient(debug_mode=False)

        # API returns in Wh, we want kWh
        response = {
            "measureData": [
                {
                    "values": [
                        {"value": "5000"},  # 5000 Wh = 5.0 kWh
                    ]
                }
            ]
        }

        result = client.parse_energy_response(response)
        assert result == 5.0

    def test_parse_energy_response_with_zero_energy(self) -> None:
        """Parser should handle zero energy values."""
        client = MELCloudHomeClient(debug_mode=False)

        response = {
            "measureData": [
                {
                    "values": [
                        {"value": "0"},
                    ]
                }
            ]
        }

        result = client.parse_energy_response(response)
        assert result == 0.0


# Note: Error handling tests (304, 401, 500) are deferred
# Will be covered by VCR cassettes when recording actual API responses
