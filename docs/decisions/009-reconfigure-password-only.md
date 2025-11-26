# ADR-009: Reconfigure Flow Supports Password-Only Updates

## Status

Accepted

## Date

2025-11-25

## Context

Phase 1 adds a reconfigure flow to allow users to update their MELCloud credentials without removing and re-adding the integration. This preserves entity history and customizations.

The question arose: should reconfigure allow changing the email address, or only the password?

In Home Assistant, the `unique_id` identifies a config entry. For this integration, the `unique_id` is set to the user's email address (`email.lower()`). Changing the email would mean changing the `unique_id`.

## Decision

**Reconfigure only supports password updates. Email changes require delete + re-add.**

The reconfigure flow:
- Shows the current email as read-only context
- Allows updating the password only
- Validates new credentials before saving
- Reloads the integration after successful update

## Rationale

1. **Home Assistant best practice**: The `unique_id` should be immutable. The March 2025 HA developer docs explicitly state that unique_id changes are deprecated behavior and integrations should not rely on them.

2. **Entity ID stability**: Entity IDs are based on device UUIDs (e.g., `climate.melcloud_0efc_76db`), not the email. Deleting and re-adding the integration with a different email will preserve entity IDs and history as long as the same physical devices are discovered.

3. **Simpler implementation**: Changing `unique_id` requires special handling (`async_update_entry` with explicit `unique_id` parameter) and conflict checking against other entries. Password-only updates use the standard `async_update_reload_and_abort` helper.

4. **Rare use case**: Email changes are uncommon. Users typically:
   - Change their password (supported by reconfigure)
   - Want to refresh device list (supported by integration reload after reconfigure)
   - Switch to a different account entirely (delete + re-add is appropriate)

## Consequences

### Positive

- Follows HA best practices for config entry management
- Simpler, more maintainable code
- Entity history preserved for common use cases

### Negative

- Users who change their MELCloud email must delete and re-add the integration
- This is a minor inconvenience for a rare scenario

## Alternatives Considered

### Allow email changes with unique_id update

Could use `async_update_entry(entry, unique_id=new_email, data=...)` and check for conflicts with existing entries.

Rejected because:
- Violates HA best practice (unique_id should be stable)
- More complex implementation
- Rare use case doesn't justify the complexity

## References

- [Home Assistant Config Flow Documentation](https://developers.home-assistant.io/docs/config_entries_config_flow_handler/)
- [HA Blog: New checks for config flow unique ID (March 2025)](https://developers.home-assistant.io/blog/2025/03/01/config-flow-unique-id/)
