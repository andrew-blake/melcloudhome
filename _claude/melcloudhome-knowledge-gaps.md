# MELCloud Home API - Knowledge Gaps & Testing Plan

**Document Version:** 1.1
**Last Updated:** 2025-11-16
**Status:** Gap Analysis Complete - GAP-002 RESOLVED ✅

---

## Overview

This document catalogs all known gaps in our MELCloud Home API understanding and provides a systematic plan to address them. We now have 87% API coverage with critical enum mappings fully verified. The remaining gaps consist of edge cases, advanced features, and non-blocking issues.

---

## Executive Summary

### Current Knowledge Status

| Category | Coverage | Confidence | Priority to Fill |
|----------|----------|------------|------------------|
| Authentication | 90% | High | Low |
| Basic Control API | 95% | Very High | Low |
| Schedule CRUD | 85% | High | Medium |
| Schedule Enable/Disable | 40% | Low | **HIGH** |
| Telemetry Basics | 80% | High | Low |
| Enum Mappings | 100% ✅ | Very High | ~~HIGH~~ **DONE** |
| Advanced Features | 20% | Low | Low |
| Scenes | 0% | None | Medium |
| Error Handling | 60% | Medium | Medium |
| Edge Cases | 30% | Low | Medium |

**Overall API Understanding: ~87%** (improved from 85%)

---

## Critical Gaps (Blocking Production)

### GAP-001: Schedule Enable/Disable Endpoint Failures

**Status:** 🔴 CRITICAL - Feature Broken

**What We Know:**
- Endpoint: `PUT /api/cloudschedule/{unit_id}/enabled`
- Request body: `{"enabled": true}` or `{"enabled": false}`
- Both enable and disable attempts returned HTTP 500 errors
- Response body was empty

**What We DON'T Know:**
- Root cause of 500 errors
- Prerequisites for enabling schedules
- Whether schedules must meet validation criteria
- If unit configuration affects enablement

**Impact:**
- Cannot programmatically enable/disable schedules
- Users would need to use MELCloud app for this
- Major limitation for HA automation
- Could be showstopper for schedule feature

**Hypotheses:**
1. Schedules must have future times (not past)
2. At least one schedule must exist
3. Schedules must be "valid" (all required fields populated)
4. Unit capabilities may restrict schedule enablement
5. Time zone or DST issues

**Testing Plan:**
```
Test 1: Prerequisites Testing
- [ ] Try enabling with zero schedules
- [ ] Try enabling with one valid schedule
- [ ] Try enabling with multiple schedules
- [ ] Try enabling with past-time schedule
- [ ] Try enabling with future-time schedule

Test 2: Schedule Validation
- [ ] Create minimal schedule (only required fields)
- [ ] Create complete schedule (all fields)
- [ ] Test with different operation modes
- [ ] Test with different day combinations

Test 3: Timing Issues
- [ ] Create schedule for tomorrow, try enabling
- [ ] Create schedule for next week, try enabling
- [ ] Test around DST transition dates

Test 4: Error Response Analysis
- [ ] Capture full error response with headers
- [ ] Check for any error messages in body
- [ ] Look for validation errors in response
- [ ] Monitor browser console for client-side errors
```

**Resolution Path:**
1. Execute testing plan above
2. If still failing, check UI behavior (does enable work in app?)
3. Compare request headers/cookies with successful UI requests
4. Consider contacting Mitsubishi API support (if available)
5. Document workaround: instruct users to enable via app

**Estimated Time:** 1-2 hours
**Priority:** P0 - Must fix or document limitation

---

### GAP-002: Operation Mode Enum Mapping (Schedule API)

**Status:** 🟢 RESOLVED - Fully Verified

**Resolution Date:** 2025-11-16

**Verified Mapping:**
```
1 = Heat       ✅ Verified via UI test
2 = Dry        ✅ Verified via UI test
3 = Cool       ✅ Verified via UI test
4 = Fan        ✅ Verified via UI test
5 = Automatic  ✅ Verified via UI test
```

**Testing Methodology:**
- Created schedule for each mode via UI
- Captured network request POST body
- Observed operationMode integer value
- All 5 modes tested and verified

**Findings:**
- Schedule API uses different integer mapping than expected
- Order is NOT alphabetical or same as Control API
- Mapping: 1=Heat, 2=Dry, 3=Cool, 4=Fan, 5=Automatic
- All modes supported in schedule creation

**Documentation Updated:**
- ✅ `melcloudhome-schedule-api.md` updated with verified values
- ✅ All "inferred" warnings removed
- ✅ Ready for production implementation

