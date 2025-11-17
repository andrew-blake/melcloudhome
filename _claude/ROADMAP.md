# MELCloud Home Integration Roadmap

**Current Version:** v1.1.0 ✅
**Status:** Production-ready with all core features
**Next Release:** v1.2 (WebSocket + Sensors)

---

## v1.1: Polish & Diagnostics ✅ COMPLETED

**Status:** Released (2025-11-17)
**Reference:** `_claude/NEXT-STEPS.md`, `_claude/websocket-research-defer.md`

**What's IN v1.1:**
- ✅ Integration icon (icons.json with mdi:heat-pump)
- ✅ Diagnostics data export
- ✅ Entity naming confirmed (already clean and modern)
- ✅ Documentation updates

**Benefits:**
- Professional appearance (custom icon)
- Easy troubleshooting (diagnostics export)
- Complete documentation

**What's DEFERRED to v1.2:**
- ⏸️ WebSocket real-time updates (needs reliability investigation)
- ⏸️ WiFi signal sensor
- ⏸️ Error state binary sensor
- ⏸️ Current temperature sensor (already in climate entity attributes)
- ⏸️ Target temperature sensor (already in climate entity attributes)
- ⏸️ Energy consumption sensor (complex, needs simplification)

**Rationale for Deferrals:**
- **Temperature sensors:** Climate entity already exposes these as attributes. Users can create template sensors if needed for statistics. Only add if users specifically request easier access.
- **Energy sensor:** Over-engineered in original requirements (100+ lines of edge case handling). Needs simplified algorithm and user demand validation before implementation.

---

## v1.2: WebSocket + Sensors 🎯 NEXT

**Primary Goal:** Add real-time updates and sensor platform
**Secondary Goal:** Prepare for HACS distribution
**Reference:** Legacy MELCloud integration for sensor patterns

### Pre-Implementation Review

**Before v1.2 implementation, review and evaluate:**

1. **Legacy MELCloud Integration Analysis**
   - Review: https://github.com/home-assistant/core/tree/master/homeassistant/components/melcloud
   - Identify features we're missing (sensor platform, services, etc.)
   - Evaluate if their patterns are best practices or legacy approaches
   - Critical assessment: Not all "official" patterns are necessarily better
   - Document decisions in ADR if we diverge from their approach

2. **Home Assistant Climate Best Practices**
   - Review official climate integration guidelines
   - Check for modern patterns we should adopt
   - Compare our implementation against current HA standards
   - Look at other well-maintained climate integrations for patterns

3. **Integration Quality Checklist**
   - Entity naming conventions (stable IDs ✅)
   - Device registry patterns
   - State management and coordinator patterns
   - Error handling and recovery
   - Diagnostics support ✅
   - Testing coverage

**Outcome:** Document findings and create v1.2 implementation plan based on critical review

### WebSocket Real-Time Updates (Investigation Required)

**Status:** Deferred from v1.1 - needs reliability investigation
**Effort:** 4-6 hours (investigation + implementation)
**Reference:** `_claude/websocket-research-defer.md`

**Issue Discovered:**
- WebSocket messages not consistently delivered to all devices
- Only one device receiving updates in testing
- Needs deeper protocol investigation

**What to investigate:**
- Message format and routing logic
- Why only one device receives updates
- Reliability and connection handling
- Fallback to polling if WebSocket fails

**Implementation Plan (once reliable):**
- WebSocket connection management
- Message parsing and handling
- State update propagation
- Graceful degradation to polling

### Sensor Platform (Based on MELCloud Integration)

**Status:** New feature for v1.2
**Effort:** 4-6 hours
**Reference:** Legacy MELCloud integration sensor.py

**Inspired by MELCloud Integration:**
- Room temperature sensor (for statistics/history)
- Energy consumption sensor (kWh, total_increasing)
- WiFi signal strength sensor (connectivity monitoring)
- Error state binary sensor (proactive alerts)

**Benefits:**
- Long-term statistics for temperature
- Energy monitoring and tracking
- Connectivity troubleshooting
- Automation triggers for errors

**Implementation:**
- Create `sensor.py` platform
- Add sensor entities for each device
- Use appropriate device classes
- State class: `measurement` (temp, wifi) and `total_increasing` (energy)

---

## v1.3: HACS Distribution 🚀

**Goal:** Publish to HACS for easier installation and updates
**Effort:** 4-6 hours

**Approach:** HACS with bundled library (keep current architecture)
- ✅ Keep API library bundled in `api/` subfolder (KISS principle)
- ✅ Publish to HACS with bundled architecture
- ✅ Prove stability and adoption first
- ⏳ Consider PyPI split later only if there's demand

**Rationale:**
- Faster time to HACS (no architectural changes needed)
- Simpler for users (no external dependencies)
- Easier to maintain (one repository)
- Can split later if needed (not blocking HACS)

**Requirements:**
- [ ] Create HACS-compatible repository structure
- [ ] Add HACS manifest validation
- [ ] Submit to HACS default repository
- [ ] Create release workflow
- [ ] Documentation for HACS installation
- [ ] Version tagging strategy

**Benefits:**
- One-click installation for users
- Automatic updates
- Wider distribution
- Community visibility
- Easier bug reporting

---

## v1.4: Library Split (Optional)

**Goal:** Split Python library to PyPI package (only if needed)

**When to consider:**
- Library is useful outside Home Assistant
- Other projects want to use the API client
- Library changes frequently (needs independent versioning)
- Community requests it

