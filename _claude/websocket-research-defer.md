# WebSocket Research Findings - DEFERRED

**Date**: 2025-01-17
**Status**: ⚠️ DEFERRED to v1.2+
**Reason**: Inconsistent message delivery across devices

---

## Decision: Defer WebSocket Implementation

**Why Defer:**
- ⚠️ **Unreliable message delivery**: Only one device receiving updates
- ⚠️ **Inconsistent behavior**: Dining Room (on, multiple changes) = no messages
- ⚠️ **Unpredictable**: Living Room (off) = constant messages
- ⚠️ **High risk**: Implementing unreliable real-time updates worse than polling
- ✅ **Current polling works**: 60s interval is acceptable for v1.0

**What We Learned:**
- ✅ Authentication method documented (query param)
- ✅ Connection protocol understood (HTTP upgrade)
- ✅ Message format captured (JSON array with settings)
- ⚠️ Subscription model unclear (why only one device?)
- ⚠️ Reliability unknown (needs more investigation)

---

## Research Summary

### Connection Protocol ✅

**Token Endpoint:**
```
GET /ws/token → {"hash": "...", "userId": "..."}
```

**WebSocket URL:**
```
wss://ws.melcloudhome.com/?hash={hash}
```

**Authentication:**
- Query parameter (not header)
- Standard HTTP 101 upgrade
- No handshake messages needed

**Connection Characteristics:**
- ✅ No keepalive required
- ✅ Auto-subscribe (no subscription messages)
- ✅ Receive-only (no client messages needed)

### Message Format ✅

**Example Message:**
```json
[
  {
    "messageType": "unitStateChanged",
    "Data": {
      "id": "bf8d1e84-95cc-44d8-ab9b-25b87a945119",
      "unitType": "ata",
      "settings": [
        {"name": "Power", "value": "False"},
        {"name": "SetTemperature", "value": 21},
        {"name": "RoomTemperature", "value": 18}
      ]
    }
  }
]
```

**Type Coercion Required:**
- Power: `"False"` (string) not `false` (boolean)
- ActualFanSpeed: `"0"` (string) not `0` (int)
- SetFanSpeed: Mixed (`0` int, `"Auto"` string, or `1-5` int)

### Critical Issue ⚠️

**Problem**: Inconsistent message delivery

**Observed Behavior:**
- Device 1 (Living Room, OFF): Receiving many WebSocket messages
- Device 2 (Dining Room, ON): No messages despite multiple setting changes

**Tested**:
- ✅ Multiple changes to Dining Room settings
- ✅ Both devices visible in REST API
- ✅ Both devices controlled via REST API
- ❌ WebSocket only sends updates for Living Room

**Possible Causes:**
1. Bug in MELCloud Home WebSocket server
2. Device-specific subscription required (undocumented)
3. Race condition or timing issue
4. Account/building-specific configuration
5. Device firmware version differences

**Risk Assessment:**
- 🔴 HIGH: Implementing unreliable real-time updates
- 🔴 HIGH: Users expecting instant updates that may not arrive
- 🔴 MEDIUM: Complexity of hybrid WebSocket + polling fallback
- 🟢 LOW: Current 60s polling is acceptable

---

## Alternative Approaches Considered

### Option 1: Implement with Per-Device Fallback
- WebSocket for devices that work
- Polling for devices that don't
- **Rejected**: Too complex, inconsistent UX

### Option 2: Implement WebSocket-Only (No Fallback)
- Accept that some devices won't update in real-time
- **Rejected**: Unacceptable reliability

### Option 3: Implement Full Hybrid (WebSocket + Polling)
- WebSocket for real-time, polling as backup
- **Rejected**: High complexity for uncertain benefit

### Option 4: Defer WebSocket Implementation ✅
- Keep current 60s polling (reliable)
- Investigate WebSocket behavior more thoroughly
- Implement in v1.2+ when understood
- **SELECTED**: Best risk/reward ratio

---

## What We Need Before Implementing

**Technical Investigation:**
1. Test with different account configurations
2. Test with different device firmware versions
3. Test with different building setups
4. Capture more message types (WiFi, error)
5. Monitor for 24+ hours to understand patterns

**Questions to Answer:**
- Why do only some devices get messages?
- Is there a device-level subscription?
- Are there WebSocket connection limits?
- Does device firmware affect WebSocket support?
- Is there a building-level configuration?

**Community Research:**
- Check if other users report same issue
- Review MELCloud Home forums/support
- Test with multiple accounts

---

## v1.1 Revised Scope (Without WebSocket)

**Remove:**
- ❌ WebSocket real-time updates
- ❌ WiFi signal sensor (requires WebSocket)
- ❌ Error binary sensor (requires WebSocket)
- ❌ Hybrid coordinator logic

**Keep:**
- ✅ Integration icon (fix 404)
- ✅ Basic diagnostics export
- ✅ Entity naming cleanup (remove `_heatpump`)
- ✅ README improvements
- ✅ Current 60s polling (reliable)

**Estimated Time**: 1-2 hours (reduced from 4 hours)

---

## Roadmap

### v1.1 (Next) - Polish & Diagnostics
- Integration icon
- Diagnostics export
- Entity naming improvements
- Documentation updates
- **Timeline**: 1-2 hours

### v1.2 (Future) - WebSocket Investigation
- Investigate inconsistent message delivery
- Test with multiple devices/accounts
- Implement WebSocket only if reliable
- **Timeline**: TBD (research needed)

### v2.0 (Long-term) - Advanced Features
- Energy tracking (if WebSocket reliable)
- Schedules API
- Scenes support
- **Timeline**: TBD

---

## Documentation for Future Reference

### Working cURL Command
```bash
curl 'wss://ws.melcloudhome.com/?hash=0125be99-65cb-4c97-a705-24794d6774b7' \
  -H 'Upgrade: websocket' \
  -H 'Origin: https://melcloudhome.com' \
  -H 'Connection: Upgrade' \
  -H 'Sec-WebSocket-Version: 13'
```

### Message Format Reference
```python
# Type coercion needed
def coerce_bool(value):
    return value.lower() == "true" if isinstance(value, str) else bool(value)

def coerce_int(value):
    return int(value) if isinstance(value, str) else value

# Delta merge required
for setting in message["Data"]["settings"]:
    field = setting["name"]
    value = coerce_type(setting["value"], field)
    device_state[field] = value
```

---

## Conclusion

**Decision**: Defer WebSocket to v1.2+

**Rationale**:
- Inconsistent behavior makes it unreliable
- More investigation needed
- Current polling works well
- Focus on polish and stability for v1.1

**Next Steps**:
1. Implement v1.1 without WebSocket (1-2 hours)
2. Continue monitoring WebSocket behavior
3. Investigate with community/support
4. Revisit in v1.2 when better understood

**Status**: ✅ Research complete, WebSocket deferred
