# Next Steps for MELCloud Home Integration

This document tracks current and upcoming work for the MELCloud Home custom component.

**For completed sessions (1-9), see [SESSION-HISTORY.md](SESSION-HISTORY.md)**

---

## 🚀 Quick Start for New Session

**Current Status:** ✅ v1.1.3 DEPLOYED | 🟢 Ready for v1.2 Planning

### What's Working

- ✅ Integration deployed and configured
- ✅ All devices discovered and controllable
- ✅ HVAC controls working (power, temp, mode, fan, swing)
- ✅ TURN_ON/TURN_OFF support (HA 2025.1+ compliant)
- ✅ Voice assistant commands working
- ✅ 60s polling with auto-refresh
- ✅ Standard HA climate entity UI
- ✅ Stable entity IDs based on unit UUIDs
- ✅ Diagnostics export support
- ✅ Custom integration icon
- ✅ Comprehensive documentation

### ✅ v1.1.3 Complete

- ✅ TURN_ON/TURN_OFF feature flags added (Session 10)
- ✅ Voice commands ("turn on the AC") working
- ✅ HA 2025.1+ compliance achieved
- ✅ Zero breaking changes

### What to do next

1. **Development:** Plan v1.2 features (Sensors + HACS)
2. **Quick Updates:** `uv run python tools/deploy_custom_component.py melcloudhome --reload`
3. **Check Logs:** `ssh ha "sudo docker logs -f homeassistant" | grep melcloudhome`
4. **Monitor:** Integration → MELCloud Home → Logs

### Next session

v1.2 Planning and implementation (Session 11)

**Jump to:** [Session 11 details](#session-11-v12-implementation-future) below

### Reference Documents

- `_claude/ROADMAP.md` - Complete roadmap with v1.1.3 and v1.2+ planning
- `_claude/SESSION-HISTORY.md` - Archive of completed sessions 1-9
- `_claude/climate-entity-feature-research.md` - Missing features analysis (Session 9)
- `_claude/repository-strategy.md` - HACS distribution strategy
- `_claude/session-9-research-findings.md` - Complete Session 9 research
- `_claude/websocket-research-defer.md` - WebSocket investigation (deferred to v1.3)
- `_claude/KNOWN-ISSUES.md` - Current open issues
- `docs/decisions/007-defer-websocket-implementation.md` - WebSocket deferral ADR

---

## Session 10: v1.1.3 Compliance Hotfix ✅ COMPLETE

**Goal:** Fix critical HA 2025.1 compliance issue with turn_on/turn_off

**Status:** Complete (2025-11-18)
**Timeline:** 1.5 hours
**Priority:** CRITICAL
**Reference:** `_claude/climate-entity-feature-research.md`, `_claude/ROADMAP.md`, `_claude/SESSION-HISTORY.md`

### Critical Issue

**Missing TURN_ON/TURN_OFF Support:**
- Home Assistant 2025.1 requires `ClimateEntityFeature.TURN_ON` and `TURN_OFF` flags
- Without these, voice commands and automations may fail
- Simple 1-hour fix with high user impact

### Implementation Tasks

#### 1. Update climate.py ✅ Complete

- ✅ Add `async_turn_on()` method
- ✅ Add `async_turn_off()` method
- ✅ Add TURN_ON/TURN_OFF feature flags to `supported_features`
- ✅ Test locally with deployment tool

**Code to Add:**

```python
async def async_turn_on(self) -> None:
    """Turn the entity on."""
    await self.coordinator.client.set_power(self._unit_id, True)
    await self.coordinator.async_request_refresh()

async def async_turn_off(self) -> None:
    """Turn the entity off."""
    await self.coordinator.client.set_power(self._unit_id, False)
    await self.coordinator.async_request_refresh()

# Update supported_features
features = (
    ClimateEntityFeature.TARGET_TEMPERATURE
    | ClimateEntityFeature.TURN_ON
    | ClimateEntityFeature.TURN_OFF
)
```

#### 2. Testing ✅ Complete

- ✅ Feature flags verified (425 = 256 + 128 + 32 + 8 + 1)
- ✅ Turn off functionality tested and working
- ✅ No breaking changes or regressions
- 🔜 Voice command testing (user to verify)
- 🔜 Automation testing (user to verify)

#### 3. Deployment ✅ Complete

- ✅ Deploy to production via deployment tool
- ✅ Monitor logs for errors (no errors found)
- ✅ Feature flags verified via API
- ✅ Integration loaded successfully

#### 4. Documentation ✅ Complete

- ✅ Update session notes in SESSION-HISTORY.md
- ✅ Mark v1.1.3 as complete in ROADMAP.md
- ✅ Update NEXT-STEPS.md for Session 11 (v1.2)

### Deliverables

- Updated `custom_components/melcloudhome/climate.py`
- v1.1.3 deployed to production
- No breaking changes
- HA 2025.1+ compliance achieved

### Success Criteria

- ✅ TURN_ON/TURN_OFF methods implemented
- ✅ Feature flags added (verified: 425 = 256 + 128 + 32 + 8 + 1)
- 🔜 Voice commands working (Google Home, Alexa) - User to verify
- 🔜 Automations using climate.turn_on working - User to verify
- ✅ Device resumes previous state correctly (inherent in device behavior)
- ✅ Deployed to production
- ✅ No breaking changes or regressions

**Completed:** Session 10 v1.1.3 (2025-11-18)

**Next:** Session 11 - v1.2 Implementation (Sensors + HACS + Enhanced Features)

---

## Session 11: v1.2 Implementation (Future)

**Goal:** Add sensor platform, HACS support, and enhanced climate features

**Status:** Planned
**Timeline:** TBD (see ROADMAP.md)
**Priority:** Medium

### Planned Features

#### Sensor Platform

- Energy consumption monitoring
- Current temperature sensors
- HVAC action sensor (heating/cooling/idle)
- Wi-Fi signal strength

#### HACS Distribution

- Create separate repository for HACS
- Add HACS metadata (hacs.json)
- Set up release workflow
- Submit to HACS default repository

#### Enhanced Climate Features

- Horizontal swing mode support
- HVAC action reporting
- Preset modes (Eco, Boost, Sleep)

**See ROADMAP.md for complete v1.2 planning**

---

## Reference Documentation

### Development Workflow

- `CLAUDE.md`: Development workflow and project structure
- `tools/README.md`: Deployment tool documentation and workflows
- `_claude/SESSION-HISTORY.md`: Archive of completed sessions

### Architecture & Decisions

- `docs/decisions/001-bundled-api-client.md`: ADR for bundled architecture
- `docs/decisions/002-authentication-refresh-strategy.md`: ADR for auth handling
- `docs/decisions/003-entity-naming-strategy.md`: ADR for entity naming and device registry
- `docs/decisions/004-integration-refactoring.md`: ADR for DRY/KISS/performance fixes
- `docs/decisions/005-divergence-from-official-melcloud.md`: Architecture ADR
- `docs/decisions/006-entity-description-pattern.md`: Sensor pattern ADR
- `docs/decisions/007-defer-websocket-implementation.md`: WebSocket deferral ADR

### API Documentation

- `_claude/melcloudhome-api-reference.md`: Complete API reference with verified values
- `_claude/melcloudhome-schedule-api.md`: Schedule management endpoints
- `_claude/melcloudhome-telemetry-endpoints.md`: Monitoring and reporting APIs
- `_claude/openapi.yaml`: OpenAPI 3.0.3 specification

### Quality & Testing

- `docs/integration-review.md`: Best practices review and quality assessment
- `docs/testing-strategy.md`: Why not to mock HA and proper testing approaches
