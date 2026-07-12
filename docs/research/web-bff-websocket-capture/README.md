# Web BFF & WebSocket API Capture

## What Was Captured

Browser DevTools HAR export of the **web app** (`melcloudhome.com`, a Blazor
WebAssembly SPA), captured 2026-07-12. Covers the full login, dashboard load,
and a **live WebSocket session** carrying real-time unit-state deltas.

This complements the [mobile BFF capture](../mobile-bff-captures/README.md): the
mobile app and the web app are two different front ends over the same backend,
and this capture is what pinned down the real-time WebSocket protocol for issue
[#174](https://github.com/andrew-blake/melcloudhome/issues/174).

## Key Findings

### Web app stack

- **Blazor WebAssembly** SPA (`_framework/blazor.webassembly.js`,
  `_framework/dotnet.native.*`, `blazor.boot.json`).
- **BFF pattern** (Duende): a server-side cookie session fronts the SPA. Login
  is kicked off by `GET /bff/login`, the session is read via `GET /bff/user`,
  and state-changing calls carry an `x-csrf` anti-forgery header.
- **Web BFF host:** `melcloudhome.com` — distinct from the mobile BFF host
  `mobile.bff.melcloudhome.com`. Same auth server and same data model, different
  edge.

### Login flow — single region, no per-country routing

Full redirect chain observed:

```
GET /bff/login                              (melcloudhome.com)      302
GET /connect/authorize                      (auth.melcloudhome.com) 302
GET /Account/Login                          (auth.melcloudhome.com) 302
GET /ExternalLogin/Challenge?scheme=cognito-meu                     302
GET /oauth2/authorize                       (cognito eu-west-1)     302
GET /login                                  (cognito eu-west-1)     200  ← credentials page
POST /login                                 (cognito eu-west-1)     302
GET /signin-oidc-meu                        (auth.melcloudhome.com) 302
GET /ExternalLogin/Callback                 (auth.melcloudhome.com) 302
GET /connect/authorize/callback             (auth.melcloudhome.com) 302
GET /signin-oidc                            (melcloudhome.com)      302
GET /dashboard                              (melcloudhome.com)      200
```

- IdentityServer federates to **a single external scheme** (`cognito-meu`) and
  **a single Cognito user pool** in `eu-west-1` (pool `eu-west-1_gFEQiVmPM`, app
  client `3g4d5l5kivuqi7oia68gib7uso`, visible in the CloudFront asset paths).
- There is **no country/region branching** — no geo-redirect, no per-country
  endpoint, no client-side script that computes the login URL. Routing is
  entirely server-side and single-region.
- The only locale-dependent request in the whole capture is
  `GET /api/announcement/it-IT` (localized in-app announcements). It has nothing
  to do with auth routing.

### Real-time WebSocket — issue #174

1. **Get the credential** — `GET /ws/token` (authenticated by the BFF session
   cookie + `x-csrf`) returns:

   ```json
   { "hash": "<uuid>", "userId": "<uuid>" }
   ```

   In this capture `hash == userId` (the two fields held the same UUID).

2. **Open the socket** — `wss://ws.melcloudhome.com/?hash=<hash>` → HTTP `101`
   Switching Protocols. The upgrade is authenticated **only** by the `hash`
   query parameter — no cookie or bearer is sent on the handshake.
   `Origin: https://melcloudhome.com`.

3. **Receive deltas** — captured text frames are a JSON array of
   `unitStateChanged` messages carrying **only the settings that changed**:

   ```json
   [{"messageType":"unitStateChanged",
     "Data":{"id":"<unitId>","unitType":"ata",
             "settings":[{"name":"Power","value":true}]}}]
   ```

   Note the field casing: `messageType` (lower-case) and `Data` (upper-case).
   In the capture, toggling a unit's power produced two frames (`Power: true`
   then `Power: false`) — confirming out-of-band changes are pushed live. This
   is exactly the shape the WebSocket listener parses.

### Mobile vs web: same WebSocket, two credential fronts

| | Mobile app | Web app |
|---|---|---|
| Hash source | AWS Lambda Function URL (bearer-authenticated) | `GET /ws/token` (BFF session cookie) |
| Response document | `{ "hash", "userId" }` | `{ "hash", "userId" }` |
| Connection | `wss://ws.melcloudhome.com/?hash=<hash>` | same |

Two different ways to obtain the credential, but the **same document shape and
the same socket**. The integration authenticates as the mobile client, so it
uses the Lambda path.

### Web BFF endpoint catalog (observed)

| Endpoint | Method(s) | Purpose |
|---|---|---|
| `/api/configuration` | GET | App/runtime configuration |
| `/bff/login`, `/bff/user` | GET | BFF login kickoff / session probe |
| `/ws/token` | GET | Issue the WebSocket `hash` credential |
| `/api/user/context` | GET | User + buildings + units context |
| `/api/user/systeminvites` | GET | Pending share/system invites |
| `/api/announcement/{locale}` | GET | Localized in-app announcements |
| `/api/cloudschedule/{id}` | POST / PUT / DELETE | Cloud schedule CRUD |
| `/api/cloudschedule/{id}/enabled` | PUT | Enable/disable a schedule |
| `/api/ataunit/{id}` | PUT | Send ATA control commands |

## Capture File

[`web-bff-websocket_anonymized.har`](web-bff-websocket_anonymized.har) is a
**curated, anonymized** slice of the original capture, safe to commit and
replay. `*.har` is gitignored by default; a scoped `.gitignore` exception
(`!docs/research/**/*_anonymized.har`) allows scrubbed capture files like this
one.

How it was produced from the raw browser HAR:

1. `tools/anonymize_har.py` — replaces UUIDs (user, building, device, system),
   emails, names, MAC/IP addresses, and tokens with stable placeholders so
   cross-request references still line up.
2. Manual curation (the anonymizer is not sufficient on its own — always review):
   - **Dropped the Cognito credential POST entirely** (it carried the username,
     password, and `cognitoAsfData` device fingerprint).
   - Dropped static assets (Blazor/`_framework`, `_content`, CSS, fonts, CDN
     libraries) and de-duplicated repeated polling calls.
   - Stripped `Cookie`/`Set-Cookie`/`Authorization`/`x-csrf` headers, HTML
     response bodies, and noisy `_initiator` stacks.
   - Redacted OIDC `code`/`state`/`session_state`, the BFF `sid`/session_state,
     and residual name claims in `/bff/user` (whose `{type,value}` claim shape
     the field-name anonymizer misses).

The **raw** `.har` contains a real `userId`, session artifacts, credentials, and
PII — it is **not** committed. Keep raw captures outside the repo (see
[mobile-bff-captures](../mobile-bff-captures/README.md) for the convention).

## Related

- **Issue:** [#174](https://github.com/andrew-blake/melcloudhome/issues/174) — real-time WebSocket updates
- **ADRs:** `docs/decisions/007-defer-websocket-implementation.md`,
  `docs/decisions/018-out-of-band-state-sync-limitation.md`
- **Mobile capture:** [docs/research/mobile-bff-captures/README.md](../mobile-bff-captures/README.md)
- **RE guide:** [docs/research/REVERSE_ENGINEERING.md](../REVERSE_ENGINEERING.md)
