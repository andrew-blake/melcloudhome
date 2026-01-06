# ADR-013: Automatic Friendly Device Names via name_by_user

## Status

Accepted

## Date

2026-01-06

## Context

After implementing `has_entity_name=True` in v2.0.0 to follow Home Assistant best practices, device names became UUID-based (e.g., `melcloudhome_bf8d_5119`) to ensure stable entity IDs. While this preserved automation compatibility, it created a significant UX problem:

**Problem:** During device onboarding, users could not identify which device corresponded to which physical location because they only saw cryptic UUID patterns instead of meaningful location names.

**Example:** A user with 6 devices would see:
- `melcloudhome_bf8d_5119`
- `melcloudhome_0efc_76db`
- `melcloudhome_83eb_bf1f`

Instead of:
- Living Room
- Dining Room
- Study

This made initial setup confusing and required users to manually rename each device through the UI after identifying them through trial and error.

## Decision

**Programmatically set `name_by_user` to friendly API location names during integration setup.**

The `name_by_user` field in Home Assistant's device registry is designed for user customizations but has a functional API (`async_update_device`) that we can leverage to provide better default names.

### Implementation Strategy

Add a `_migrate_device_names()` function that:
1. Runs after `async_forward_entry_setups()` to ensure devices exist
2. Iterates through all devices in the device registry
3. Sets `name_by_user` to friendly names from API data for devices that:
   - Have UUID-pattern names (regex: `^melcloudhome_[0-9a-f]{4}_[0-9a-f]{4}$`)
   - Haven't been customized by user (`name_by_user is None`)
   - Exist in coordinator data with valid building/unit names

### Naming Scheme

Uses v1.3.4 naming pattern: `f"{building.name} {unit.name}"`

**Examples:**
- Building: "My Home", Unit: "Living Room AC" → `"My Home Living Room AC"`
- Building: "Office", Unit: "Conference Room" → `"Office Conference Room"`

## Rationale

### Why This Approach?

1. **Preserves Entity ID Stability**
   - Device `name` field remains UUID-based (`melcloudhome_xxxx_yyyy`)
   - Entity IDs continue using stable UUID format
   - No breaking changes for existing automations

2. **Improves User Experience**
   - Users see friendly names immediately during onboarding
   - No manual renaming required for multiple devices
   - Clear device identification in UI

3. **Respects User Control**
   - Only updates devices with auto-generated UUID names
   - Never overwrites user customizations
   - Users can rename via UI anytime

4. **Idempotent Design**
   - Safe to run on every restart
   - Handles new devices automatically
   - Zero maintenance overhead

5. **Consistent with Platform Philosophy**
   - Provides sensible defaults
   - Allows user customization
   - Follows "convention over configuration"

### Why Not Alternatives?

**Alternative 1: Document Manual Renaming**
- ❌ Poor UX for users with multiple devices
- ❌ Doesn't solve the onboarding confusion problem
- ❌ Requires trial and error to identify devices

**Alternative 2: Use Friendly Names for Device `name` Field**
- ❌ Breaks entity ID stability (entity IDs would change)
- ❌ Potential breaking change for automations
- ❌ Violates Home Assistant's `has_entity_name` pattern

**Alternative 3: Version-Gated Migration**
- ❌ Added complexity without benefit
- ❌ Doesn't handle new devices or edge cases
- ❌ Requires state persistence

## Safety Checks

The implementation includes 6 safety layers:

1. **Config Entry Validation:** Only processes devices for this entry
2. **Domain Validation:** Only processes MELCloud Home devices
3. **UUID Pattern Check:** Only updates auto-generated names
4. **User Customization Check:** Skips if `name_by_user` is set
5. **Data Availability Check:** Skips if unit not in coordinator data
6. **Idempotent Design:** Safe to run multiple times

## Consequences

### Positive

