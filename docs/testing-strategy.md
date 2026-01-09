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

## Proper Testing Approaches for HA Integrations

### Approach 1: **API Layer Testing** (Our Choice) ✅

**What we test:**
- ✅ Complete API client functionality (82 tests)
- ✅ All CRUD operations with real API (via VCR)
- ✅ Error handling and edge cases
- ✅ Data model parsing and validation

**Why this works:**
- Tests the actual integration logic
- Uses real API responses (recorded)
- Fast (VCR replay)
- No HA dependency needed

**Example:**
```python
# tests/test_client_control.py
@pytest.mark.vcr
async def test_set_temperature(authenticated_client):
    """Test setting temperature."""
    await authenticated_client.set_temperature("unit-id", 22.0)
    device = await authenticated_client.get_device("unit-id")
    assert device.set_temperature == 22.0
```

**Coverage:** 82% of integration code

### Approach 2: **Manual Testing in Real HA** ✅

**Our deployment tool enables this:**
```bash
# Fast deploy and test cycle
make deploy-test
```

**What we test:**
- ✅ Integration loads correctly
- ✅ Config flow works
- ✅ Entities appear in HA
- ✅ Controls work in UI
- ✅ State updates correctly

**Manual test checklist:**
- Configuration → Integrations → Add Integration
- Verify all devices discovered
- Test power on/off
- Test temperature changes
- Test all HVAC modes
- Test fan speeds and swing modes
- Verify 60s polling works
- Test error recovery

### Approach 3: **pytest-homeassistant-custom-component** (Future)

**When to use:**
- Publishing to HACS
- Multiple contributors
- Need CI/CD integration

**Requirements:**
- Python 3.13+
- homeassistant package
- Complex dependency resolution

**Example:**
```python
async def test_config_flow(hass):
    """Test config flow with real HA fixtures."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"
```

**Why we're NOT using it:**
- Dependency conflicts
- Overkill for personal use
- Manual testing is sufficient

### Approach 4: **Home Assistant Test Framework** (Core Only)

For integrations being added to HA core.

**Not applicable** for custom components.

---

## Our Complete Testing Strategy

### Layer 1: Unit Tests (API Client) ✅
- **Tool:** pytest + VCR
- **What:** All API operations
- **Coverage:** 82%
- **Speed:** Fast (12s with VCR)
- **Status:** Comprehensive

### Layer 2: Integration Tests (Manual) ✅
- **Tool:** deploy_custom_component.py + HA UI
- **What:** Real HA integration behavior
- **Coverage:** All user-facing features
- **Speed:** 2-5s with --reload
- **Status:** Manual checklist provided

### Layer 3: Code Quality ✅
- **Tools:** ruff, mypy, pre-commit
- **What:** Type safety, linting, formatting
- **Coverage:** 100% of code
- **Status:** All passing

---

## Testing Workflow

### During Development:
```bash
# 1. Write/modify code
vim custom_components/melcloudhome/climate.py

# 2. Run API tests
uv run pytest tests/

# 3. Run quality checks
uv run ruff check custom_components/
uv run mypy custom_components/melcloudhome

# 4. Deploy and test
make deploy-test

# 5. Manual verification in HA UI
```

### Before Commit:
```bash
# Pre-commit hooks run automatically
git commit -m "..."
# Runs: ruff, mypy, formatting, etc.
```

### Before Release:
```bash
# 1. Full test suite
uv run pytest tests/ --cov

# 2. Full deployment test
make deploy

# 3. Manual testing checklist
# See local development notes

# 4. Monitor logs
make deploy-watch
```

---

## Best Practices for HA Custom Components

### ✅ DO:
- Test API/business logic comprehensively
- Use VCR for API testing
- Test in real Home Assistant
- Use deployment automation
- Follow HA architecture patterns
- Run code quality tools

### ❌ DON'T:
- Mock homeassistant modules
- Skip testing in real HA
- Test only happy paths
- Ignore type checking
- Skip manual verification

---

## Why This Approach Works

1. **API tests** ensure core functionality is correct
2. **Real HA testing** verifies integration points
3. **Fast deployment** enables rapid iteration
4. **No mocking issues** from complex HA internals
5. **Type safety** catches errors at development time

**Result:** High confidence in integration quality without complex test infrastructure

---

## Future Improvements (v1.1+)

If publishing to HACS or adding collaborators:

1. Set up Python 3.13 environment
2. Install pytest-homeassistant-custom-component
3. Add HA integration tests with real fixtures
4. Set up CI/CD pipeline

**For now:** Current approach is excellent for personal use and development.
