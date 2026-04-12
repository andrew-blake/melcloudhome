#!/usr/bin/env python3
"""Proof-of-concept: MELCloud Home mobile BFF API via OAuth PKCE.

Tests the full auth flow and API access against mobile.bff.melcloudhome.com.

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

# Constants from Charles capture analysis
AUTH_BASE = "https://auth.melcloudhome.com"
MOBILE_BFF_BASE = "https://mobile.bff.melcloudhome.com"
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
                print(f"   FAILED: {resp.status} {await resp.text()}")
                return
            par_data = await resp.json()
            request_uri = par_data["request_uri"]
            print(f"   OK: request_uri={request_uri[:50]}...")

        # Step 2: Authorize — follow redirects to Cognito login page
        print("2. Authorize (follow redirects to Cognito)...")
        authorize_url = (
            f"{AUTH_BASE}/connect/authorize"
            f"?client_id={CLIENT_ID}&request_uri={request_uri}"
        )
        # Follow redirects but stop at the Cognito login page
        async with session.get(
            authorize_url,
            headers={"User-Agent": USER_AGENT},
            allow_redirects=True,
        ) as resp:
            final_url = str(resp.url)
            if COGNITO_DOMAIN_SUFFIX not in final_url:
                print(f"   UNEXPECTED: ended up at {final_url}")
                print(f"   Status: {resp.status}")
                if resp.status >= 500:
                    print("   Auth server returning 5xx — partially affected by outage")
                    return
                # Might have been redirected back with a code already (existing session)
                if "code=" in final_url:
                    print("   Already authenticated via existing session")
                    # Extract code from redirect
                    # This path would need handling but skip for PoC
                    return
                body = await resp.text()
                print(f"   Body preview: {body[:200]}")
                return

            # Extract CSRF token from Cognito login page
            body = await resp.text()
            csrf_match = re.search(r'name="_csrf"\s+value="([^"]+)"', body)
            if not csrf_match:
                print("   FAILED: could not extract CSRF token from Cognito page")
                return
            csrf_token = csrf_match.group(1)
            cognito_login_url = str(resp.url)
            print(f"   OK: Cognito login page at {cognito_login_url[:60]}...")

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
            final_url = str(resp.url)
            # The redirect chain should end at auth.melcloudhome.com with a page
            # that contains a JS redirect to melcloudhome:// with the auth code
            body = await resp.text()

            # Look for the auth code in the page (redirect page or final URL)
            code_match = re.search(r"code=([^&\"' ]+)", body) or re.search(
                r"code=([^&\"' ]+)", final_url
            )
            if not code_match:
                if "error" in final_url.lower() or "error" in body.lower():
                    print(f"   FAILED: auth error at {final_url}")
                    error_match = re.search(r"error[_description]*=([^&]+)", final_url)
                    if error_match:
                        print(f"   Error: {error_match.group(1)}")
                    return

                # Debug: dump the redirect page to understand its structure
                print(f"   Redirect page URL: {final_url}")
                # Look for any URLs in the page
                url_matches = re.findall(
                    r'(https?://[^"\'<>\s]+|/connect/[^"\'<>\s]+)', body
                )
                for u in url_matches[:10]:
                    print(f"   Found URL: {u}")

                # The redirect page may contain a JS redirect or a link
                # to melcloudhome:// — look for the authorize/callback URL
                callback_match = re.search(
                    r"/connect/authorize/callback\?([^\"' ]+)", body
                ) or re.search(r"/connect/authorize/callback\?([^\"' ]+)", final_url)
                if callback_match:
                    callback_qs = callback_match.group(1).replace("&amp;", "&")
                    # Need to follow this URL to get the actual code redirect
                    import urllib.parse

                    callback_url = f"{AUTH_BASE}/connect/authorize/callback?{urllib.parse.unquote(callback_qs)}"
                    print("   Found callback URL, following...")

                    # Follow callback but DON'T follow the melcloudhome:// redirect
                    async with session.get(
                        callback_url,
                        headers={"User-Agent": USER_AGENT},
                        allow_redirects=False,
                    ) as cb_resp:
                        location = cb_resp.headers.get("Location", "")
                        if location.startswith("melcloudhome://"):
                            code_match = re.search(r"code=([^&]+)", location)
                            if code_match:
                                auth_code = code_match.group(1)
                                print(f"   OK: got auth code {auth_code[:20]}...")
                            else:
                                print(
                                    f"   FAILED: no code in redirect: {location[:100]}"
                                )
                                return
                        else:
                            # Might be another redirect in the chain
                            print(f"   Redirect to: {location[:100]}")
                            # Follow one more hop
                            async with session.get(
                                location
                                if location.startswith("http")
                                else f"{AUTH_BASE}{location}",
                                headers={"User-Agent": USER_AGENT},
                                allow_redirects=False,
                            ) as cb_resp2:
                                location2 = cb_resp2.headers.get("Location", "")
                                code_match = re.search(r"code=([^&]+)", location2)
                                if code_match:
                                    auth_code = code_match.group(1)
                                    print(f"   OK: got auth code {auth_code[:20]}...")
                                else:
                                    body2 = await cb_resp2.text()
                                    print(
                                        f"   FAILED: {cb_resp2.status} Location: {location2[:100]}"
                                    )
                                    print(f"   Body: {body2[:500]}")
                                    return
                else:
                    print("   FAILED: no auth code or callback found")
                    print(f"   URL: {final_url}")
                    print(f"   Body preview: {body[:500]}")
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
                print(f"   FAILED: {resp.status} {await resp.text()}")
                return
            token_data = await resp.json()
            access_token = token_data["access_token"]
            refresh_token = token_data.get("refresh_token", "")
            expires_in = token_data.get("expires_in", "?")
            print(f"   OK: access_token (expires in {expires_in}s)")
            print(f"   OK: refresh_token={'yes' if refresh_token else 'no'}")
            print(f"   OK: scope={token_data.get('scope', '?')}")

        # Step 5: Test mobile BFF endpoints
        api_headers = {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }

        print("\n5. Testing mobile BFF endpoints...")

        # /context
        async with session.get(
            f"{MOBILE_BFF_BASE}/context",
            headers=api_headers,
        ) as resp:
            if resp.status == 200:
                ctx = await resp.json(content_type=None)
                buildings = ctx.get("buildings", []) + ctx.get("guestBuildings", [])
                ata_count = sum(len(b.get("airToAirUnits", [])) for b in buildings)
                atw_count = sum(len(b.get("airToWaterUnits", [])) for b in buildings)
                print(f"   GET /context -> 200 ({ata_count} ATA, {atw_count} ATW)")
            else:
                print(f"   GET /context -> {resp.status} FAILED")

        # /config
        async with session.get(
            f"{MOBILE_BFF_BASE}/config",
            headers=api_headers,
        ) as resp:
            print(f"   GET /config -> {resp.status}")

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
                print(
                    f"   OK: new refresh_token={'yes' if new_tokens.get('refresh_token') else 'no'}"
                )
            else:
                print(f"   FAILED: {resp.status} {await resp.text()}")

        print("\n✅ All steps completed")


if __name__ == "__main__":
    asyncio.run(main())
