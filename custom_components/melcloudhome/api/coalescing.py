"""Coalesce control writes that arrive together for one unit.

Two requests to one unit are spaced by the request pacer's minimum, and a
command arriving that close behind another can be accepted by the cloud and
ignored by the device, leaving a unit running while every surface reads off
(ADR-026). Writes arriving within one event-loop turn are therefore merged into
a single multi-field request.

The HomeKit bridge is what produces them: it dispatches each characteristic
write as its own un-awaited task, so setting a mode and a temperature on one
tile sends two service calls microseconds apart.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

_LOGGER = logging.getLogger(__name__)

# Margin, not mechanism. A write dispatched in the same event-loop turn as
# another is already queued before the dispatch task's first step, so a window
# of zero merges the HomeKit case this exists for; test_a_zero_window_still_merges
# holds that. The wait covers a caller separated by an await this reasoning does
# not account for, and ten milliseconds is short enough to be imperceptible on a
# lone command.
DEFAULT_COALESCE_WINDOW = 0.01

# The server answers 200 and silently drops a cross-axis vane combination on a
# unit without horizontal vanes (issue #100), so the two axes never ride
# together however close their writes arrive.
_NEVER_TOGETHER = frozenset({"vaneVerticalDirection", "vaneHorizontalDirection"})


class _Pending:
    """One request being assembled, and everyone waiting on its outcome."""

    def __init__(self) -> None:
        """Start empty; fields and waiters are added as writes arrive."""
        self.fields: dict[str, Any] = {}
        self.waiters: list[asyncio.Future[None]] = []
        self.dispatched = False


def _may_merge(pending: dict[str, Any], incoming: dict[str, Any]) -> bool:
    """Whether these fields may share a request with what is pending."""
    return len(_NEVER_TOGETHER & (pending.keys() | incoming.keys())) < 2


class WriteCoalescer:
    """Merges control writes to one unit that arrive in the same turn."""

    def __init__(
        self,
        send: Callable[[str, dict[str, Any]], Awaitable[None]],
        window: float = DEFAULT_COALESCE_WINDOW,
    ) -> None:
        """Initialise.

        Args:
            send: Coroutine sending one unit's merged fields as one request
            window: Seconds to collect before dispatching
        """
        self._send = send
        self._window = window
        self._pending: dict[str, _Pending] = {}
        # A task with no strong reference can be garbage collected mid-flight.
        self._tasks: set[asyncio.Task[None]] = set()

    async def submit(self, unit_id: str, fields: dict[str, Any]) -> None:
        """Send these fields, merged with any write still being assembled.

        Returns when the request carrying them has completed, and raises
        whatever that request raised.
        """
        entry = self._pending.get(unit_id)
        if entry is None or entry.dispatched or not _may_merge(entry.fields, fields):
            entry = _Pending()
            # The dispatch runs in its own task, so a caller being cancelled
            # never cancels the request other callers are waiting on. The entry
            # is published only once that task exists: a create_task that raises
            # on a closing loop would otherwise leave an entry with no
            # dispatcher, and the next write would merge into it and hang.
            task = asyncio.create_task(self._dispatch(unit_id, entry))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
            self._pending[unit_id] = entry

        # Nothing awaits between reading the entry and joining it, so a
        # dispatch cannot begin in the gap and leave these fields unsent.
        entry.fields.update(fields)
        waiter: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        entry.waiters.append(waiter)
        await waiter

    async def _dispatch(self, unit_id: str, entry: _Pending) -> None:
        """Wait out the window, then send everything collected as one request."""
        try:
            await asyncio.sleep(self._window)
            # Both of these happen before the request is awaited: a write
            # arriving during the round trip has to start its own request, and
            # merging into a payload that has already gone would lose it.
            #
            # Either line alone is enough to prevent that, so no test fails if
            # one is removed. Keep both: the flag is the guard, and the removal
            # is what stops _pending growing without bound.
            entry.dispatched = True
            if self._pending.get(unit_id) is entry:
                del self._pending[unit_id]
            if len(entry.waiters) > 1:
                _LOGGER.debug(
                    "Coalesced %d writes for %s into one request: %s",
                    len(entry.waiters),
                    unit_id[-8:],
                    ", ".join(sorted(entry.fields)),
                )
            await self._send(unit_id, dict(entry.fields))
        except BaseException as err:
            # Delivered to every waiter instead of being re-raised here: this
            # task has no awaiter, so re-raising would only be logged and the
            # callers would hang. A CancelledError travels the same way, which
            # cancels each waiting caller in turn; this task then completes
            # normally, which only happens when the loop is being torn down.
            entry.dispatched = True
            if self._pending.get(unit_id) is entry:
                del self._pending[unit_id]
            for waiter in entry.waiters:
                if not waiter.done():
                    waiter.set_exception(err)
        else:
            for waiter in entry.waiters:
                if not waiter.done():
                    waiter.set_result(None)
