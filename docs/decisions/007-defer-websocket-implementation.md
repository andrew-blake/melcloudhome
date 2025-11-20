# ADR-007: Defer WebSocket Implementation to Post-v1.2

**Status:** Accepted
**Date:** 2025-11-17
**Context:** Session 9 - v1.2 planning and scope refinement

## Context

During v1.1 development, we investigated WebSocket support for real-time device updates. The MELCloud Home API provides a WebSocket endpoint that could enable sub-second update latency instead of the current 60-second polling interval.

Initial investigation revealed inconsistent behavior that requires further research before production implementation.

## Decision

**We will defer WebSocket implementation to post-v1.2** and continue using the proven polling-based approach with `DataUpdateCoordinator`.

## Rationale

### 1. Inconsistent Behavior Observed

During testing, WebSocket messages exhibited unreliable delivery:

**Issue:** Only one device receiving updates consistently
- Multiple devices connected to same account
- WebSocket connection established successfully
- Messages only delivered to one device (inconsistent which one)
- No clear pattern in message routing

**Unknown Factors:**
- Message format and routing logic unclear
- Device subscription mechanism not understood
- Authentication/authorization requirements for WebSocket unclear
- No official API documentation for WebSocket protocol

### 2. Current Polling Works Well

The existing implementation is proven and reliable:
- ✅ 60-second polling interval (API rate limit compliant)
- ✅ DataUpdateCoordinator handles errors gracefully
- ✅ Automatic re-authentication on token expiry
- ✅ No known reliability issues
- ✅ 100% message delivery (vs inconsistent WebSocket)

**User Impact:** 60-second latency is acceptable for HVAC control
- Not time-critical (unlike lighting)
- State changes are infrequent
- Users can trigger manual refresh if needed

### 3. Scope Management for v1.2

v1.2 has significant value without WebSocket:

**High-Value Features:**
- ✅ Sensor platform (statistics, energy tracking)
- ✅ Binary sensors (error alerts)
- ✅ HACS distribution (easier installation)
- ✅ Entity descriptions (modern pattern)

**Estimated Effort:**
- Without WebSocket: 13-17 hours
- With WebSocket: 17-23 hours
- **Savings:** 4-6 hours of uncertain/risky work

### 4. Risk Mitigation

Deferring reduces v1.2 risks:
- ❌ **Don't risk:** Introducing instability with unreliable WebSocket
- ❌ **Don't risk:** Debugging complex async WebSocket issues
- ❌ **Don't risk:** Delayed v1.2 release for uncertain feature
- ✅ **Do:** Ship proven, stable features users need now

### 5. Future Investigation Path

Clear path forward for post-v1.2:

**Investigation Needed:**
1. Deep packet analysis of WebSocket protocol
2. Understand message routing mechanism
3. Identify device subscription requirements
4. Determine authentication model
5. Test reliability at scale (multiple devices/buildings)

**Implementation Requirements:**
- Reliability must be ≥99% (current polling: 100%)
- Graceful fallback to polling if WebSocket fails
- No memory leaks from long-running connections
- Proper reconnection handling
- Comprehensive error handling

## Consequences

### Positive

1. **Faster v1.2 Release:** 13-17 hours vs 17-23 hours
2. **Lower Risk:** Ship stable, proven features
3. **Focus:** Deliver high-value sensor platform well
4. **HACS Sooner:** Users get easier installation faster
5. **Proper Investigation:** Time to understand WebSocket properly

### Negative

1. **No Real-Time Updates:** 60-second polling continues
2. **User Expectation:** Some users may want instant updates
3. **Competitive Feature:** Other integrations may have WebSocket

### Neutral

1. **Not a Regression:** Current behavior unchanged
2. **Future Path Clear:** Can add WebSocket later
3. **Incremental Value:** v1.2 still valuable without it

## Mitigation

To address negative consequences:

