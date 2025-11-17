# Known Issues & v1.1 Improvements

**Version:** 1.0.0
**Status:** Production - Working with minor cosmetic issues

---

## 🐛 Open Issues

### #1 - Missing Integration Icon
- **Issue:** Icon shows 404 error
- **Impact:** Cosmetic only
- **Fix:** Add local icon files (icon.png, logo.png)
- **Priority:** LOW

---

## ✅ Resolved Issues

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

## 📋 v1.1 Plan

**Remaining:**
- [ ] #1 - Add integration icon (low priority, cosmetic only)

**Fixed in v1.0.1:**
- [x] #4 - Remove email from title ✅
- [x] #5 - Add attribution to device model ✅
- [x] #2 & #3 - Dashboard documentation ✅
- [x] #6 - Document turn_on behavior ✅

**Integration is production-ready!** Only minor icon issue remains.
