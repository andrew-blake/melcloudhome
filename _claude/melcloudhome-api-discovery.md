# MELCloud Home API Discovery

Complete API documentation captured from https://melcloudhome.com

## Technology Stack

- **Frontend**: Blazor WebAssembly (.NET/C# running in browser)
- **Backend**: Backend-for-Frontend (BFF) pattern
- **Authentication**: AWS Cognito (OAuth 2.0 + PKCE)
- **Region**: eu-west-1 (Ireland)
- **Real-time**: WebSocket support (`wss://ws.melcloudhome.com`)
- **Session**: Cookie-based (server-side session management)

---

## Authentication Flow

### OAuth 2.0 Authorization Code Flow with PKCE

**Step 1: Initiate Login**
```
GET https://melcloudhome.com/bff/login?returnUrl=/dashboard
→ Redirects to auth.melcloudhome.com
```

**Step 2: OAuth Authorize**
```
GET https://auth.melcloudhome.com/connect/authorize
→ Redirects to AWS Cognito
```

**Step 3: Cognito Login Page**
```
GET https://live-melcloudhome.auth.eu-west-1.amazoncognito.com/login
Parameters:
- client_id: 3g4d5l5kivuqi7oia68gib7uso
- redirect_uri: https://auth.melcloudhome.com/signin-oidc-meu
- response_type: code
- scope: openid profile
- code_challenge_method: S256 (PKCE)
```

**Step 4: Submit Credentials**
```
POST https://live-melcloudhome.auth.eu-west-1.amazoncognito.com/login

Headers:
- content-type: application/x-www-form-urlencoded
- user-agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36...

Body:
_csrf={csrf_token}
&username={email}
&password={password}
&cognitoAsfData={advanced_security_fingerprint}

Response: 302 Redirect
Location: https://auth.melcloudhome.com/signin-oidc-meu?code={auth_code}&state={state}
Set-Cookie: cognito={session_cookie}
```

**Important Notes:**
- ⚠️ `cognitoAsfData` is required (AWS Advanced Security Features - device fingerprinting)
- ⚠️ Must use proper User-Agent (Chrome Mac) to avoid bot detection
- ✅ Returns authorization code in redirect
- ✅ Sets Cognito session cookie

**Step 5: Token Exchange (Server-Side)**
```
Multiple redirects occur server-side:
1. Callback to auth.melcloudhome.com with authorization code
2. Token exchange happens server-side (not visible to client)
3. Final redirect to melcloudhome.com/dashboard with session cookie
```

**Result:**
- Session managed via HTTP-only cookies
- No JWT tokens in client
- Session expires in ~8 hours (28781 seconds)

---

## HTTP Headers for API Requests

### Required Headers (All API Requests)

**User-Agent (CRITICAL for avoiding bot detection):**
```
Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36
```

**Client Hints (Chrome Specific):**
```
sec-ch-ua: "Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"
sec-ch-ua-mobile: ?0
sec-ch-ua-platform: "macOS"
```

**CSRF Protection (POST/PUT/DELETE requests):**
```
x-csrf: 1
```

**Content Type (JSON payloads):**
```
Content-Type: application/json; charset=utf-8
```

### Python Implementation Example

```python
import requests

# Base headers for all requests
BASE_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
    'sec-ch-ua': '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"macOS"',
}

# For API requests
API_HEADERS = {
    **BASE_HEADERS,
    'x-csrf': '1',
    'Content-Type': 'application/json; charset=utf-8',
}

# Example usage
session = requests.Session()
session.headers.update(BASE_HEADERS)

# For API calls, add CSRF header
response = session.put(
    f'https://melcloudhome.com/api/ataunit/{unit_id}',
    json=payload,
    headers={'x-csrf': '1', 'Content-Type': 'application/json; charset=utf-8'}
)
```

### Header Notes

**Why User-Agent is Critical:**
- AWS Cognito uses Advanced Security Features (ASF) for bot detection
- Mismatched or missing User-Agent may trigger additional verification
- Chrome on macOS has been tested and works reliably

**CSRF Protection:**
- The `x-csrf: 1` header is required for all state-changing operations
- GET requests don't require this header
- Server validates CSRF token from session cookie

**Client Hints:**
- Optional but recommended for full browser impersonation
- Help avoid triggering security features
- Match the User-Agent platform (macOS in this case)

**Session Management:**
- All requests use session cookies (HTTP-only)
- No Authorization header needed after login
- Session expires in ~8 hours

---

## API Endpoints

### Configuration

**Get Configuration**
```
GET https://melcloudhome.com/api/configuration

Auth: None required
Response: 200 OK

{
  "webSocketUrl": "wss://ws.melcloudhome.com",
  "branchSettings": { ... },
  "timezones": { ... }
}
```

### User Authentication

**Check User Session**
```
GET https://melcloudhome.com/bff/user?slide=false

Auth: Session cookie (automatic)
Response: 200 OK

[
  {"type": "given_name", "value": "Andrew"},
  {"type": "family_name", "value": "Blake"},
  {"type": "email", "value": "a.blake01@gmail.com"},
  {"type": "locale", "value": "en-GB"},
  {"type": "sub", "value": "0125be99-65cb-4c97-a705-24794d6774b7"},
  {"type": "bff:session_expires_in", "value": 28781},
  {"type": "bff:logout_url", "value": "/bff/logout?sid=..."}
]
```

**Get WebSocket Token**
```
GET https://melcloudhome.com/ws/token

Auth: Session cookie
Response: 200 OK

{
  "hash": "0125be99-65cb-4c97-a705-24794d6774b7",
  "userId": "0125be99-65cb-4c97-a705-24794d6774b7"
}
```

### User Context & Devices

**Get User Context (MAIN ENDPOINT)**
```
GET https://melcloudhome.com/api/user/context

Auth: Session cookie
Response: 200 OK

{
  "id": "0125be99-65cb-4c97-a705-24794d6774b7",
  "firstname": "Andrew",
  "lastname": "Blake",
  "email": "a.blake01@gmail.com",
  "language": "en",
  "country": "GB",
  "numberOfDevicesAllowed": 10,
  "buildings": [
    {
      "id": "1800cb6b-c2c1-4837-b873-d741ad45d860",
      "name": "Orchard Cottage",
      "timezone": "Europe/London",
      "airToAirUnits": [
        {
          "id": "0efce33f-5847-4042-88eb-aaf3ff6a76db",
          "givenDisplayName": "Dinning Room",
          "displayIcon": "DiningRoom",
          "settings": [
            {"name": "RoomTemperature", "value": "16.5"},
            {"name": "Power", "value": "False"},
            {"name": "OperationMode", "value": "Heat"},
            {"name": "ActualFanSpeed", "value": "Auto"},
            {"name": "SetFanSpeed", "value": "0"},
            {"name": "VaneHorizontalDirection", "value": "Swing"},
            {"name": "VaneVerticalDirection", "value": "Five"},
            {"name": "InStandbyMode", "value": "False"},
            {"name": "SetTemperature", "value": "20"},
            {"name": "IsInError", "value": "False"},
            {"name": "ErrorCode", "value": ""}
          ],
          "isInError": false,
          "scheduleEnabled": false,
          "connectedInterfaceIdentifier": "FE0000060403388D3DFFFE8656D305FF01",
          "capabilities": {
            "isMultiSplitSystem": true,
            "isLegacyDevice": false,
            "hasStandby": true,
            "hasCoolOperationMode": true,
            "hasHeatOperationMode": true,
            "hasAutoOperationMode": true,
            "hasDryOperationMode": true,
            "hasAutomaticFanSpeed": true,
            "hasAirDirection": true,
            "hasSwing": true,
            "hasExtendedTemperatureRange": true,
            "hasEnergyConsumedMeter": true,
            "numberOfFanSpeeds": 5,
            "minTempCoolDry": 16,
            "maxTempCoolDry": 31,
            "minTempHeat": 10,
            "maxTempHeat": 31,
            "minTempAutomatic": 16,
            "maxTempAutomatic": 31,
            "hasDemandSideControl": true,
            "hasHalfDegreeIncrements": true,
            "supportsWideVane": false
          },
          "rssi": -37,
          "timeZone": "Europe/London",
          "isConnected": true,
          "connectedInterfaceType": 2,
          "systemId": "402a5705-fce5-4f6f-a5b8-a7fe66d3aa98"
        }
      ],
      "airToWaterUnits": []
    }
  ],
  "guestBuildings": [],
  "scenes": []
}
```

**Key Fields:**
- `buildings[].airToAirUnits[]` - List of A/C units
- `settings[]` - Current state of each unit
- `capabilities` - What features each unit supports
- `rssi` - WiFi signal strength
- `isConnected` - Connection status

### Device Control

**Control A/C Unit (MAIN CONTROL ENDPOINT)**
```
PUT https://melcloudhome.com/api/ataunit/{unit_id}

Headers:
- x-csrf: 1
- content-type: application/json; charset=utf-8
- user-agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36...

Auth: Session cookie

Body (partial update - only include fields to change):
{
  "power": true,                          // true/false
  "operationMode": "Heat",                // "Heat", "Cool", "Auto", "Dry", "Fan"
  "setFanSpeed": 3,                       // 0=Auto, 1-5 for manual speeds
  "vaneHorizontalDirection": "Swing",     // "Swing", "Left", "LeftCentre", "Centre", "RightCentre", "Right"
  "vaneVerticalDirection": "Auto",        // "Auto", "One", "Two", "Three", "Four", "Five"
  "setTemperature": 21.5,                 // Temperature (supports 0.5 increments)
  "temperatureIncrementOverride": null,   // Override increment size (optional)
  "inStandbyMode": false                  // Standby mode
}

Response: 200 OK (empty body)
```

**Important Notes:**
- ✅ Supports **partial updates** - only send fields you want to change
- ✅ Other fields can be `null` or omitted
- ✅ Temperature supports half-degree increments (e.g., 20.5)
- ⚠️ Must include `x-csrf: 1` header
- ⚠️ Must use proper User-Agent

**Example: Turn On Unit**
```json
{"power": true}
```

**Example: Change Temperature**
```json
{"setTemperature": 22}
```

**Example: Change Mode and Fan**
```json
{
  "operationMode": "Cool",
  "setFanSpeed": 4
}
```

---

## Operation Modes

Available modes (from capabilities):
- `Heat` - Heating mode
- `Cool` - Cooling mode
- `Auto` - Automatic heat/cool
- `Dry` - Dehumidify mode
- `Fan` - Fan only (no heating/cooling)

---

## Fan Speeds

- `0` - Auto
- `1` - Speed 1 (lowest)
- `2` - Speed 2
- `3` - Speed 3 (medium)
- `4` - Speed 4
- `5` - Speed 5 (highest)

---

## Vane Directions

**Horizontal:**
- `Swing` - Auto swing
- `Left`
- `LeftCentre`
- `Center`
- `RightCentre`
- `Right`

**Vertical:**
- `Auto` - Auto position
- `Swing` - Auto swing
- `One` - Position 1 (highest)
- `Two` - Position 2
- `Three` - Position 3 (middle)
- `Four` - Position 4
- `Five` - Position 5 (lowest)

---

## Implementation Notes

### For Python API Client

1. **Authentication:**
   - Implement OAuth 2.0 Authorization Code flow with PKCE
   - Handle AWS Cognito form-based login
   - Include `cognitoAsfData` (device fingerprinting)
   - Store session cookies (handled automatically by aiohttp)
   - Session expires in ~8 hours

2. **Required Headers:**
   - `User-Agent`: `Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36`
   - `x-csrf`: `1` (for control endpoints)
   - `content-type`: `application/json; charset=utf-8` (for control endpoints)

3. **State Management:**
   - Poll `/api/user/context` for device state (recommend every 60 seconds)
   - Parse `buildings[].airToAirUnits[]` for device list
   - Parse `settings[]` array for current state

4. **Control:**
   - Use `PUT /api/ataunit/{unit_id}` with partial updates
   - Only send fields you want to change
   - Empty 200 response = success

5. **Error Handling:**
   - 401 = Session expired, need to re-authenticate
   - Monitor `bff:session_expires_in` and refresh before expiration

### For Home Assistant Integration

**Config Flow:**
- Implement OAuth flow or screen-scrape Cognito login
- Store session cookies in config entry
- Implement reauth flow for session expiration

**Coordinator:**
- Poll `/api/user/context` every 60 seconds
- Parse device list and current states
- Check session expiration and refresh if needed

**Climate Entity:**
- Map API modes to HA HVACMode
- Map fan speeds to HA fan modes
- Use `/api/ataunit/{id}` for control
- Debounce updates (wait 0.5s after control before refresh)

---

## Summary

**✅ Complete API Discovered:**
1. OAuth 2.0 + PKCE authentication via AWS Cognito
2. Session-based auth (BFF pattern with cookies)
3. Device list: `GET /api/user/context`
4. Device control: `PUT /api/ataunit/{unit_id}`
5. WebSocket token: `GET /ws/token`

**✅ Key Requirements:**
- Proper User-Agent (Chrome Mac)
- AWS Cognito device fingerprinting
- CSRF header for control
- Cookie-based session management

**✅ Ready to Implement:**
- All endpoints documented
- Request/response formats captured
- Authentication flow understood
- Control mechanism clear
