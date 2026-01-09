# ADR-011: Multi-Device-Type Architecture

**Date:** 2026-01-03
**Status:** Accepted
**Deciders:** @andrew-blake

## Context

The MELCloud Home integration currently supports Air-to-Air (A2A) A/C units only. The MELCloud Home API also provides Air-to-Water (A2W) heat pump control through the same service, sharing authentication and the `/api/user/context` endpoint. We need to decide how to architecturally incorporate A2W support into the existing codebase.

## Decision Drivers

- **Code Reuse** - Shared authentication, session management, and API patterns
- **API Reality** - UserContext endpoint already returns both device types
- **Maintenance Burden** - Single developer, avoid unnecessary complexity
- **ADR-001 Compliance** - Maintain "Bundled API Client" approach
- **Testing Overhead** - Minimize duplication in test infrastructure
- **Type Safety** - Maintain clear boundaries between device types

## Options Considered

### Option A: Extend Current Module (CHOSEN)

**Structure:**
```
custom_components/melcloudhome/api/
├── __init__.py
├── auth.py              # Shared (no changes)
├── exceptions.py        # Shared (no changes)
├── const.py             # Add A2W constants
├── models.py            # Add A2W models
└── client.py            # Add A2W methods
```

**Client Usage:**
```python
client = MELCloudHomeClient()
await client.login(user, pass)

# Get all devices (both types)
context = await client.get_user_context()
a2a_units = context.get_all_air_to_air_units()
a2w_units = context.get_all_air_to_water_units()

# Control A2A
await client.set_temperature(a2a_unit_id, 22.0)

# Control A2W
await client.set_zone_temperature(a2w_unit_id, 21.0)
await client.set_dhw_temperature(a2w_unit_id, 50.0)
```

**Pros:**
- **90% code overlap** - Auth, session, validation, control patterns
- **Natural API structure** - UserContext already multi-type
- **Zero duplication** - Single auth layer, single session
- **Maintains ADR-001** - Still bundled, still simple
- **Clear method names** - Device type evident from method name
- **Simpler testing** - Single client to mock
- **Easy maintenance** - Everything in one place

**Cons:**
- Larger `const.py` and `models.py` files
- More methods in `MELCloudHomeClient`
- Potential confusion about which methods apply to which device type

### Option B: Separate Submodules

**Structure:**
```
custom_components/melcloudhome/api/
├── __init__.py
├── auth.py              # Shared
├── exceptions.py        # Shared
├── a2a/
│   ├── const.py
│   ├── models.py
│   └── client.py
└── a2w/
    ├── const.py
    ├── models.py
    └── client.py
```

**Pros:**
- Clean physical separation
- Each device type self-contained
- Easier to understand in isolation

**Cons:**
- **Code duplication** - Control pattern repeated
- **Shared UserContext confusion** - Which module owns it?
- **Auth complexity** - Must coordinate between modules
- **Import complexity** - More complex from HA integration
- **Testing duplication** - Two clients to mock/test
- **Goes against ADR-001** - Adds unnecessary structure

### Option C: Separate PyPI Package

**Structure:**
```
pypi: melcloudhome-api-a2w
  - New package on PyPI
  - custom_components imports both packages
```

**Pros:**
- Maximum separation
- Could be used by other projects

**Cons:**
- **Violates ADR-001** - "Bundled API Client" principle
- **Deployment complexity** - Two packages to maintain
- **Premature optimization** - No evidence of need
- **Auth nightmare** - Two packages, one session?
- **YAGNI violation** - Not needed yet

## Decision

**Chosen: Option A - Extend Current Module**

We will extend the existing `custom_components/melcloudhome/api/` module with A2W support by:
1. Adding A2W constants to `const.py`
2. Adding A2W models (`AirToWaterUnit`, `AirToWaterCapabilities`) to `models.py`
3. Adding A2W control methods to `MELCloudHomeClient` in `client.py`
4. Updating `UserContext` model to expose `air_to_water_units`

## Rationale

### Shared Infrastructure (100%)
- **Authentication:** AWS Cognito OAuth - identical for both
- **Session management:** Same cookies, same headers
- **UserContext endpoint:** `/api/user/context` returns BOTH types
- **Control pattern:** Sparse PUT with nulls - identical

### API Overlap (90%)
- **Endpoint structure:** Same pattern, different prefix (`ataunit` vs `atwunit`)
- **Request format:** JSON with same header requirements
- **Response format:** Empty 200 for control, settings array for state
- **Validation:** Same approach to null handling

### Natural Separation
Device type is evident from method names:
- A2A: `set_temperature()`, `set_mode()`, `set_fan_speed()`
- A2W: `set_zone_temperature()`, `set_dhw_temperature()`, `set_forced_hot_water()`

