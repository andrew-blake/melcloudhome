# Entity Naming Implementation - Fix "Recreate IDs" Issue

## Current State

**IMPLEMENTED (but flawed):** Post-registration entity registry updates in `__init__.py`
- Function: `_async_update_entity_friendly_names()`
- Achieves short friendly names: "Room Temperature" ✓
- Maintains stable entity IDs: `sensor.melcloudhome_bf2d_5666_room_temperature` ✓
- **PROBLEM:** Breaks Home Assistant's "Recreate IDs" feature ✗

**Commit:** `a8342fc` - feat: Add short friendly names to entities while preserving stable entity IDs

## Problem Discovered

When "Recreate IDs" is clicked on a MELCloud entity, Home Assistant proposes changing:
- FROM: `sensor.melcloudhome_bf2d_5666_room_temperature`
- TO: `sensor.room_temperature`

This happens because we set `entity.name = "Room Temperature"` in the registry, and HA's "Recreate IDs" uses the current friendly name to propose new entity IDs.

**Why this matters:** Users could accidentally break all their automations by clicking "Recreate IDs".

## Investigation Results

We investigated how the Home Assistant backup service achieves:
- Entity ID: `sensor.backup_backup_manager_state` (long, stable)
- Friendly Name: "Manager State" (short)
- "Recreate IDs": Shows "no changes" ✓

**Key findings:**
1. Backup service uses `has_entity_name = True` from the start
2. Entity ID is generated as: `{domain}.{device_name}_{entity_name}`
3. Device name is stable: "Backup"
4. Entity name is short: "Manager State"
5. Result: Entity ID matches what would be generated, so "Recreate IDs" works

## The Solution

**Use `has_entity_name = True` with UUID-based device names**

Instead of:
- Device name: "My Home Living Room" (user-facing, changeable)
- Entity name: "MELCloudHome bf2d 5666 Room Temperature" (long)
- `has_entity_name = False`

Do:
- Device name: "melcloudhome_bf2d_5666" (UUID-based, stable)
- Entity name: "Room Temperature" (short)
- `has_entity_name = True`

**Result:**
- Entity ID: `sensor.melcloudhome_bf2d_5666_room_temperature` (unchanged!)
- Friendly display: "Room Temperature" (short!)
- "Recreate IDs": No changes (compatible!)

## Implementation Tasks

### 1. Revert Previous Implementation

**File:** `custom_components/melcloudhome/__init__.py`

Remove:
- `_async_update_entity_friendly_names()` function
- Call to `await _async_update_entity_friendly_names(hass, entry)`

This approach is fundamentally flawed and should be completely removed.

### 2. Update Device Info Helpers

**File:** `custom_components/melcloudhome/const.py`

Update `create_device_info()` function (~lines 126-158):

```python
def create_device_info(unit: DeviceUnit, building: "Building") -> "DeviceInfo":
    """Create standardized device info for ATA or ATW units."""
    from homeassistant.helpers.device_registry import DeviceInfo
    from .api.models import AirToWaterUnit

    # Extract UUID fragments for stable device naming
    unit_id_clean = unit.id.replace("-", "")
    device_name = f"melcloudhome_{unit_id_clean[:4]}_{unit_id_clean[-4:]}"

    # Determine model string based on unit type
    if isinstance(unit, AirToWaterUnit):
        model = f"Air-to-Water Heat Pump (Ecodan FTC{unit.ftc_model} via MELCloud Home)"
    else:  # AirToAirUnit
        model = "Air-to-Air Heat Pump (via MELCloud Home)"

    return DeviceInfo(
        identifiers={(DOMAIN, unit.id)},
        name=device_name,  # UUID-based, stable
        manufacturer="Mitsubishi Electric",
        model=model,
        suggested_area=building.name,  # Use building for area suggestion
    )
```

Do the same for `create_atw_device_info()` if it exists separately.

### 3. Update Entity Base Classes

**File:** `custom_components/melcloudhome/const.py`

Change `ATAEntityBase` and `ATWEntityBase` classes:

```python
class ATAEntityBase(CoordinatorEntity[MELCloudHomeCoordinator]):
    """Base class for ATA entities."""

    _attr_has_entity_name = True  # Changed from False
    # ... rest stays the same
```

```python
class ATWEntityBase(CoordinatorEntity[MELCloudHomeCoordinator]):
    """Base class for ATW entities."""

    _attr_has_entity_name = True  # Changed from False
    # ... rest stays the same
```

### 4. Update Entity Name Helper

**File:** `custom_components/melcloudhome/const.py`

