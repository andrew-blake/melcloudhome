"""mitmdump addon for capturing MELCloud API **and WebSocket** traffic.

Extends ``capture.py`` with the real-time WebSocket path (issue #174): it adds
``ws.melcloudhome.com`` and the WS-hash Lambda to the domain filter, and logs
the full socket lifecycle — the ``{hash, userId}`` fetch, the 101 handshake,
every frame (direction + content), and the close — to the console and to a
readable ``.jsonl`` alongside the raw ``.flow``.

Written for mitmproxy 12 (uses ``logging`` rather than the removed ``ctx.log``).

Usage:
    mitmdump -s capture_ws.py

Outputs (under the addon's ``captures/`` dir):
    <timestamp>.flow     raw mitmproxy flows (binary; contains credentials)
    <timestamp>-ws.jsonl one JSON object per WebSocket frame (for analysis)
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import IO

from mitmproxy import ctx, http
from mitmproxy.io import FlowWriter

logger = logging.getLogger("melcloud.capture")

CAPTURES_DIR = Path(__file__).parent / "captures"

# MELCloud domains of interest — now including the real-time WebSocket and the
# Lambda Function URL that issues the WS "hash" credential.
DOMAINS = [
    "mobile.bff.melcloudhome.com",
    "auth.melcloudhome.com",
    "amazoncognito.com",
    "ws.melcloudhome.com",
    "lambda-url.eu-west-1.on.aws",
]


class MELCloudWSCapture:
    def __init__(self) -> None:
        self.writer: FlowWriter | None = None
        self._file: IO[bytes] | None = None
        self._ws_log: IO[str] | None = None
        self.flow_count = 0
        self.frame_count = 0

    def load(self, loader: object) -> None:
        CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(tz=UTC).strftime("%Y-%m-%d-%H%M%S")
        self._file = open(CAPTURES_DIR / f"{ts}.flow", "wb")  # noqa: SIM115
        self.writer = FlowWriter(self._file)
        self._ws_log = open(  # noqa: SIM115
            CAPTURES_DIR / f"{ts}-ws.jsonl", "w", encoding="utf-8"
        )
        logger.warning("Saving flows to %s.flow", CAPTURES_DIR / ts)
        logger.warning("Saving WS frames to %s-ws.jsonl", CAPTURES_DIR / ts)
        ctx.options.flow_detail = 0
        # Pass these through untouched: Apple/Google pin certs, and
        # auth.melcloudhome.com / Cognito pin too (and we don't need the login
        # flow) — intercepting them would break the app's token refresh.
        ctx.options.ignore_hosts = [
            r".*\.apple\.com",
            r".*\.icloud\.com",
            r".*\.googleapis\.com",
            r".*\.gstatic\.com",
            r".*\.google\.com",
            r"auth\.melcloudhome\.com",
            r".*\.amazoncognito\.com",
        ]

    def _match(self, flow: http.HTTPFlow) -> bool:
        return any(d in flow.request.pretty_host for d in DOMAINS)

    def request(self, flow: http.HTTPFlow) -> None:
        # Strip the permessage-deflate offer on the WS upgrade: mitmproxy is
        # unreliable relaying compressed frames (the socket dies with a 1006
        # abnormal close), so force an uncompressed socket we can capture.
        if "ws.melcloudhome.com" in flow.request.pretty_host:
            flow.request.headers.pop("Sec-WebSocket-Extensions", None)

    def response(self, flow: http.HTTPFlow) -> None:
        if not self._match(flow):
            return
        self.flow_count += 1
        status = flow.response.status_code if flow.response else "---"
        size = len(flow.response.content or b"") if flow.response else 0
        logger.warning(
            "[%d] %s %s -> %s (%d bytes)",
            self.flow_count,
            flow.request.method,
            flow.request.pretty_url,
            status,
            size,
        )
        if self.writer:
            self.writer.add(flow)

    # --- WebSocket lifecycle ------------------------------------------------ #
    def websocket_start(self, flow: http.HTTPFlow) -> None:
        if not self._match(flow):
            return
        logger.warning("[WS OPEN] %s", flow.request.pretty_url)

    def websocket_message(self, flow: http.HTTPFlow) -> None:
        if not self._match(flow) or flow.websocket is None:
            return
        msg = flow.websocket.messages[-1]
        direction = "C->S" if msg.from_client else "S->C"
        try:
            content = msg.content.decode("utf-8", "replace")
        except Exception:
            content = repr(msg.content)
        self.frame_count += 1
        logger.warning("[WS %s] %s", direction, content[:400])
        if self._ws_log:
            self._ws_log.write(
                json.dumps(
                    {
                        "ts": datetime.now(tz=UTC).isoformat(),
                        "dir": direction,
                        "from_client": msg.from_client,
                        "content": content,
                    }
                )
                + "\n"
            )
            self._ws_log.flush()

    def websocket_end(self, flow: http.HTTPFlow) -> None:
        if not self._match(flow) or flow.websocket is None:
            return
        logger.warning(
            "[WS CLOSE] code=%s reason=%r",
            flow.websocket.close_code,
            flow.websocket.close_reason,
        )
        if self.writer:
            self.writer.add(flow)  # flow now carries all frames


addons = [MELCloudWSCapture()]
