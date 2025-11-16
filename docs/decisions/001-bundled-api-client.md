# ADR-001: Bundled API Client Architecture

**Date:** 2025-11-16
**Status:** Accepted
**Deciders:** @andrew-blake

## Context

Building a Home Assistant custom component for MELCloud Home requires an API client to communicate with the cloud service. We needed to decide how to structure the API client library in relation to the Home Assistant integration.

## Decision Drivers

- **KISS Principle** - Keep it simple, stupid
- **YAGNI Principle** - You aren't gonna need it (yet)
- **Fast Iteration** - In development phase, speed matters
- **Single Developer** - No team coordination needed
- **Personal Use** - Not distributing to community yet

## Options Considered

### Option A: Separate Repository + PyPI Package
**Structure:** `pymelcloudhome` on PyPI, HA integration references it

**Pros:**
- Professional structure, industry standard
- Can share library with other projects
- Semantic versioning
- Suitable for HA core submission

**Cons:**
- More complex setup and maintenance
- PyPI account and publishing required
- Multi-repo coordination overhead
- Slower iteration (publish → install → test cycle)

### Option B: Monorepo with Subfolders
**Structure:** Both library and integration in same repo, separate folders

**Pros:**
- Single repo easier than separate repos
- Can use git+https:// for development

**Cons:**
- Still requires build/publish process
- git+https:// has validation issues in some HA versions
- Not significantly simpler than Option A

### Option C: Bundled in Custom Component (CHOSEN)
**Structure:** API client in `custom_components/melcloudhome/api/` subfolder

**Pros:**
- Simplest structure - single folder
- Fast iteration - change code instantly
- Zero publishing overhead
- Easy deployment - copy one folder
- No version conflicts
- Can migrate to PyPI later if needed

**Cons:**
- Cannot easily share library with other projects
- Not suitable for HA core submission (but can migrate)
- No semantic versioning for API client

## Decision

**Chosen: Option C - Bundled API Client**

Bundle the API client directly in the custom component's `api/` subfolder.

```
custom_components/melcloudhome/
├── api/                    # Bundled API client
│   ├── __init__.py
│   ├── client.py
│   ├── auth.py
│   └── models.py
├── __init__.py             # HA integration
├── climate.py
└── ...
```

**Import pattern:**
```python
from .api import MELCloudHomeClient
```

## Consequences

### Positive
- **Fastest development** - Change API code and test immediately
- **Simplest deployment** - Copy single folder to HA config
- **No external dependencies** - Self-contained custom component
- **Easy maintenance** - Everything in one place

### Negative
- **No reusability** - Library can't be shared (yet)
- **Not core-ready** - Would need refactor for HA core submission

### Migration Path
If needs change, migration to separate package is straightforward:
1. Move `api/` folder to separate repo
2. Publish to PyPI as `pymelcloudhome`
3. Update `manifest.json`: `"requirements": ["pymelcloudhome==0.1.0"]`
4. Change imports: `from pymelcloudhome import MELCloudHomeClient`

## References

- Home Assistant official integrations (MELCloud, Sensibo)
- NEXT-STEPS.md - Implementation approach section
- Research findings in planning phase (2025-11-16)

## Notes

Decision aligns with KISS/YAGNI:
- Start simple (bundled)
- Add complexity only when actually needed (separate package)
- Can always evolve later based on real usage

Most HA custom components start bundled and only separate the library when submitting to core or when community adoption requires it.
