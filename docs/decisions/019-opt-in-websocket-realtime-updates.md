# ADR-019: Opt-In Real-Time WebSocket Updates

**Status:** Accepted
**Date:** 2026-07-19
**Supersedes:** [ADR-007](007-defer-websocket-implementation.md) (deferral); resolves the structural limitation documented in [ADR-018](018-out-of-band-state-sync-limitation.md) when enabled

## Context

ADR-007 deferred WebSocket support because the protocol was not understood and
message delivery looked unreliable — with multiple devices on one account, only
one device appeared to receive updates. ADR-018 later documented the
consequence as structural: out-of-band changes (MELCloud app, physical remote)
take up to 60 seconds to reach HA, and the control-client dedup can silently
drop commands issued inside that stale window. Both ADRs named WebSocket push
as the correct long-term fix.

The investigation in issue #174 re-derived the protocol from the MELCloud Home
web app (captures in
[research/web-bff-websocket-capture](../research/web-bff-websocket-capture/README.md),
PR #175) and contradicted ADR-007's blocker: a single socket serves **all**
units on the account, and multi-day live monitoring showed out-of-band updates
arriving reliably for every unit. The one-device-only behavior observed in
2025 did not reproduce.

### Protocol summary

- A Lambda Function URL (`WS_HASH_URL`), called with the normal Bearer token,
  returns a short-lived `{hash, userId}` credential.
- The client connects to `wss://ws.melcloudhome.com/?hash=<hash>`.
- The server pushes `unitStateChanged` messages; inbound frames are ignored.
  Frames carry the unit id and the *changed* settings only.
- AWS API Gateway drops every connection at a hard 2-hour cap; reconnection
  is normal operation, not an error.

## Decision

Implement WebSocket support as an **opt-in accelerator over REST polling**
(options-flow toggle `enable_websocket`, default off, labeled experimental):

1. **REST stays the source of truth.** A delta frame is never applied to
   entity state. It only triggers the existing debounced coordinator refresh
   (~2 s), which re-reads `/context` over REST.
2. **Polling continues unchanged.** The 60-second poll runs whether or not the
   socket is healthy; entities never become unavailable because of WebSocket
   state.
3. **The listener is best-effort.** Any failure — hash endpoint down,
   handshake refused, hash expired — backs off and retries; the integration
   silently degrades to plain polling.

### Why deltas are refresh triggers, not state

Building entity state directly from frames would mean trusting a second,
less-tested parser for the same data, and the frames don't deserve that trust:

- **Frames are partial.** Only changed settings appear; everything else would
  have to be merged with cached state.
- **Frames are inconsistently typed.** The same field differs between the
  socket and REST representations (e.g. `SetFanSpeed` arrives as an int while
  `ActualFanSpeed` is a string; `Data` vs `data` casing varies).
- **MELCloud silently drops invalid writes.** A frame proves the server
  emitted an event, not that the resulting state is what the frame implies —
  only a REST read shows the state the server actually settled on.

Treating deltas purely as "something changed, go poll now" keeps the single
proven REST parser authoritative and makes the WebSocket path safe to fail in
any direction.

### Resilience

- Exponential reconnect backoff, 5 s → 300 s, with ±20% jitter
  (`random.uniform(0.8, 1.2)`) so a MELCloud outage doesn't resynchronize
  every installation onto the same reconnect schedule.
- The backoff resets only after a session that survived ≥ 60 s. A server that
  accepts the handshake and closes immediately (expired/revoked hash,
  server-side throttling) keeps escalating — every reconnect cycle costs a
  Lambda hash fetch and potentially a token refresh, so this is the one path
  that could otherwise nudge an account toward rate limits.
- aiohttp heartbeat (30 s) detects dead connections.
- Connection lost/restored transitions log at INFO so a user who enables the
  toggle can tell from default logs whether it is working; per-retry noise
  stays at DEBUG.

### Lifecycle

The listener (`api/websocket.py`) is deliberately HA-agnostic: one
long-running `run()` coroutine plus a delta callback. The coordinator owns it,
launching it via `entry.async_create_background_task`, so HA cancels it
automatically on entry unload/reload — no manual cancel bookkeeping.
It is disabled in debug/mock mode.

## Consequences

- With the toggle on, the ADR-018 stale window shrinks from ≤ 60 s to roughly
  the debounce delay plus one REST poll — which also defuses the dedup
  command-drop scenario in practice. ADR-018's limitation still applies to
  the default (off) configuration.
- The integration requires HA ≥ 2025.8.0 (`OptionsFlowWithReload`, new in
  2025.8; entry-scoped background tasks have been available since ~2023.4).
- One extra long-lived connection and a hash fetch per (re)connect; steady
  state adds no REST traffic beyond the refreshes that real changes trigger.
- The mock server does not yet expose a WS endpoint; local dev/e2e coverage
  of the socket is planned separately (#180).

## References

- [ADR-007: Defer WebSocket Implementation](007-defer-websocket-implementation.md)
- [ADR-018: Out-of-Band State Sync Limitation](018-out-of-band-state-sync-limitation.md)
- Issue #174 — WebSocket investigation; PR #175 — protocol captures
- PR #176 — implementation
