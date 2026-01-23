# Testing Strategy for Home Assistant Custom Integrations

## The Problem with Mocking Home Assistant

**Why NOT to mock homeassistant modules:**

### 1. **Metaclass Conflicts**
```python
# This WILL fail:
sys.modules["homeassistant"] = MagicMock()
class MyEntity(CoordinatorEntity, ClimateEntity):  # TypeError: metaclass conflict
```

Home Assistant entities use complex metaclasses that can't be properly mocked with MagicMock.

### 2. **False Positives**
- Tests pass but integration fails in real HA
- Mocks don't match actual HA API behavior
- Miss HA-specific validation and error cases

### 3. **Maintenance Burden**
- HA APIs change frequently
- Mocks become outdated
- More effort to maintain than actual tests

### 4. **Doesn't Test Integration Points**
- Coordinator interaction with HA core
- Entity registry integration
- Device registry integration
- Config flow integration

**Verdict:** ❌ **Don't mock homeassistant - it's bad practice**

---

## Our Two-Tier Testing Strategy

### Tier 1: **API Layer Testing** (Native Python) ✅

**What we test:**
- ✅ Complete API client functionality (82 tests)
- ✅ All CRUD operations with real API (via VCR)
- ✅ Error handling and edge cases
- ✅ Data model parsing and validation

**How it works:**
- Tests the API client without any Home Assistant dependency
- Uses real API responses (recorded with VCR cassettes)
- Fast execution (~12s with VCR replay)
- No Docker required

**Example:**
```python
# tests/api/test_client_control.py
@pytest.mark.vcr
async def test_set_temperature(authenticated_client):
    """Test setting temperature."""
    await authenticated_client.set_temperature("unit-id", 22.0)
    device = await authenticated_client.get_device("unit-id")
    assert device.set_temperature == 22.0
```

**Run with:** `make test-api` or `pytest tests/api/ -v -m "not e2e"`

**Coverage:** 82% of API client code

---

### Tier 2: **Home Assistant Integration Testing** (Docker) ✅

**What we test:**
- ✅ Integration setup and teardown
- ✅ Config flow (user authentication, options)
- ✅ Entity registration and lifecycle
- ✅ State management through HA core
- ✅ Service calls (climate controls, water heater)
- ✅ Coordinator updates and error handling

**How it works:**
- Uses `pytest-homeassistant-custom-component` framework
- Runs in Docker container with clean HA environment
- Provides real HA fixtures (`hass`, `hass_client`, etc.)
- Mocks API client at the boundary (not HA internals)
- Tests through HA core interfaces (states, services)

**Why Docker:**
- `pytest-homeassistant-custom-component` has dependency conflicts with project dependencies
- Requires specific HA environment and fixtures
- Docker provides isolation and reproducibility
- Matches CI/CD environment

**Example:**
```python
# tests/integration/test_climate_ata.py
async def test_set_temperature(hass, setup_integration):
    """Test setting temperature through HA service."""
    state = hass.states.get("climate.melcloudhome_test_unit")
    assert state.state == HVACMode.HEAT

    await hass.services.async_call(
        "climate", "set_temperature",
        {"entity_id": "climate.melcloudhome_test_unit", "temperature": 22},
        blocking=True
    )

    state = hass.states.get("climate.melcloudhome_test_unit")
    assert state.attributes["temperature"] == 22
```

**Run with:** `make test` (Docker Compose with mock server and HA integration tests)

**Test structure:**
- `tests/integration/` - HA integration tests
- `tests/integration/Dockerfile` - Test environment
- Tests execute from `tests/integration/` directory to load pytest_plugins correctly

**Coverage:** Config flow, entity platforms, coordinator, service calls

---

### Tier 3: **Manual Testing** (Production HA) ✅

**When to use:**
- Final verification before release
- Testing with real MELCloud account
- UI/UX validation
- Long-running stability tests

**Our deployment tool:**
```bash
make deploy-test  # Deploy + API verification
make deploy-watch # Deploy + live log monitoring
```

**Manual test checklist:**
- Configuration → Integrations → Add Integration
- Verify all devices discovered
- Test power on/off
- Test temperature changes
- Test all HVAC modes
- Test fan speeds and swing modes
- Verify 60s polling works
- Test error recovery

**Note:** Use sparingly - Docker integration tests cover most scenarios.

---

## Complete Testing Stack

### 1. API Tests (Native Python) ✅
- **Tool:** pytest + VCR
- **What:** API client operations, models, error handling
- **Coverage:** 82% of API client code
- **Speed:** ~12 seconds
- **Command:** `make test-api`

### 2. Integration Tests (Docker) ✅
- **Tool:** pytest-homeassistant-custom-component
- **What:** HA integration, config flow, entities, services
- **Coverage:** Config flow, coordinator, entity platforms
- **Speed:** ~30 seconds (includes Docker build cache)
- **Command:** `make test`

### 3. Code Quality ✅
- **Tools:** ruff, mypy, pre-commit
- **What:** Type safety, linting, formatting
- **Coverage:** 100% of code
- **Status:** All passing

### 4. Manual Verification (Production HA) ✅
- **Tool:** Deployment scripts + real HA instance
- **What:** Final verification, UI/UX, real MELCloud API
- **When:** Pre-release only
- **Command:** `make deploy-test`

---

## Testing Workflow

### During Development:
```bash
# 1. Write/modify code
vim custom_components/melcloudhome/climate.py

# 2. Run API tests (fast)
make test-api

# 3. Run integration tests (if touching HA integration code)
make test

# 4. Run quality checks
make lint
make type-check

# 5. Optional: Deploy to dev environment for manual testing
make dev-up        # Start local dev environment
make dev-restart   # Reload after changes
```

### Before Commit:
```bash
# Pre-commit hooks run automatically
git commit -m "..."
# Runs: ruff format, ruff check, mypy, etc.

# Or run manually:
make pre-commit
```

### Before Release:
```bash
# 1. Full test suite
make test-api  # API unit tests (fast)
make test      # All tests with combined coverage

# 2. All quality checks
make all       # format, lint, type-check

# 3. Optional: Deploy to production HA for final verification
make deploy-test

# 4. Monitor logs
make deploy-watch
```

---

## Best Practices for HA Custom Components

### ✅ DO:
- Test API/business logic comprehensively with VCR
- Test HA integration through `hass.states` and `hass.services` interfaces
- Mock at the API boundary (not HA internals)
- Use Docker for HA integration tests to avoid dependency conflicts
- Run both API and integration test suites before releases
- Follow HA architecture patterns (coordinator, entities)
- Use code quality tools (ruff, mypy)

### ❌ DON'T:
- Mock homeassistant modules or core classes
- Test coordinator/entity internals directly
- Skip integration tests for HA-specific code
- Test only happy paths
- Ignore type checking
- Manipulate coordinator.data directly in tests

---

## Why This Approach Works

1. **API tests** ensure client functionality is correct (fast feedback)
2. **Integration tests** verify HA integration points (real fixtures)
3. **Docker isolation** avoids dependency hell
4. **No HA mocking** prevents false positives from complex internals
5. **Type safety** catches errors at development time
6. **Local dev environment** enables rapid iteration

**Result:** High confidence in integration quality with comprehensive test coverage

---

## Architecture Decision

This testing strategy reflects **ADR-012: Docker-Based Integration Testing**.

**Key decision:** Use Docker containers for HA integration tests instead of installing pytest-homeassistant-custom-component locally, avoiding dependency conflicts while maintaining comprehensive test coverage.

See `docs/decisions/012-docker-integration-tests.md` for full rationale.
