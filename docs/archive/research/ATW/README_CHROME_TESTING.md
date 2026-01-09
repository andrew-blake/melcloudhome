# Chrome DevTools Testing Guide

Scripts for testing MELCloud Home web client with mock data.

## Files

- **`chrome_override/`** - Local Overrides folder structure
  - `melcloudhome.com/api/user/context` - Mock API response
- **`block_and_log_mutations.js`** - Intercept and log API mutations (POST/PUT/PATCH/DELETE)

## Setup

### 1. Enable Local Overrides

```
DevTools (F12) → Sources → Overrides
→ Select folder: docs/research/ATW/chrome_override
→ Allow access
```

### 2. Load Blocking Script (One Time)

```
DevTools (F12) → Console
→ Copy/paste: docs/research/ATW/block_and_log_mutations.js
→ Press Enter
```

Output:
```
📦 API mutation blocking script loaded

Commands:
  blockMutations()    - Enable blocking (POST/PUT/PATCH/DELETE)
  unblockMutations()  - Disable blocking

💡 Run blockMutations() to start
```

### 3. Control Blocking

**Enable:**
```javascript
blockMutations()
```

**Disable:**
```javascript
unblockMutations()
```

Toggle anytime - no reload needed! 🔄

## What Happens

✅ **GET /api/user/context** → Returns your mock data
🚫 **POST/PUT/PATCH/DELETE /api/*** → Blocked, logged to console, returns 200

## Usage

1. Open melcloudhome.com
2. Enable overrides + run blocking script
3. Log in
4. Interact with UI (change temperature, toggle power, etc.)
5. **Check Console** - all PUT requests are logged with full JSON payload
6. UI thinks commands succeeded (gets 200 responses)

## Example Console Output

```
🚫 BLOCKED PUT Request
  URL: https://melcloudhome.com/api/atwunit/bf2d256c-42ac-4799-a6d8-c6ab433e5666
  Method: PUT
  Body (JSON):
  {
    "power": true,
    "setTemperatureZone1": 22,
    "forcedHotWaterMode": false,
    ...
  }
```

## Why This Works

- **No real API calls** - Safe to test with fake data
- **See command structure** - Learn what the web client sends
- **UI feedback** - Web client updates normally
- **Reverse engineering** - Understand API request patterns

## Notes

- ✅ Script survives until page reload
- ✅ Toggle blocking on/off without reloading
- ✅ Override persists across reloads
- ✅ Can test both ATA and ATW devices
- ⚠️ All UUIDs must be real random ones (not AAAA-AAAA-AAAA...)
- ⚠️ MAC addresses must look realistic (not all same chars)
