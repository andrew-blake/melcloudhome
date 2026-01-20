"""Tests for request pacing."""

import asyncio

import pytest

from custom_components.melcloudhome.api.pacing import RequestPacer

# Test constants
FLOAT_TOLERANCE = 0.01  # Tolerance for floating point comparisons


@pytest.fixture
def mock_sleep(mocker):
    """Mock asyncio.sleep for testing."""
    return mocker.patch("asyncio.sleep")


@pytest.fixture
def mock_time(mocker):
    """Mock time.time for testing."""
    return mocker.patch("custom_components.melcloudhome.api.pacing.time")


class TestRequestPacer:
    """Test RequestPacer enforces minimum spacing between requests."""

    @pytest.mark.asyncio
    async def test_first_request_proceeds_immediately(self, mock_sleep):
        """First request should not wait."""
        pacer = RequestPacer()
        async with pacer:
            pass  # Simulate request

        # First request should not sleep
        mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_second_request_waits_if_too_soon(self, mock_sleep, mock_time):
        """Second request should wait if less than min_interval has passed."""
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
        assert abs(call_args - 0.3) < FLOAT_TOLERANCE

    @pytest.mark.asyncio
    async def test_second_request_no_wait_if_time_passed(self, mock_sleep, mock_time):
        """Second request should not wait if min_interval has passed."""
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

    @pytest.mark.asyncio
    async def test_concurrent_requests_are_serialized(self):
        """Concurrent requests should be queued and executed sequentially."""
        execution_order = []

        pacer = RequestPacer(min_interval=0.01)  # Short interval for test speed

        async def mock_request(request_id: int) -> None:
            async with pacer:
                execution_order.append(f"start_{request_id}")
                await asyncio.sleep(0.001)  # Simulate work
                execution_order.append(f"end_{request_id}")

        # Launch 3 concurrent requests
        await asyncio.gather(
            mock_request(1),
            mock_request(2),
            mock_request(3),
        )

        # Verify serialization - each request should fully complete before next starts
        assert execution_order == [
            "start_1",
            "end_1",
            "start_2",
            "end_2",
            "start_3",
            "end_3",
        ]

    @pytest.mark.asyncio
    async def test_failed_request_updates_timestamp(self, mock_sleep, mock_time):
        """Failed request should still update last_request_time."""
        # Simulate time progression
        mock_time.side_effect = [
            1.0,
            1.5,
            1.7,
            1.7,
        ]  # First enter, first exit, second enter, second exit

        pacer = RequestPacer(min_interval=0.5)

        # First request fails
        with pytest.raises(ValueError):
            async with pacer:
                raise ValueError("Test error")

        # Second request (0.2s after first ended at 1.5, now at 1.7)
        async with pacer:
            pass

        # Should wait because first request updated timestamp even though it failed
        mock_sleep.assert_called_once()
        call_args = mock_sleep.call_args[0][0]
        assert abs(call_args - 0.3) < FLOAT_TOLERANCE

    @pytest.mark.asyncio
    async def test_failed_request_releases_lock(self):
        """Failed request should release lock to prevent deadlock."""
        pacer = RequestPacer()

        # First request fails
        with pytest.raises(ValueError):
            async with pacer:
                raise ValueError("Test error")

        # Second request should proceed (lock was released)
        async with pacer:
            pass  # Should not hang

        # If we get here, lock was properly released
        assert True
