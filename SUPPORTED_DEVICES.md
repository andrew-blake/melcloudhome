# Supported Devices

This document lists hardware that has been tested with the **MELCloud Home** Home Assistant custom integration.

> **Note**
> This integration is *unofficial* and not affiliated with Mitsubishi Electric. It targets the **MELCloud Home** platform only, not the legacy **MELCloud** service.

---

## Wi‑Fi Adapters

These Wi‑Fi interfaces determine whether your system uses **MELCloud Home** (supported by this integration) or the older **MELCloud** (not supported here).

### Confirmed compatible (MELCloud Home)

These adapters have been tested with this integration and are known to work with MELCloud Home:

- **MAC‑597**
  - 4th‑generation Wi‑Fi adapter
  - Uses the **MELCloud Home** app / API
  - Tested and working with this integration

### Not supported by this integration

These adapters use the *legacy* MELCloud API, which is handled by the official Home Assistant `melcloud` integration, **not** this one:

- **MAC‑567**
- **MAC‑577**
- **MAC‑587**

If your system uses one of these adapters and appears in the classic MELCloud app, you should use the built‑in Home Assistant **MELCloud** integration instead of this custom integration.

---

## Indoor Units

### Notes on Multi‑Split Systems

Some indoor units connected to **multi‑split** outdoor units may not expose per‑indoor **energy usage** through the MELCloud Home API. In these cases, the official MELCloud Home app itself may show missing or incorrect energy values. When this happens, the Home Assistant integration cannot provide accurate `kWh` sensors for those specific indoor units.

Do not to set the indoor unit to Auto or set conflicting Heat/Cool on linked indoor units to avoid invalid outdoor unit states.

### Tested and working

Below is a list of indoor units that have been reported to work with the MELCloud Home integration. In all cases, the unit must be connected to MELCloud Home (typically via a MAC‑597 or built‑in equivalent).

| Indoor Unit Model | Wi‑Fi Adapter | Notes                |
|-------------------|--------------|----------------------|
| **MSZ‑AY25VGK2**  | MAC‑597      | Single‑split system. |
| **MSZ‑AY25VGK2**  | MAC‑597      | Multi-split system.  |

> **Tip**
> Model numbers may vary slightly by region (e.g. “VG” vs “VGK” or numerical suffixes). If your model is similar to one listed here, it may still work, but please treat it as *untested* until confirmed.

### Reported but unverified

These models have been mentioned by users but have not yet been fully verified by the maintainer:

| Indoor Unit Model | Wi‑Fi Adapter | Status     | Notes |
|-------------------|--------------|-----------|-------|
| *None yet*        |              |           |       |

---

## Multi‑Split and Other Topologies

Multi‑split, ducted, or VRF systems may behave differently depending on how Mitsubishi exposes them to MELCloud Home (e.g. multiple logical devices vs a single aggregate device).

Current status:

- **Multi‑split systems**: *Not yet tested.*
- **Ducted units**: *Not yet tested.*
- **Commercial / VRF systems**: *Not supported* unless they appear as standard devices in the MELCloud Home app.

If you successfully use this integration with one of these configurations, please consider contributing details (see below).

---

## Contributing Tested Hardware

Contributions to expand this list are very welcome.

When opening a pull request to add or update a device, please include:

1. **Indoor unit model** (full designation, e.g. `MSZ‑AY25VGK2`).
2. **Wi‑Fi adapter model** (e.g. `MAC‑597`).
3. **MELCloud platform** used:
   - `MELCloud Home` (this integration)
   - `MELCloud` (use the core HA integration instead)
4. Any **notable quirks**:
   - Missing features compared to the official app
   - Known issues (e.g. slow state updates, limited modes)
   - Firmware versions if relevant

A simple template for additions:

```text
### Tested and working

| Indoor Unit Model | Wi‑Fi Adapter | Notes |
|-------------------|--------------|-------|
| MSZ‑AY25VGK2      | MAC‑597      | Works with MELCloud Home integration vX.Y.Z. |
```

Thank you to everyone who helps confirm models and improve this list.
