"""Base control client with shared functionality."""

import asyncio
import logging
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class RefreshRequester(Protocol):
    """Protocol for objects that can request coordinator refresh."""

    async def async_request_refresh(self) -> None:
        """Request immediate coordinator refresh."""
        ...


class ControlClientBase:
    """Base class for control clients with shared debouncing logic."""

    def __init__(
        self,
        hass: "HomeAssistant",
        coordinator_refresh: RefreshRequester,
    ) -> None:
        """Initialize base control client.

        Args:
            hass: Home Assistant instance
            coordinator_refresh: Object with async_request_refresh method
        """
        self._hass = hass
        self._coordinator_refresh = coordinator_refresh
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
            await self._coordinator_refresh.async_request_refresh()

        self._refresh_debounce_task = self._hass.async_create_task(_delayed_refresh())
