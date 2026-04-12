# ADR-017: Migrate from Web BFF to Mobile BFF API

**Date:** 2026-04-12
**Status:** Accepted
**Supersedes:** ADR-002 (authentication refresh strategy — now implemented via OAuth)

## Context

On 2026-04-10, the MELCloud Home web BFF (`melcloudhome.com`) began returning HTTP 503 errors. The outage persisted for 2+ days with no fix from Mitsubishi. During the outage:

- Users saw misleading "invalid credentials" errors (#86)
- The integration became completely non-functional
- The mobile app continued working normally

Investigation via Charles proxy capture revealed the mobile app uses a separate API surface (`mobile.bff.melcloudhome.com`) with proper OAuth 2.0 authentication and JWT Bearer tokens. The response payloads are identical to the web BFF — same JSON structure, same device data.

The web BFF relies on cookie-based sessions obtained by scraping a Cognito login page with browser-spoofed headers. The mobile BFF uses standard OAuth 2.0 Authorization Code + PKCE with refresh tokens. Both authenticate against the same Cognito user pool via `auth.melcloudhome.com`.

## Decision

Migrate fully from the web BFF to the mobile BFF API. Drop the web BFF dependency entirely.

## Alternatives Considered

**Keep both APIs with failover:** Rejected. Two auth implementations, two endpoint mappings, complex failover logic — all for a scenario where both BFFs would likely fail together anyway. The web BFF has been down for days with no fix; the mobile BFF stayed up throughout. Maintaining two paths doesn't justify the complexity.

**Auth-only migration (keep web BFF endpoints with Bearer tokens):** Rejected. Unconfirmed whether the web BFF accepts Bearer auth, and this wouldn't solve the core problem — the web BFF being down.

## Consequences

**Positive:**
- Resilient to web BFF outages (the trigger for this decision)
- Refresh tokens eliminate the ~8-hour re-login cycle (fulfils ADR-002's planned migration)
- Standard OAuth flow replaces brittle browser-session scraping

**Negative:**
- Depends on `client_id=homemobile` — same category of risk as current browser spoofing
- VCR test cassettes, mock server, and API docs all need updating
- All reverse-engineered; no API contract guarantee

## Validation

A proof-of-concept script (`tools/test_mobile_api.py`) confirmed the full OAuth flow and API access works from Python, including token refresh — all while the web BFF returned 503.

## Implementation

See [mobile BFF migration plan](../../_claude/plans/2026-04-12-mobile-bff-migration-plan.md).