**Current Decision:** Keep bundled (KISS principle)
**Reconsider:** If there's demand after HACS release

**See:** ADR-001 for bundled vs split decision

---

## v1.x: Quality of Life Features

### Options Flow
**Priority:** Low
**Effort:** 2-3 hours
- Reconfigure credentials without removing integration
- Change energy polling interval
- Enable/disable WebSocket
- Change update intervals

### Schedule Management
**Priority:** Medium (if users request it)
**Effort:** 6-8 hours
- Implement schedule API endpoints
- Create service calls for schedule CRUD
- UI for viewing/editing schedules
- See: `_claude/melcloudhome-schedule-api.md`

### Translations
**Priority:** Low
**Effort:** 2-4 hours per language
- Add translation files
- Community contributions
- Support common languages (FR, DE, ES, IT)

---

## v2.0: Advanced Features

### Multi-Account Support
**Goal:** Support multiple MELCloud accounts in one HA instance
**Effort:** 4-6 hours
- Multiple config entries
- Per-account coordinators
- Entity naming conflicts resolution

### Scenes API Integration
**Goal:** Support MELCloud scenes
**Effort:** 6-8 hours
- Discover available scenes
- Create HA scenes from MELCloud scenes
- Service calls for scene activation
- See: `_claude/melcloudhome-api-reference.md`

### Advanced Automation Support
**Goal:** Expose all device capabilities
**Effort:** 4-6 hours
- Additional sensors (humidity, power consumption, etc.)
- Select entities for vane positions
- Number entities for precise control

### OAuth Refresh Tokens
**Goal:** Use refresh tokens instead of password storage
**Effort:** 3-4 hours
**Blocker:** API doesn't support refresh tokens yet
**See:** ADR-002

---

## Prioritization Matrix

| Feature | Value | Effort | Priority | Target |
|---------|-------|--------|----------|--------|
| Icon + Diagnostics | Medium | 2h | P0 | ✅ v1.1 |
| WebSocket Investigation | High | 4-6h | P1 | v1.2 |
| Sensor Platform | High | 4-6h | P1 | v1.2 |
| HACS Distribution | High | 4-6h | P2 | v1.3 |
| Options Flow | Low | 2-3h | P2 | v1.x |
| Schedule Management | Medium | 6-8h | P2 | v1.x |
| Library Split | Low | 8-10h | P3 | v1.4+ |
| Translations | Low | 2-4h | P3 | v1.x |
| Multi-Account | Low | 4-6h | P3 | v2.0 |
| Scenes API | Low | 6-8h | P3 | v2.0 |

**P0:** Must have for this version
**P1:** Should have for next version
**P2:** Nice to have if users request it
**P3:** Future consideration

---

## Release Strategy

### v1.1 Release ✅ COMPLETE
**Released:** 2025-11-17
**Criteria Met:**
- ✅ Icon and diagnostics working
- ✅ Tests passing (>80% coverage)
- ✅ Manual testing complete
- ✅ Documentation updated
- ✅ No critical bugs

### v1.2 Release (WebSocket + Sensors)
**Target:** After WebSocket investigation and sensor platform complete
**Criteria:**
- WebSocket reliability confirmed
- Sensor platform implemented
- Tests passing (>80% coverage)
- Manual testing complete
- Documentation updated
- No critical bugs

### v1.3 Release (HACS)
**Target:** 2-4 weeks after v1.2 stable
**Criteria:**
- v1.2 proven stable in production
- No major bugs reported
- HACS requirements met
- Release workflow automated

### Future Releases
**Cadence:** As needed based on:
- User feedback
- Bug reports
- Feature requests
- API changes

---

## Decision Points

**When to split library:**
- ⏸️ WAIT for HACS adoption
- ⏸️ WAIT for stability
- ⏸️ WAIT for external library demand
- ✅ THEN consider PyPI split

**When to add features:**
- ✅ User requests (signals demand)
- ✅ Low effort / high value
- ✅ Enables new use cases
- ❌ Just because we can

**When to break changes:**
- ⚠️ Major version only (v2.0)
- ⚠️ Clear migration guide
- ⚠️ Deprecation warnings first
- ⚠️ Document breaking changes

---

## Success Metrics

**v1.1 Success:** ✅ ACHIEVED
- ✅ Icon shows correctly in HA UI
- ✅ Diagnostics export works with redacted credentials
- ✅ Entity naming is clean and modern
- ✅ Documentation complete and accurate
- ✅ No critical bugs reported

**v1.2 Success:**
- WebSocket connects reliably (>99% uptime)
- State updates appear < 1 second
- Sensor platform working (temp, energy, wifi, errors)
- No memory leaks (24+ hour runs)
- User satisfaction (instant updates, useful sensors)

**v1.3 Success:**
- HACS installation works first time
- 10+ HACS installations
- Positive community feedback
- Low bug report rate

**Long-term Success:**
- Integration remains stable
- Active maintenance
- Community contributions
- Becomes go-to for MELCloud Home users

---

## Maintenance Plan

**Regular:**
- Monitor GitHub issues
- Update dependencies
- Test against new HA versions
- Fix critical bugs within 1 week

**As Needed:**
- API changes (adapt integration)
- HA breaking changes (update code)
- Security issues (immediate fix)

**Community:**
- Review pull requests
- Answer questions
- Accept translations
- Consider feature requests