No risk of calling wrong method - TypeScript/IDE autocomplete makes it obvious.

### Maintains ADR-001 Principles
- Still bundled (not separate package)
- Still simple (single client)
- Still fast iteration (no multi-package coordination)
- Can still migrate to PyPI later if needed

## Consequences

### Positive

1. **Zero Duplication** - Auth, session, validation logic shared
2. **Single Source of Truth** - One place for all MELCloud API interaction
3. **Simpler Testing** - Single `MELCloudHomeClient` to mock
4. **Natural Organization** - Device type separation through methods, not modules
5. **Easy Discovery** - All API methods in one client class
6. **Consistent with ADR-001** - Maintains bundled approach

### Negative

1. **Larger Files** - `const.py`, `models.py`, `client.py` will grow
   - *Mitigation:* Still manageable at ~500-1000 lines per file
   - *Mitigation:* Clear section comments separate device types

2. **Method Namespace** - More methods in single class
   - *Mitigation:* Clear naming convention (zone vs dhw vs plain)
   - *Mitigation:* IDE autocomplete helps discovery

3. **Import Simplicity** - Single import gets everything
   - *Consequence:* Not a problem for bundled approach
   - *Benefit:* Actually simpler - don't choose between imports

### Risks

**Risk:** Confusion about which methods apply to which device type
**Mitigation:** Clear docstrings, method naming, type hints

**Risk:** Files become too large
**Mitigation:** Can refactor to submodules later if truly needed (YAGNI for now)

## Implementation Notes

### File Growth Estimates
Based on A2A implementation:
- `const.py`: ~200 lines (A2A) + ~150 lines (A2W) = ~350 lines total
- `models.py`: ~250 lines (A2A) + ~200 lines (A2W) = ~450 lines total
- `client.py`: ~400 lines (A2A) + ~300 lines (A2W) = ~700 lines total

All files remain under 1000 lines - maintainable.

### Method Naming Convention
```python
# A2A methods (keep existing)
set_temperature(unit_id, temp)          # Room temperature
set_mode(unit_id, mode)                 # Operation mode
set_fan_speed(unit_id, speed)           # Fan control

# A2W methods (new)
set_zone_temperature(unit_id, temp)     # Zone heating
set_dhw_temperature(unit_id, temp)      # DHW tank
set_zone_mode(unit_id, mode)            # Zone operation mode
set_forced_hot_water(unit_id, enabled)  # DHW priority
set_holiday_mode(unit_ids, ...)         # Multi-unit
set_frost_protection(unit_ids, ...)     # Multi-unit
```

Clear naming makes device type obvious without needing separate modules.

## Migration Path

If needs change in future:
1. Create `api/a2a/` and `api/a2w/` submodules
2. Move device-specific code to respective modules
3. Keep shared code (`auth.py`, `exceptions.py`, `UserContext`) in `api/`
4. Update imports in HA integration
5. Maintain single `MELCloudHomeClient` that delegates to submodules

This migration is straightforward and non-breaking.

## References

- ADR-001: Bundled API Client Architecture (maintains same principles)
- `docs/research/ATW/MelCloud_ATW_Complete_API_Documentation.md`
- `docs/research/ATW/MelCloud_ATW_API_Reference.md`
- API comparison analysis (plan file: smooth-leaping-lemon.md)
- GitHub Discussion #26: heat pump support

## Related Decisions

- ADR-001: Established bundled client principle (still applies)
- This decision extends ADR-001 to multi-device-type scenario
- Future: May need ADR for multi-coordinator vs single-coordinator in HA layer

## Notes

**Key Insight:** The API itself treats device types as a unified service:
- Single authentication
- Single UserContext endpoint
- Parallel arrays in same response

Our architecture should mirror this reality. Separating into modules would be fighting against the API's natural structure.

**Design Principle:** "Make the easy thing the right thing"
- Easy thing: Add methods to existing client
- Right thing: Leverage shared infrastructure
- Result: Easy thing IS the right thing

---

## Implementation Evolution

**Date:** 2026-01-09
**Status:** Actual implementation differs from original plan (Option A), but maintains core principles

### Actual Implementation

While the decision chose **Option A** (extend current module), the implementation evolved during development to better support maintainability and code organization.

**API Layer Structure (as implemented):**

