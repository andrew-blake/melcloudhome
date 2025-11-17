# MELCloud Home Integration Roadmap

**Current Version:** v1.0.1
**Status:** Production-ready with minor cosmetic improvements
**Next Release:** v1.1 (WebSocket + Sensors)

---

## v1.1: Real-Time Updates & Sensors 🎯 IN PROGRESS

**Status:** Requirements complete, ready for implementation
**Timeline:** 7 hours
**Reference:** `_claude/v1.1-requirements.md`

**Features:**
- ✅ WebSocket real-time updates (< 1 second)
- ✅ Temperature sensors (current, target) with statistics support
- ✅ WiFi signal sensor
- ✅ Energy consumption sensor (Energy Dashboard compatible)
- ✅ Error state binary sensor
- ✅ Integration icon (no more 404)
- ✅ Diagnostic data export

**Benefits:**
- Instant state updates (no 60s delay)
- Statistics-based chart cards
- Energy Dashboard integration
- Proactive error monitoring
- Professional appearance

---

## v1.2: HACS Distribution 🚀

**Goal:** Publish to HACS for easier installation and updates

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

**Effort:** 4-6 hours
- HACS preparation (2 hours)
- Testing (1 hour)
- Documentation (1 hour)
- Submission (1-2 hours)

**Trigger:** After v1.1 is stable and tested

---

## v1.3: Library Split (Optional)

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
| WebSocket + Sensors | High | 7h | P0 | v1.1 |
| Icon + Diagnostics | Medium | 1h | P0 | v1.1 |
| HACS Distribution | High | 4-6h | P1 | v1.2 |
| Options Flow | Low | 2-3h | P2 | v1.x |
| Schedule Management | Medium | 6-8h | P2 | v1.x |
| Library Split | Low | 8-10h | P3 | v1.3+ |
| Translations | Low | 2-4h | P3 | v1.x |
| Multi-Account | Low | 4-6h | P3 | v2.0 |
| Scenes API | Low | 6-8h | P3 | v2.0 |

**P0:** Must have for this version
**P1:** Should have for next version
**P2:** Nice to have if time/demand
**P3:** Future consideration

---

## Release Strategy

### v1.1 Release
**Target:** After WebSocket implementation complete
**Criteria:**
- All v1.1 features working
- Tests passing (>80% coverage)
- Manual testing complete
- Documentation updated
- No critical bugs

### v1.2 Release (HACS)
**Target:** 2-4 weeks after v1.1 stable
**Criteria:**
- v1.1 proven stable in production
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

**v1.1 Success:**
- WebSocket connects reliably (>99% uptime)
- Energy tracking accurate (<1% error)
- No memory leaks (24+ hour runs)
- User satisfaction (controls work instantly)

**v1.2 Success:**
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
