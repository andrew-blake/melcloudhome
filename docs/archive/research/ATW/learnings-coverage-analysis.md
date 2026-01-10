# A2W Research Learnings - Coverage Analysis

**Purpose:** Track which research findings are captured in architectural documentation vs still in research notes only

**Date:** 2026-01-03

---

## Core API Behavior - Captured ✅

These are documented in `docs/api/atw-api-reference.md`:

- [x] Control endpoint: PUT /api/atwunit/{unitId}
- [x] Sparse update pattern (nulls ignored)
- [x] Empty 200 response for control commands
- [x] UserContext structure (shared with A2A)
- [x] Settings as name-value array
- [x] Telemetry endpoint structure
- [x] 9 telemetry measure types
- [x] Energy endpoints
- [x] Error log structure
- [x] Schedule endpoints
- [x] Holiday mode (multi-unit)
- [x] Frost protection (multi-unit)
- [x] Operation mode string values (HeatRoomTemperature, HeatFlowTemperature, HeatCurve)
- [x] Temperature ranges (Zone: 10-30°C, DHW: 40-60°C)
- [x] 3-way valve physical limitation
- [x] OperationMode as status field (not control)
- [x] Forced hot water mode behavior (priority, not on/off)
- [x] Summer mode workaround (set Zone to 10°C)

---

## Architectural Decisions - Captured ✅

These are documented in `docs/decisions/011-multi-device-type-architecture.md`:

- [x] Extend current module vs separate module decision
- [x] 90% API overlap rationale
- [x] Shared auth/session justification
- [x] Method naming strategy
- [x] File growth estimates
- [x] Migration path if needed

---

## User Context & Requirements - Partially Captured ⚠️

**Captured in ADR-011:**
- [x] Vacation home use case (mentioned)
- [x] Guest management need (mentioned)

**Not captured anywhere (OK to stay in discussion):**
- Video URLs: https://youtube.com/shorts/0wxJefIMU_I, https://youtu.be/jQhsyMLIZO0
- Planned HA automations:
  - Temperature range restrictions
  - Door sensor integration (terrace door open → disable)
  - Security system integration (armed_away → shutdown)
  - Simplified HA interface for guests
- Pre-arrival heating pattern (12 hours before arrival)
- Spain vacation property context

**Recommendation:** These are user-specific requirements, not API behavior. Keep in GitHub discussion for context, don't need in architectural docs.

---

## Testing Coverage - Missing from Architectural Docs ⚠️

**From research/ATW/MelCloud_ATW_Complete_API_Documentation.md:**

### Temperature Testing
- Zone 1 tested: 30°C, 31°C, 39°C, 50°C (during bug investigation)
- Zone 1 tested: 10°C, 30°C (after bug fix)
- DHW tested: 40°C, 49°C, 50°C, 51°C, 60°C

### Feature Testing
- Power control: Multiple on/off cycles
- Forced hot water: 4 toggles tested
- Operation modes: All 3 tested
- Schedules: Create + enable/disable tested
- Holiday mode: 2 activations
- Frost protection: Tested

**Recommendation:** Add testing coverage section to `atw-api-reference.md`? Or keep in research docs only?

---

## Technical Details - Some Missing ⚠️

### Missing from New Docs

1. **Polling Frequency Observations:**
   - Web app polls `/api/telemetry/actual` very frequently (every few seconds)
   - UserContext polled less frequently (~12 times in 107 calls)
   - **Recommendation:** Add polling best practices to API reference

2. **Error Codes:**
   - E4 error mentioned (outdoor temp sensor / high pressure)
   - **Recommendation:** Start error code reference document if more codes discovered

3. **ProhibitHotWater Field:**
   - Appears in settings array
   - Purpose unclear
   - Always "False" in observations
   - **Recommendation:** Add to API reference as "unknown field"

4. **Telemetry Time Ranges:**
   - Hourly: from=2025-12-14 10:00&to=2025-12-14 10:59
   - Daily: from=2025-12-14 00:00&to=2025-12-14 22:59
   - Weekly/Monthly: from=2025-12-07 23:00&to=2025-12-14 22:59
   - **Status:** Captured in examples, could be more explicit

5. **FTC Model Variations:**
   - Test system: FTC Model 3
   - Other models: Unknown differences
   - **Recommendation:** Note in docs that testing was FTC Model 3 only

6. **Schedule Integer Mapping:**
   - Still unknown (0/1/2 → which modes?)
   - **Status:** Documented as "requires testing"

---

## Hardware Details - Missing ⚠️

### User's System Details (from discussion)

**@pwa-2025's system:**
- Model: EHSCVM2D Hydrokit
- FTC: Model 3
- Configuration: Single zone, underfloor heating, DHW
- Location: Spain (vacation home)
- Usage: Intermittent occupancy

**@vincent-d-izo's system (Issue #30):**
- Model: Mitsubishi Ecodan Hydrobox Duo Silence Zubadan
- Link: https://www.izi-by-edf-renov.fr/produit/pompe-a-chaleur-ecodan-hydrobox-duo-silence-zubadan-mitsubishi

**Recommendation:** Create `docs/research/ATW/tested-hardware.md` listing known working models?

---

## Recommendations

### 1. Add to atw-api-reference.md ✏️

**Section: Testing Coverage**
```markdown
## Testing Coverage

This API documentation is based on:
- 107 captured API calls from comprehensive testing
- FTC Model 3 system
- Single zone configuration (no Zone 2)
- Underfloor heating + DHW

**Tested operations:**
- Power control (multiple cycles)
- All 3 operation modes
- Zone temperatures: 10-30°C range
- DHW temperatures: 40-60°C range
- Forced hot water mode (4 toggles)
- Schedule creation and enable/disable
- Holiday mode and frost protection

**Hardware tested:**
- EHSCVM2D Hydrokit (FTC Model 3)
- Mitsubishi Ecodan Hydrobox (model TBD)
```

**Section: Unknown Fields**
```markdown
## Unknown/Undocumented Fields

**ProhibitHotWater:**
- Appears in settings array
- Always "False" in observations
- Purpose unclear
- Do not modify unless understood
```

**Section: Polling Best Practices**
```markdown
## Polling Best Practices

Based on web app behavior:
- `/api/telemetry/actual/{unitId}`: Very frequent (every few seconds)
- `/api/user/context`: Less frequent (periodic)

**Recommendation for HA integration:**
- UserContext: 60-second minimum (avoid rate limiting)
- Telemetry: Optional, only if needed for graphs
- Prefer UserContext for state updates
```

### 2. Create docs/research/ATW/tested-hardware.md ✏️

List known working A2W models for community reference.

### 3. Keep in Research Docs Only ✓

These don't need to be in architectural docs:
- Specific user requirements (automation ideas)
- Video demonstrations
- HAR file analysis details
- Testing methodology

---

## Summary

**Well Captured:** Core API behavior, architectural decisions, device comparison
**Minor Gaps:** Polling best practices, unknown fields, error codes
**Not Needed:** User-specific automations, videos, detailed test methodology

**Recommended Actions:**
1. Add 3 sections to `atw-api-reference.md` (testing coverage, unknown fields, polling)
2. Create `tested-hardware.md` for community
3. Keep research docs as historical reference
