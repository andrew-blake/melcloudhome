"""Base control client with shared functionality."""

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class ControlClientBase:
    """Base class for control clients with shared debouncing logic.

    Subclasses must set self._async_request_refresh to the coordinator's
    refresh method in their __init__.
    """

    def __init__(self, hass: "HomeAssistant") -> None:
        """Initialize base control client.

        Args:
            hass: Home Assistant instance
        """
        self._hass = hass
        self._refresh_debounce_task: asyncio.Task | None = None

    async def async_request_refresh_debounced(self, delay: float = 2.0) -> None:
        """Request a coordinator refresh with debouncing.

        Multiple rapid calls will cancel previous timers and only refresh once
        after the last call settles. This prevents race conditions when scenes
        or automations make multiple rapid service calls.

        Args:
            delay: Seconds to wait before refreshing (default 2.0)
        """
        # Cancel any pending refresh
        if self._refresh_debounce_task and not self._refresh_debounce_task.done():
            self._refresh_debounce_task.cancel()
            _LOGGER.debug("Cancelled pending debounced refresh, resetting timer")

        async def _delayed_refresh() -> None:
            """Wait then refresh."""
            await asyncio.sleep(delay)
            _LOGGER.debug("Debounced refresh executing after %.1fs delay", delay)
            await self._async_request_refresh()  # type: ignore[attr-defined]

        self._refresh_debounce_task = self._hass.async_create_task(_delayed_refresh())