**Time Spent:** 45 minutes
**Priority:** P0 - COMPLETED

---

### GAP-003: Rate Limiting and API Quotas

**Status:** 🟡 HIGH RISK - Unknown Limits

**What We Know:**
- API uses HTTPS REST endpoints
- CSRF token required via `x-csrf: 1` header
- No rate limit errors encountered during testing (low volume)

**What We DON'T Know:**
- Requests per minute/hour/day limits
- Rate limit response codes (429? 503?)
- Rate limit headers (X-RateLimit-*?)
- Per-endpoint vs global limits
- Penalty for exceeding (temporary ban? permanent?)
- Whether limits differ for different endpoints

**Impact:**
- HA polling could hit rate limits
- Multi-unit systems multiply request volume
- Could get account blocked
- Need backoff strategy
- May need WebSocket for real-time updates instead

**Testing Plan:**
```
Test 1: Rapid Polling
- [ ] Poll /api/user/context 100 times in 1 minute
- [ ] Monitor for error responses
- [ ] Check response headers for rate limit info
- [ ] Document any 429/503 responses

Test 2: Sustained Load
- [ ] Poll every 10 seconds for 1 hour
- [ ] Poll every 30 seconds for 6 hours
- [ ] Monitor for degradation or blocking
- [ ] Document sustainable polling rate

Test 3: Burst Control
- [ ] Send 10 control commands in 10 seconds
- [ ] Send 50 control commands in 1 minute
- [ ] Check for rejection or throttling
- [ ] Verify commands execute successfully

Test 4: WebSocket Investigation
- [ ] Monitor /ws/token endpoint usage
- [ ] Check for WebSocket connections in DevTools
- [ ] Analyze real-time update mechanism
- [ ] Determine if polling can be replaced
```

**Resolution Path:**
1. Start with conservative polling (every 60 seconds)
2. Gradually increase frequency while monitoring
3. Document first signs of throttling
4. Implement exponential backoff
5. Investigate WebSocket alternative
6. Recommend polling intervals in documentation

**Estimated Time:** 2-3 hours (requires sustained testing)
**Priority:** P0 - Must know before production deployment

---

## High Priority Gaps (Limits Functionality)

### GAP-004: Vane Direction Enum Mapping

**Status:** 🟡 MEDIUM RISK - Functional Limitation

**What We Know:**
- Schedule API uses integer enums for vane positions
- Observed values in existing schedules: 6, 7
- Control API uses strings: "Auto", "Swing", "One"-"Five", "Left", "Center*", "Right"
- Separate enums for vertical and horizontal

**What We DON'T Know:**
- Complete integer-to-position mapping
- Whether 6=Auto and 7=Swing (or vice versa)
- Values for specific positions (One-Five for vertical)
- Values for Left/Center/Right (horizontal)
- If vertical and horizontal use same enum values

**Current Best Guess:**
```
Vertical/Horizontal (Unknown order):
6 = Auto (maybe?)
7 = Swing (maybe?)
0-5 = Specific positions? (which ones?)
```

**Impact:**
- Cannot set specific vane positions in schedules
- Can only use "default" values (6, 7) seen in existing schedules
- Limits user control over airflow direction
- Not critical (Auto/Swing work fine) but reduces functionality

**Testing Plan:**
```
Test 1: Systematic Vane Testing (Vertical)
For each value 0-10:
- [ ] Create schedule with vaneVerticalDirection: N
- [ ] Check if schedule creation succeeds
- [ ] Observe vane icon/label in schedule list
- [ ] Cross-reference with control API positions

Test 2: Systematic Vane Testing (Horizontal)
For each value 0-10:
- [ ] Create schedule with vaneHorizontalDirection: N
- [ ] Check if schedule creation succeeds
- [ ] Observe vane icon/label in schedule list
- [ ] Cross-reference with control API positions

Test 3: Cross-Reference Existing Data
- [ ] Review /api/user/context response
- [ ] Check device capabilities vane settings
- [ ] Compare with control API vane values
- [ ] Look for enum definitions in responses
```

**Resolution Path:**
1. Create schedules with each enum value
2. Observe UI representation
3. Build verified mapping table
4. Update documentation with verified values
5. Implement dropdown mapping in HA integration

**Estimated Time:** 45-60 minutes
**Priority:** P1 - Should verify for complete feature set

---

### GAP-005: Schedule UPDATE Endpoint

**Status:** 🟡 MISSING FEATURE - UX Impact

**What We Know:**
- Can CREATE schedules: `POST /api/cloudschedule/{unit_id}`
- Can DELETE schedules: `DELETE /api/cloudschedule/{unit_id}/{schedule_id}`
- No UPDATE endpoint discovered

