"""E2E tests for request pacing against mock server with rate limiting.

These tests require the mock server running with rate limiting enabled:
    make dev-up

The mock server enforces 500ms rate limiting, allowing us to verify
that RequestPacer prevents 429 errors in production-like scenarios.
"""

import asyncio

import pytest

from custom_components.melcloudhome.api.client import MELCloudHomeClient


class TestRateLimitingE2E:
    """E2E tests verifying RequestPacer prevents rate limit errors."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_scene_with_three_devices_succeeds(self):
        """
        E2E test: Simulate scene turning on 2 ATA + 1 ATW device.

        This matches the production incident where 3 A/C units were
        turned on simultaneously and hit rate limits.

        Requires: make dev-up (mock server with rate limiting enabled)

        Mock server devices:
        - ATA 1: 0efc1234-5678-9abc-def0-1234567887db (Living Room AC)
        - ATA 2: bf8d5678-90ab-cdef-0123-456789ab5119 (Bedroom AC)
        - ATW 1: bf2d256c-42ac-4799-a6d8-c6ab433e5666 (House Heat Pump)
        """
        client = MELCloudHomeClient(debug_mode=True)

        try:
            # Login to mock server
            await client.login("test@example.com", "password")

            # Get device IDs
            context = await client.get_user_context()
            ata_devices = context.buildings[0].air_to_air_units
            atw_devices = context.buildings[0].air_to_water_units

            assert len(ata_devices) >= 2, "Mock should have 2+ ATA devices"
            assert len(atw_devices) >= 1, "Mock should have 1+ ATW devices"

            ata1_id = ata_devices[0].id
            ata2_id = ata_devices[1].id
            atw1_id = atw_devices[0].id

            # Simulate scene: Turn on all 3 devices simultaneously
            results = await asyncio.gather(
                client.ata.set_power(ata1_id, True),
                client.ata.set_power(ata2_id, True),
                client.atw.set_power(atw1_id, True),
            )

            # All requests should succeed (no 429 errors)
            # set_power returns None on success, so just verify no exceptions
            assert len(results) == 3

        finally:
            await client.close()

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_ten_concurrent_requests_succeeds(self, mocker):
        """
        E2E test: 10 rapid control requests across three units.

        Ten writes issued in one turn reach three units, so coalescing merges
        them into three requests, one per unit (ADR-026). Every caller still
        returns.

        The requests are counted rather than timed. The same code took 3.05 s
        on one run of this suite and 126 s on the next, so elapsed time cannot
        distinguish merged writes from unmerged ones here.

        Requires: make dev-up (mock server with rate limiting enabled)
        """
        client = MELCloudHomeClient(debug_mode=True)

        try:
            # Login to mock server
            await client.login("test@example.com", "password")

            # Get device IDs
            context = await client.get_user_context()
            ata_devices = context.buildings[0].air_to_air_units
            atw_devices = context.buildings[0].air_to_water_units

            ata1_id = ata_devices[0].id
            ata2_id = ata_devices[1].id
            atw1_id = atw_devices[0].id

            # Count real requests while still reaching the mock server
            sent: list[str] = []
            real_request = client._api_request

            async def counting_request(method, endpoint, **kwargs):
                if method == "PUT":
                    sent.append(endpoint)
                return await real_request(method, endpoint, **kwargs)

            mocker.patch.object(client, "_api_request", new=counting_request)

            # Create 10 mixed operations
            results = await asyncio.gather(
                # ATA 1 operations
                client.ata.set_temperature(ata1_id, 22.0),
                client.ata.set_fan_speed(ata1_id, "Auto"),
                client.ata.set_mode(ata1_id, "Heat"),
                # ATA 2 operations
                client.ata.set_temperature(ata2_id, 21.0),
                client.ata.set_fan_speed(ata2_id, "Two"),
                client.ata.set_mode(ata2_id, "Cool"),
                # ATW 1 operations
                client.atw.set_temperature_zone1(atw1_id, 23.0),
                client.atw.set_mode_zone1(atw1_id, "HeatRoomTemperature"),
                client.atw.set_dhw_temperature(atw1_id, 50.0),
                client.atw.set_forced_hot_water(atw1_id, False),
            )
            # Every caller returns, whether or not its write shared a request
            assert len(results) == 10

            # One PUT per unit: the writes to each unit arrived in one turn
            assert len(sent) == 3, f"Expected 3 PUTs, got {len(sent)}: {sent}"

        finally:
            await client.close()
