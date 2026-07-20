"""Real-time WebSocket listener for MELCloud Home.

Default-on accelerator over REST polling (see issue #174). Connects to the same
WebSocket the official app uses and reports per-unit ``unitStateChanged``
deltas so out-of-band changes (physical remote, MELCloud app, another HA
instance) surface without waiting for the next poll.

Deliberately HA-agnostic: it manages a single long-running ``run()`` coroutine
and knows nothing about Home Assistant. The coordinator owns the task lifecycle
and decides what to do with each delta (v1: trigger a coordinator refresh).

Best-effort by design — any failure (token endpoint down, handshake refused,
hash expired) just backs off and retries; REST polling remains the source of
truth, so the integration degrades gracefully to polling if the WS is
unavailable.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

import aiohttp

if TYPE_CHECKING:
    from .client import MELCloudHomeClient

_LOGGER = logging.getLogger(__name__)

# Reconnect backoff (seconds). The server drops the connection at a hard 2-hour
# AWS API Gateway cap; that is normal and reconnection is immediate.
_INITIAL_BACKOFF = 5
_MAX_BACKOFF = 300
_HEARTBEAT = 30
# A session must survive this long before the backoff resets. A server that
# accepts the 101 and closes immediately (expired/revoked hash, throttling)
# would otherwise make every cycle look "clean" and reconnect at the initial
# backoff forever — each cycle costing a hash fetch and possibly a token
# refresh.
_STABLE_SESSION_SECS = 60

# Callback invoked for each unit that reports a state change:
# (unit_id, [changed setting names]).
DeltaHandler = Callable[[str, list[str]], Awaitable[None]]
# Sync callback invoked when the connection state flips (True = connected).
StateHandler = Callable[[bool], None]


class MELCloudHomeWebSocket:
    """Resilient MELCloud Home WebSocket listener."""

    def __init__(
        self,
        client: MELCloudHomeClient,
        on_delta: DeltaHandler,
        on_state_change: StateHandler | None = None,
    ) -> None:
        """Initialise with an authenticated client and a delta callback."""
        self._client = client
        self._on_delta = on_delta
        self._on_state_change = on_state_change
        self._closing = False
        self._connected = False
        self._ever_connected = False

    @property
    def connected(self) -> bool:
        """Whether a WebSocket session is currently established."""
        return self._connected

    def _set_connected(self, connected: bool) -> None:
        """Update connection state and notify the owner, swallowing errors."""
        self._connected = connected
        if self._on_state_change is None:
            return
        try:
            self._on_state_change(connected)
        except Exception:
            # A misbehaving state callback must never kill the listener.
            _LOGGER.debug("WebSocket state callback failed", exc_info=True)

    def stop(self) -> None:
        """Signal the run loop to exit (the owner also cancels the task)."""
        self._closing = True

    async def run(self) -> None:
        """Connect, listen, and reconnect until stopped or cancelled."""
        backoff = _INITIAL_BACKOFF
        while not self._closing:
            started = time.monotonic()
            try:
                await self._connect_once()
            except asyncio.CancelledError:
                raise
            except Exception as err:
                # Best-effort listener: any failure just backs off and retries.
                _LOGGER.debug("WebSocket session ended: %s", err)

            was_connected = self._connected
            if self._connected:
                self._set_connected(False)
                if not self._closing:
                    _LOGGER.info(
                        "WebSocket connection lost; reconnecting"
                        " (polling continues meanwhile)"
                    )

            # Reset only after a session that actually connected and survived.
            # A clean return from an accept-then-immediately-close server must
            # keep escalating, and so must a hash endpoint that hangs past the
            # threshold before failing — elapsed time alone proves nothing.
            if was_connected and time.monotonic() - started >= _STABLE_SESSION_SECS:
                backoff = _INITIAL_BACKOFF

            if self._closing:
                break
            # Jitter the sleep so a MELCloud outage doesn't have every
            # installation reconnecting on the same schedule.
            await asyncio.sleep(backoff * random.uniform(0.8, 1.2))
            backoff = min(backoff * 2, _MAX_BACKOFF)

    async def _connect_once(self) -> None:
        """Open one WebSocket session and pump messages until it closes."""
        ws_hash = await self._client.async_get_ws_hash()
        session = await self._client.async_ws_session()
        async with session.ws_connect(
            f"{self._client.ws_host}/?hash={ws_hash}",
            heartbeat=_HEARTBEAT,
        ) as ws:
            _LOGGER.info(
                "WebSocket %s",
                "connection restored" if self._ever_connected else "connected",
            )
            self._set_connected(True)
            self._ever_connected = True
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    await self._handle_text(msg.data)
                elif msg.type in (
                    aiohttp.WSMsgType.CLOSE,
                    aiohttp.WSMsgType.CLOSING,
                    aiohttp.WSMsgType.CLOSED,
                    aiohttp.WSMsgType.ERROR,
                ):
                    break
        _LOGGER.debug("WebSocket disconnected")

    async def _handle_text(self, raw: str) -> None:
        """Parse a text frame and dispatch any per-unit deltas."""
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return

        items = payload if isinstance(payload, list) else [payload]
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("messageType") != "unitStateChanged":
                continue
            data = item.get("Data") or item.get("data") or {}
            unit_id = data.get("id")
            if not unit_id:
                continue
            names = [
                s["name"]
                for s in data.get("settings", [])
                if isinstance(s, dict) and s.get("name")
            ]
            try:
                await self._on_delta(str(unit_id), names)
            except Exception:
                # A misbehaving handler must never kill the listen loop.
                _LOGGER.debug("WebSocket delta handler failed", exc_info=True)