- ✅ **Immediate UX improvement:** Users see friendly names during onboarding
- ✅ **Zero user action required:** Works automatically for all users
- ✅ **Preserves automation safety:** Entity IDs remain stable
- ✅ **User control maintained:** Manual renames are respected
- ✅ **Handles upgrades gracefully:** Works for both fresh installs and upgrades
- ✅ **Self-healing:** Automatically handles new devices

### Negative

- ⚠️ **No precedent:** No other core integrations programmatically set `name_by_user`
- ⚠️ **Potential policy violation:** Home Assistant docs suggest `name_by_user` is "set via UI, not integration" (though no explicit prohibition exists)
- ⚠️ **Future compatibility risk:** Could break if Home Assistant changes device registry behavior
- ⚠️ **Limited discoverability:** Users might not know they can customize names

### Mitigation

- **Well-tested:** Comprehensive integration tests cover all scenarios
- **Respects user control:** Never overwrites user customizations
- **Easy to remove:** Can be disabled or removed if policy changes
- **Monitored:** Logging provides visibility into migration activity

## Implementation

### Core Function

Added to `custom_components/melcloudhome/__init__.py`:

```python
async def _migrate_device_names(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: MELCloudHomeCoordinator,
) -> None:
    """Migrate device names from UUID format to friendly API names."""
    from homeassistant.helpers import device_registry as dr
    from .const import DOMAIN

    device_reg = dr.async_get(hass)

    # Build mapping: unit_id -> friendly_name
    friendly_names: dict[str, str] = {}
    for building in coordinator.data.buildings:
        for unit in building.air_to_air_units:
            friendly_names[unit.id] = f"{building.name} {unit.name}"
        for unit in building.air_to_water_units:
            friendly_names[unit.id] = f"{building.name} {unit.name}"

    # Iterate devices and update if needed
    migrated_count = 0
    for device in device_reg.devices.values():
        # 6 safety checks...
        if should_migrate(device):
            device_reg.async_update_device(
                device.id,
                name_by_user=friendly_names[unit_id]
            )
            migrated_count += 1

    if migrated_count > 0:
        _LOGGER.info("Device name migration complete: %d device(s) updated", migrated_count)
```

### Integration Point

```python
async def async_setup_entry(hass, entry):
    # ... initialization ...
    await async_forward_entry_setups(entry, platforms)
    await _migrate_device_names(hass, entry, coordinator)  # ← NEW
    # ... rest of setup ...
```

### Test Coverage

Added 4 comprehensive integration tests:
- `test_device_name_migration_uuid_pattern` - Verifies migration works
- `test_device_name_migration_respects_user_customization` - Verifies user renames preserved
- `test_device_name_migration_multiple_devices` - Verifies ATA + ATW handling
- `test_device_name_migration_idempotent` - Verifies repeated setups safe

## Performance

- **Execution time:** <1ms for typical installations (3-6 devices)
- **Frequency:** Once per Home Assistant restart
- **Overhead:** Negligible (O(n) where n = device count)

## Monitoring

The migration logs activity for transparency:

```
DEBUG: Migrated device name: melcloudhome_bf8d_5119 -> Living Room (device_id=56851e19)
INFO:  Device name migration complete: 3 device(s) updated
```

## Version

Included in v2.0.0 release.

## References

- [Home Assistant Device Registry Documentation](https://developers.home-assistant.io/docs/device_registry_index/)
- [has_entity_name Quality Scale Rule](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/has-entity-name/)
- [Entity Naming Blog Post](https://developers.home-assistant.io/blog/2022/07/10/entity_naming/)
- [GitHub Issue #97332](https://github.com/home-assistant/core/issues/97332) - Clarifies `name_by_user` intent

## Related ADRs

- [ADR-003: Entity Naming Strategy](003-entity-naming-strategy.md) - Original entity naming decisions
- [ADR-010: Entity ID Prefix Change](010-entity-id-prefix-change.md) - Previous entity ID changes

## Future Considerations

- Monitor Home Assistant community feedback on this pattern
- Consider proposing this as an official pattern if widely beneficial
- May need to adjust if Home Assistant explicitly prohibits this approach
- Could enhance with user preference setting if needed
