# Contributing to MELCloud Home

Contributions are welcome, whether you're reporting bugs, proposing features, or submitting code changes.

## How to Contribute

### Reporting Bugs

Report bugs by [opening a new issue](https://github.com/andrew-blake/melcloudhome/issues/new).

**Security vulnerabilities:** Please follow the process in [SECURITY.md](SECURITY.md) instead of opening a public issue.

**Good bug reports include:**

- Summary and background
- Specific steps to reproduce
- What you expected vs what actually happened
- Diagnostics export from Home Assistant if relevant
- Notes on what you've tried

### Proposing Features

Open an issue to discuss new features before starting work. This helps ensure the feature aligns with the project's goals and avoids duplicate effort.

### Submitting Code

1. Fork the repository
2. Create a feature branch from `main` (we use GitHub Flow)
3. Make your changes
4. Run tests and code quality checks
5. Submit a pull request

**Branch naming:**

- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation

## Development Setup

**Prerequisites:**

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager
- Docker (for Home Assistant integration tests)

**Setup:**

```bash
# Install dependencies
uv sync

# Install pre-commit hooks
uv run pre-commit install

# Run all checks
make all
```

## Testing Requirements

All code changes require tests. See [docs/testing-best-practices.md](docs/testing-best-practices.md) for guidelines.

**Test your changes:**

```bash
make test-api          # API unit tests (native, fast)
make test              # Integration + E2E tests (Docker Compose)
make test-ci           # Complete test suite with coverage (for PRs)
```

**Integration tests:**

- Run in Docker container with Home Assistant dependencies
- Must follow HA testing patterns (see docs/testing-best-practices.md):
  - Test through `hass.states` and `hass.services` interfaces only
  - Mock the API client at the boundary
  - Never test internal coordinator implementation directly

**API tests with VCR cassettes:**

- API tests use pytest-recording to record/replay HTTP interactions
- Cassettes stored in `tests/api/cassettes/`
- Most tests work without real credentials (use existing cassettes)
- To record new cassettes: Set `MELCLOUD_USER` and `MELCLOUD_PASSWORD` environment variables
- **Note:** Be careful not to commit credentials in cassettes (library sanitises automatically)

## Code Quality Standards

**Linting and formatting:**

- Ruff (formatting and linting)
- mypy (type checking with strict mode)
- Pre-commit hooks (run automatically on commit)

**Commands:**

```bash
make format        # Auto-format code
make lint          # Check for issues
make type-check    # Type checking
```

**Code coverage:**

- Minimum 70% patch coverage for PRs
- Codecov reports coverage on all pull requests
- Focus on testing public interfaces and integration points

## Pull Request Process

1. Ensure all tests pass locally (`make all`)
2. Update documentation if you've changed functionality
3. CHANGELOG.md updates are not required (maintainer handles releases)
4. PRs must pass all CI checks:
   - Ruff formatting and linting
   - mypy type checking
   - API tests
   - Home Assistant integration tests
   - Code coverage (70% minimum for changed code)
   - HACS and Hassfest validation

**Commit messages:**

Use conventional commits format:

- `feat:` - New features
- `fix:` - Bug fixes
- `docs:` - Documentation changes
- `test:` - Test additions or changes
- `refactor:` - Code refactoring
- `chore:` - Maintenance tasks

Example: `feat: Add support for ATW heat pump devices`

## Documentation

**Key documentation:**

- **openapi.yaml** - Complete API specification (OpenAPI 3.0.3)
- **docs/api/** - API reference and endpoint documentation
- **docs/decisions/** - Architecture Decision Records (ADRs)
- **docs/research/** - Reverse engineering notes and findings
- **docs/testing-best-practices.md** - Home Assistant testing guidelines

ADRs document significant architectural decisions and their rationale. When making major architectural changes, consider adding an ADR.

## API Discovery and Reverse Engineering

The MELCloud Home API was reverse engineered by observing the official web application. This enables contributing device support without owning the hardware.

### Reverse Engineering Tools

**We provide specialized tools** for understanding API behavior without real devices:

- **Chrome Local Overrides** - Inject captured API data into official web app
- **Request Proxying** - Capture control commands without affecting real hardware
- **Mock Server** - Simulate API responses for local testing

**Full guide:** [tools/reverse-engineering/README.md](tools/reverse-engineering/README.md) and [docs/research/REVERSE_ENGINEERING.md](docs/research/REVERSE_ENGINEERING.md)

### Contributing Without Hardware

**You can help add device support even if you don't own the device:**

1. User reports unsupported device (e.g., different Ecodan model)
2. They capture HAR file from https://melcloudhome.com
3. You use Chrome Local Overrides to inject that data
4. Observe official web app behavior
5. Document API structure and mappings
6. Implement integration support

**See:** [Workflow 1 in REVERSE_ENGINEERING.md](docs/research/REVERSE_ENGINEERING.md#workflow-1-add-support-for-user-reported-device)

### Adding New Device Types

If you're adding support for new device types (e.g., ERV ventilators):

1. Capture HAR from official web app
2. Use reverse engineering tools to understand API
3. Document request/response patterns
4. Update openapi.yaml with new endpoints
5. Implement corresponding client methods
6. Add tests with VCR cassettes

**Tools:**
- Chrome DevTools + Local Overrides
- Mock server for testing
- pytest-recording (VCR) for API tests

The openapi.yaml specification serves as the authoritative API reference. Update it when adding new endpoints.

## Adding Device Support

If you've tested the integration with hardware not listed in [SUPPORTED_DEVICES.md](SUPPORTED_DEVICES.md), please submit a PR with:

- Indoor unit model number
- WiFi adapter model
- Configuration notes (single-split, multi-split, etc.)
- Any quirks or limitations observed

**For new device types (ATW, ERV):**

- Document API endpoints used (update openapi.yaml)
- Add corresponding data models:
  - Shared models: `api/models.py` (Building, UserContext, etc.)
  - Device-specific: `api/models_ata.py` or `api/models_atw.py`
- Implement platform files (e.g., water_heater.py for ATW)
- Add integration tests
- Update SUPPORTED_DEVICES.md

## License

By contributing, you agree that your contributions will be licensed under the MIT Licence.

## Questions?

Open an issue or discussion if you have questions about contributing.
