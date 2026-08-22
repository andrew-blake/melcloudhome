#!/usr/bin/env python3
"""Dump melcloudhome sensor states alongside their `last_reading` provenance.

`last_reading` is the time the *unit* recorded a value, so comparing it against
the wall clock is how you tell a fresh reading from one frozen by a poll that
stopped succeeding (issue #200, ADR-022). The History UI will not chart a custom
attribute, so this is how you read it.

Runs against a Home Assistant instance over the REST API. Against the local dev
container it mints its own short-lived token from the stored refresh token, so
no long-lived token is needed:

    python3 tools/dump_sensor_readings.py                       # dev container
    python3 tools/dump_sensor_readings.py --redact              # safe to paste
    python3 tools/dump_sensor_readings.py \\
        --url "$HA_URL" --token "$HA_TOKEN" --insecure          # prod, via .env

Ages are in minutes. `changed` and `updated` are HA's own `last_changed` and
`last_updated`, which move only when the state value or the attributes change —
comparing them against `reading age` is what separates "the reading really is
steady" from "nothing has been written for hours".

`last_reported` is deliberately absent. It does advance on every identical
rewrite inside the state machine, but `State.json_fragment` is a cached_property
that the fast path never invalidates, so `/api/states` serves a stale value for
it and any column here would mislead.

`--redact` drops the building-name prefix from each entity_id and keeps the
UUID-derived short id, the same rule the integration's own diagnostics uses. Use
it for anything you publish: some devices are shared by other people and one
building name is a street address.
"""

from __future__ import annotations

import argparse
import json
import ssl
import subprocess
import sys
import urllib.request
from datetime import UTC, datetime

DEV_CONTAINER = "ha-melcloud-dev"
DEV_URL = "http://127.0.0.1:8123"
ATTR = "last_reading"


def mint_dev_token(container: str, url: str) -> str:
    """Exchange a refresh token from the container's auth store for an access token.

    Runs inside the container so it can read /config/.storage/auth, and prints
    only the resulting access token - never a refresh token.
    """
    script = (
        "import json,urllib.parse,urllib.request\n"
        "auth=json.load(open('/config/.storage/auth'))\n"
        "for rt in auth['data']['refresh_tokens']:\n"
        "    if rt.get('token_type')!='normal' or not rt.get('client_id'): continue\n"
        "    body=urllib.parse.urlencode({'grant_type':'refresh_token',"
        "'refresh_token':rt['token'],'client_id':rt['client_id']}).encode()\n"
        f"    req=urllib.request.Request('{url}/auth/token',data=body)\n"
        "    try:\n"
        "        with urllib.request.urlopen(req,timeout=10) as r:\n"
        "            print(json.load(r)['access_token']); break\n"
        "    except Exception: pass\n"
    )
    out = subprocess.run(
        ["docker", "exec", "-i", container, "python", "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )
    token = out.stdout.strip().splitlines()[-1] if out.stdout.strip() else ""
    if not token:
        sys.exit(f"could not mint a token from {container}: {out.stderr.strip()}")
    return token


def fetch_states(url: str, token: str, insecure: bool = False) -> list[dict]:
    req = urllib.request.Request(  # noqa: S310 - operator-supplied URL
        f"{url.rstrip('/')}/api/states", headers={"Authorization": f"Bearer {token}"}
    )
    # The prod instance answers on https://homeassistant.local:8123 with a
    # self-signed certificate, so --insecure is the only way to reach its API.
    # Its public hostname sits behind a proxy that 302s API requests, and a
    # bearer token cannot get past that.
    context = ssl._create_unverified_context() if insecure else None  # noqa: S323
    with urllib.request.urlopen(req, timeout=20, context=context) as resp:  # noqa: S310
        states: list[dict] = json.load(resp)
        return states


def redact_entity_id(entity_id: str) -> str:
    """Drop the real-name prefix, keep everything from `melcloudhome_` onwards.

    Same rule as the integration's own diagnostics redaction: the prefix comes
    from a building or device name someone chose, while the short id after the
    marker is derived from the device UUID and names nobody. Keeping it is what
    makes a redacted table still correlate row-to-device.
    """
    domain, _, object_id = entity_id.partition(".")
    marker = "melcloudhome_"
    index = object_id.find(marker)
    if index <= 0:
        return entity_id
    return f"{domain}.{object_id[index:]}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", default=DEV_URL, help=f"HA base URL (default {DEV_URL})")
    ap.add_argument(
        "--token", help="long-lived token; omitted means mint from --container"
    )
    ap.add_argument(
        "--container", default=DEV_CONTAINER, help="dev container to mint from"
    )
    ap.add_argument("--redact", action="store_true", help="replace device names")
    ap.add_argument(
        "--all", action="store_true", help="also list sensors with no provenance"
    )
    ap.add_argument(
        "--insecure",
        action="store_true",
        help="skip TLS verification (prod answers with a self-signed cert)",
    )
    args = ap.parse_args()

    token = args.token or mint_dev_token(args.container, args.url)
    states = fetch_states(args.url, token, args.insecure)

    now = datetime.now(UTC)
    backed: list[tuple[str, ...]] = []
    plain: list[tuple[str, ...]] = []

    for state in states:
        entity_id = state["entity_id"]
        if not entity_id.startswith("sensor.") or "melcloudhome" not in entity_id:
            continue
        attrs = state["attributes"]
        name = redact_entity_id(entity_id) if args.redact else entity_id

        def mins(stamp: str | None) -> str:
            if not stamp:
                return "-"
            return f"{(now - datetime.fromisoformat(stamp)).total_seconds() / 60:.0f}"

        row: tuple[str, ...] = (
            str(name),
            str(state["state"]),
            str(attrs.get(ATTR) or "null"),
            mins(attrs.get(ATTR)),
            mins(state.get("last_changed")),
            mins(state.get("last_updated")),
        )
        (backed if ATTR in attrs else plain).append(row)

    print(
        f"\n{len(backed)} sensors with {ATTR} — wall clock {now.isoformat(timespec='seconds')}\n"
    )
    header = f"| entity_id | state | {ATTR} | reading age | changed | updated |"
    print(header)
    print("|---|---|---|---|---|---|")
    for row in sorted(backed):
        print(f"| {' | '.join(row)} |")

    print(
        f"\n{len(plain)} sensors without {ATTR} (context-sourced, energy, diagnostics)"
    )
    if args.all:
        print(header)
        print("|---|---|---|---|---|---|")
        for row in sorted(plain):
            print(f"| {' | '.join(row)} |")


if __name__ == "__main__":
    main()