**What We DON'T Know:**
- Is there a `PUT /api/cloudschedule/{unit_id}/{schedule_id}` endpoint?
- Or `PATCH /api/cloudschedule/{unit_id}/{schedule_id}`?
- How does UI handle schedule editing?
- Must we DELETE + CREATE to modify?

**Impact:**
- To edit schedule, must delete and recreate
- Loses schedule ID (if user has references)
- More API calls required
- Potential for temporary gaps if delete succeeds but create fails
- Poor UX for schedule management

**Testing Plan:**
```
Test 1: Try PUT Method
- [ ] Create a test schedule, note ID
- [ ] Send PUT to /api/cloudschedule/{unit_id}/{schedule_id}
- [ ] Include modified schedule in body
- [ ] Check for 200 (success) vs 404/405 (not found/not allowed)

Test 2: Try PATCH Method
- [ ] Send PATCH with partial changes
- [ ] Check response code
- [ ] Verify if schedule was updated

Test 3: Observe UI Behavior
- [ ] Open schedule in UI for editing
- [ ] Make changes in UI
- [ ] Monitor DevTools network tab
- [ ] Capture actual update mechanism
- [ ] Document endpoint used

Test 4: Alternative Patterns
- [ ] Check if DELETE returns new ID
- [ ] Check if POST can specify ID (idempotent create)
- [ ] Look for batch update endpoints
```

**Resolution Path:**
1. Monitor UI schedule editing behavior
2. Test PUT and PATCH methods
3. If no UPDATE exists, implement DELETE+CREATE pattern
4. Add transaction safety (rollback on failure)
5. Document limitation in integration docs

**Estimated Time:** 30-45 minutes
**Priority:** P1 - Important for good UX

---

### GAP-006: Scenes API (Undiscovered)

**Status:** 🔴 COMPLETELY UNKNOWN

**What We Know:**
- "Scenes" menu item exists in hamburger menu
- `/api/user/context` response includes `"scenes": []` (empty array)
- No scenes have been created in test account

**What We DON'T Know:**
- What scenes are (saved device states? groups? automation?)
- Scene creation API
- Scene execution/trigger API
- Scene data structure
- Scene capabilities (multi-unit? scheduled? conditional?)
- How scenes differ from schedules

**Impact:**
- Missing entire feature category
- Unknown if scenes are important for HA integration
- Could be redundant with HA scenes/scripts
- Or could provide unique cloud-based automation

**Testing Plan:**
```
Test 1: UI Exploration
- [ ] Navigate to Scenes from hamburger menu
- [ ] Take screenshots of scene interface
- [ ] Document UI options and fields
- [ ] Try creating a simple scene

Test 2: Scene Creation
- [ ] Create scene via UI
- [ ] Monitor network requests during creation
- [ ] Capture POST/PUT endpoint
- [ ] Document request body structure
- [ ] Check /api/user/context for new scene

Test 3: Scene Execution
- [ ] Trigger/activate scene via UI
- [ ] Capture API call for scene execution
- [ ] Observe what happens to devices
- [ ] Document scene execution behavior

Test 4: Scene Management
- [ ] List scenes (GET endpoint)
- [ ] Edit scene (UPDATE endpoint)
- [ ] Delete scene (DELETE endpoint)
- [ ] Test scene with multiple units
- [ ] Test scene with schedules

Test 5: Advanced Scene Features
- [ ] Check for conditional logic
- [ ] Check for time-based triggers
- [ ] Check for geofencing
- [ ] Check for scene sharing/templates
```

**Resolution Path:**
1. Full UI exploration and documentation
2. Capture all scene-related API endpoints
3. Create `melcloudhome-scenes-api.md` document
4. Determine if scenes should be integrated into HA
5. Decide integration strategy (expose vs ignore)

**Estimated Time:** 1-2 hours
**Priority:** P1 - Should document before finalizing integration

---

## Medium Priority Gaps (Enhanced Functionality)

### GAP-007: Temperature Range Validation by Mode

**Status:** 🟢 LOW RISK - Conservative Approach Works

**What We Know:**
- General temperature range: 10-31°C
- Device capabilities specify mode-specific ranges:
  - Heat: 10-31°C
  - Cool/Dry: 16-31°C
  - Auto: 16-31°C
- Increments: 0.5°C (half-degree support confirmed)

**What We DON'T Know:**
- If schedule API enforces these ranges server-side
- What happens with out-of-range values (reject? clamp?)
- If control API and schedule API have same validation
- Edge case: Heat mode at 15.5°C

