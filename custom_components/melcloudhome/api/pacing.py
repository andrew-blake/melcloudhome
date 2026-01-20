"""Request pacing to prevent rate limiting."""

import asyncio
import logging
from time import time

_LOGGER = logging.getLogger(__name__)

# Default minimum interval between API requests
DEFAULT_MIN_REQUEST_INTERVAL = 0.5  # seconds


class RequestPacer:
    """Enforces minimum spacing between API requests.

    Uses asyncio.Lock to serialize concurrent requests and enforces
    a minimum time interval between consecutive requests to prevent
    rate limiting from the API server.

    Example:
        async with RequestPacer() as pacer:
            result = await make_api_call()
    """

    def __init__(self, min_interval: float = DEFAULT_MIN_REQUEST_INTERVAL):
        """Initialize request pacer.

        Args:
            min_interval: Minimum seconds between requests (default 0.5)
        """
        self._min_interval = min_interval
        self._last_request_time = 0.0  # Far past, first request won't wait
        self._lock = asyncio.Lock()

    async def __aenter__(self):
        """Acquire lock and enforce minimum interval."""
        await self._lock.acquire()

        try:
            # Calculate elapsed time and wait if needed
            # (inside try block to ensure lock release on any exception)
            elapsed = time() - self._last_request_time
            if elapsed < self._min_interval:
                wait_time = self._min_interval - elapsed
                _LOGGER.debug("Request pacing: waiting %.2fs", wait_time)
                await asyncio.sleep(wait_time)
        except BaseException:
            # If exception occurs during pacing (including cancellation),
            # release lock before re-raising to prevent deadlock
            self._lock.release()
            raise

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Update timestamp and release lock."""
        self._last_request_time = time()
        self._lock.release()
        return False  # Don't suppress exceptions
