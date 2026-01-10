# API Reverse Engineering Guide

## Overview

This guide explains the two-phase approach for adding support for new devices:

1. **Phase 1 (Device Owner):** Record HAR from real device and share redacted version
2. **Phase 2 (Developer):** Use developer tools to simulate device and implement support

## Phase 1: Recording Real Device Behavior (Device Owners)

### Purpose

If you have a device that isn't yet supported (e.g., specific heat pump controller, multi-zone system), you can help developers add support by capturing its API behavior.

### What You'll Need

- Your device (physical hardware)
- Access to https://melcloudhome.com
- Chrome browser

### Recording Process

**Step 1: Start HAR Recording**

```
1. Open Chrome
2. Navigate to https://melcloudhome.com
3. Press F12 to open DevTools
4. Click "Network" tab
5. ✓ Check "Preserve log" checkbox
6. Click the record button (red dot) if not already recording
```

**Step 2: Use Your Device**

```
1. Login to MELCloud Home
2. Navigate to your device
3. Interact with ALL available controls:
   - Change temperatures
   - Switch modes (heating/cooling/auto)
   - Toggle zones if available
   - Adjust fan speeds
   - Enable/disable features
   - Check all available tabs/screens
4. Let it run for 1-2 minutes to capture telemetry updates
```

**Step 3: Save HAR File**

```
1. Right-click anywhere in the Network tab
2. Select "Save all as HAR with content"
3. Save as descriptive name: device-model-YYYYMMDD.har
```

**Step 4: Anonymize Sensitive Data**

**⚠️ CRITICAL: Remove personal information and session cookies before sharing**

HAR files contain sensitive data in multiple places. Open the HAR file in a text editor and redact:

**A. Session Cookies (CRITICAL - in ALL requests)**

MELCloud Home uses cookie-based authentication. You MUST remove all cookies.

Find **every** `"cookies": [...]` array and replace with empty array:

```json
"cookies": [],
```

Easiest method: Search and replace in your editor:

- **Search for:** `"cookies": [` followed by any content until `]`
- **Replace with:** `"cookies": []`

Or manually search for `"cookies"` and delete all cookie objects inside each array.

**B. Personal Data (in `/api/user/context` response body)**

Find the response body for the `/api/user/context` and other endpoints, and redact:

```json
{
  "id": "AAAAA...",                      // Replace with "AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA"
  "email": "you@example.com",            // Replace with "user@example.com"
  "firstname": "YourName",               // Replace with "User"
  "lastname": "YourLastName",            // Replace with "Name"
  "phoneNumber": "+44...",               // Remove entirely
  "buildings": [{
    "id": "BBBB...",                     // Replace with "DDDDDDDD-DDDD-DDDD-DDDD-DDDDDDDDDDDD"
    "addressText": "123 Main St",        // Remove or generalize to "Home"
    "latitude": 51.5074,                 // Remove or generalize
    "longitude": -0.1278,                // Remove or generalize
    "airToAirUnits": [{
      "id": "CCCC...",                   // Replace with "CCCCCCCC-CCCC-CCCC-CCCC-CCCCCCCCCCCC"
      "connectedInterfaceIdentifier": "112233445566",  // Replace with similar pattern
      "systemId": "EEEE..."              // Replace with "EEEEEEEE-EEEE-EEEE-EEEE-EEEEEEEEEEEE"
    }],
    "airToWaterUnits": [{
      "id": "BBBB...",                   // Replace with "BBBBBBBB-BBBB-BBBB-BBBB-BBBBBBBBBBBB"
      "macAddress": "aa:bb:cc:dd:ee:ff"  // Replace with "AABBCCDDEEFF"
    }]
  }]
}
```

**C. Passwords (if present)**

If you recorded the login POST request, search for `"password"` fields and DELETE the entire field:

```json
{
  "name": "password",
  "value": "..."  // DELETE this entire object
}
```

**Quick Search Patterns:**

Use your editor's find function to locate sensitive data:

- `"cookies": [` - Session cookies (CRITICAL)
- `"password"` - Password fields
- Your actual email address
- Your actual phone number
- Your device MAC addresses

**Example Anonymization Pattern:**

Use consistent replacement patterns like the example above:

- User ID: `AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA`
- Building ID: `DDDDDDDD-DDDD-DDDD-DDDD-DDDDDDDDDDDD`
- ATA Unit ID: `CCCCCCCC-CCCC-CCCC-CCCC-CCCCCCCCCCCC`
- ATW Unit ID: `BBBBBBBB-BBBB-BBBB-BBBB-BBBBBBBBBBBB`
- System ID: `EEEEEEEE-EEEE-EEEE-EEEE-EEEEEEEEEEEE`

**Keep These Fields (needed for development):**

- Device model numbers (`ftcModel`, `deviceType`, etc.)
- Capabilities (`hasZone2`, `hasDHW`, `hasHotWater`, etc.)
- Temperature ranges (`minSetTemperature`, `maxSetTemperature`)
- Available modes and features
- Timezone (generic like `"Europe/Madrid"` is fine)
- Current temperatures and states
- RSSI/signal strength values

**Step 5: Share with Developers**

Create a GitHub Discussion or Issue:

```markdown
**Title:** Support for [Device Model/Controller Type]

**Description:**
I have a [device type] with [controller model] that shows these features:
- [List visible features: zones, DHW, etc.]

**Attached:**
Anonymized HAR file from [date]

**Additional Notes:**
[Any special behaviors, error messages, or quirks you've noticed]
```

