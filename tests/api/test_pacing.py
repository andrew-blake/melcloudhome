"""Tests for request pacing."""

import pytest


class TestRequestPacer:
    """Test RequestPacer enforces minimum spacing between requests."""

    @pytest.mark.asyncio
    async def test_first_request_proceeds_immediately(self, mocker):
        """First request should not wait."""
        from custom_components.melcloudhome.api.pacing import RequestPacer

        mock_sleep = mocker.patch("asyncio.sleep")

        pacer = RequestPacer()
        async with pacer:
            pass  # Simulate request

        # First request should not sleep
        mock_sleep.assert_not_called()
