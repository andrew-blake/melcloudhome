#!/usr/bin/env python3
"""Test MELCloud Home mobile BFF API via OAuth PKCE.

Validates the full auth flow and API access against mobile.bff.melcloudhome.com.
Useful for verifying credentials work and checking API response shapes.

Usage:
    source .env
    python tools/test_mobile_api.py
"""

import asyncio
import base64
import hashlib
import os
import re
import secrets
import sys

import aiohttp

AUTH_BASE = "https://auth.melcloudhome.com"
BFF_BASE = "https://mobile.bff.melcloudhome.com"
COGNITO_DOMAIN_SUFFIX = ".amazoncognito.com"
CLIENT_ID = "homemobile"
REDIRECT_URI = "melcloudhome://"
SCOPES = "openid profile email offline_access IdentityServerApi"
USER_AGENT = "MonitorAndControl.App.Mobile/52 CFNetwork/3860.400.51 Darwin/25.3.0"


def generate_pkce() -> tuple[str, str]:
    """Generate PKCE code verifier and challenge."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


async def main() -> None:
    email = os.environ.get("MELCLOUD_USER")
    password = os.environ.get("MELCLOUD_PASSWORD")
    if not email or not password:
        print("Set MELCLOUD_USER and MELCLOUD_PASSWORD environment variables")
        sys.exit(1)

    print(f"Testing mobile API OAuth flow for {email}\n")

    code_verifier, code_challenge = generate_pkce()
    state = base64.urlsafe_b64encode(secrets.token_bytes(16)).rstrip(b"=").decode()

    jar = aiohttp.CookieJar()
    timeout = aiohttp.ClientTimeout(total=30)

    async with aiohttp.ClientSession(cookie_jar=jar, timeout=timeout) as session:
        # Step 1: Pushed Authorization Request
        print("1. PAR request...")
        async with session.post(
            f"{AUTH_BASE}/connect/par",
            data={
                "response_type": "code",
                "state": state,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
                "client_id": CLIENT_ID,
                "scope": SCOPES,
                "redirect_uri": REDIRECT_URI,
            },
            headers={"User-Agent": USER_AGENT},
        ) as resp:
            if resp.status != 201:
                print(f"   FAILED: {resp.status}")
                return
            par_data = await resp.json()
            request_uri = par_data["request_uri"]
            print(f"   OK: request_uri={request_uri[:50]}...")

        # Step 2: Authorize — follow redirects to Cognito login page
        print("2. Authorize (follow redirects to Cognito)...")
        async with session.get(
            f"{AUTH_BASE}/connect/authorize"
            f"?client_id={CLIENT_ID}&request_uri={request_uri}",
            headers={"User-Agent": USER_AGENT},
            allow_redirects=True,
        ) as resp:
            final_url = str(resp.url)
            if COGNITO_DOMAIN_SUFFIX not in final_url:
                print(f"   UNEXPECTED: ended up at {final_url}")
                return

            body = await resp.text()
            csrf_match = re.search(r'name="_csrf"\s+value="([^"]+)"', body)
            if not csrf_match:
                print("   FAILED: could not extract CSRF token")
                return
            csrf_token = csrf_match.group(1)
            cognito_login_url = str(resp.url)
            print("   OK: Cognito login page")

        # Step 3: Submit credentials to Cognito
        print("3. Cognito login...")
        async with session.post(
            cognito_login_url,
            data={
                "_csrf": csrf_token,
                "username": email,
                "password": password,
                "cognitoAsfData": "",
            },
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/22F76"
                ),
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": f"https://{cognito_login_url.split('/')[2]}",
                "Referer": cognito_login_url,
            },
            allow_redirects=True,
        ) as resp:
            body = await resp.text()
            final_url = str(resp.url)

            # Extract callback URL from redirect page
            callback_match = re.search(r"/connect/authorize/callback\?([^\"' ]+)", body)
            if not callback_match:
                code_match = re.search(r"code=([^&\"' ]+)", final_url) or re.search(
                    r"code=([^&\"' ]+)", body
                )
                if not code_match:
                    print("   FAILED: no auth code or callback found")
                    return
                auth_code = code_match.group(1)
            else:
                callback_qs = callback_match.group(1).replace("&amp;", "&")
                callback_url = f"{AUTH_BASE}/connect/authorize/callback?{callback_qs}"

                # Follow callback to get auth code from redirect
                async with session.get(
                    callback_url,
                    headers={"User-Agent": USER_AGENT},
                    allow_redirects=False,
                ) as cb_resp:
                    location = cb_resp.headers.get("Location", "")
                    code_match = re.search(r"code=([^&]+)", location)
                    if not code_match:
                        print("   FAILED: no code in redirect")
                        return
                    auth_code = code_match.group(1)

            print(f"   OK: got auth code {auth_code[:20]}...")

        # Step 4: Exchange code for tokens
        print("4. Token exchange...")
        async with session.post(
            f"{AUTH_BASE}/connect/token",
            data={
                "grant_type": "authorization_code",
                "code": auth_code,
                "redirect_uri": REDIRECT_URI,
                "code_verifier": code_verifier,
                "client_id": CLIENT_ID,
            },
            headers={"User-Agent": USER_AGENT},
        ) as resp:
            if resp.status != 200:
                print(f"   FAILED: {resp.status}")
                return
            token_data = await resp.json()
            access_token = token_data["access_token"]
            refresh_token = token_data.get("refresh_token", "")
            expires_in = token_data.get("expires_in", "?")
            print(f"   OK: access_token (expires in {expires_in}s)")
            print(f"   OK: refresh_token={'yes' if refresh_token else 'no'}")

        # Step 5: Test mobile BFF endpoints
        api_headers = {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }

        print("\n5. Testing mobile BFF endpoints...")

        async with session.get(f"{BFF_BASE}/context", headers=api_headers) as resp:
            if resp.status == 200:
                ctx = await resp.json(content_type=None)
                buildings = ctx.get("buildings", []) + ctx.get("guestBuildings", [])
                ata_count = sum(len(b.get("airToAirUnits", [])) for b in buildings)
                atw_count = sum(len(b.get("airToWaterUnits", [])) for b in buildings)
                print(f"   GET /context -> 200 ({ata_count} ATA, {atw_count} ATW)")
            else:
                print(f"   GET /context -> {resp.status} FAILED")

        # Step 6: Test token refresh
        print("\n6. Token refresh...")
        async with session.post(
            f"{AUTH_BASE}/connect/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": CLIENT_ID,
            },
            headers={"User-Agent": USER_AGENT},
        ) as resp:
            if resp.status == 200:
                new_tokens = await resp.json()
                print(
                    f"   OK: new access_token (expires in {new_tokens.get('expires_in', '?')}s)"
                )
            else:
                print(f"   FAILED: {resp.status}")

        print("\nAll steps completed")


if __name__ == "__main__":
    asyncio.run(main())
