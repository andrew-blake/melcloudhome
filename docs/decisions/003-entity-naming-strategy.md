# ADR-003: Entity Naming and Device Registry Strategy

**Date:** 2025-01-17
**Status:** Accepted
**Deciders:** @andrew-blake

## Context

Home Assistant entities need stable, unique identifiers and human-friendly names. The integration must handle devices across multiple buildings (homes/locations) while being future-proof if users add more buildings later. Home Assistant's entity naming patterns have evolved, with modern integrations using device-centric naming rather than setting entity IDs directly.

## Decision Drivers

- **Future-proofing** - Entity IDs are permanent once created
- **User experience** - Names should be clear and unambiguous
- **Modern HA patterns** - Follow 2024+ best practices
- **Multi-building support** - Users may have vacation homes, rental properties, etc.
- **Name consistency** - Avoid confusion when configuration changes

## Options Considered

### Option A: Conditional Building Names
**Pattern:** Include building name only when multiple buildings exist

```python
# 1 building
entity_id: climate.living_room
name: "Living Room"

# 2+ buildings (names suddenly change!)
entity_id: climate.living_room_2  # HA adds suffix - confusing!
name: "Home Living Room"
```

**Pros:**
- Cleaner names for single-building users
- Shorter entity IDs initially

**Cons:**
- Entity naming changes when buildings added
- Inconsistent patterns across devices
- Entity ID conflicts require ugly suffixes (_2, _3)
- Breaks automations when names change
- Dynamic name property confusing

### Option B: Legacy Direct entity_id Assignment
**Pattern:** Set `self.entity_id` directly with building name

```python
self.entity_id = f"climate.{slugify(building.name)}_{slugify(unit.name)}"
```

**Pros:**
- Direct control over entity_id
- Predictable naming

**Cons:**
- **Deprecated pattern** - Not recommended in modern HA
- Bypasses entity registry
- Doesn't integrate with device registry properly
- No support for entity name overrides

### Option C: Modern Device-Centric Naming (CHOSEN)
**Pattern:** Use `_attr_has_entity_name` with device info, always include building

```python
_attr_has_entity_name = True
_attr_unique_id = unit.id  # Device UUID

device_info = DeviceInfo(
    identifiers={(DOMAIN, unit.id)},
    name=f"{building.name} {unit.name}",  # Always includes building
    manufacturer="Mitsubishi Electric",
    model="Air-to-Air Heat Pump",
    suggested_area=building.name,
)
```

**Result:**
```python
# Always consistent, regardless of building count
entity_id: climate.home_living_room_climate
device_name: "Home Living Room"
entity_name: uses device name (or custom override)
```

**Pros:**
- **Future-proof** - Works when buildings added
- **Consistent** - Same pattern for all devices
- **Modern HA** - Follows 2024+ best practices
- **Entity registry** - Proper integration with HA's registry
- **User overridable** - Users can customize names in UI
- **Device registry** - Groups entities properly
- **Area suggestion** - Building becomes suggested area

**Cons:**
- Slightly longer names even with one building
- Device name includes building (unavoidable for uniqueness)

## Decision

**Chosen: Option C - Modern Device-Centric Naming with Building Always Included**

Use Home Assistant's modern entity naming pattern with device registry integration.

### Implementation Pattern

```python
class MELCloudHomeClimate(CoordinatorEntity, ClimateEntity):
    """MELCloud Home climate entity."""

    def __init__(self, coordinator, unit: AirToAirUnit, building: Building):
        super().__init__(coordinator)

        # Permanent unique identifier (device UUID)
        self._attr_unique_id = unit.id

        # Enable modern naming pattern
        self._attr_has_entity_name = True

        # Store for lookups
        self._unit_id = unit.id
        self._building_id = building.id

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        building = self._get_building()
        device = self._device

        return DeviceInfo(
            identifiers={(DOMAIN, self._unit_id)},
            name=f"{building.name} {device.name}",  # Always includes building
            manufacturer="Mitsubishi Electric",
            model="Air-to-Air Heat Pump",
            suggested_area=building.name,
            via_device=(DOMAIN, self.coordinator.config_entry.entry_id),
        )
```

