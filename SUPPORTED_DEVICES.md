# Supported Devices

This document lists hardware tested with the **MELCloud Home** Home Assistant custom integration.

> **Note:** This integration is *unofficial* and targets **MELCloud Home** only, not the legacy **MELCloud** service.

---

## Compatibility Check

### Is your WiFi adapter supported?

This integration **only works with MELCloud Home** (not the legacy MELCloud app).

**✅ Compatible WiFi adapters:**

- MAC-567 (including MAC-567IF-E, MAC-567IFB-E)
- MAC-577 (including MAC-577IF-E, MAC-577IF-2)
- MAC-587 (including MAC-587IF-E)
- MAC-597

**❌ Not supported:**

- Legacy MELCloud adapters → Use the official [Home Assistant MELCloud integration](https://www.home-assistant.io/integrations/melcloud/) instead

> **How to check:** If your system uses the **MELCloud Home** mobile app, you're compatible. If it uses the classic **MELCloud** app, use the official HA integration.

---

## Air-to-Air (ATA) Systems

Air-to-Air systems are air conditioning units (wall-mounted, ducted, or console) that provide heating and cooling.

### Confirmed Working Models

| Indoor Unit | WiFi Adapter | Type | Notes |
|-------------|--------------|------|-------|
| MSZ-AY20VKGP | MAC-577 | Wall split | |
| MSZ-AY25VKGP | MAC-577 | Wall split | Energy tracking works |
| MSZ-AY25VGK / VGK2 | MAC-597 | Wall split | Single or multi-split |
| MSZ-AY35VKGP | MAC-577 | Wall split | |
| MSZ-AY42VKGP | MAC-577 | Wall split | |
| MSZ-AY50VGK | MAC-587 | Wall split | Energy tracking works |
| MSZ-LN25VGWRAC | MAC-587 | Wall split | Multi-split |
| MSZ-LN35VG2B | MAC-597 | Wall split | |
| MFZ-KT50VG | MAC-587 | Console | |
| PEAD-M50JA2 + SUZ-M50VAR2 | MAC-587 + PAR-41MAA | Ducted commercial | Energy tracking works |
| PEAD-M71JAQ | MAC-587 | Ducted | |

> **Note:** Model suffixes may vary by region (VG/VGK/VGK2). Similar models likely work but are untested.

### Multi-Split & Topology Notes

**Multi-split systems:** ✅ Confirmed working

- Multiple indoor units report correctly as separate entities
- ⚠️ **Energy tracking limitation**: Some multi-split indoor units may not report individual energy consumption (API/hardware limitation, also affects official MELCloud Home app)
- Do not set units to Auto or conflicting Heat/Cool modes on linked indoor units

**Ducted systems:** ✅ Confirmed working

- Both residential and commercial ducted systems tested

**Console units:** ✅ Confirmed working

**Commercial / VRF systems:** Limited support - Only works if they appear as standard devices in MELCloud Home app

---

## Air-to-Water (ATW) Heat Pumps

Air-to-Water systems are heat pumps for underfloor heating/radiators and domestic hot water (DHW).

### ⚠️ Status: Experimental

ATW support is **EXPERIMENTAL** - Available in v2.0.0+ but **NOT tested on real hardware**. Implementation based on reverse-engineered API only.

**Current Implementation (v2.0.0):**
- Zone 1 heating control ✓
- DHW tank control ✓
- System power control ✓
- Temperature sensors (Zone 1 room, DHW tank) ✓
- Operation status monitoring ✓
- Single zone systems only (no Zone 2)

### Theoretically Compatible Models

| Model | Notes |
|-------|-------|
| EHSCVM2D Hydrokit | Based on HAR analysis from Discussion #26. Zone 1 + DHW support. |

> **⚠️ Use at your own risk.** See [EXPERIMENTAL-ATW.md](EXPERIMENTAL-ATW.md) for full details, limitations, and safety warnings.

**Call for testers:** If you have an Ecodan heat pump (any model) and can help test, see [Discussion #26](https://github.com/andrew-blake/melcloudhome/discussions/26).

---

## Contributing Tested Hardware

Contributions to expand this list are very welcome!

### For ATA (Air-to-Air) Systems

Please include:

1. **Indoor unit model** (e.g. `MSZ-AY25VGK2`)
2. **WiFi adapter** (e.g. `MAC-597`)
3. **Type** (Wall split, Ducted, Console)
4. **Notable quirks** (if any): Energy tracking, multi-split behavior, missing features

**Example:**

```markdown
| MSZ-AY25VGK2 | MAC-597 | Wall split | Energy tracking works |
```

### For ATW (Air-to-Water) Heat Pumps

Please include:

1. **Heat pump model** (e.g. `EHSCVM2D Hydrokit`)
2. **Configuration** (Zone 1 only, Zone 1 + 2, DHW support)
3. **Test results**: What works, what doesn't, any issues encountered
4. **Diagnostics**: Include `ftc_model` value from entity attributes (for our records)

**Example:**

```markdown
| EHSCVM2D Hydrokit | Zone 1 + DHW working, no issues found (ftc_model=3) |
```

> **Important:** For ATW systems, please test thoroughly and report any issues. These systems control heating and hot water - safety is critical!

Thank you to everyone who helps confirm models and improve this list!
