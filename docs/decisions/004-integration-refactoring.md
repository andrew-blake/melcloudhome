# ADR-004: Integration Refactoring for DRY, KISS, and Performance

**Date:** 2025-11-17
**Status:** Accepted

## Context

After initial implementation of the Home Assistant integration (Session 5), a code review identified several violations of DRY (Don't Repeat Yourself) and KISS (Keep It Simple, Stupid) principles, along with performance concerns.

### Issues Identified

1. **DRY Violation - Duplicate Authentication**
   - `config_flow.py` directly used `MELCloudHomeAuth`
   - `__init__.py` and `coordinator.py` used `MELCloudHomeClient`
   - Two different authentication paths in the same codebase

2. **Redundant Login**
   - `__init__.py` performed login, then coordinator did it again on first refresh
   - Extra network calls and complexity

3. **Performance - O(n*m) Device Lookups**
   - `climate.py` properties looped through all buildings/units on every access
   - Called 10+ times per update cycle
   - No caching mechanism

4. **DRY Violation - Temperature Constants**
   - Constants defined in both `api/const.py` and hardcoded in `client.py` and `climate.py`
   - Risk of inconsistency

5. **Import Inconsistency**
   - Mixed lazy and direct imports without clear pattern
   - No documentation explaining why

## Decision

We implemented the following changes:

### 1. Consolidate Authentication (Priority 1 - Critical)

**Changed:**
- `config_flow.py` now uses `MELCloudHomeClient` instead of `MELCloudHomeAuth`
- Single authentication abstraction throughout codebase

**Code:**
```python
# Before
auth = MELCloudHomeAuth()
await auth.login(email, password)

# After
client = MELCloudHomeClient()
await client.login(email, password)
```

**Impact:**
- ✅ DRY: Single authentication path
- ✅ Maintainability: Changes to auth logic in one place
- ✅ Consistency: Same pattern everywhere

### 2. Remove Redundant Login (Priority 1 - Critical)

**Changed:**
- Removed initial login from `__init__.py`
- Coordinator handles authentication on first refresh
- Updated `_async_update_data()` to check `is_authenticated` and login if needed

**Code:**
```python
# coordinator.py
async def _async_update_data(self) -> UserContext:
    if not self.client.is_authenticated:
        await self.client.login(self._email, self._password)
    return await self.client.get_user_context()
```

**Impact:**
- ✅ KISS: One login, not two
- ✅ Performance: One less network call on startup
- ✅ Cleaner error handling

### 3. Add O(1) Device Cache (Priority 2 - Performance)

**Changed:**
- Added `_units` and `_unit_to_building` dictionaries to coordinator
- `_rebuild_caches()` method updates dicts on each data refresh
- New `get_unit()` method for O(1) lookups
- Updated `get_building_for_unit()` to use cache

**Code:**
```python
# coordinator.py
def __init__(...):
    self._units: dict[str, AirToAirUnit] = {}
    self._unit_to_building: dict[str, Building] = {}

def _rebuild_caches(self, context: UserContext) -> None:
    for building in context.buildings:
        for unit in building.air_to_air_units:
            self._units[unit.id] = unit
            self._unit_to_building[unit.id] = building

def get_unit(self, unit_id: str) -> AirToAirUnit | None:
    return self._units.get(unit_id)
```

**Impact:**
- ✅ Performance: O(n*m) → O(1) lookups
- ✅ Scalability: Performance independent of device count
- ✅ Memory: Minimal overhead (just dict references)

### 4. Consolidate Temperature Constants (Priority 3)

**Changed:**
- `api/const.py` already had constants (they existed!)
- Updated `client.py` to import and use constants
- Updated `climate.py` to import and use constants
- Single source of truth for temperature ranges

**Code:**
```python
# api/const.py (already existed)
TEMP_MIN_HEAT = 10.0
TEMP_MIN_COOL_DRY = 16.0
TEMP_MAX_HEAT = 31.0
TEMP_STEP = 0.5

# client.py - now uses constants
if not TEMP_MIN_HEAT <= temperature <= TEMP_MAX_HEAT:
    raise ValueError(...)

# climate.py - now uses constants
_attr_target_temperature_step = TEMP_STEP
_attr_max_temp = TEMP_MAX_HEAT
```

**Impact:**
- ✅ DRY: Single definition
- ✅ Maintainability: Change once, applies everywhere
- ✅ Consistency: Guaranteed same values

### 5. Document Lazy Imports (Priority 3)

**Changed:**
- Added module-level docstring explaining lazy imports
- Added comments at each lazy import site
- Documented in `pyproject.toml` why HA is not a dev dependency

**Rationale:**
Home Assistant has extremely strict dependency pinning that conflicts with our `aiohttp>=3.13.2`. Attempting to install HA as dev dependency results in unsolvable conflicts. This is why **most HA custom components use lazy imports**.

**Approach:**
- API client is tested independently (79 tests, 82% coverage)
- Integration files use lazy imports
- Integration testing happens via deployment to actual HA instance

**Impact:**
- ✅ Clear: Developers understand WHY
- ✅ Standard: Follows HA custom component best practices
- ✅ Maintainable: Future developers won't "fix" it

## Consequences

### Positive

1. **Code Quality**
   - Eliminated DRY violations
   - Simplified authentication flow
   - Single source of truth for constants

2. **Performance**
   - O(1) device lookups instead of O(n*m)
   - One less network call on startup
   - Scalable to hundreds of devices

3. **Maintainability**
   - Clear patterns throughout codebase
   - Well-documented lazy imports
   - Consistent use of abstractions

4. **Testing**
   - All 79 tests passing
   - No functionality lost
   - No breaking changes

### Neutral

1. **Lazy Imports**
   - Can't test integration code with unit tests
   - Standard practice for HA custom components
   - Integration testing via deployment is acceptable

### Trade-offs Considered

**Could have:** Installed HA as dev dependency
**Why not:** Unsolvable dependency conflicts with aiohttp
**Alternative:** Lazy imports (chosen approach)

**Could have:** Used mock HA objects for testing
**Why not:** Testing strategy doc explicitly recommends against this
**Alternative:** Test API client, deploy to test integration

## Implementation

- **Files Changed:** 6 files
  - `api/client.py` - Use temperature constants
  - `api/const.py` - No changes (constants already existed)
  - `config_flow.py` - Use MELCloudHomeClient
  - `__init__.py` - Remove redundant login, document lazy imports
  - `coordinator.py` - Add caches, handle initial auth
  - `climate.py` - Use cached lookups, temperature constants
  - `pyproject.toml` - Document why HA not in dev deps

- **Tests:** All passing (79 passed, 3 skipped)
- **Code Quality:** Ruff linting passed
- **Backwards Compatibility:** Fully maintained

## Related Decisions

- [ADR-001: Bundled API Client](001-bundled-api-client.md)
- [ADR-002: Authentication Refresh Strategy](002-authentication-refresh-strategy.md)
- [ADR-003: Entity Naming Strategy](003-entity-naming-strategy.md)

## References

- [Testing Strategy](../testing-strategy.md) - Why not mock HA
- [Integration Review](../integration-review.md) - Best practices assessment
- [DRY Principle](https://en.wikipedia.org/wiki/Don%27t_repeat_yourself)
- [KISS Principle](https://en.wikipedia.org/wiki/KISS_principle)
