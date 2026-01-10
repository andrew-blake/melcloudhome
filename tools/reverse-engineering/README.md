# API Reverse Engineering Tools

Tools for understanding MELCloud Home API behavior by observing the official web application.

## Purpose

**Capture and understand API responses without needing physical hardware.**

These tools enable:
- Contributing device support when you don't own the device
- Understanding official API behavior from web client observations
- Testing integration behavior with captured real-world data
- Documenting undocumented API fields and values

## Tools

### 1. Chrome Local Overrides

**Inject captured API responses into the official web app.**

**Why:** See how the official web app behaves with specific device data (e.g., user's ATW heat pump) without owning that hardware.

**Setup:**
1. Chrome DevTools (F12) → **Sources** → **Overrides**
2. Select folder: `tools/reverse-engineering/chrome_override`
3. Allow access when prompted

**Usage:**
1. Get API response data from real HAR capture (user-provided)
2. Extract `/api/user/context` response from HAR
3. Paste into `chrome_override/melcloudhome.com/api/user/context`
4. Visit https://melcloudhome.com
5. **Login with YOUR real credentials** (auth is real, only context is overridden)
6. Web app loads the captured device data instead of your devices
7. Observe and document behavior (UI display, controls, labels, capabilities)

> **Important:**
> - Override data MUST come from real HAR recordings, not fabricated data.
> - You login with your real credentials, but `/api/user/context` is replaced with captured data.
> - This lets you see how the web app behaves with devices you don't own.

### 2. Request Proxying

**Capture API mutation payloads from the official web app.**

**Why:** Understand exact API request format for control commands without affecting real hardware.

**Setup:**
1. Start mock server: `make dev-up` (from repo root)
2. Chrome console on https://melcloudhome.com
3. Paste contents of `proxy_mutations.js`
4. Run: `blockMutations()`

**Usage:**
- Use official web app controls (change temperature, modes, etc.)
- POST/PUT/DELETE requests → logged and sent to mock server
- Web app receives fake 200 success
- Check console/mock server logs for captured payloads
- Run `unblockMutations()` when done

### 3. Mock Server

**Simulate MELCloud API locally for integration testing.**

**Why:** Test integration with various device configurations without real hardware.

**Setup:**
```bash
make dev-up
# Home Assistant: http://localhost:8123 (dev/dev)
# Mock API: http://localhost:8080
```

**Customize:** Edit `tools/mock_melcloud_server.py` to simulate different device types, API values, capabilities.

## Workflows

### Contribute ATW Device Support (No Hardware Required)

**Scenario:** User reports they have an unsupported Ecodan heat pump.

**Steps:**
1. Ask user to capture HAR file from https://melcloudhome.com (see HAR capture guide below)
2. User anonymizes and shares HAR
3. Extract `/api/user/context` response from their HAR
4. Paste into `chrome_override/melcloudhome.com/api/user/context`
5. Use Chrome Local Overrides to load official web app with their data
6. Observe web app behavior (UI labels, controls, capabilities)
7. Document API structure, field meanings, and mappings
8. Implement integration support based on findings

### Understand Control Command Format

**Scenario:** Need to implement temperature control but don't know exact API format.

**Steps:**
1. Start mock server
2. Enable request proxying in Chrome
3. Use official web app to change temperature
4. Check logs for captured POST payload
5. Document API format
6. Implement in integration

### Test Integration with Different Device Types

**Scenario:** Want to verify integration works with a different controller type (e.g., user reported `ftcModel: 4`).

**Steps:**
1. Get API response data from user's HAR capture
2. Configure mock server with that data
3. Test integration against mock server
4. Verify entities, controls, displays work correctly

## Contributing

### Have Real Hardware?

**Help us by providing API data:**
1. Capture HAR file from https://melcloudhome.com
2. Anonymize sensitive data (email, IDs, addresses)
3. Share via GitHub Discussion or Issue
4. We'll use reverse engineering tools to implement support

### Want to Help Without Hardware?

**Use these tools to:**
- Test reported device configurations
- Verify API documentation accuracy
- Implement support for devices reported by users
- Document findings in `docs/api/`

## Full Documentation

See [../../docs/research/REVERSE_ENGINEERING.md](../../docs/research/REVERSE_ENGINEERING.md) for comprehensive guide.

## Safety

- Chrome overrides: Local browser only, no API calls made
- Request proxying: Real API not called, fake success returned to web app
- Mock server: Local network only, no external access
- Always test with these tools before real hardware
