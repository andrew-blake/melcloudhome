# ADR-018: Out-of-Band State Sync Limitation and Deduplication Trade-off

**Status:** Accepted (limitation documented) — resolved by [ADR-019](019-websocket-realtime-updates.md)'s default-on WebSocket accelerator; still applies when the WebSocket toggle is turned off
**Date:** 2026-06-14

## Context

A user reported that when they change a setting in the MELCloud iPhone app, Home Assistant doesn't reflect it — and if they then try to command the same attribute from HA before the next poll, nothing happens. The unit doesn't respond.

Investigation traced the root cause to an interaction between the polling architecture and the deduplication logic in the control client layer.

## The Problem

The control client (`control_client_ata.py`, `control_client_atw.py`) deduplicates API calls by comparing the requested value against the coordinator's cached device state:

```python
device = self._get_device(unit_id)
if device and device.power == power:
    return  # skip API call
```

`_get_device` returns state from the coordinator's last `/context` poll. The poll interval is 60 seconds. If a user changes state out-of-band (via the MELCloud app or physical remote) and then immediately tries to command the same attribute from HA, the cache still reflects the old state — and the dedup check silently drops the API call.

**Example:** Unit is on. User turns it off from iPhone. User tries to turn it on from HA within 60s. Cache says power=on. HA requests power=on. Dedup fires. Unit never receives the command.

## Why Deduplication Exists

Deduplication was introduced in v2.0.0 (ATW support, January 2026) to address a real rate-limiting problem. HA scenes fire all service calls simultaneously for every attribute in the scene, even unchanged ones. Without dedup, applying a scene to a unit already at the target state fired 5–6 redundant API calls in one burst.

The MELCloud API rate-limited under this burst pattern. The `RequestPacer` (0.5s minimum between requests) was added as a second layer, but alone wasn't sufficient — dedup was needed to reduce call *count* before spacing could help. Together they achieve approximately 70% call reduction in typical scene usage.

Dedup and `RequestPacer` are complementary and were designed as a two-layer system. Removing dedup while keeping the pacer still results in burst patterns that may hit rate limits.

## Why Polling Frequency Doesn't Fix It

Reducing the poll interval (e.g. 60s → 30s) narrows the stale window but doesn't close it. A user changing state in the app and commanding HA within the new interval still hits the same problem. Additionally:

- ADR-007 chose 60s specifically as "API rate limit compliant" — the headroom above that threshold is unknown
- Reducing to 15s (4× baseline load) increases rate-limit risk for the steady-state poll itself
- At any polling frequency, the window can't reach zero without push/WebSocket

## Why WebSocket Doesn't Fix It (Yet)

Real-time push from the MELCloud server would eliminate the stale window entirely and make this a non-issue. However, WebSocket was deferred in ADR-007: the MELCloud WebSocket protocol exhibited unreliable message delivery during investigation (messages only reaching one device inconsistently). The protocol is not fully understood.

Until WebSocket is reliable and implemented, the stale-cache window is structural.

## Candidates Considered

| Option | Closes window? | Risk |
|---|---|---|
| Remove dedup entirely | No — re-exposes rate limiting | High: burst scene patterns hit API limits |
| Remove dedup from power only | Yes, for power | Low: 1 extra call per redundant scene trigger |
| Skip dedup when cache is stale (threshold) | No — threshold becomes a scene footgun | Medium: scenes firing after idle period bypass dedup, causing bursts |
| Force /context refresh before each command | No — adds a call per command | High: scenes fire 2× API calls minimum; slower and worse |
| Track "last commanded" instead of cache | No — doesn't eliminate scene redundancy | Medium: complex; doesn't solve original dedup problem |
| Reduce poll to 30s + remove power dedup | Partially | Low-medium: halves window, fixes worst case |
| WebSocket | Yes | Deferred (ADR-007) |

## Decision

**Document as a known limitation.** No code change at this time.

The deduplication and polling interval are a deliberate trade-off: scene reliability and API rate-limit compliance were prioritised over sub-60s sync of out-of-band changes. This is consistent with ADR-007's position that 60-second latency is acceptable for HVAC control.

The correct long-term fix is WebSocket push (ADR-007). Until then, the stale-cache window is inherent to the architecture.

### If the user impact grows

If out-of-band sync issues become a recurring complaint, the lowest-risk partial fix is:

1. **Remove dedup from `async_set_power` only** — power is the highest-impact case (unit can't be turned on at all). A single extra set_power call in a scene doesn't create a burst. All other attributes retain dedup.
2. **Reduce poll to 30s** — halves the window for all attributes. Requires verifying API rate-limit headroom first.

Do not remove dedup broadly without resolving rate-limit exposure.

## User Communication

Out-of-band changes (MELCloud app, physical remote) sync to HA within 60 seconds. If a user changes state in the app and needs to command immediately from HA, waiting ~60 seconds resolves it. This is a standard limitation of polling-based integrations.

## References

- [ADR-007: Defer WebSocket Implementation](007-defer-websocket-implementation.md)
- [ADR-011: Multi-Device-Type Architecture](011-multi-device-type-architecture.md) — introduced control client layer and dedup
- GitHub Discussion #135 — original user report
