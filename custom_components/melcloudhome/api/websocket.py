"""Real-time WebSocket listener for MELCloud Home.

Opt-in accelerator over REST polling (see issue #174). Connects to the same
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
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

import aiohttp

from .const_shared import WS_HOST

if TYPE_CHECKING:
    from .client import MELCloudHomeClient

_LOGGER = logging.getLogger(__name__)

# Reconnect backoff (seconds). The server drops the connection at a hard 2-hour
# AWS API Gateway cap; that is normal and reconnection is immediate.
_INITIAL_BACKOFF = 5
_MAX_BACKOFF = 300
_HEARTBEAT = 30

# Callback invoked for each unit that reports a state change:
# (unit_id, [changed setting names]).
DeltaHandler = Callable[[str, list[str]], Awaitable[None]]


class MELCloudHomeWebSocket:
    """Resilient MELCloud Home WebSocket listener."""

    def __init__(self, client: MELCloudHomeClient, on_delta: DeltaHandler) -> None:
        """Initialise with an authenticated client and a delta callback."""
        self._client = client
        self._on_delta = on_delta
        self._closing = False

    def stop(self) -> None:
        """Signal the run loop to exit (the owner also cancels the task)."""
        self._closing = True

    async def run(self) -> None:
        """Connect, listen, and reconnect until stopped or cancelled."""
        backoff = _INITIAL_BACKOFF
        while not self._closing:
            try:
                await self._connect_once()
                backoff = _INITIAL_BACKOFF  # reset after a clean session
            except asyncio.CancelledError:
                raise
            except Exception as err:
                # Best-effort listener: any failure just backs off and retries.
                _LOGGER.debug("WebSocket session ended: %s", err)

            if self._closing:
                break
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, _MAX_BACKOFF)

    async def _connect_once(self) -> None:
        """Open one WebSocket session and pump messages until it closes."""
        ws_hash = await self._client.async_get_ws_hash()
        session = await self._client.async_ws_session()
        async with session.ws_connect(
            f"{WS_HOST}/?hash={ws_hash}",
            heartbeat=_HEARTBEAT,
        ) as ws:
            _LOGGER.debug("WebSocket connected")
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
