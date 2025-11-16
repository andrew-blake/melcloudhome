# MELCloud Home Integration

Home Assistant custom component for Mitsubishi Electric MELCloud Home air conditioning systems.

## Status

🚧 **In Development** - Core API client foundation complete (~87% API coverage)

**Completed:**
- ✅ API discovery and documentation
- ✅ OpenAPI 3.0 specification
- ✅ Bundled API client (const, exceptions, models)
- ✅ Development environment (ruff, mypy, pre-commit)

**In Progress:**
- 🔄 API client implementation (auth, client)
- 🔄 Home Assistant integration (climate entity)

**Deferred:**
- ⏸️ Scenes API (v2.0)

## Project Structure

```
custom_components/melcloudhome/  # HA custom component
├── api/                         # Bundled API client
│   ├── const.py                 # API constants & enums
│   ├── exceptions.py            # Custom exceptions
│   ├── models.py                # Data models
│   ├── auth.py                  # OAuth authentication (TODO)
│   └── client.py                # Main API client (TODO)
├── manifest.json                # Integration metadata (TODO)
├── climate.py                   # Climate entity (TODO)
└── ...

_claude/                         # API documentation
openapi.yaml                     # OpenAPI specification
```

## Development

**Setup:**
```bash
uv sync                          # Install dependencies
source .venv/bin/activate        # Activate venv
pre-commit install               # Install git hooks
```

**Commands:**
```bash
make format                      # Format code
make lint                        # Run linter
make type-check                  # Type checking
make all                         # Run all checks
```

**API Documentation:**
```bash
# View OpenAPI spec with Scalar UI
open http://localhost:8080/scalar-docs.html
```

## Architecture

**Approach:** Bundled API client (KISS/YAGNI)
- API client bundled in `custom_components/melcloudhome/api/`
- No separate PyPI package (can migrate later if needed)
- Single folder deployment
- Fast iteration

See [ADR-001](docs/decisions/001-bundled-api-client.md) for decision rationale.

## Resources

- **API Docs:** `_claude/` directory
- **OpenAPI Spec:** `openapi.yaml`
- **Pre-commit:** `.pre-commit-config.yaml`
- **Linting:** `pyproject.toml` (ruff, mypy)

## License

See LICENSE file.