**Testing Plan:**
```
Test 1: Boundary Testing - Heat Mode
- [ ] Schedule with Heat at 9.5°C (below min)
- [ ] Schedule with Heat at 10°C (at min)
- [ ] Schedule with Heat at 31°C (at max)
- [ ] Schedule with Heat at 31.5°C (above max)

Test 2: Boundary Testing - Cool Mode
- [ ] Schedule with Cool at 15.5°C (below min)
- [ ] Schedule with Cool at 16°C (at min)
- [ ] Schedule with Cool at 31°C (at max)

Test 3: Invalid Increments
- [ ] Schedule with temperature 20.3°C (not 0.5 increment)
- [ ] Schedule with temperature 20.7°C
- [ ] Check if accepted, rejected, or rounded

Test 4: Error Response Analysis
- [ ] Document error messages for invalid temps
- [ ] Check if API provides validation guidance
- [ ] Look for min/max in error response
```

**Resolution Path:**
1. Implement client-side validation using known ranges
2. Test boundary conditions
3. Handle errors gracefully with user feedback
4. Update documentation with confirmed ranges
5. Add unit tests for validation logic

**Estimated Time:** 30 minutes
**Priority:** P2 - Low risk, can use conservative validation

---

### GAP-008: Schedule Conflict Resolution

**Status:** 🟢 LOW RISK - Edge Case

**What We Know:**
- Multiple schedules can exist for same unit
- Can have schedules for different days
- Can have multiple schedules per day

**What We DON'T Know:**
- What happens with same day, same time conflicts?
- Does last-created win? First? Undefined?
- Are conflicts prevented at creation time?
- How do schedules interact with manual overrides?
- Duration of manual override before schedule resumes?

**Testing Plan:**
```
Test 1: Identical Time Conflicts
- [ ] Create schedule: Monday 10:00 Heat 20°C
- [ ] Create schedule: Monday 10:00 Cool 25°C
- [ ] Check if second creation rejected
- [ ] If allowed, observe which executes

Test 2: Overlapping Schedules
- [ ] Create schedule: Monday 10:00 Heat 20°C
- [ ] Create schedule: Monday 10:01 Cool 25°C
- [ ] Observe behavior (immediate switch? delay?)

Test 3: Manual Override Interaction
- [ ] Create schedule: Today [now+5min] Heat 20°C
- [ ] Manually set to Cool 25°C before schedule time
- [ ] Wait for schedule time
- [ ] Observe if schedule executes or is skipped

Test 4: Schedule Deletion During Override
- [ ] Set manual override
- [ ] Delete all schedules
- [ ] Check if manual override persists
```

**Resolution Path:**
1. Document conflict behavior in testing
2. Add warnings in HA UI about conflicts
3. Implement client-side conflict detection
4. Recommend best practices to users
5. Consider adding conflict resolution options

**Estimated Time:** 45-60 minutes (requires waiting for schedule times)
**Priority:** P2 - Edge case, can document limitation

---

### GAP-009: Error Codes and Diagnostics

**Status:** 🟡 MEDIUM RISK - Limited Error Handling

