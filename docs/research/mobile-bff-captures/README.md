# Mobile BFF API Captures

## What Was Captured

Mobile app traffic captured via Charles Proxy on 2026-04-11 and 2026-04-12, intercepting the MELCloud Home iOS app communicating with the mobile BFF API.

## Key Findings

- **Mobile BFF base URL:** `mobile.bff.melcloudhome.com`
- **Auth server:** `auth.melcloudhome.com` (IdentityServer4)
- **Auth flow:** OAuth 2.0 Authorization Code + PKCE via Pushed Authorization Requests (PAR)
- **Token endpoint:** `/connect/token` returns `application/json`
- **Data endpoints:** Return `text/plain; charset=utf-8` (not `application/json`)
- **Client ID:** `homemobile` (public OAuth client, no client secret)
- **User-Agent:** `MonitorAndControl.App.Mobile/52 CFNetwork/3860.400.51 Darwin/25.3.0`

### Endpoint Mapping (Web BFF to Mobile BFF)

| Web BFF | Mobile BFF |
|---------|-----------|
| `/api/user/context` | `/context` |
| `/api/ataunit/{id}` | `/monitor/ataunit/{id}` |
| `/api/atwunit/{id}` | `/monitor/atwunit/{id}` |
| `/api/telemetry/energy/{id}` | `/telemetry/telemetry/energy/{id}` |
| `/api/telemetry/actual/{id}` | `/telemetry/telemetry/actual/{id}` |
| `/api/report/trendsummary` | `/report/v1/trendsummary` |
| `/api/atwcloudschedule/{id}` | `/monitor/atwcloudschedule/{id}` |

### OAuth PKCE Flow

1. POST `/connect/par` (Pushed Authorization Request)
2. GET `/connect/authorize` → redirects to Cognito
3. POST Cognito login (credentials + CSRF)
4. Redirect back to `/connect/authorize/callback`
5. 302 to `melcloudhome://` with auth code
6. POST `/connect/token` (code + code_verifier exchange)

### JWT Structure

Access tokens are JWTs with standard claims (sub, email, scope). Refresh tokens are opaque. Token lifetime is 3600 seconds (1 hour).

## Raw Captures

Raw Charles proxy session files are stored in Google Drive (contain real credentials and tokens):

`/Users/ablake/Google Drive (a.blake01)/MELCloud Home/`

These are NOT committed to the repository.

## Related

- **ADR:** `docs/decisions/017-migrate-to-mobile-bff.md`
- **PoC script:** `tools/test_mobile_api.py`
- **Device state tool:** `tools/dump_device_state.py`