## Phase 2: Developer Simulation (Without Physical Device)

### Purpose

Once you receive a HAR file from a device owner, you can simulate that device locally to develop integration support without owning the hardware.

### Tools

These tools work together to simulate devices without hardware. Set them up in this order:

#### 1. Mock Server

**Purpose:** Simulate MELCloud API locally for testing and receiving proxied requests.

**Location:** `tools/mock_melcloud_server.py`

**Setup:**

```bash
# Start complete dev environment
make dev-up

# Access points:
# - Home Assistant: http://localhost:8123 (dev/dev)
# - Mock API: http://localhost:8080

# Verify it's running
curl http://localhost:8080/api/user/context
```

**Customize:**

Edit `tools/mock_melcloud_server.py` to change device configurations:
- Device types (ATA, ATW)
- Capabilities (ftcModel, zones, DHW)
- Initial states (temperatures, modes)

> **Why start with this:**
>
> - Required by Request Proxying tool (needs somewhere to send intercepted requests)
> - Useful for integration testing with Home Assistant
> - Can be customized to match devices from HAR captures

#### 2. Chrome Overrides + Request Proxying

**Purpose:** Simulate a captured device in the official web app and capture control command payloads without hitting the real API.

**What you need:**
- Mock server running (Tool #1)
- Captured HAR file from device owner
- Chrome browser

**Locations:**
- Chrome overrides: `tools/reverse-engineering/chrome_override/`
- Proxy script: `tools/reverse-engineering/proxy_mutations.js`

**Complete Setup:**

**Step 1: Prepare Chrome Local Overrides**

```
1. Open Chrome DevTools (F12)
2. Sources tab → Overrides (left sidebar)
3. Click "Select folder for overrides"
4. Choose: /path/to/melcloudhome/tools/reverse-engineering/chrome_override
5. Allow access when prompted
6. ✓ Ensure "Enable Local Overrides" is checked
```

**Step 2: Extract Device Data from HAR**

```
1. Open received HAR file in text editor (it's JSON)
2. Search for: "/api/user/context"
3. Find response body
4. Copy entire JSON response
5. Save to: chrome_override/melcloudhome.com/api/user/context
```

**Step 3: Set Up Session**

```
1. Ensure mock server is running:
   curl http://localhost:8080/api/user/context

2. Navigate to https://melcloudhome.com (DO NOT login yet!)

3. Open Console (F12 → Console tab)

4. Paste entire contents of proxy_mutations.js

5. Run: blockMutations()
   - You should see: "Mutations will be blocked and proxied"

6. NOW login with YOUR credentials:
   - Authentication is real (uses your account)
   - Device data is replaced with captured data
   - You'll see their device as if it were in your account
```

**Step 4: Observe and Capture HARs**

```
1. Observe web app behavior:
   - How device is displayed
   - Available controls and ranges
   - UI labels and terminology
   - Zone configurations
   - Special features

2. Use web app controls (change temp, modes, etc.)

3. Check console for logged control requests

4. Check mock server logs for received payloads:
   docker logs melcloudhome-melcloud-mock-1 -f

5. When done: unblockMutations() (or just refresh page)
```

> **⚠️ CRITICAL:**
>
> - Mock server MUST be running before starting
> - Set up proxy BEFORE logging in (it only intercepts future requests)
> - Refreshing the page clears the proxy - re-paste and re-run `blockMutations()`
> - If you refresh, repeat Step 3 (re-inject proxy script)

> **How it works:**
>
> - **Chrome Local Overrides:** DevTools intercepts `/api/user/context` and returns local file instead of real API
> - **Request Proxying:** JavaScript intercepts fetch() calls for mutations (POST/PUT/PATCH/DELETE)
> - Control commands are logged to console and proxied to mock server (port 8080)
> - Web app receives fake 200 success responses
> - Real MELCloud API is never contacted
> - No real hardware is affected
> - NOTE: state changes are disregarded by the mock server - so you only can see what the API client needs to send to the API to make state changes

## Best Practices

### For Device Owners (Recording HARs)

**Do:**

- ✓ Use Chrome (best DevTools support)
- ✓ Enable "Preserve log" before starting
- ✓ Interact with ALL device features during recording
- ✓ Let it run 1-2 minutes to capture telemetry
- ✓ Anonymize ALL personal information before sharing
- ✓ Provide context about device model and visible features

**Don't:**

- ✗ Share HAR files without anonymizing first
- ✗ Skip interacting with controls (we need those API calls)
- ✗ Delete the HAR after sharing (keep a backup)

### For Developers (Using Captured Data)

**Do:**

- ✓ Always use overrides/proxying to prevent real API calls
- ✓ Test thoroughly in mock environment before real hardware
- ✓ Document findings in API reference docs
- ✓ Use conservative values (safe temperature ranges) for initial tests
- ✓ Coordinate with device owner for final hardware testing

**Don't:**

- ✗ Test unverified implementations on real hardware first
- ✗ Assume API behavior without observing official web app
- ✗ Fabricate data - always use real HAR captures
- ✗ Skip documentation - future developers need your findings

### Safety Considerations

**Before deploying to real hardware:**

1. Verify implementation with mock server
2. Test with overrides against official web app behavior
3. Use safe, conservative test values
4. Have device owner monitor during initial test
5. Start with read-only operations
6. Test one control at a time
