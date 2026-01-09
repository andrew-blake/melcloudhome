# ADR-011: Multi-Device-Type Architecture

**Date:** 2026-01-03
**Status:** Accepted
**Deciders:** @andrew-blake

## Context

MELCloud Home API supports both Air-to-Air (ATA/A2A) and Air-to-Water (ATW/A2W) devices through the same authentication and `/api/user/context` endpoint. Need to add ATW support to the existing ATA-only integration.

**Key constraints:**

- Single developer, minimize complexity
- 90% shared infrastructure (auth, session, control patterns)
- UserContext endpoint returns both device types in one response
- Must maintain bundled approach (ADR-001)

## Decision

**Extend the existing `api/` module with ATW support using facade pattern.**

### Planned Structure (Option A)

Originally planned single `client.py` with all methods:

```python
client = MELCloudHomeClient()
await client.set_temperature(ata_id, temp)      # ATA
await client.set_zone_temperature(atw_id, temp) # ATW
```

### Actual Implementation (Evolved during development)

Facade pattern with specialized clients:

```python
client = MELCloudHomeClient()
await client.ata.set_temperature(ata_id, temp)
await client.atw.set_temperature_zone1(atw_id, temp)
```

**File structure:**

```
api/
├── client.py          # Facade - composes ata + atw clients
├── client_ata.py      # ATA control methods (~214 lines)
├── client_atw.py      # ATW control methods (~248 lines)
├── models_ata.py      # ATA models (~171 lines)
├── models_atw.py      # ATW models (~260 lines)
├── const_ata.py       # ATA constants
├── const_atw.py       # ATW constants
├── const_shared.py    # Shared constants
├── parsing.py         # Shared utilities
├── auth.py            # Shared (no changes)
└── exceptions.py      # Shared (no changes)
```

## Rationale

**Why extend vs separate packages:**

- 90% code overlap (auth, session, control patterns)
- API treats device types as unified service (same auth, single UserContext)
- Single developer - avoid multi-package coordination overhead
- Maintains bundled approach (ADR-001)

**Why facade pattern emerged:**

- Natural separation points: ATA/ATW have completely different APIs
- Better Single Responsibility Principle compliance
- Keeps files manageable (<300 lines each)
- Single import for consumers: `from .api import MELCloudHomeClient`
- Maintains all benefits of monolithic approach with better organization

**Alternatives rejected:**

- Separate PyPI packages: Violates ADR-001, premature
- Submodule structure (`api/ata/`, `api/atw/`): Unnecessary complexity for current size

## Consequences

**Positive:**

- Zero duplication - shared auth, session, validation
- Single client import - simple for consumers
- Manageable file sizes - all under 300 lines
- Clear boundaries - device type evident from code structure

**Negative:**

- More files than originally planned (acceptable trade-off)

## Migration Path

If further separation needed:

1. Move to `api/ata/` and `api/atw/` submodules
2. Keep facade at `api/client.py` for backward compatibility
3. Non-breaking change

## References

- ADR-001: Bundled API Client
- `docs/architecture.md`: Full structure diagrams
