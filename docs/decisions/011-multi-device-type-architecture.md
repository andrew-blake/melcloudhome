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
