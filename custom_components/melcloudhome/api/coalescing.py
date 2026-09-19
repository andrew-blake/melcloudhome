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

# Margin, not the mechanism: a window of zero already merges two writes made in
# one turn, which test_a_zero_window_still_merges holds. The production path
# relies on the HomeKit bridge and the service registry starting tasks eagerly,
# so one added await anywhere in that chain would break it silently. Ten
# milliseconds covers that and is imperceptible on a lone command.
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
        if entry is None or not _may_merge(entry.fields, fields):
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
            # Before the request is awaited, so a write arriving during the
            # round trip starts its own request rather than joining a payload
            # that has already gone.
            if self._pending.get(unit_id) is entry:
                del self._pending[unit_id]
            if len(entry.waiters) > 1:
                _LOGGER.debug(
                    "Coalesced %d writes for %s into one request: %s",
                    len(entry.waiters),
                    unit_id[-8:],
                    ", ".join(sorted(entry.fields)),
                )
            # The send waits on the pacer too, so under contention a write
            # arriving during that wait starts its own request. Merging helps
            # least when the pacer is busiest. Untested: pacing is off under
            # pytest.
            await self._send(unit_id, dict(entry.fields))
        except BaseException as err:
            # Delivered to every waiter instead of being re-raised here: this
            # task has no awaiter, so re-raising would only be logged and the
            # callers would hang. A CancelledError raised while this task is
            # suspended travels the same way and cancels each waiting caller.
            # A cancellation landing before the task's first step does not: the
            # throw happens at the coroutine's entry point, this block never
            # runs, and the waiters are left unresolved. Only a loop-wide
            # teardown does that, and it is cancelling those callers anyway.
            if self._pending.get(unit_id) is entry:
                del self._pending[unit_id]
            for waiter in entry.waiters:
                if not waiter.done():
                    waiter.set_exception(err)
        else:
            # Resolved in submission order, which is the order entry.fields was
            # updated in. Each caller's write-through then applies its own field
            # in that same order, so the coordinator's copy ends on the value the
            # payload carried even when two callers wrote the same field. A set
            # of waiters, or resolving them concurrently, would break that.
            for waiter in entry.waiters:
                if not waiter.done():
                    waiter.set_result(None)