**What We Know:**
- Device has `isInError: false` boolean flag
- Error log endpoint exists: `GET /api/ataunit/{unit_id}/errorlog`
- Current test unit has no errors (can't test)

**What We DON'T Know:**
- Complete list of error codes
- Error code format (string? integer? hex?)
- Error severity levels
- Error descriptions/messages
- How to clear errors
- Auto-clear vs manual clear
- Error notification mechanism

**Testing Plan:**
```
Test 1: Error Log Exploration
- [ ] Call /api/ataunit/{unit_id}/errorlog
- [ ] Document response format
- [ ] Check if empty or contains historical errors
- [ ] Look for error code field names

Test 2: Manufactured Error Testing (If Safe)
- [ ] Create impossible schedule (far past)
- [ ] Send invalid control command
- [ ] Rapidly toggle power
- [ ] Check if generates errors

Test 3: Error Monitoring
- [ ] Poll error log periodically
- [ ] Wait for natural error occurrence
- [ ] Document error when it appears
- [ ] Test error clearing (if possible)

Test 4: Cross-Reference Documentation
- [ ] Search Mitsubishi documentation
- [ ] Check service manual error codes
- [ ] Map API errors to hardware errors
```

**Resolution Path:**
1. Monitor systems for natural errors
2. Document error codes as they occur
3. Create error code reference document
4. Implement error code display in HA
5. Add troubleshooting guide

**Estimated Time:** Ongoing (collect over time)
**Priority:** P2 - Can handle unknown errors gracefully

---

### GAP-010: Telemetry Details

**Status:** 🟢 LOW RISK - Basic Functionality Works

**What We Know:**
- Temperature history: `GET /api/telemetry/actual`
- Operation mode history: `GET /api/telemetry/operationmode`
- Energy consumption: `GET /api/telemetry/energy`
- Basic date range parameters work

**What We DON'T Know:**
- Maximum date range allowed per query
- Data retention period (how far back?)
- Data granularity (per minute? per 15 min? per hour?)
- Rate limits for telemetry queries
- If aggregation endpoints exist (daily totals, averages)
- Missing data handling (gaps in history)

**Testing Plan:**
```
Test 1: Date Range Limits
- [ ] Query last 7 days
- [ ] Query last 30 days
- [ ] Query last 365 days
- [ ] Query from 5 years ago
- [ ] Document first failure point

Test 2: Data Granularity
- [ ] Query 1 hour period
- [ ] Count data points returned
- [ ] Calculate time between points
- [ ] Check if consistent across time ranges

Test 3: Rate Limiting
- [ ] Make 10 telemetry queries in 1 minute
- [ ] Make 100 telemetry queries in 10 minutes
- [ ] Monitor for throttling
- [ ] Document safe query rate

Test 4: Missing Data
- [ ] Simulate unit offline period
- [ ] Query data spanning offline period
- [ ] Document gap representation (null? omitted?)
```

**Resolution Path:**
1. Test various date ranges
2. Document data granularity
3. Implement safe polling intervals
4. Add data aggregation in HA (if API doesn't provide)
5. Handle gaps gracefully

**Estimated Time:** 1 hour
**Priority:** P2 - Nice to have, basic queries work

---

## Low Priority Gaps (Advanced Features)

### GAP-011: Advanced Device Features

**Status:** 🟢 LOW RISK - Optional Features

**Features Mentioned in Capabilities but Not Tested:**

1. **Frost Protection**
   - Field: `"frostProtection": null`
   - Purpose: Prevent freezing when away
   - API: Unknown

2. **Overheat Protection**
   - Field: `"overheatProtection": null`
   - Purpose: Safety limit on heating
   - API: Unknown

3. **Holiday Mode**
   - Field: `"holidayMode": null`
   - Purpose: Extended away settings
   - API: Unknown

4. **Demand Side Control**
   - Capability: `"hasDemandSideControl": true`
   - Purpose: Load shedding for utility programs
   - API: Unknown

5. **Energy Produced Opt-in**
   - Field: `"energyProducedOptIn": null`
   - Purpose: Solar integration? Reporting?
   - API: Unknown

6. **Wide Vane Support**
   - Capability: `"supportsWideVane": false`
   - Some units may have this
   - API: Unknown

**Testing Plan:**
```
Test 1: UI Feature Exploration
For each feature:
- [ ] Search UI for feature controls
- [ ] Take screenshots of settings
- [ ] Document configuration options
- [ ] Enable/configure if available

Test 2: API Discovery
For each feature:
- [ ] Monitor network during UI interaction
- [ ] Capture GET/PUT/POST requests
- [ ] Document endpoint and payload
- [ ] Test via direct API calls

Test 3: Integration Planning
For each feature:
- [ ] Assess value for HA integration
- [ ] Determine if should expose in HA
- [ ] Plan entity/service structure
- [ ] Document configuration requirements
```

**Resolution Path:**
1. Deprioritize unless user requests feature
2. Document as "future enhancement"
3. Explore UI as time permits
4. Add to integration roadmap
5. Implement based on user demand

**Estimated Time:** 2-3 hours total
**Priority:** P3 - Future enhancements

---

### GAP-012: Multi-Building and Guest Access

**Status:** 🟢 LOW RISK - Single-Building Tested

**What We Know:**
- User can have multiple buildings
- User can have guest access to other buildings
- Test account has 1 building, 2 units
- Structure supports multi-building

**What We DON'T Know:**
- Guest user permission levels
- What guests can/cannot do
- Guest API endpoints (invite, revoke)
- Building-level controls (if any)
- Bulk operations across buildings
- How guest buildings appear in UI

**Testing Plan:**
```
Test 1: Guest Access Setup
- [ ] Create second test account
- [ ] Grant guest access from main account
- [ ] Monitor API calls during guest invite
- [ ] Document invitation mechanism

Test 2: Guest Permissions
- [ ] Login as guest user
- [ ] Attempt various operations
- [ ] Document what is allowed/denied
- [ ] Check for permission-denied errors

Test 3: Multi-Building Operations
- [ ] Test with account having 2+ buildings
- [ ] Check for bulk operation endpoints
- [ ] Test building-level settings
- [ ] Document any building management APIs
```

**Resolution Path:**
1. Support single building first (MVP)
2. Add multi-building support in v2
3. Document guest access as "not yet supported"
4. Collect user feedback on need
5. Implement if demanded

**Estimated Time:** 1-2 hours
**Priority:** P3 - Advanced use case

---

### GAP-013: WebSocket / Real-Time Updates

**Status:** 🟡 MEDIUM PRIORITY - Polling Alternative

**What We Know:**
- WebSocket token endpoint exists: `GET /ws/token`
- Token returned during page load
- No WebSocket connection observed in testing

**What We DON'T Know:**
- WebSocket connection URL
- Connection protocol and authentication
- Message format for device updates
- Subscription mechanism (per unit? per building? global?)
- Heartbeat/keepalive requirements
- Reconnection handling

**Potential Benefits:**
- Real-time device state updates (no polling delay)
- Reduced API calls (no need to poll)
- Lower rate limit risk
- Better battery life for mobile
- Instant status updates in HA

**Testing Plan:**
```
Test 1: Token Acquisition
- [ ] Call /ws/token endpoint
- [ ] Document token format
- [ ] Check token expiration
- [ ] Test token refresh mechanism

Test 2: Connection Discovery
- [ ] Monitor browser for WebSocket connections
- [ ] Try connecting to common WS URLs
- [ ] Check for wss://melcloudhome.com/ws
- [ ] Document connection endpoint

Test 3: Message Protocol
- [ ] Subscribe to device updates
- [ ] Trigger device state change
- [ ] Capture WebSocket messages
- [ ] Document message format (JSON?)
- [ ] Map messages to device states

Test 4: Reliability Testing
- [ ] Test reconnection on disconnect
- [ ] Test multiple subscriptions
- [ ] Test concurrent connections
- [ ] Document best practices
```

**Resolution Path:**
1. Start with polling implementation
2. Investigate WebSocket as optimization
3. Implement WebSocket if protocol is clear
4. Fall back to polling if WebSocket unavailable
5. Document both approaches

**Estimated Time:** 2-3 hours
**Priority:** P2 - Optimization, not required

---

### GAP-014: Control API Edge Cases

**Status:** 🟢 LOW RISK - Basic Cases Work

**What We Know:**
- Basic control works: `PUT /api/ataunit/{unit_id}`
- Can set power, mode, temperature, fan, vanes
- UI-verified values all work

**What We DON'T Know:**
- Partial update support (single field change?)
- Field interdependencies and validation
- Concurrent update handling (optimistic locking?)
- What happens with invalid field combinations
- If all fields required or some optional

**Edge Cases to Test:**
```
Test 1: Partial Updates
- [ ] Send only {"power": false}
- [ ] Send only {"setTemperature": 22}
- [ ] Check if update succeeds or requires all fields

Test 2: Invalid Combinations
- [ ] Heat mode with temp below 10°C
- [ ] Cool mode with temp below 16°C
- [ ] Dry mode with temperature
- [ ] Fan mode with temperature
- [ ] Power off with mode/temp changes

Test 3: Field Validation
- [ ] Missing required fields
- [ ] Extra unknown fields
- [ ] Null values for required fields
- [ ] Empty strings for string fields
- [ ] Document validation errors

Test 4: Concurrent Updates
- [ ] Two clients update simultaneously
- [ ] Check for race conditions
- [ ] Check for version conflicts
- [ ] Document behavior (last write wins?)
```

**Resolution Path:**
1. Test common use cases first
2. Document edge case behavior
3. Implement client-side validation
4. Add error handling for edge cases
5. Warn users of known limitations

**Estimated Time:** 1 hour
**Priority:** P3 - Edge cases, basic functionality works

---

## Testing Execution Plan

### Phase 1: Critical Blocking Issues (P0)
**Target:** Must complete before production deployment
**Estimated Time:** 4-6 hours

```
Week 1 - Critical Gaps:
□ GAP-001: Schedule Enable/Disable (1-2 hours)
  - Full diagnostic testing
  - Determine if fixable or document workaround

□ GAP-002: Operation Mode Enums (30-60 minutes)
  - Create schedule for each mode
  - Verify mapping table
  - Update documentation

□ GAP-003: Rate Limiting (2-3 hours)
  - Sustained polling test
  - Burst test
  - Document safe limits
  - Implement backoff strategy
```

**Success Criteria:**
- ✅ Schedule enable issue resolved OR documented workaround
- ✅ All operation modes verified
- ✅ Safe polling rate determined
- ✅ Rate limit handling implemented

---

### Phase 2: High-Value Features (P1)
**Target:** Should complete for full feature set
**Estimated Time:** 4-5 hours

```
Week 2 - High Priority:
□ GAP-004: Vane Position Enums (45-60 minutes)
  - Systematic testing of vane values
  - Build verified mapping

□ GAP-005: Schedule UPDATE Endpoint (30-45 minutes)
  - Test PUT/PATCH methods
  - Observe UI editing behavior
  - Document update pattern

□ GAP-006: Scenes API (1-2 hours)
  - Complete UI exploration
  - Capture all scene endpoints
  - Create scenes API document
  - Decide integration strategy
```

**Success Criteria:**
- ✅ Vane positions documented (or confirmed as low priority)
- ✅ Schedule edit pattern determined
- ✅ Scenes API fully documented
- ✅ Integration plan includes/excludes scenes

---

### Phase 3: Enhanced Functionality (P2)
**Target:** Nice-to-have improvements
**Estimated Time:** 4-5 hours

```
Week 3 - Medium Priority:
□ GAP-007: Temperature Validation (30 minutes)
  - Boundary testing
  - Document validation rules

□ GAP-008: Schedule Conflicts (45-60 minutes)
  - Test conflict scenarios
  - Document behavior
  - Add UI warnings

□ GAP-009: Error Codes (Ongoing)
  - Collect codes as they occur
  - Build reference over time

□ GAP-010: Telemetry Details (1 hour)
  - Test date ranges
  - Document granularity
  - Optimize queries

□ GAP-013: WebSocket Investigation (2-3 hours)
  - Explore real-time updates
  - Implement if beneficial
```

**Success Criteria:**
- ✅ Client-side validation complete
- ✅ Conflict handling documented
- ✅ Error code reference started
- ✅ Telemetry optimized
- ✅ WebSocket evaluated (implement or skip)

---

### Phase 4: Advanced Features (P3)
**Target:** Future enhancements based on user demand
**Estimated Time:** 5-7 hours (can defer)

```
Future - Low Priority:
□ GAP-011: Advanced Features (2-3 hours)
  - Document when requested
  - Implement based on demand

□ GAP-012: Multi-Building/Guest (1-2 hours)
  - Add in v2 if needed

□ GAP-014: Control Edge Cases (1 hour)
  - Handle as bugs are reported
```

**Success Criteria:**
- ✅ Documented for future implementation
- ✅ Clear roadmap for v2 features

---

## JavaScript Inspection Findings (2025-11-16)

### Investigation Summary

**Attempted to inspect JavaScript for API constants, enums, and validation rules.**

**Result:** ❌ Not Helpful - Blazor WebAssembly Architecture

### What We Found

MELCloud Home is built with **Blazor WebAssembly**, which means:
- Application logic is compiled C# code running as WebAssembly
- JavaScript layer is minimal (only browser interop)
- No API endpoints, enums, or constants in JavaScript
- All application code is in compiled `.wasm` binaries

**JavaScript Files Examined:**
1. `/js/app.js` - Only contains browser interop functions:
   - `getBrowserLanguage()`, `getBrowserTimeZone()`, etc.
   - Network connectivity listeners
   - File download helpers
   - No API-related code

2. `/appsettings.json` - No accessible configuration
3. `localStorage` - Only contains language preference (`BlazorCulture: "en-GB"`)
4. No inline scripts with configuration data

**Application Code Location:**
- `Me.MelCloudHome.MonitorAndControl.App.Client.wasm` (main app)
- `Me.MelCloudHome.MonitorAndControl.App.Shared.wasm` (shared code)
- `Me.MelCloudHome.MonitorAndControlService.SharedModel.wasm` (models)

These contain the actual API endpoints, enums, and validation rules, but are compiled binaries.

### Why JavaScript Inspection Won't Help

**To extract information from WASM binaries would require:**
1. Download .wasm files
2. Convert to .NET DLL format
3. Decompile with tools (ILSpy, dnSpy)
4. Navigate potentially obfuscated C# code
5. Risk violating terms of service

**This approach is:**
- ❌ Complex and time-consuming
- ❌ May violate ToS
- ❌ Code might be obfuscated
- ❌ Code may not match runtime behavior
- ❌ Doesn't show server-side validation

### Why Network Observation is Superior

**Our current methodology (observing network traffic) is better because:**

✅ **Ground Truth** - Shows actual API behavior, not assumptions
✅ **Hardware Verified** - Tested with real devices and server
✅ **Complete Picture** - Includes server-side validation and responses
✅ **No Ambiguity** - Exact request/response contract observed
✅ **Legally Safe** - Just observing public API traffic
✅ **More Reliable** - Network traffic is the source of truth

**Conclusion:** Continue with UI-driven observation methodology. JavaScript inspection provides no value for Blazor WebAssembly applications.

---

## Testing Best Practices

### Methodology: UI-Driven Observation Only

**CRITICAL RULE:** Always use the UI to drive API calls. Never POST/PUT/DELETE directly.

**Why:**
1. ✅ UI includes client-side validation (prevents invalid requests)
2. ✅ UI shows complete user flow (may make multiple API calls)
3. ✅ UI handles authentication and CSRF tokens correctly
4. ✅ Safer - won't send malformed requests that could cause issues
5. ✅ Shows real-world behavior exactly as users experience it

**Process:**
1. Open Chrome DevTools Network tab
2. Clear network log
3. Perform action in UI (click button, toggle switch, save form)
4. Observe network requests triggered
5. Inspect request headers, body, and response
6. Document findings
7. Verify by repeating action

**Example - Testing Schedule Enable:**
```
❌ WRONG: Use evaluate_script to POST {"enabled": true}
✅ RIGHT: Click the enable/disable toggle in UI, observe the request
```

### Safety Guidelines

**DO:**
- ✅ Test during moderate weather (not extreme heat/cold)
- ✅ Have manual override ready
- ✅ Test on non-critical times (not during sleep/work)
- ✅ Start with safe values (moderate temperatures)
- ✅ Monitor device behavior during tests
- ✅ Keep MELCloud app accessible for emergency control

**DON'T:**
- ❌ Test during extreme weather conditions
- ❌ Test when occupants are sleeping
- ❌ Use extreme temperature values
- ❌ Rapidly cycle power (can damage compressor)
- ❌ Test multiple units simultaneously initially
- ❌ Lock yourself out of manual control

### Documentation Standards

For each gap resolved:
1. Document actual behavior observed
2. Update relevant API documentation
3. Add test case to validation suite
4. Update code with verified values
5. Remove "inferred" warnings
6. Add unit tests for verified behavior

### Rollback Plan

If testing causes issues:
1. Have MELCloud app ready for manual control
2. Delete test schedules immediately
3. Reset to safe known state
4. Document issue for investigation
5. Don't proceed until understood

---

## Progress Tracking

### Gap Resolution Status

| Gap ID | Priority | Status | Assigned Date | Completed Date | Notes |
|--------|----------|--------|---------------|----------------|-------|
| GAP-001 | P0 | 🔴 Open | - | - | Schedule enable broken |
| GAP-002 | P0 | 🟢 Resolved | 2025-11-16 | 2025-11-16 | Mode enum mapping verified |
| GAP-003 | P0 | 🔴 Open | - | - | Unknown rate limits |
| GAP-004 | P1 | 🔴 Open | - | - | Vane enum mapping |
| GAP-005 | P1 | 🔴 Open | - | - | Missing UPDATE endpoint |
| GAP-006 | P1 | 🔴 Open | - | - | Scenes completely unknown |
| GAP-007 | P2 | 🟡 Open | - | - | Temp validation rules |
| GAP-008 | P2 | 🟡 Open | - | - | Schedule conflicts |
| GAP-009 | P2 | 🟡 Open | - | - | Error codes |
| GAP-010 | P2 | 🟡 Open | - | - | Telemetry limits |
| GAP-011 | P3 | 🟢 Open | - | - | Advanced features |
| GAP-012 | P3 | 🟢 Open | - | - | Multi-building |
| GAP-013 | P2 | 🟡 Open | - | - | WebSocket |
| GAP-014 | P3 | 🟢 Open | - | - | Control edge cases |

**Legend:**
- 🔴 Open - Not started
- 🟡 In Progress - Testing underway
- 🟢 Resolved - Completed and documented
- ⚫ Deferred - Low priority, postponed

---

## Related Documentation

- **`melcloudhome-api-reference.md`** - Control API (update as gaps filled)
- **`melcloudhome-schedule-api.md`** - Schedule API (update as gaps filled)
- **`melcloudhome-telemetry-endpoints.md`** - Telemetry API (update as gaps filled)
- **`NEXT-STEPS.md`** - Overall project status and next steps

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-11-16 | Initial gap analysis and testing plan |
| 1.1 | 2025-11-16 | GAP-002 resolved - operation mode enum mapping fully verified |

**Status:** Gap-filling in progress - 1 of 14 gaps resolved (API coverage now 87%)
