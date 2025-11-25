# ADR-010: Entity ID Prefix Change (Breaking Change)

## Status

Accepted

## Date

2025-11-25

## Context

Entity IDs were using `melcloud_` prefix (e.g., `climate.melcloud_0efc_76db`) but the integration domain is `melcloudhome`. This inconsistency was confusing.

The entity ID format uses the first 4 and last 4 hex characters of the device UUID for readability while maintaining practical uniqueness.

## Decision

**Change entity ID prefix from `melcloud_` to `melcloudhome_`.**

Before:
```
climate.melcloud_0efc_76db
sensor.melcloud_0efc_76db_room_temperature
binary_sensor.melcloud_0efc_76db_error_state
```

After:
```
climate.melcloudhome_0efc_76db
sensor.melcloudhome_0efc_76db_room_temperature
binary_sensor.melcloudhome_0efc_76db_error_state
```

## Rationale

1. **Consistency**: Prefix should match integration domain (`melcloudhome`)
2. **Clarity**: Avoids confusion with other MELCloud integrations
3. **Early stage**: Only one user currently, minimal migration impact

## Breaking Change

This is a **breaking change**. Users must update:
- Automations referencing old entity IDs
- Dashboard configurations
- Scripts and templates

Entity history will be lost for affected entities as they will be recreated with new IDs.

## Migration

No automatic migration provided. Users should:
1. Note any automations/dashboards using old entity IDs
2. Update the integration
3. Update references to use new entity IDs

## Consequences

### Positive

- Consistent naming with integration domain
- Clear distinction from other MELCloud integrations

### Negative

- Breaking change for existing users
- Entity history reset

## Implementation

Changed `_attr_name` in climate.py, sensor.py, and binary_sensor.py from:
```python
self._attr_name = f"MELCloud {unit_id_clean[:4]} {unit_id_clean[-4:]}"
```

To:
```python
self._attr_name = f"MELCloudHome {unit_id_clean[:4]} {unit_id_clean[-4:]}"
```

## Version

Included in v1.2.0 release.
