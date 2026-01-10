# ADR-013: Automatic Friendly Device Names

**Date:** 2026-01-06
**Status:** Accepted
**Deciders:** @andrew-blake

## Context

After implementing `has_entity_name=True` (v2.0.0), device names became UUID-based (`melcloudhome_bf8d_5119`) for stable entity IDs. This creates poor onboarding UX - users can't identify which device is which physical location.

**Problem:** 6 devices show as cryptic UUIDs instead of "Living Room", "Dining Room", etc.

## Decision

**Programmatically set `name_by_user` to friendly API location names during setup.**

Uses `device_registry.async_update_device()` to set friendly names from API data during integration setup.

**Naming scheme:** `f"{building.name} {unit.name}"` (e.g., "My Home Living Room AC")

**Implementation:**

```python
async def _migrate_device_names(hass, entry, coordinator):
    """Set name_by_user for devices with UUID-pattern names."""
    device_reg = dr.async_get(hass)

    # Build mapping: unit_id -> friendly_name
    friendly_names = {}
    for building in coordinator.data.buildings:
        for unit in building.air_to_air_units + building.air_to_water_units:
            friendly_names[unit.id] = f"{building.name} {unit.name}"

    # Update devices matching UUID pattern that haven't been customized
    for device in device_reg.devices.values():
        if (UUID_PATTERN.match(device.name) and
            device.name_by_user is None and
            unit_id in friendly_names):
            device_reg.async_update_device(
                device.id,
                name_by_user=friendly_names[unit_id]
            )
```

**Safety checks:**

1. Only updates UUID-pattern names (`melcloudhome_xxxx_yyyy`)
2. Skips if `name_by_user` already set (respects user customization)
3. Only processes devices for this config entry
4. Idempotent - safe to run on every restart

## Rationale

**Why this approach:**

- Preserves entity ID stability (device `name` stays UUID-based)
- Improves UX (users see friendly names immediately)
- Respects user control (never overwrites manual renames)
- Zero maintenance (automatic for new devices)

**Alternatives rejected:**

- Document manual renaming: Poor UX, doesn't solve problem
- Use friendly names for device `name`: Breaks entity ID stability
- Version-gated migration: Unnecessary complexity

**Risks accepted:**

- No other core integrations do this
- Home Assistant docs suggest `name_by_user` is UI-only (no explicit prohibition)
- Could break if HA changes device registry behavior

## Consequences

**Positive:**

- Immediate UX improvement
- Works automatically
- Preserves automation safety
- Self-healing (handles new devices)

**Negative:**

- Unconventional use of `name_by_user`
- Future compatibility risk
- **Entity ID recreation risk**: If user deletes entities and uses "Recreate entity IDs", HA regenerates them from `name_by_user` (friendly name) instead of device `name` (UUID), breaking automations

**Mitigation:**

- Comprehensive integration tests
- Easy to disable if needed
- Logging for visibility

## References

- [Home Assistant Device Registry](https://developers.home-assistant.io/docs/device_registry_index/)
- [GitHub Issue #97332](https://github.com/home-assistant/core/issues/97332) - Clarifies `name_by_user` intent
- ADR-003: Entity Naming Strategy
- ADR-010: Entity ID Prefix Change
