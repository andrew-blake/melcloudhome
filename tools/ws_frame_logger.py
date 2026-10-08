"""Log every raw MELCloud WebSocket frame to a .jsonl, and summarise what it carried.

Research tool: answers "what does the socket actually carry?" for every unit on
an account, with no phone or proxy. tools/mitmproxy/capture_ws.py records the
official app's socket instead.

Capture uses the integration's own client for login, token refresh and the WS
hash. It reconnects with backoff until the duration ends, and logs in again
whenever a connect fails before the socket opens. One JSON object per line:

    {"at": <utc iso>, "event": "frame", "raw": <frame text>}
    {"at": <utc iso>, "event": "connected" | "disconnected" | "relogin", ...}

Output is opened in append mode, so --out with an existing file continues it.
Never logs the connection URL: its ?hash= is a live credential (== userId).
The output holds unit IDs, so it defaults to the gitignored _claude/ws-logs/.

Usage (from the repo root):
    set -a; . ./.env; set +a
    nohup caffeinate -i uv run python tools/ws_frame_logger.py --hours 24 &
    uv run python tools/ws_frame_logger.py --summary _claude/ws-logs/<file>.jsonl
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

import aiohttp

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from custom_components.melcloudhome.api.client import MELCloudHomeClient

OUT_DIR = Path(__file__).resolve().parent.parent / "_claude" / "ws-logs"
MAX_BACKOFF = 300
CONNECT_TIMEOUT = 30


def now() -> datetime:
    return datetime.now(UTC)


async def run(hours: float, out_path: Path) -> None:
    client = MELCloudHomeClient()
    await client.login(os.environ["MELCLOUD_USER"], os.environ["MELCLOUD_PASSWORD"])
    end = now() + timedelta(hours=hours)
    frames = 0
    backoff = 5

    with out_path.open("a", encoding="utf-8") as out:

        def write(event: str, **fields: object) -> None:
            out.write(
                json.dumps({"at": now().isoformat(), "event": event, **fields}) + "\n"
            )
            out.flush()

        try:
            while now() < end:
                opened = False
                try:
                    ws_hash = await client.async_get_ws_hash()
                    session = await client.async_ws_session()
                    # Unbounded, a connect has hung for 15 minutes.
                    ws = await asyncio.wait_for(
                        session.ws_connect(
                            f"{client.ws_host}/?hash={ws_hash}", heartbeat=30
                        ),
                        CONNECT_TIMEOUT,
                    )
                    async with ws:
                        opened = True
                        write("connected")
                        print(f"{now():%H:%M:%S} connected", flush=True)
                        backoff = 5
                        while now() < end:
                            left = (end - now()).total_seconds()
                            try:
                                msg = await ws.receive(timeout=left)
                            except TimeoutError:
                                break
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                frames += 1
                                write("frame", raw=msg.data)
                            elif msg.type in (
                                aiohttp.WSMsgType.CLOSE,
                                aiohttp.WSMsgType.CLOSING,
                                aiohttp.WSMsgType.CLOSED,
                                aiohttp.WSMsgType.ERROR,
                            ):
                                break
                    if now() >= end:
                        # Our own close at the end of the run reads as 1006; not a drop.
                        write("finished", frames=frames)
                    else:
                        # close_code separates a server close (1000/1001/...) from a
                        # heartbeat or network failure (None or 1006).
                        write(
                            "disconnected",
                            close_code=ws.close_code,
                            frames_so_far=frames,
                        )
                except Exception as err:
                    # type only: an aiohttp error can embed the URL, and the URL holds the hash
                    write(
                        "disconnected", error=type(err).__name__, frames_so_far=frames
                    )
                if not opened and now() < end:
                    # Failed before the socket opened: hash fetch or token refresh is the
                    # likely cause (tokens die after a few hours), so start a fresh login.
                    try:
                        await client.login(
                            os.environ["MELCLOUD_USER"], os.environ["MELCLOUD_PASSWORD"]
                        )
                        write("relogin", ok=True)
                    except Exception as err:
                        write("relogin", ok=False, error=type(err).__name__)
                if now() < end:
                    print(f"{now():%H:%M:%S} reconnecting in {backoff}s", flush=True)
                    await asyncio.sleep(
                        min(backoff, max((end - now()).total_seconds(), 0))
                    )
                    backoff = min(backoff * 2, MAX_BACKOFF)
        finally:
            await client.close()
            print(f"done: {frames} frames -> {out_path}", flush=True)


def summarise(path: Path) -> str:
    """Return the vocabulary a log holds: per (unitType, setting), types and values.

    Also reports connection events, the longest gap between frames (a socket that
    stays open but goes quiet shows up here), and runs that overlapped in one file
    (a second "connected" before the first run's "disconnected" means two sockets
    wrote here at once, so frame counts are doubled for that span).
    """
    events: Counter[str] = Counter()
    values: defaultdict[tuple[str, str], defaultdict[str, Counter[str]]] = defaultdict(
        lambda: defaultdict(Counter)
    )
    units: defaultdict[tuple[str, str], set[str]] = defaultdict(set)
    message_types: Counter[str] = Counter()
    drop_reasons: Counter[str] = Counter()
    first = last = prev = None
    gap = (0.0, "")
    open_sockets = 0
    overlaps: list[str] = []

    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        at = datetime.fromisoformat(entry["at"])
        first = first or at
        last = at
        events[entry["event"]] += 1
        if entry["event"] == "connected":
            prev = None  # gaps are measured within a connection, not across restarts
            open_sockets += 1
            if open_sockets > 1:
                overlaps.append(entry["at"])
        elif entry["event"] in ("disconnected", "finished"):
            open_sockets = max(open_sockets - 1, 0)
            if entry["event"] == "disconnected":
                drop_reasons[str(entry.get("error") or entry.get("close_code"))] += 1
        if entry["event"] != "frame":
            continue
        if prev is not None and (at - prev).total_seconds() > gap[0]:
            gap = ((at - prev).total_seconds(), entry["at"])
        prev = at
        for message in json.loads(entry["raw"]):
            message_types[message.get("messageType", "?")] += 1
            data = message.get("Data") or {}
            for setting in data.get("settings") or []:
                key = (data.get("unitType", "?"), setting["name"])
                units[key].add(data.get("id", "?"))
                value = setting["value"]
                values[key][type(value).__name__][json.dumps(value)] += 1

    out = [
        f"span: {first} -> {last}",
        f"events: {dict(events)}",
        f"disconnect reasons (close code or error): {dict(drop_reasons)}",
        f"messageTypes: {dict(message_types)}",
        f"longest gap between frames: {gap[0]:.0f}s, ending {gap[1]}",
    ]
    if overlaps:
        out.append(f"OVERLAPPING RUNS at: {', '.join(overlaps)}")
    out.append("")
    for key in sorted(values):
        frames = sum(sum(c.values()) for c in values[key].values())
        parts = [
            f"{type_name}: {', '.join(sorted(seen, key=lambda v: (len(v), v)))}"
            for type_name, seen in values[key].items()
        ]
        out.append(
            f"{key[0]} {key[1]} ({frames} frames, {len(units[key])} units) | "
            + " | ".join(parts)
        )
    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--hours", type=float, default=24.0)
    parser.add_argument(
        "--out", type=Path, default=None, help="appends if the file exists"
    )
    parser.add_argument(
        "--summary", type=Path, default=None, help="summarise a log instead"
    )
    args = parser.parse_args()
    if args.summary:
        print(summarise(args.summary))
        return
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = args.out or OUT_DIR / f"{now():%Y-%m-%d-%H%M%S}-ws.jsonl"
    asyncio.run(run(args.hours, out))


if __name__ == "__main__":
    main()
