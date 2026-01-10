# Testing Best Practices for MELCloud Home Integration

This document outlines testing standards for the MELCloud Home integration, based on official Home Assistant and HACS guidelines.

**Last Updated:** 2025-11-27

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

## Integration Testing Standards

### ✅ CORRECT Approach

```python
"""Test climate entity behavior through Home Assistant core interfaces."""
from unittest.mock import AsyncMock, PropertyMock, patch

import pytest
from homeassistant.components.climate import HVACMode
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.melcloudhome.const import DOMAIN

# Mock path for API client (at boundary)
MOCK_CLIENT_PATH = "custom_components.melcloudhome.MELCloudHomeClient"


def create_mock_user_context():
    """Create mock API response data."""
    # Create mock Building/Unit objects matching API models
    # ... (use real model classes, mock data)
    pass


@pytest.mark.asyncio
async def test_climate_entity_reflects_device_state(hass: HomeAssistant) -> None:
    """Test that climate entity state matches device data."""
    # 1. Mock at API client level
    with patch(MOCK_CLIENT_PATH) as mock_client:
        client = mock_client.return_value
        client.login = AsyncMock()
        client.close = AsyncMock()
        client.get_user_context = AsyncMock(return_value=create_mock_user_context())
        type(client).is_authenticated = PropertyMock(return_value=True)

        # 2. Setup through core interface
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # 3. Assert state through hass.states ONLY
        state = hass.states.get("climate.melcloudhome_device_id")
        assert state is not None
        assert state.state == HVACMode.HEAT
        assert state.attributes["current_temperature"] == 20.0
        assert state.attributes["temperature"] == 21.0


@pytest.mark.asyncio
async def test_service_call_changes_state(hass: HomeAssistant) -> None:
    """Test that service calls update entity state."""
    with patch(MOCK_CLIENT_PATH) as mock_client:
        # ... setup as above ...

        # 4. Call service through hass.services
        await hass.services.async_call(
            "climate",
            "set_temperature",
            {"entity_id": "climate.melcloudhome_device_id", "temperature": 22.0},
            blocking=True,
        )

        # 5. Verify state changed (through hass.states)
        state = hass.states.get("climate.melcloudhome_device_id")
        assert state.attributes["temperature"] == 22.0

        # ✅ GOOD: Test observable behavior
        # ❌ BAD: Don't assert internal calls
        # coordinator.async_set_temperature.assert_called_once()  # DON'T DO THIS
```

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

### Fixture Patterns

**Shared setup fixture:**
```python
@pytest.fixture
async def setup_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the integration with mocked data."""
    mock_context = create_mock_user_context()

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        return entry


@pytest.mark.asyncio
async def test_with_shared_fixture(hass: HomeAssistant, setup_integration) -> None:
    """Test using shared setup fixture."""
    state = hass.states.get("climate.entity_id")
    assert state.state == HVACMode.HEAT
```

---

## API Testing Standards

### Using VCR Cassettes

```python
import pytest
from custom_components.melcloudhome.api.client import MELCloudHomeClient

@pytest.mark.vcr()  # Automatically records/replays API responses
@pytest.mark.asyncio
async def test_login_success() -> None:
    """Test successful login with real API response."""
    client = MELCloudHomeClient()
    await client.login("test@example.com", "password")

    assert client.is_authenticated
    assert client.auth.access_token is not None


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_401_unauthorized() -> None:
    """Test handling of 401 Unauthorized error."""
    client = MELCloudHomeClient()

    # Cassette contains 401 response
    with pytest.raises(AuthenticationError, match="Unauthorized"):
        await client.get_user_context()
```

**Cassette management:**
- Store in `tests/fixtures/vcr_cassettes/`
- Scrub sensitive data (see `tests/conftest.py`)
- Keep cassettes minimal (one request/response per test)
- Manually create cassettes for error scenarios if needed

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
# API tests (fast, no Docker needed)
make test                        # or: pytest tests/api/ -v

# Integration tests (in Docker - requires pytest-homeassistant-custom-component)
make test-ha

# Note: Integration tests run in Docker because pytest-homeassistant-custom-component
# has dependency conflicts with local dev environment (aiohttp version incompatibility).
# See tests/integration/Dockerfile for test environment setup.
```

### Docker Integration Test Details

**Why Docker?**
- `pytest-homeassistant-custom-component` requires Home Assistant
- HA requires aiohttp 3.8-3.11 (incompatible with our aiohttp >=3.13.2)
- Docker provides isolated environment with correct dependencies

**What happens when you run `make test-ha`:**
1. Builds Docker image from `tests/integration/Dockerfile` (Python 3.12 + HA test fixtures)
2. Mounts repository as `/app` in container
3. Runs pytest from `tests/integration/` directory (treats it as root for pytest_plugins)
4. Outputs results to terminal

**Manual Docker commands:**
```bash
# Build test image
docker build -t melcloudhome-test:latest -f tests/integration/Dockerfile .

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

### Example Tests (Study These)

- **HA Core climate tests:** `homeassistant/tests/components/demo/test_climate.py`
- **Platinum integrations:** Philips Hue, deCONZ, National Weather Service
- **This project:**
  - ✅ `tests/integration/test_init.py` - Excellent integration test patterns
  - ✅ `tests/integration/test_config_flow.py` - Config flow testing
  - ✅ `tests/api/test_auth.py` - API testing with VCR

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

1. Check this document first
2. Study examples in `tests/integration/test_init.py`
3. Review HA core tests for similar features
4. Ask: "Am I testing observable user behavior, or internal implementation?"

**Rule of thumb:** If your test would break when refactoring the coordinator but the integration still works for users, you're testing the wrong thing.
