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

    @pytest.mark.asyncio
    async def test_second_request_waits_if_too_soon(self, mocker):
        """Second request should wait if less than min_interval has passed."""
        from custom_components.melcloudhome.api.pacing import RequestPacer

        mock_sleep = mocker.patch("asyncio.sleep")
        mock_time = mocker.patch("custom_components.melcloudhome.api.pacing.time")

        # Simulate time progression
        mock_time.side_effect = [
            1.0,
            1.0,
            1.2,
            1.2,
        ]  # First enter, first exit, second enter, second exit

        pacer = RequestPacer(min_interval=0.5)

        # First request
        async with pacer:
            pass

        # Second request (0.2s later, needs to wait 0.3s more)
        async with pacer:
            pass

        # Should have called sleep with 0.3 seconds
        mock_sleep.assert_called_once()
        call_args = mock_sleep.call_args[0][0]
        assert abs(call_args - 0.3) < 0.01  # Allow small floating point error

    @pytest.mark.asyncio
    async def test_second_request_no_wait_if_time_passed(self, mocker):
        """Second request should not wait if min_interval has passed."""
        from custom_components.melcloudhome.api.pacing import RequestPacer

        mock_sleep = mocker.patch("asyncio.sleep")
        mock_time = mocker.patch("custom_components.melcloudhome.api.pacing.time")

        # Simulate time progression - enough time passed
        mock_time.side_effect = [
            1.0,
            1.0,
            1.6,
            1.6,
        ]  # Start, end first, start second (0.6s later), end second

        pacer = RequestPacer(min_interval=0.5)

        # First request
        async with pacer:
            pass

        # Second request (0.6s later, no wait needed)
        async with pacer:
            pass

        # Should not have called sleep
        mock_sleep.assert_not_called()
