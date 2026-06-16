#!/usr/bin/env python3
"""Dump current state of all MELCloud devices via mobile BFF API.

Authenticates via OAuth PKCE and prints device settings in a format
suitable for before/after comparison.

Usage:
    source .env
    python tools/dump_device_state.py                    # All devices
    python tools/dump_device_state.py --unit-id <uuid>   # Single device
    python tools/dump_device_state.py --json              # JSON output

Requires MELCLOUD_USER and MELCLOUD_PASSWORD environment variables.
"""

import argparse
import asyncio
import base64
import hashlib
import json
import os
import re
import secrets
import sys

import aiohttp

AUTH_BASE = "https://auth.melcloudhome.com"
BFF_BASE = "https://mobile.bff.melcloudhome.com"
CLIENT_ID = "homemobile"
REDIRECT_URI = "melcloudhome://"
SCOPES = "openid profile email offline_access IdentityServerApi"
UA = "MonitorAndControl.App.Mobile/52 CFNetwork/3860.400.51 Darwin/25.3.0"


async def authenticate(
    session: aiohttp.ClientSession, email: str, password: str
) -> str:
    """Run OAuth PKCE flow and return access token."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    state = base64.urlsafe_b64encode(secrets.token_bytes(16)).rstrip(b"=").decode()

    # PAR
    async with session.post(
        f"{AUTH_BASE}/connect/par",
        data={
            "response_type": "code",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "client_id": CLIENT_ID,
            "scope": SCOPES,
            "redirect_uri": REDIRECT_URI,
        },
        headers={"User-Agent": UA},
    ) as resp:
        if resp.status != 201:
            print(f"PAR failed: {resp.status}", file=sys.stderr)
            sys.exit(1)
        par = await resp.json()
        request_uri = par["request_uri"]

    # Authorize -> Cognito
    async with session.get(
        f"{AUTH_BASE}/connect/authorize?client_id={CLIENT_ID}&request_uri={request_uri}",
        headers={"User-Agent": UA},
        allow_redirects=True,
    ) as resp:
        html = await resp.text()
        csrf_match = re.search(r'name="_csrf"\s+value="([^"]+)"', html)
        if not csrf_match:
            print("Failed to extract CSRF token", file=sys.stderr)
            sys.exit(1)
        csrf = csrf_match.group(1)
        cognito_url = str(resp.url)

    # Cognito login
    async with session.post(
        cognito_url,
        data={
            "_csrf": csrf,
            "username": email,
            "password": password,
            "cognitoAsfData": "",
        },
        headers={
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/22F76",
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": f"https://{cognito_url.split('/')[2]}",
            "Referer": cognito_url,
        },
        allow_redirects=True,
    ) as resp:
        body = await resp.text()
        cb_match = re.search(r"/connect/authorize/callback\?([^\"' ]+)", body)
        if not cb_match:
            print("Failed to extract callback URL", file=sys.stderr)
            sys.exit(1)
        cb_qs = cb_match.group(1).replace("&amp;", "&")

    # Callback
    async with session.get(
        f"{AUTH_BASE}/connect/authorize/callback?{cb_qs}",
        headers={"User-Agent": UA},
        allow_redirects=False,
    ) as resp:
        location = resp.headers.get("Location", "")
        code_match = re.search(r"code=([^&]+)", location)
        if not code_match:
            print(
                f"Failed to extract auth code from: {location[:100]}", file=sys.stderr
            )
            sys.exit(1)
        code = code_match.group(1)

    # Token exchange
    async with session.post(
        f"{AUTH_BASE}/connect/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "code_verifier": verifier,
            "client_id": CLIENT_ID,
        },
        headers={"User-Agent": UA},
    ) as resp:
        if resp.status != 200:
            print(f"Token exchange failed: {resp.status}", file=sys.stderr)
            sys.exit(1)
        tokens = await resp.json()
        access_token: str = tokens["access_token"]
        return access_token


def format_unit(unit: dict, unit_type: str, building_name: str, timezone: str) -> dict:
    """Extract unit state into a clean dict."""
    settings = {}
    for s in unit.get("settings", []):
        settings[s["name"]] = s["value"]

    return {
        "id": unit["id"],
        "name": unit.get("givenDisplayName", "Unknown"),
        "type": unit_type,
        "building": building_name,
        "timezone": timezone,
        "settings": settings,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Dump MELCloud device state")
    parser.add_argument("--unit-id", help="Filter to a single unit ID")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    email = os.environ.get("MELCLOUD_USER")
    password = os.environ.get("MELCLOUD_PASSWORD")
    if not email or not password:
        print(
            "Set MELCLOUD_USER and MELCLOUD_PASSWORD environment variables",
            file=sys.stderr,
        )
        sys.exit(1)

    jar = aiohttp.CookieJar()
    async with aiohttp.ClientSession(
        cookie_jar=jar, timeout=aiohttp.ClientTimeout(total=30)
    ) as session:
        access_token = await authenticate(session, email, password)
        headers = {"Authorization": f"Bearer {access_token}", "User-Agent": UA}

        async with session.get(f"{BFF_BASE}/context", headers=headers) as resp:
            ctx = await resp.json(content_type=None)

        units = []
        for source in ("buildings", "guestBuildings"):
            for b in ctx.get(source, []):
                for unit in b.get("airToAirUnits", []):
                    units.append(format_unit(unit, "ATA", b["name"], b["timezone"]))
                for unit in b.get("airToWaterUnits", []):
                    units.append(format_unit(unit, "ATW", b["name"], b["timezone"]))

        # Filter if requested
        if args.unit_id:
            units = [u for u in units if u["id"] == args.unit_id]
            if not units:
                print(f"Unit {args.unit_id} not found", file=sys.stderr)
                sys.exit(1)

        # Output
        if args.json:
            print(json.dumps(units, indent=2, sort_keys=True))
        else:
            for unit in units:
                print(f"{'=' * 60}")
                print(
                    f"{unit['type']} | {unit['name']} | {unit['building']} ({unit['timezone']})"
                )
                print(f"ID: {unit['id']}")
                print(f"{'-' * 60}")
                for name, value in unit["settings"].items():
                    print(f"  {name}: {value}")
                print()


if __name__ == "__main__":
    asyncio.run(main())
