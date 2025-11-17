# Known Issues & Improvements

**Version:** 1.1.2
**Status:** Production - Minor cosmetic issue with images

---

## 🐛 Open Issues

### #7 - Missing Images in Integration UI
- **Issue:** Missing/broken images when adding and managing the integration
- **Impact:** Cosmetic only - functionality not affected
- **Investigation:** Requires Chrome DevTools MCP to diagnose image loading
- **Priority:** LOW
- **Next Steps:** Use Chrome MCP in next session to inspect network requests and identify missing assets

---

## ✅ Resolved Issues

### #1 - Missing Integration Icon
- **Issue:** Icon shows 404 error
- **Solution:** ✅ Created icons.json with Material Design Icon (mdi:heat-pump)
- **Status:** RESOLVED (2025-11-17 - v1.1.0)

### #2 & #3 - Dashboard Setup
- **Issue:** Default entity card shows only temperature
- **Solution:** ✅ Documented in README.md - use "thermostat" card type
- **Status:** RESOLVED (2025-11-17)

### #4 - Email in Integration Title
- **Issue:** Title showed "MELCloud Home v2 (a.blake01@gmail.com)"
- **Solution:** ✅ Changed to "MELCloud Home" in config_flow.py:50
- **Status:** RESOLVED (2025-11-17)

### #5 - Device Attribution
- **Issue:** Showed as "by Mitsubishi Electric" (could be misleading)
- **Solution:** ✅ Changed model to "Air-to-Air Heat Pump (via MELCloud Home)" in climate.py:77
- **Status:** RESOLVED (2025-11-17)

### #6 - No turn_on/turn_off Action
- **Issue:** Error when calling `climate.turn_on`
- **Solution:** ✅ Documented in README.md - this is standard HA behavior for ALL climate entities
- **Workaround:** Use `climate.set_hvac_mode` with desired mode
- **Status:** RESOLVED (2025-11-17)

---

## 📋 Version Summary

**v1.1.2 (2025-11-17):**
- [x] Stable entity IDs based on unit UUIDs ✅
- [x] Removed via_device deprecation warning ✅
- [x] Renamed from "MELCloud Home v2" to "MELCloud Home" ✅
- [ ] #7 - Missing images in integration UI (open, cosmetic)

**v1.1.0 (2025-11-17):**
- [x] #1 - Added integration icon (icons.json) ✅
- [x] Added diagnostics support ✅
- [x] Updated documentation ✅

**v1.0.1 (2025-11-17):**
- [x] #4 - Remove email from title ✅
- [x] #5 - Add attribution to device model ✅
- [x] #2 & #3 - Dashboard documentation ✅
- [x] #6 - Document turn_on behavior ✅

**Integration is production-ready with one minor cosmetic issue remaining.**