Modify `create_entity_name()` function (~lines 99-123):

```python
def create_entity_name(unit: DeviceUnit, suffix: str = "") -> str:
    """Generate short entity name for has_entity_name=True.

    With has_entity_name=True, entity_id is generated as:
    {domain}.{device_name}_{entity_name}

    Device name already contains UUID (melcloudhome_bf2d_5666),
    so entity name should just be the descriptive part.

    Args:
        unit: ATA or ATW unit object (used for context, but UUID now in device name)
        suffix: Entity suffix (e.g., "Room Temperature", "Zone 1", "Tank")
                Empty string for base entities (ATA climate)

    Returns:
        Short entity name or None for device-name-only entities

    Examples:
        >>> create_entity_name(unit, "Room Temperature")
        "Room Temperature"

        >>> create_entity_name(unit, "")
        None  # Base ATA climate uses device name only
    """
    return suffix.strip() if suffix else None
```

### 5. Update Climate Entities

**File:** `custom_components/melcloudhome/climate.py`

**ATAClimate** (around line 79):
```python
_attr_has_entity_name = True  # Changed from False

def __init__(...):
    # ...
    self._attr_name = None  # Use device name for base ATA climate
```

**ATWClimateZone1** (around line 348):
```python
_attr_has_entity_name = True  # Changed from False

def __init__(...):
    # ...
    self._attr_name = "Zone 1"  # Short name
```

### 6. Update Sensor Entities

**File:** `custom_components/melcloudhome/sensor.py`

**ATASensor** and **ATWSensor** `__init__` methods:

```python
def __init__(...):
    # ...
    # Convert description key to friendly name
    # "room_temperature" → "Room Temperature"
    short_name = description.key.replace("_", " ").title()

    # Fix acronyms
    acronym_fixes = {
        "Dhw": "DHW",
        "Wifi": "WiFi",
        "Ftc": "FTC",
    }
    for incorrect, correct in acronym_fixes.items():
        short_name = short_name.replace(incorrect, correct)

    self._attr_name = short_name
```

### 7. Update Binary Sensor Entities

**File:** `custom_components/melcloudhome/binary_sensor.py`

Same pattern as sensors - derive short names from description keys with acronym fixes.

### 8. Update Water Heater Entity

**File:** `custom_components/melcloudhome/water_heater.py`

```python
_attr_has_entity_name = True  # Changed from False

def __init__(...):
    # ...
    self._attr_name = "Tank"  # Short name
```

### 9. Update Switch Entity

**File:** `custom_components/melcloudhome/switch.py`

```python
_attr_has_entity_name = True  # Changed from False

def __init__(...):
    # ...
    self._attr_name = "System Power"  # Short name
```

### 10. Update Tests

**Files:** `tests/integration/test_*.py`

Update assertions for device names (entity IDs should remain the same):
- Old device name: "My Home Living Room"
- New device name: "melcloudhome_0efc_9abc"

## Testing Checklist

After implementation:

1. ✅ **Fresh install:** Entity IDs match `sensor.melcloudhome_{uuid}_key` format
2. ✅ **Friendly names:** Show short versions (e.g., "Room Temperature")
3. ✅ **"Recreate IDs":** Click it, verify shows "no changes"
4. ✅ **Device names:** Show UUID-based format (e.g., "melcloudhome_0efc_9abc")
5. ✅ **Acronyms:** DHW, WiFi, FTC properly capitalized
6. ✅ **Base ATA climate:** Entity uses device name (entity_id: `climate.melcloudhome_xxxx`)
7. ✅ **ATW climate zone:** Entity uses "Zone 1" (entity_id: `climate.melcloudhome_xxxx_zone_1`)

## Migration Impact

**For existing users:**
- Entity IDs: No change ✓ (automations continue working)
- Device names: Change from user-facing to UUID-based (visual only)
- Friendly names: Get shorter (improvement)

**Version bump:** Patch or minor (no breaking changes to entity IDs)

## Files to Modify Summary

1. `__init__.py` - Remove registry update function
2. `const.py` - Update device info, base classes, name helper
3. `climate.py` - Update has_entity_name and names
4. `sensor.py` - Update has_entity_name and names
5. `binary_sensor.py` - Update has_entity_name and names
6. `water_heater.py` - Update has_entity_name and names
7. `switch.py` - Update has_entity_name and names
8. `tests/` - Update device name assertions

## Reference Documentation

- Plan file: `_claude/entity-naming-short-names-plan.md`
- ADR-003: `docs/decisions/003-entity-naming-strategy.md` (will need updating after implementation)
- Old approach commit: `a8342fc`
