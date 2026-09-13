"""Base control client with shared functionality."""

import asyncio
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class ControlClientBase:
    """Base class for control clients with shared debouncing logic.

    Subclasses must set self._async_request_refresh to the coordinator's
    refresh method in their __init__.
    """

    def __init__(
        self,
        hass: "HomeAssistant",
        async_update_listeners: Callable[[], None],
    ) -> None:
        """Initialize base control client.

        Args:
            hass: Home Assistant instance
            async_update_listeners: Coordinator hook that pushes cached state
                to entities
        """
        self._hass = hass
        self._refresh_debounce_task: asyncio.Task | None = None
        self._async_update_listeners = async_update_listeners

    def _notify_listeners(self) -> None:
        """Push a written-through value to entities without waiting for a poll.

        Entities read the cached model, so a write-through stays invisible until
        listeners are told. A raising listener must not fail the service call:
        the write already succeeded. HA guards this itself from 2026.7.4; the
        hacs.json floor is 2025.8.0, which does not.
        """
        try:
            self._async_update_listeners()
        except Exception:
            _LOGGER.exception("Listener update failed after a control write")

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
            # Only the wait is cancellable. Cancelling this task once the
            # refresh has started would cancel the refresh itself, which HA's
            # coordinator records as a silent failure (last_update_success
            # False, no log, no listener update) followed by a bogus
            # "recovered" on the next poll.
            await asyncio.shield(self._async_request_refresh())  # type: ignore[attr-defined]

        self._refresh_debounce_task = self._hass.async_create_task(_delayed_refresh())

    def cancel_pending_refresh(self) -> None:
        """Cancel any pending debounced refresh (call on shutdown).

        A refresh queued <=2s before unload must not fire after the client
        session is closed — it would resurrect a fresh ClientSession that
        nothing ever closes.
        """
        if self._refresh_debounce_task and not self._refresh_debounce_task.done():
            self._refresh_debounce_task.cancel()
