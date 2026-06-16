"""
mitmdump addon for capturing MELCloud API traffic.

Usage:
    mitmdump -s tools/mitmproxy/capture.py

Saves flows to tools/mitmproxy/captures/<timestamp>.flow
Logs request/response summaries to console.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from mitmproxy import ctx, http
from mitmproxy.io import FlowWriter

CAPTURES_DIR = Path(__file__).parent / "captures"

# MELCloud domains of interest
DOMAINS = [
    "mobile.bff.melcloudhome.com",
    "auth.melcloudhome.com",
    "amazoncognito.com",
]


class MELCloudCapture:
    def __init__(self) -> None:
        self.writer: FlowWriter | None = None
        self.flow_count = 0

    def load(self, loader: object) -> None:
        CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(tz=UTC).strftime("%Y-%m-%d-%H%M%S")
        outfile = CAPTURES_DIR / f"{timestamp}.flow"
        self.writer = FlowWriter(open(outfile, "wb"))  # noqa: SIM115
        ctx.log.warn(f"Saving flows to {outfile}")
        # Suppress default mitmdump output — this script logs MELCloud traffic itself
        ctx.options.flow_detail = 0
        # Pass through Apple/Google traffic without interception to avoid
        # TLS handshake errors flooding the console (these domains pin certs)
        ctx.options.ignore_hosts = [
            r".*\.apple\.com",
            r".*\.icloud\.com",
            r".*\.googleapis\.com",
            r".*\.gstatic\.com",
            r".*\.google\.com",
        ]
        # Suppress connection-level log messages (connect/disconnect noise)
        ctx.options.termlog_verbosity = "warn"

    def response(self, flow: http.HTTPFlow) -> None:
        if not any(d in flow.request.pretty_host for d in DOMAINS):
            return

        self.flow_count += 1
        status = flow.response.status_code if flow.response else "---"
        size = (
            len(flow.response.content) if flow.response and flow.response.content else 0
        )
        ctx.log.warn(
            f"[{self.flow_count}] {flow.request.method} {flow.request.pretty_url} "
            f"-> {status} ({size} bytes)"
        )

        if self.writer:
            self.writer.add(flow)


addons = [MELCloudCapture()]
