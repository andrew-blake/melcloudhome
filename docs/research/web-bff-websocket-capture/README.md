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

   In this capture the two fields held the **same** UUID (`hash == userId`); the
   anonymized HAR preserves that by giving both the same placeholder.

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

### Multi-device routing (one socket serves all units)

Confirmed against a 3-ATA-unit account: with a **single** socket open, each unit's
out-of-band change produced a delta for **that unit only** (matched by its `id`),
with no cross-talk. All three units are served on the one socket. (Verified from
the integration's own delta logs while toggling each unit in turn.)

### WebSocket setting value types

The values below come from frames captured while changing each setting type in
[`web-bff-websocket_settings_anonymized.har`](web-bff-websocket_settings_anonymized.har)
(WS entries only, unit IDs anonymised) and from a log of every frame over 39
hours on an account with both unit types, recorded with
[`tools/ws_frame_logger.py`](../../../tools/ws_frame_logger.py). The ATA enum
values were mapped by stepping one unit through every mode, fan speed and vane
position from Home Assistant and matching each echo to the command.

A frame carries only the settings that changed, so one frame can hold several
(`RoomTemperature`, `Power` and `ActualFanSpeed` together is common). `name` is
PascalCase. Values arrive in two encodings:

- **Command echo.** Straight after a write, the frame carries enum settings as
  ints and `Power` as a JSON boolean.
- **Device report.** The unit's own periodic report carries the same settings
  as words (`"Auto"`, `"Swing"`, `"True"`), as `/context` does. A report can
  hold the state from before the latest command: one said `"Right"` two seconds
  after horizontal Swing was set.

Air-to-air (ATA):

| Setting (`name`) | WebSocket `value` | Type | REST `/context` gives |
|---|---|---|---|
| `Power` | `true` / `false` (echo), `"True"` / `"False"` (report) | boolean or string | string `"False"` |
| `OperationMode` | `1` Heat, `2` Dry, `3` Cool, `4` Fan, `5` Automatic | int | string `"Cool"` |
| `SetTemperature` | `20`, `20.5`, `24.5` | number (int or float; 0.5 steps) | string `"20"` |
| `RoomTemperature` | `21`, `21.5` | number (int or float) | string `"21.5"` |
| `SetFanSpeed` | `0` Auto, `1` to `5` One to Five | int | string `"Auto"` |
| `ActualFanSpeed` | `"0"` to `"4"` | **string** of a digit | string word `"Off"`, `"Two"` |
| `VaneVerticalDirection` | `0` Auto, `1` to `5` One to Five, `6` Swing (echo); `"Auto"` (report) | int or string | string `"Swing"` |
| `VaneHorizontalDirection` | `0` Auto, `1` Left, `2` LeftCentre, `3` Centre, `4` RightCentre, `5` Right, `7` Swing (echo); `"Right"`, `"Swing"` (report) | int or string | string `"Centre"` |

`6` never appeared for `VaneHorizontalDirection`.

Air-to-water (ATW):

| Setting (`name`) | WebSocket `value` | Type | REST `/context` gives |
|---|---|---|---|
| `OperationMode` | `"Stop"`, `"Heating"`, `"HotWater"`, `"FreezeStat"` | string | the same words |
| `ForcedHotWaterMode` | `"False"` | string | string `"False"` |
| `OutdoorTemperature` | `4` to `39` | int | string `"22"` |
| `RoomTemperatureZone1` | `19`, `19.5` | number (int or float) | string `"19"` |
| `TankWaterTemperature` | `"44"`, `"44.5"` | **string** | string `"47"` |

A parser that applies frame values needs its own coercion per setting. The
socket's types differ from `/context` and between echo and report frames.
They also differ across settings: `SetFanSpeed` is an int and `ActualFanSpeed`
a digit string, and `TankWaterTemperature` is a string where the other
temperatures are numbers.

### WebSocket message types

The 39-hour log holds these `messageType` values:

- `unitStateChanged`: the setting deltas above.
- `unitCommunicationLost` and `unitCommunicationRestored`: the cloud lost or
  regained contact with a unit.

```json
[{"messageType":"unitCommunicationLost",
  "Data":{"id":"<unitId>","timestamp":"2026-10-05T17:32:23.447+01:00"}}]
```

The two communication messages carry lowercase `id` and `timestamp` and no
`unitType`. The timestamp is local time with its UTC offset, about 10 seconds
before the frame arrived. The integration acts on `unitStateChanged` only.

No frame carried a Wi-Fi signal (`rssi`) value.

**Socket lifecycle:** across the capture there were **no client→server frames**
— no subscribe/handshake message; the client just opens `?hash=<hash>` and
receives. The upgrade negotiates the `permessage-deflate` extension (compressed
frames) and no subprotocol. Ping/pong keepalive and the server's close frame are
**not** observable here (Chrome does not surface WS control frames; a mitmproxy
relay destabilises this socket — see the reverse-engineering guide). The
integration drives its own keepalive via aiohttp `heartbeat=30s` and treats any
close as reconnect-with-backoff, so those details don't affect the client.
The frame logger records the closes. The server ends every session at the
2-hour cap, mostly with close code `1006` (dropped without a close frame) and
occasionally `1001` (going away).

### Mobile vs web: same WebSocket, two credential fronts

| | Mobile app | Web app |
|---|---|---|
| Hash source | AWS Lambda Function URL (bearer-authenticated) | `GET /ws/token` (BFF session cookie) |
| Response document | `{ "hash", "userId" }` | `{ "hash", "userId" }` |
| Connection | `wss://ws.melcloudhome.com/?hash=<hash>` | same |

Two different ways to obtain the credential, but the **same document shape and
the same socket**. The integration authenticates as the mobile client, so it
uses the Lambda path. Confirmed with a mitmproxy capture of the mobile app: its
Lambda fetch returns `{"hash": "<uuid>", "userId": "<uuid>"}` with `hash ==
userId`, and the value is the **same** hash the integration itself obtains — so
mobile, web, and the integration share one per-user credential (≈ the userId).
(iOS routes HTTP through a manual proxy but **not** the raw `wss` socket, so the
mobile socket frames themselves must be read another way — see the RE guide.)

### Root cause found: token persistence reloads the whole entry (dogfooding, 2026-07-12)

> **Scope note.** This section describes the **unmerged opt-in WebSocket feature
> branch**, not code on `main`. The names below (`async_get_ws_hash`, the
> WebSocket listener, the options-reload listener) live on that branch; `main`
> does not have them yet.

Dogfooding the opt-in WebSocket surfaced *transient* auth failures
(`ConfigEntryAuthFailed`, "Authentication failed after re-auth. Please
reconfigure."), each self-recovering on the next poll. Debug logging on the live
instance traced it to a regression **introduced by the WebSocket branch itself**
— it should be fixed before the WS code ships, not worked around.

**What the debug logs showed.** The coordinator's setup (energy + telemetry
timers + the WS listener) ran **three times in ~2h**, at exactly the
token-refresh moments (14:35 startup, then 15:22 and 16:22). Each run re-started
the WS listener and re-scheduled the timers. At 16:22 a proactive refresh got
HTTP **400** (the rotating refresh token was rejected), the client fell back to a
full re-login (200), and recovered.

**Root cause — a token refresh reloads the entire config entry.**

1. Every token refresh calls the `on_tokens_refreshed` callback →
   `coordinator._persist_tokens()`, which writes the new tokens with
   `hass.config_entries.async_update_entry(entry, data=...)`. (`_persist_tokens`
   already exists on `main`; on its own it is harmless.)
2. The WS branch adds `entry.add_update_listener(_async_options_updated)` in
   `__init__.py` so the integration reloads when the **WebSocket toggle** option
   changes. But HA fires that listener on **any** entry update — including the
   `data` write in step 1.
3. `_async_options_updated` calls `async_reload(entry)` unconditionally → the
   integration is torn down and set up again.

So on this branch **every token refresh reloads the integration.** MELCloud
refresh tokens are single-use/rotating; the reload re-initialises the client and
restores tokens from `entry.data` while other flows are mid-refresh, so the
rotating token occasionally desyncs → the 400 and the transient
`ConfigEntryAuthFailed`.

**Not a pre-existing `main` bug.** On `main`, `_persist_tokens` writes
`entry.data` but there is no update listener, so nothing reloads. The reload only
appears once the WS branch adds the options listener. The WS also adds more
refresh triggers (`async_get_ws_hash` fires `on_tokens_refreshed` too;
delta-driven debounced refreshes raise REST volume), which is why the desync
surfaces in practice rather than staying theoretical.

**Sensible fix (not a workaround).** The chosen fix is to make the options
listener react to *option* changes only, so a token-only `data` write no longer
reloads: `_async_options_updated` compares the entry's options against the
last-seen snapshot and returns early when they are unchanged. (A more thorough
alternative — keeping rotating tokens out of `entry.data` entirely, in a
`helpers.storage.Store`, so persistence never touches the config entry — was
considered but is heavier and needs a data migration; the targeted guard is
enough here since the reload is the WS branch's own new listener.) Separately,
the WS listener need not be recycled on every refresh at all: the `hash` is
user-scoped (≈ `userId`) and the socket is valid until the 2-hour cap.

The token-contention question here is a **debug-log** finding, not a HAR one —
it was confirmed from the `api.websocket` / `coordinator` / `api.auth` logs on
the live instance, not from a capture.

This is a coordinator/`__init__` fix that benefits the whole integration; the WS
work depends on it. Separately, consider not tearing the WS listener down on
every refresh at all — the `hash` is user-scoped (≈ `userId`) and the socket is
valid until the 2-hour cap, so it need not be recycled when the REST token
rotates.

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