```
custom_components/melcloudhome/api/
├── __init__.py              # Exports MELCloudHomeClient facade
├── auth.py                  # Shared authentication (AWS Cognito OAuth)
├── exceptions.py            # Shared exception classes
├── client.py                # Facade pattern - composes client_ata + client_atw
├── client_ata.py            # ATA-specific control methods
├── client_atw.py            # ATW-specific control methods
├── const_shared.py          # Shared constants (User-Agent, endpoints)
├── const_ata.py             # ATA-specific constants (modes, fan speeds)
├── const_atw.py             # ATW-specific constants (zone modes, temp ranges)
├── models.py                # Shared models (Building, UserContext)
├── models_ata.py            # ATA-specific models (AirToAirUnit)
├── models_atw.py            # ATW-specific models (AirToWaterUnit)
└── parsing.py               # Shared parsing utilities
```

**Integration Layer Structure (as implemented):**

```
custom_components/melcloudhome/
├── const.py                 # Integration-level constants
├── const_ata.py             # ATA entity constants (HVAC modes, fan modes)
├── const_atw.py             # ATW entity constants (preset modes, temp ranges)
├── climate_ata.py           # ATA climate entity
├── climate_atw.py           # ATW climate entity (Zone 1)
├── water_heater.py          # ATW water heater entity
├── switch.py                # ATW system power switch
├── sensor.py                # Both ATA and ATW sensors
└── binary_sensor.py         # Both ATA and ATW binary sensors
```

### Facade Pattern Implementation

**MELCloudHomeClient** acts as a facade that composes specialized clients:

```python
# client.py
class MELCloudHomeClient:
    """Main client - Facade pattern."""

    def __init__(self):
        self._auth = MELCloudHomeAuth()
        self._ata_client = ATAClient(self._auth)
        self._atw_client = ATWClient(self._auth)

    # Delegate to specialized clients
    async def set_temperature(self, unit_id, temp):
        return await self._ata_client.set_temperature(unit_id, temp)

    async def set_temperature_zone1(self, unit_id, temp):
        return await self._atw_client.set_temperature_zone1(unit_id, temp)
```

### Why This Is Better Than Option A

**Original Option A:** Add all methods to single client file, all constants to single const file, all models to single models file.

**Actual Implementation Benefits:**

1. **Better Single Responsibility Principle**
   - Each client file focuses on one device type
   - Each const file contains related constants only
   - Each model file contains related models only

2. **Easier Navigation and Maintenance**
   - Developers can quickly find ATA-specific or ATW-specific code
   - Smaller files are easier to review and understand
   - Clear separation reduces cognitive load

3. **Facade Pattern Advantages**
   - Main client provides unified interface (maintains Option A goal)
   - Internal complexity hidden from consumers
   - Easy to extend with new device types (A2W2, etc.)

4. **Maintains All Benefits of Option A**
   - ✅ Zero duplication - shared auth, session, validation
   - ✅ Single source of truth - one place for all API interaction
   - ✅ Simpler testing - single facade to mock
   - ✅ Easy discovery - all API methods available from main client
   - ✅ Consistent with ADR-001 - still bundled

5. **File Sizes Remain Manageable**
   - `client_ata.py`: ~300 lines
   - `client_atw.py`: ~250 lines
   - `models_ata.py`: ~150 lines
   - `models_atw.py`: ~200 lines
   - All files under 400 lines (very maintainable)

### Design Evolution Rationale

During implementation, it became clear that:

1. **Natural Separation Points Emerged**
   - ATA and ATW have completely different control APIs
   - Constants don't overlap (different modes, different ranges)
   - Models have different fields and parsing logic

2. **Facade Pattern Was Natural Fit**
   - Client needed to delegate to device-specific logic anyway
   - Composition better than inheritance for this use case
   - Maintains single import for consumers: `from .api import MELCloudHomeClient`

3. **SRP Violations Would Occur in Option A**
   - Single `client.py` with 700+ lines mixing ATA and ATW logic
   - Single `const.py` with unrelated constants side-by-side
   - Single `models.py` with very different parsing requirements

**Conclusion:** The implementation evolved to a cleaner architecture while maintaining all the benefits of Option A. The facade pattern provides the "single client" interface while internal structure follows better software engineering principles.

### Migration Path Still Valid

The migration path described in the original ADR remains valid. If needed, we could:
1. Further split into `api/ata/` and `api/atw/` submodules
2. Keep facade at `api/client.py` for backward compatibility
3. This would be non-breaking for integration layer

However, current structure is already clean and maintainable, so such migration is not needed.

### Key Takeaway

**Original Decision (Option A) was correct in principle:**
- Single API module ✅
- Shared infrastructure ✅
- Bundled approach ✅

**Implementation refined the structure:**
- Facade pattern for cleaner code organization
- Better SRP compliance
- Same external interface

This evolution demonstrates good software engineering: Make initial architectural decisions based on principles, then refine implementation details as code reveals natural boundaries.
