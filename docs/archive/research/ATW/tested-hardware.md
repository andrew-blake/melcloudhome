# Tested Air-to-Water Hardware

List of confirmed working Air-to-Water heat pump models with the MELCloud Home API.

**Last Updated:** 2026-01-03

---

## Confirmed Compatible Models

### EHSCVM2D Hydrokit

**Status:** ✅ Fully tested and documented

**Details:**
- **Manufacturer:** Mitsubishi Electric
- **Model:** EHSCVM2D Hydrokit
- **FTC Model:** 3
- **System Type:** Air-to-Water heat pump
- **Configuration:**
  - Zone 1: Underfloor heating
  - Zone 2: Not present (hasZone2=false)
  - DHW: Domestic hot water tank
- **Capabilities:**
  - Temperature range (Zone 1): 10-30°C
  - Temperature range (DHW): 40-60°C
  - Operation modes: HeatRoomTemperature, HeatFlowTemperature, HeatCurve
  - Forced hot water mode: Supported
  - Energy metering: Estimated only (no measured)
  - WiFi: MAC-567 or similar adapter
- **Testing:**
  - 107 API calls captured
  - All major features tested
  - Schedules, holiday mode, frost protection verified
- **Data Source:**
  - GitHub Discussion #26 (@pwa-2025)
  - HAR files: recording2 and recording3
  - Complete API documentation created

**Notes:**
- Single zone configuration only (no Zone 2 testing)
- Underfloor heating system (10-30°C range appropriate)
- Located in Spain (vacation home use case)
- Temperature range bug discovered and reported to Mitsubishi (now fixed)

---

## Compatibility Notes

### FTC Model Variations

**FTC Model 3:**
- Confirmed working with API
- All documented features supported
- `ftcModel: 3` in capabilities

**Other FTC Models:**
- Not yet tested
- May have different capabilities or behavior
- If you have a different FTC model, please contribute test data via GitHub Discussion

### Required Components

**WiFi Adapter:**
- Compatible MAC-567, MAC-577, or similar
- Enables cloud connectivity
- Required for MELCloud Home access

---

## How to Contribute

If you have an Air-to-Water heat pump and want to help test compatibility:

1. **Check your model:**
   - Look at your FTC controller model number
   - Check MELCloud Home app to confirm it appears

2. **Contribute data via GitHub:**
   - Open or comment on Discussion #26
   - Provide model information
   - Optionally: HAR file capture (see research docs for instructions)

3. **What we need:**
   - Model number (e.g., EHSCVM2D)
   - FTC model from API (check capabilities.ftcModel)
   - Zone configuration (1 or 2 zones)
   - DHW support (yes/no)
   - Any unusual behavior or errors

---

## Untested Models (Pending)

### Mitsubishi Ecodan Hydrobox Duo Silence Zubadan

**Status:** ❓ Reported but not tested

**Details:**
- **Manufacturer:** Mitsubishi Electric
- **Product:** Ecodan Hydrobox Duo Silence Zubadan
- **Source:** GitHub Issue #30 (@vincent-d-izo)
- **Current status:** Integration doesn't detect devices yet (ATW support not implemented)
- **Link:** https://www.izi-by-edf-renov.fr/produit/pompe-a-chaleur-ecodan-hydrobox-duo-silence-zubadan-mitsubishi

**Next steps:**
- Once ATW implementation complete, request testing from user
- Gather FTC model and capabilities
- Confirm API compatibility

---

## References

- **API Documentation:** [../../api/atw-api-reference.md](../../api/atw-api-reference.md)
- **GitHub Discussion #26:** https://github.com/andrew-blake/melcloudhome/discussions/26
- **GitHub Issue #30:** https://github.com/andrew-blake/melcloudhome/issues/30
- **Research Documentation:** [MelCloud_ATW_Complete_API_Documentation.md](MelCloud_ATW_Complete_API_Documentation.md)
