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

    @pytest.mark.requires_mock
    @pytest.mark.asyncio
    async def test_scene_with_three_devices_succeeds(self):
        """
        E2E test: Simulate scene turning on 2 ATA + 1 ATW device.

        This matches the production incident where 3 A/C units were
        turned on simultaneously and hit rate limits.

        Requires: make dev-up (mock server with rate limiting enabled)

        Mock server devices:
        - ATA 1: 0efc1234-5678-9abc-def0-123456787db (Living Room AC)
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