1. **Document Clearly:**
   - README states polling-based (60s updates)
   - Changelog notes WebSocket deferred, not canceled
   - Users know it's on roadmap

2. **Manual Refresh:**
   - Coordinator supports `async_request_refresh()`
   - Users can trigger immediate update if needed
   - Service call or automation support

3. **Post-v1.2 Priority:**
   - WebSocket is first feature for v1.3
   - Dedicated investigation session
   - Proper time for protocol research

## Implementation Impact

### v1.2 Scope Changes

**REMOVED:**
- ❌ WebSocket connection management
- ❌ WebSocket message parsing
- ❌ Real-time state updates
- ❌ Fallback logic

**KEPT (Unchanged):**
- ✅ Sensor platform with entity descriptions
- ✅ Binary sensor platform
- ✅ HACS repository setup
- ✅ DataUpdateCoordinator (60s polling)

### Code Changes

**No changes required** - existing polling continues as-is.

**Documentation updates:**
- Update ROADMAP.md (WebSocket → v1.3)
- Update README.md (clarify polling-based)
- Reference this ADR in WebSocket research doc

## Alternatives Considered

### Alternative 1: Implement WebSocket Despite Issues

**Approach:** Add WebSocket with known issues, mark as experimental

**Pros:**
- Users can opt-in to test
- Real-time updates for some devices

**Cons:**
- Inconsistent behavior confuses users
- Support burden for unreliable feature
- Risk of bug reports and negative feedback
- Delays v1.2 for uncertain value

**Rejected because:** Shipping unreliable features harms integration quality and reputation.

### Alternative 2: Delay All of v1.2 Until WebSocket Works

**Approach:** Don't release v1.2 until WebSocket is reliable

**Pros:**
- Complete feature set
- No future WebSocket refactoring

**Cons:**
- Delays valuable sensor platform
- Delays HACS distribution
- Uncertain timeline (weeks? months?)
- Blocks user value unnecessarily

**Rejected because:** Sensor platform and HACS provide immediate user value, shouldn't be blocked.

### Alternative 3: Defer WebSocket (Selected)

**Approach:** Ship v1.2 without WebSocket, investigate properly post-release

**Pros:**
- Faster release (13-17h vs 17-23h)
- Lower risk
- Focus on proven features
- Time for proper WebSocket investigation

**Cons:**
- No real-time updates in v1.2
- Potential user disappointment

**Selected because:** Maximizes user value while minimizing risk. Clear path forward for WebSocket in v1.3.

## Success Criteria

**v1.2 Success (Without WebSocket):**
- ✅ Sensor platform working reliably
- ✅ Binary sensors providing error alerts
- ✅ HACS installation smooth
- ✅ Polling continues at 60s (proven reliable)
- ✅ No user complaints about stability

**Post-v1.2 WebSocket Investigation:**
- 🔲 Understand message routing mechanism
- 🔲 Achieve ≥99% message delivery reliability
- 🔲 Document WebSocket protocol completely
- 🔲 Implement with graceful fallback
- 🔲 Test with multiple devices/buildings

## References

- [WebSocket Research (v1.1 Investigation)](../research/websocket-research-defer.md) - Initial findings
- [Session 9 Research Findings](../research/session-9-research-findings.md) - WebSocket patterns from Nest

## Timeline

**v1.1:** Initial WebSocket investigation → Inconsistent behavior discovered
**v1.2:** Defer WebSocket → Focus on sensors + HACS
**v1.3+:** Dedicated WebSocket investigation and implementation

## Notes

This decision prioritizes shipping stable, valuable features over incomplete experimental ones. WebSocket remains a desired feature but must meet reliability standards before production release.

The existing 60-second polling via DataUpdateCoordinator is proven, reliable, and sufficient for HVAC control use cases. Real-time updates are a nice-to-have, not a requirement.

**Key Insight:** Better to ship v1.2 without WebSocket than to delay v1.2 or ship unreliable WebSocket implementation.