### Naming Results

**Single Building:**
```yaml
Device:
  name: "Home Living Room"
  suggested_area: "Home"
Entity:
  entity_id: climate.home_living_room_climate
  friendly_name: "Home Living Room Climate" (or user override)
```

**Multiple Buildings:**
```yaml
Device 1:
  name: "Home Living Room"
  suggested_area: "Home"
Entity 1:
  entity_id: climate.home_living_room_climate

Device 2:
  name: "Vacation Home Living Room"
  suggested_area: "Vacation Home"
Entity 2:
  entity_id: climate.vacation_home_living_room_climate
```

## Consequences

### Positive

- **Future-proof** - No conflicts when buildings added
- **Stable entity IDs** - Never change after creation
- **Consistent pattern** - Same approach for all entities
- **Modern HA compliance** - Follows 2024+ best practices
- **Entity registry integration** - Proper unique_id handling
- **Device registry integration** - Groups related entities
- **User customization** - Names overridable in HA UI
- **Area integration** - Building suggests area assignment
- **Migration ready** - If submitting to HA core later

### Negative

- **Longer names** - Even single-building users see building in device name
- **Can't omit building** - No way to have "Living Room" alone
- **User education** - Might seem redundant for single-building users

### Trade-offs Accepted

**Verbosity vs Future-proofing:** Chose future-proofing
- Slightly longer names now avoid major issues later
- Entity IDs are permanent - better to have clear names upfront
- Users can rename in UI if they prefer

**Consistency vs Brevity:** Chose consistency
- Same pattern for all devices regardless of building count
- Predictable for users and developers
- No "magic" conditional logic

## Migration Path

If this decision proves problematic:

1. **Can't change entity IDs** - They're permanent in registry
2. **Can update device names** - These are dynamic
3. **Users can customize** - Override friendly names in UI

No breaking changes are possible without users deleting and re-adding integration.

## References

- Home Assistant Entity Documentation: https://developers.home-assistant.io/docs/core/entity
- Device Registry Documentation: https://developers.home-assistant.io/docs/device_registry_index
- Entity Registry Documentation: https://developers.home-assistant.io/docs/entity_registry_index
- `ha-integration-requirements.md` - Entity naming section
- Discussion in Session 5 planning (2025-01-17)

## Implementation Notes

### Key Requirements

1. **Always set unique_id** - Use device UUID from API
2. **Always enable has_entity_name** - Set `_attr_has_entity_name = True`
3. **Always include building in device name** - Even for single building
4. **Always provide device_info** - With proper identifiers and suggested_area
5. **Never set entity_id directly** - Let HA generate from device + entity name

### Device Name Format

```python
device_name = f"{building.name} {unit.name}"
# Examples:
# "Home Living Room"
# "Vacation Home Bedroom"
# "Office Main Floor"
```

### Entity Name

```python
_attr_name = None  # Uses device name by default
# or
_attr_name = "Climate"  # Results in "Home Living Room Climate"
```

For climate entities, using `None` (device name) is cleaner since there's typically one climate entity per device.

### Handling Device Renames

When user renames device in MELCloud:
- Device UUID (`unique_id`) stays the same
- HA recognizes it as same device
- Device name updates automatically
- Entity ID remains stable
- User's custom friendly name (if set) is preserved

## Notes

This decision aligns with Home Assistant 2024+ entity naming best practices and ensures the integration will work correctly when submitted to HA core in the future. The trade-off of slightly longer names is acceptable given the benefits of stability and consistency.

Most modern HA integrations (ESPHome, ZHA, Matter) use similar device-centric naming patterns with areas for organizing devices by location.
