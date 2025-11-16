# Next Steps for MELCloud Home Integration

## What's Done ✅

**API Discovery - COMPLETE**
- ✅ Captured complete authentication flow (OAuth + AWS Cognito)
- ✅ Documented all API endpoints
- ✅ Found device list endpoint: `GET /api/user/context`
- ✅ Found control endpoint: `PUT /api/ataunit/{unit_id}`
- ✅ Tested control (turned on Dining Room A/C)
- ✅ All documented in `melcloudhome-api-discovery.md`

## What's Next

### Option 1: Build Python API Client (Recommended First)

**Goal:** Create `pymelcloudhome` package for API access

**Steps:**
1. Create project structure:
   ```
   pymelcloudhome/
   ├── pyproject.toml
   ├── src/pymelcloudhome/
   │   ├── __init__.py
   │   ├── client.py      # Main client class
   │   ├── auth.py        # Authentication handling
   │   └── models.py      # Data models
   └── tests/
   ```

2. Implement `client.py`:
   - `async def login(username, password)` - Handle Cognito auth
   - `async def get_devices()` - Call `/api/user/context`
   - `async def set_power(unit_id, power)`
   - `async def set_temperature(unit_id, temp)`
   - `async def set_mode(unit_id, mode)`
   - Use session cookies (automatic with aiohttp)
   - Include proper User-Agent header

3. Test with real credentials from env vars:
   - `MELCLOUD_USER`
   - `MELCLOUD_PASSWORD`

**Reference:** See `melcloudhome-api-discovery.md` for exact API formats

---

### Option 2: Build HA Integration Directly

**Goal:** Create Home Assistant custom component

**Steps:**
1. Create structure:
   ```
   custom_components/melcloudhome/
   ├── manifest.json
   ├── __init__.py
   ├── config_flow.py
   ├── const.py
   ├── climate.py
   └── strings.json
   ```

2. Implement authentication in `config_flow.py`
   - Handle Cognito login (complex - may need to screen-scrape)
   - Store session cookies in config entry

3. Implement `climate.py`
   - Poll `/api/user/context` every 60s
   - Map API data to HA climate entity
   - Control via `PUT /api/ataunit/{id}`

**Reference:** See `melcloudhome-integration-guide.md` for HA patterns

---

## Recommended Approach: Python Client First

**Why:**
- Easier to test authentication independently
- Can validate API calls without HA complexity
- Reusable if building HACS integration later
- Can iterate faster

**Then:** Use the Python client in HA integration

---

## Key Implementation Details

### Authentication Challenges

**Problem:** AWS Cognito uses form-based login with device fingerprinting (`cognitoAsfData`)

**Solutions (pick one):**

1. **Screen-scraping** (easiest):
   - Use `playwright` or `selenium`
   - Navigate to login page
   - Fill form and submit
   - Extract session cookies
   - Pros: Works exactly like browser
   - Cons: Heavy dependency

2. **Reverse-engineer cognitoAsfData** (harder):
   - Analyze what data is sent
   - Generate fingerprint manually
   - Pros: Lighter weight
   - Cons: May break if Cognito changes

3. **Manual session** (simplest for testing):
   - Log in via browser
   - Copy cookies manually
   - Use for development/testing
   - Pros: Quick start
   - Cons: Not production-ready

### Required Headers

**All requests:**
```python
headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
}
```

**Control requests (PUT /api/ataunit):**
```python
headers = {
    "User-Agent": "...",
    "x-csrf": "1",
    "content-type": "application/json; charset=utf-8"
}
```

### Session Management

- Session expires in ~8 hours (check `bff:session_expires_in`)
- Cookies are HTTP-only (handled automatically by aiohttp)
- 401 response = need to re-authenticate

---

## Quick Start Command

**To continue where we left off:**

```bash
# Start building Python client
mkdir -p pymelcloudhome/src/pymelcloudhome
cd pymelcloudhome

# Create basic structure
touch pyproject.toml
touch src/pymelcloudhome/__init__.py
touch src/pymelcloudhome/client.py
touch src/pymelcloudhome/auth.py

# Start with client.py - copy examples from melcloudhome-api-discovery.md
```

---

## Files to Reference

1. **`melcloudhome-api-discovery.md`** - Complete API reference
   - All endpoints
   - Request/response formats
   - Authentication flow
   - Control examples

2. **`melcloudhome-integration-guide.md`** - HA patterns
   - Integration structure
   - Config flow examples
   - Climate entity patterns
   - Best practices

---

## Questions to Answer

Before starting, decide:

1. **Authentication approach?** (screen-scrape vs manual cookies for testing)
2. **Python client first or HA integration directly?**
3. **Publish to PyPI or keep local?**

---

## Estimated Time

- **Python client**: 2-4 hours
- **HA integration**: 3-5 hours
- **Total**: 5-9 hours

**KISS approach:** Start with Python client, test it works, then build HA integration using it.
