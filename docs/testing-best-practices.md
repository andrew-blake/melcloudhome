# Testing Best Practices for MELCloud Home Integration

This document outlines testing standards for the MELCloud Home integration, based on official Home Assistant and HACS guidelines.

**Last Updated:** 2026-01-23

---

## Table of Contents

- [Core Principles](#core-principles)
- [Test Categories](#test-categories)
- [Integration Testing Standards](#integration-testing-standards)
- [API Testing Standards](#api-testing-standards)
- [Common Pitfalls](#common-pitfalls)
- [Running Tests](#running-tests)
- [References](#references)

---

## Core Principles

### Official Home Assistant Guidance

> **"Make sure to not interact with any integration details in tests of integrations. Following this pattern will make the tests more robust for changes in the integration."**
>
> — [Home Assistant Developer Docs](https://developers.home-assistant.io/docs/development_testing/)

### Key Testing Principles

1. **Test through stable interfaces** - Use `hass.states` and `hass.services` exclusively for integration tests
2. **Mock at boundaries** - Mock external APIs (client), not internal logic (coordinator, entities)
3. **Assert on observable behavior** - Check state machine results, not internal method calls
4. **Setup through core** - Use `async_setup_component` or `hass.config_entries.async_setup`
5. **Test real scenarios** - Focus on user-facing behavior, not implementation details

---

## Test Categories

### 1. Integration Tests (`tests/integration/`)

**Purpose:** Test user-facing behavior of the integration within Home Assistant

**What to test:**
- Entity state reflects device data correctly
- Service calls change entity state as expected
- Config flow accepts valid/invalid credentials
- Integration setup/teardown works correctly
- Device discovery and dynamic updates

**Rules:**
- ✅ Test through `hass.states` and `hass.services` ONLY
- ✅ Mock `MELCloudHomeClient` at API boundary
- ✅ Use `hass.config_entries.async_setup()` for setup
- ❌ Never import or test internal classes (coordinator, entity classes)
- ❌ Never assert coordinator/entity methods were called
- ❌ Never manipulate `coordinator.data` directly

### 2. API Tests (`tests/api/`)

**Purpose:** Test the MELCloud Home API client in isolation

**What to test:**
- Authentication flows (login, token refresh, session expiry)
- API request/response handling
- Error handling (401, 500, timeouts, malformed responses)
- Data normalization (fan speeds, vane positions, temperatures)
- Edge cases (empty responses, missing fields)

**Rules:**
- ✅ Use VCR cassettes for real API responses (`@pytest.mark.vcr()`)
- ✅ Test client methods directly
- ✅ Create cassettes for error scenarios
- ✅ Scrub sensitive data (credentials, tokens)

### 3. Unit Tests (`tests/integration/test_coordinator_retry.py`, etc.)

**Purpose:** Test internal component logic in isolation

**What to test:**
- Coordinator retry logic
- Session expiry recovery
- Debouncing algorithms
- Deduplication logic

**Rules:**
- ✅ Can test private methods and internal state
- ✅ Can assert on method calls and implementation details
- ✅ Create component instances directly
- ⚠️ Label files clearly (e.g., `test_coordinator_*.py`)

---

## Test Architecture

### Separation of Concerns

Integration and E2E tests run in separate Docker services due to conflicting infrastructure needs:

- **Integration tests** run WITH pytest-homeassistant-custom-component
  - Includes pytest-socket (blocks network access for safety)
  - Tests Home Assistant integration logic
  - Validates entity behavior through `hass.states` and `hass.services`

- **E2E tests** run WITHOUT pytest-homeassistant
  - Real network access to mock server
  - Tests full HTTP stack (DNS, TCP, HTTP request/response)
  - Validates rate limiting enforcement with RequestPacer

See `docker-compose.test.yml` for implementation details.

---

## Integration Testing Standards

### Working Examples

**Study these test files for correct patterns:**

- **ATA (Air-to-Air) devices:** `tests/integration/test_climate_ata.py`
  - Complete fixture setup with shared helpers
  - ATA-specific device mocking (`mock_client.ata.*`)
  - Entity state validation through `hass.states`
  - Service call testing through `hass.services`

- **ATW (Air-to-Water) devices:** `tests/integration/test_climate_atw.py`
  - ATW-specific device mocking (`mock_client.atw.*`)
  - Multi-zone climate entity patterns
  - Water heater entity integration

- **Shared fixtures:** `tests/integration/conftest.py`
  - Helper functions: `create_mock_atw_unit()`, `create_mock_user_context()`
  - Reusable test constants
  - Common mocking patterns

### Key Pattern Summary

The tests follow this consistent pattern:

1. **Mock at API boundary** - `MELCloudHomeClient`, not coordinator
2. **Setup through core** - `hass.config_entries.async_setup()`
3. **Assert through interfaces** - `hass.states.get()` and `hass.services.async_call()`
4. **Never test internals** - No coordinator/entity imports or method assertions

See the actual test files for complete, working implementations.

### ❌ WRONG Approach (DO NOT DO THIS)

```python
"""ANTI-PATTERN: Testing internal implementation details."""
from custom_components.melcloudhome.coordinator import MELCloudHomeCoordinator
from custom_components.melcloudhome.climate import MELCloudHomeClimate

@pytest.mark.asyncio
async def test_climate_calls_coordinator(hass: HomeAssistant) -> None:
    """DON'T DO THIS: Testing internal method calls."""
    # ❌ Importing internal classes
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    # ❌ Mocking coordinator methods
    coordinator.async_set_temperature = AsyncMock()

    # Service call...
    await hass.services.async_call(...)

    # ❌ Asserting internal method calls
    coordinator.async_set_temperature.assert_called_once_with("device_id", 22.0)

    # ❌ Directly manipulating coordinator data
    coordinator.data = create_mock_user_context(...)
    coordinator.async_set_updated_data(coordinator.data)
```

**Why this is wrong:**
- Tests break when coordinator is refactored (even if behavior unchanged)
- Tests pass but integration could still be broken for users
- Violates HA's core testing principle
- Creates maintenance burden

---

## API Testing Standards

### Working Examples

**Study these test files for API testing patterns:**

- **Authentication:** `tests/api/test_auth.py`
  - VCR cassette usage with `@pytest.mark.vcr()`
  - Login flows, token refresh, session expiry
  - Error handling (401, 500, timeouts)

- **Device control:** `tests/api/test_client_ata.py`, `tests/api/test_client_atw.py`
  - ATA/ATW device-specific API calls
  - Request/response validation
  - Data normalization tests

- **Cassette configuration:** `tests/conftest.py`
  - VCR settings (cassette storage, scrubbing)
  - Sensitive data filtering
  - Recording modes

### Key Patterns

- Use `@pytest.mark.vcr()` to record/replay real API responses
- Store cassettes in `tests/fixtures/vcr_cassettes/`
- Scrub credentials and tokens (see conftest.py)
- Test client methods directly (no Home Assistant mocking needed)

---

## Common Pitfalls

### ❌ Pitfall 1: Mocking Too Deep

```python
# ❌ WRONG: Mocking internal coordinator
coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
coordinator.async_set_power = AsyncMock()

# ✅ CORRECT: Mock at API boundary
with patch(MOCK_CLIENT_PATH) as mock_client:
    mock_client.return_value.set_power = AsyncMock()
```

### ❌ Pitfall 2: Asserting Internal Calls

```python
# ❌ WRONG: Asserting coordinator methods
coordinator.async_set_temperature.assert_called_once()

# ✅ CORRECT: Assert observable state
state = hass.states.get("climate.entity_id")
assert state.attributes["temperature"] == 22.0
```

### ❌ Pitfall 3: Accessing Integration Internals

```python
# ❌ WRONG: Importing internal classes
from custom_components.melcloudhome.climate import MELCloudHomeClimate
entity = MELCloudHomeClimate(coordinator, unit, building, entry)

# ✅ CORRECT: Test through state machine
state = hass.states.get("climate.entity_id")
```

### ❌ Pitfall 4: Testing Implementation, Not Behavior

```python
# ❌ WRONG: Testing that cache is used
assert coordinator._last_call_time is not None

# ✅ CORRECT: Testing deduplication behavior
await set_temperature(20.0)  # First call
await set_temperature(20.0)  # Duplicate
# Verify API only called once via cassette or mock
```

---

## Running Tests

### Run All Tests

```bash
# API unit tests (native, fast)
make test-api

# Integration tests only
make test-integration

# E2E tests only
make test-e2e

# All tests with combined coverage
make test

# Note: Integration and E2E tests run in separate Docker services.
# See docker-compose.test.yml for test environment setup.
```

### Docker Compose Test Details

**Why Docker Compose?**
- `pytest-homeassistant-custom-component` requires Home Assistant
- HA requires aiohttp 3.8-3.11 (incompatible with our aiohttp >=3.13.2)
- E2E tests need mock MELCloud server with rate limiting
- Docker Compose provides isolated environment with both services

**What happens when you run `make test`:**
1. Runs API unit tests natively (creates `.coverage` file)
2. Starts mock MELCloud server (with rate limiting enabled)
3. Runs integration-tests service (WITH pytest-homeassistant, appends to `.coverage`)
4. Runs e2e-tests service (WITHOUT pytest-homeassistant, appends to `.coverage`, generates final reports)
5. Tears down containers

**Manual Docker commands:**
```bash
# Build test image
docker build -t melcloudhome-test:latest -f Dockerfile.test .

# Run integration tests
docker run --rm -v $(PWD):/app melcloudhome-test:latest

# Run specific test file
docker run --rm -v $(PWD):/app melcloudhome-test:latest pytest test_climate.py -v

# Run specific test
docker run --rm -v $(PWD):/app melcloudhome-test:latest pytest test_climate.py::test_name -vv
```

### Run with Coverage

```bash
# API coverage only (local)
pytest tests/api/ --cov=custom_components.melcloudhome.api --cov-report term-missing -vv

# Integration coverage (in Docker)
docker run --rm -v $(PWD):/app melcloudhome-test:latest \
  pytest . --cov=custom_components.melcloudhome --cov-report term-missing -vv
```

### Update VCR Cassettes

```bash
# Re-record all cassettes (requires real API credentials in .env)
pytest tests/api/ --vcr-record=all
```

### Snapshot Testing

```bash
# Update snapshots (for entity state dumps, JSON responses)
pytest tests/ --snapshot-update
```

---

## HACS Quality Standards

When publishing to HACS, ensure:

### Required Files

- `manifest.json` with keys: `domain`, `documentation`, `issue_tracker`, `codeowners`, `name`, `version`
- Comprehensive `README.md`
- `hacs.json` for HACS-specific configuration
- GitHub releases for version management

### Best Practices

- Register with [home-assistant/brands](https://github.com/home-assistant/brands) for UI compliance
- Follow semantic versioning
- Provide clear installation instructions
- Document breaking changes in releases

---

## References

### Official Documentation

- [Home Assistant: Testing your code](https://developers.home-assistant.io/docs/development_testing/)
- [Home Assistant: Creating a custom integration](https://developers.home-assistant.io/docs/creating_integration_manifest)
- [HACS: Integration requirements](https://www.hacs.xyz/docs/publish/integration/)
- [HACS: Publishing standards](https://www.hacs.xyz/docs/publish/start/)

### Community Resources

- [Building a HA Custom Component Part 2: Unit Testing and CI](https://aarongodfrey.dev/home%20automation/building_a_home_assistant_custom_component_part_2/)
- [pytest-homeassistant-custom-component](https://github.com/MatthewFlamm/pytest-homeassistant-custom-component)
- [HA Community: Best practices for custom components](https://community.home-assistant.io/t/best-practices-to-develop-and-maintain-a-custom-component/339295)

### Working Examples in This Project

**Primary references** - these are the source of truth:

**Integration Tests:**
- `tests/integration/test_climate_ata.py` - ATA device testing patterns
- `tests/integration/test_climate_atw.py` - ATW device testing patterns
- `tests/integration/test_config_flow.py` - Config flow validation
- `tests/integration/test_init.py` - Integration setup/teardown
- `tests/integration/conftest.py` - Shared fixtures and helpers

**API Tests:**
- `tests/api/test_auth.py` - Authentication with VCR cassettes
- `tests/api/test_client_ata.py` - ATA device control
- `tests/api/test_client_atw.py` - ATW device control

**External References:**
- **HA Core:** `homeassistant/tests/components/demo/test_climate.py`
- **Platinum integrations:** Philips Hue, deCONZ, National Weather Service

---

## Quick Reference Checklist

Before submitting a PR with new tests:

- [ ] Integration tests mock at API client boundary ONLY
- [ ] Integration tests use `hass.states` and `hass.services` exclusively
- [ ] No assertions on internal coordinator/entity method calls
- [ ] No direct imports of internal classes (coordinator, entity classes)
- [ ] API tests use VCR cassettes or appropriate mocks
- [ ] Tests follow naming convention: `test_<feature>_<scenario>`
- [ ] Tests include docstrings explaining what's being tested
- [ ] All tests pass: `make test`
- [ ] Coverage improved: `pytest tests/ --cov=custom_components.melcloudhome --cov-report term-missing`
- [ ] No new pylint/mypy errors: `make all`

---

## Questions?

If unsure about testing approach:

1. **Study working tests first** - See files listed in References section above
2. **Check principles** - Review this document for patterns and anti-patterns
3. **Review HA core** - Look at similar features in `homeassistant/tests/`
4. **Ask yourself** - "Am I testing observable user behavior, or internal implementation?"

**Rule of thumb:** If your test would break when refactoring the coordinator but the integration still works for users, you're testing the wrong thing.

**Don't duplicate** - Tests are the single source of truth for implementation patterns. This document explains the "why", tests show the "how".
