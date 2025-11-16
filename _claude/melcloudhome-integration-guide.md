# Building a MELCloud Home Integration for Home Assistant

This guide provides comprehensive technical documentation for building a Home Assistant integration for the Mitsubishi Electric MELCloud Home system (melcloudhome.com).

## 📊 Current Progress

**✅ PHASE 1: API Discovery - COMPLETE**
- Authenticated via AWS Cognito OAuth 2.0 flow
- Captured complete authentication flow with PKCE
- Found device list endpoint: `GET /api/user/context`
- Found control endpoint: `PUT /api/ataunit/{unit_id}`
- Tested control API (turned on A/C unit successfully)
- Documented all endpoints, modes, and capabilities
- See `melcloudhome-api-discovery.md` for complete API reference

**🔄 PHASE 2: Python Client - NOT STARTED**
- Need to build `pymelcloudhome` package
- Implement authentication (Cognito form-based login)
- Implement device listing and control methods

**⏳ PHASE 3: HA Integration - NOT STARTED**
- Create custom component structure
- Implement config flow
- Implement climate entity
- Test with real hardware

**Next:** See `NEXT-STEPS.md` for action items

---

## Table of Contents

0. [Getting Started - The Pragmatic Approach](#getting-started---the-pragmatic-approach) ⭐ **START HERE**
1. [MELCloud Home Specifics](#melcloud-home-specifics) ⚠️ **IMPORTANT**
2. [Integration Architecture](#integration-architecture)
3. [Climate Entity Requirements](#climate-entity-requirements)
4. [Integration Setup Pattern](#integration-setup-pattern)
5. [Config Flow Pattern](#config-flow-pattern)
6. [Data Update Coordinator](#data-update-coordinator)
7. [Error Handling](#error-handling)
8. [Reverse Engineering APIs](#reverse-engineering-apis)
9. [Quality Scale Requirements](#quality-scale-requirements)
10. [Testing Approaches](#testing-approaches)
11. [Best Practices](#best-practices)
12. [Anti-Patterns to Avoid](#anti-patterns-to-avoid)
13. [Complete Example](#complete-example)

---

## Getting Started - The Pragmatic Approach

> **"Talk is cheap. Show me the code."** - Linus Torvalds

### Philosophy: YAGNI + KISS

You don't need fancy automation, custom skills, or complex tooling to build this integration. You need:

1. A browser
2. Chrome DevTools MCP (you have it)
3. Basic coding skills
4. Your actual A/C unit for testing

That's it. Everything else is premature optimization.

### What You Actually Have

**Tools available right now:**
- ✅ Chrome DevTools MCP - Capture API requests automatically
- ✅ Read/Write/Edit - Create and modify files
- ✅ Bash - Run tests, git, docker commands
- ✅ Your brain - Still the best debugging tool

**What you DON'T need:**
- ❌ Custom skills for automation
- ❌ Fancy documentation generators
- ❌ API testing frameworks
- ❌ Complex CI/CD pipelines (not yet)

### The 5-Step Plan

```
1. Open melcloudhome.com in Chrome
   → Use Chrome DevTools MCP to capture requests

2. Document the API in a markdown file
   → Just write down what you see

3. Write Python client (pymelcloudhome)
   → Copy the API patterns, add aiohttp, done

4. Write HA integration
   → Follow the patterns in this guide

5. Test with your A/C
   → Fix bugs, iterate, ship it
```

**Total time: A few hours, not weeks.**

### Start Now

Stop reading. Open Chrome. Navigate to melcloudhome.com. Let's capture the API.

The rest of this document is reference material. Come back to it when you need specific implementation details.

---

## MELCloud Home Specifics

### Critical Implementation Details

⚠️ **READ THIS BEFORE STARTING** - These details affect everything you build.

### Authentication: AWS Cognito

MELCloud Home uses **AWS Cognito** for authentication, not a simple username/password API.

**What this means:**
- Login redirects to AWS Cognito hosted UI
- OAuth 2.0 / OpenID Connect flow
- JWT tokens (ID token, Access token, Refresh token)
- Token expiration and refresh required
- May use session cookies

**Authentication Flow (typical):**
```
1. User navigates to MELCLOUD_URL
2. Redirects to MELCLOUD_AUTH_URL (AWS Cognito)
3. User enters credentials
4. Cognito returns tokens (JWT)
5. Tokens used for API authentication
6. Tokens expire → use refresh token
```

**Implications for implementation:**
- Config flow needs to handle OAuth redirect or screen scraping
- Store refresh token in config entry
- Implement token refresh logic in coordinator
- Handle token expiration gracefully (trigger reauth)

### Bot Detection: User-Agent Requirements

⚠️ **CRITICAL:** MELCloud Home / AWS Cognito detects bots and will block requests with invalid user-agents.

**Required User-Agent (Chrome on Mac):**
```
Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36
```

**Rules:**
1. **Chrome DevTools MCP**: Automatically uses real Chrome user-agent ✅
2. **Python API client**: MUST set this user-agent in all requests ⚠️
3. **Never omit**: Requests without proper user-agent will be blocked ❌
4. **Keep updated**: If detection improves, may need to update version numbers

**Implementation:**
```python
# In your Python client
headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}
```

### Environment Variables Setup

**Required environment variables:**
```bash
export MELCLOUD_URL="https://melcloudhome.com"  # Base URL
export MELCLOUD_AUTH_URL="https://cognito-url"  # AWS Cognito URL
export MELCLOUD_USER="your-email@example.com"   # Username
export MELCLOUD_PASSWORD="your-password"        # Password
```

**For development:**
```bash
# Add to .envrc (if using direnv)
export MELCLOUD_URL="..."
export MELCLOUD_AUTH_URL="..."
export MELCLOUD_USER="..."
export MELCLOUD_PASSWORD="..."

# Load in Python
import os
MELCLOUD_URL = os.getenv("MELCLOUD_URL")
MELCLOUD_USER = os.getenv("MELCLOUD_USER")
```

### API Client Implications

**Must handle:**
1. ✅ OAuth/Cognito authentication flow
2. ✅ JWT token parsing and storage
3. ✅ Token refresh before expiration
4. ✅ Proper user-agent on ALL requests
5. ✅ Session cookie management (if needed)
6. ✅ Reauth when tokens invalid

**Example client structure:**
```python
class MelCloudHomeClient:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.base_url = os.getenv("MELCLOUD_URL")
        self.auth_url = os.getenv("MELCLOUD_AUTH_URL")
        self.access_token = None
        self.refresh_token = None
        self.token_expiry = None

    async def _ensure_valid_token(self):
        """Refresh token if expired."""
        if self.token_expiry and datetime.now() > self.token_expiry:
            await self._refresh_token()

    async def _request(self, method, endpoint, **kwargs):
        """Make authenticated request with proper headers."""
        await self._ensure_valid_token()

        headers = kwargs.pop("headers", {})
        headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Authorization": f"Bearer {self.access_token}",
        })

        async with self.session.request(
            method,
            f"{self.base_url}{endpoint}",
            headers=headers,
            **kwargs
        ) as resp:
            resp.raise_for_status()
            return await resp.json()
```

### Home Assistant Integration Implications

**Config Flow:**
- May need to implement OAuth flow (preferred)
- Or screen-scrape Cognito login (hacky but works)
- Store refresh token, not just access token
- Set appropriate timeout for token expiration

**Coordinator:**
- Check token expiration before each API call
- Refresh token automatically
- Raise ConfigEntryAuthFailed if refresh fails → triggers reauth

**Testing:**
- Test token refresh flow
- Test reauth when tokens expire
- Test with actual AWS Cognito (can't mock easily)

---

## Integration Architecture

### Directory Structure

```
custom_components/melcloudhome/
├── __init__.py          # Integration setup and coordinator
├── manifest.json        # Integration metadata
├── config_flow.py       # UI configuration flow
├── const.py            # Constants and configuration
├── climate.py          # Climate entity implementation
├── strings.json        # UI translations
├── coordinator.py      # Data update coordinator (optional but recommended)
└── entity.py           # Base entity class (optional but recommended)
```

### Reference Integrations

- **MELCloud** (`homeassistant/components/melcloud/`) - Similar Mitsubishi system
- **Sensibo** (`homeassistant/components/sensibo/`) - Platinum-rated cloud A/C integration
- **Climate Base** (`homeassistant/components/climate/`) - Core climate platform

---

## Climate Entity Requirements

### Base Class Import

```python
from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
    HVACAction,
)
from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE

class MelCloudHomeClimate(ClimateEntity):
    """Climate entity for MELCloud Home."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS  # or FAHRENHEIT
    _attr_has_entity_name = True  # Use device name as base
    _attr_name = None  # Entity name (None for main entity)
```

### HVAC Modes

Available modes that devices can support:

```python
class HVACMode(StrEnum):
    OFF = "off"           # Device off/standby
    HEAT = "heat"         # Heating mode
    COOL = "cool"         # Cooling mode
    HEAT_COOL = "heat_cool"  # Auto heat/cool
    AUTO = "auto"         # Schedule/AI based
    DRY = "dry"          # Dehumidify mode
    FAN_ONLY = "fan_only"  # Fan only
```

### HVAC Actions

Current device state (what it's actually doing):

```python
class HVACAction(StrEnum):
    COOLING = "cooling"
    HEATING = "heating"
    IDLE = "idle"
    OFF = "off"
    DRYING = "drying"
    FAN = "fan"
    DEFROSTING = "defrosting"
    PREHEATING = "preheating"
```

### Climate Features

Feature flags (bitfield using IntFlag):

```python
class ClimateEntityFeature(IntFlag):
    TARGET_TEMPERATURE = 1        # Set single target temp
    TARGET_TEMPERATURE_RANGE = 2  # Set temp range (min/max)
    TARGET_HUMIDITY = 4           # Set humidity
    FAN_MODE = 8                  # Fan speed control
    PRESET_MODE = 16              # Preset modes (eco, boost, etc.)
    SWING_MODE = 32               # Vertical swing
    TURN_OFF = 128                # Explicit turn off
    TURN_ON = 256                 # Explicit turn on
    SWING_HORIZONTAL_MODE = 512   # Horizontal swing
```

### Required Properties

```python
@property
def hvac_mode(self) -> HVACMode:
    """Return current operation mode."""
    # Map your API mode to HVACMode enum

@property
def hvac_modes(self) -> list[HVACMode]:
    """Return list of available modes."""
    # Return modes your device supports

@property
def current_temperature(self) -> float | None:
    """Return current temperature."""

@property
def target_temperature(self) -> float | None:
    """Return target temperature."""

@property
def supported_features(self) -> ClimateEntityFeature:
    """Return supported features bitmask."""

async def async_set_temperature(self, **kwargs) -> None:
    """Set new target temperature."""

async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
    """Set new operation mode."""
```

### Optional but Recommended Properties

```python
@property
def hvac_action(self) -> HVACAction | None:
    """Return current action (what device is doing)."""

@property
def fan_mode(self) -> str | None:
    """Return current fan mode."""

@property
def fan_modes(self) -> list[str] | None:
    """Return available fan modes."""
    # Common: ["auto", "low", "medium", "high"]

@property
def swing_mode(self) -> str | None:
    """Return vertical swing mode."""

@property
def swing_modes(self) -> list[str] | None:
    """Return available swing modes."""
    # Common: ["on", "off", "vertical", "horizontal", "both"]

@property
def target_temperature_step(self) -> float | None:
    """Return temperature step (e.g., 0.5 or 1.0)."""

@property
def min_temp(self) -> float:
    """Return minimum temperature."""

@property
def max_temp(self) -> float:
    """Return maximum temperature."""
```

---

## Integration Setup Pattern

### manifest.json

```json
{
  "domain": "melcloudhome",
  "name": "MELCloud Home",
  "codeowners": ["@yourusername"],
  "config_flow": true,
  "documentation": "https://github.com/yourusername/melcloudhome",
  "integration_type": "device",
  "iot_class": "cloud_polling",
  "loggers": ["pymelcloudhome"],
  "requirements": ["pymelcloudhome==0.1.0"],
  "version": "0.1.0"
}
```

**Key Fields:**
- `integration_type`: Use "device" for device integrations
- `iot_class`: "cloud_polling" for cloud APIs with periodic updates
- `config_flow`: true enables UI configuration
- `requirements`: Your Python API client package

### __init__.py

```python
"""The MELCloud Home integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from aiohttp import ClientConnectionError, ClientResponseError
from pymelcloudhome import get_devices  # Your API client

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CLIMATE]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""
    try:
        # Initialize your API client
        session = async_get_clientsession(hass)
        async with asyncio.timeout(10):
            devices = await get_devices(
                entry.data[CONF_TOKEN],
                session,
            )
    except ClientResponseError as ex:
        if ex.code == 401:
            raise ConfigEntryAuthFailed from ex
        raise ConfigEntryNotReady from ex
    except (TimeoutError, ClientConnectionError) as ex:
        raise ConfigEntryNotReady from ex

    # Store data for platforms to access
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = devices

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
```

---

## Config Flow Pattern

### config_flow.py

```python
"""Config flow for MELCloud Home."""
from __future__ import annotations

import asyncio
from http import HTTPStatus
import logging
from typing import Any

from aiohttp import ClientError, ClientResponseError
import pymelcloudhome
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class MelCloudHomeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user initiated flow."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str
                }),
            )

        # Validate credentials
        username = user_input[CONF_USERNAME]
        errors = {}

        try:
            async with asyncio.timeout(10):
                token = await pymelcloudhome.login(
                    username,
                    user_input[CONF_PASSWORD],
                    async_get_clientsession(self.hass),
                )
                # Test the token works
                await pymelcloudhome.get_devices(
                    token,
                    async_get_clientsession(self.hass),
                )
        except ClientResponseError as err:
            if err.status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
                errors["base"] = "invalid_auth"
            else:
                errors["base"] = "cannot_connect"
        except (TimeoutError, ClientError):
            errors["base"] = "cannot_connect"
        else:
            # Success - create entry
            await self.async_set_unique_id(username)
            self._abort_if_unique_id_configured({CONF_TOKEN: token})
            return self.async_create_entry(
                title=username,
                data={CONF_USERNAME: username, CONF_TOKEN: token}
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME, default=username): str,
                vol.Required(CONF_PASSWORD): str
            }),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth."""
        errors = {}

        if user_input is not None:
            try:
                async with asyncio.timeout(10):
                    token = await pymelcloudhome.login(
                        user_input[CONF_USERNAME],
                        user_input[CONF_PASSWORD],
                        async_get_clientsession(self.hass),
                    )
            except ClientResponseError as err:
                if err.status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "cannot_connect"
            except (TimeoutError, ClientError):
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data={CONF_TOKEN: token}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str
            }),
            errors=errors,
        )
```

---

## Data Update Coordinator

### Why Use a Coordinator?

- Centralizes data updates
- Provides automatic error handling
- Prevents duplicate API calls
- Required for Bronze+ tier quality
- Simplifies entity implementations

### coordinator.py

```python
"""DataUpdateCoordinator for MELCloud Home."""
from __future__ import annotations

from datetime import timedelta
import logging

from pymelcloudhome import Client
from pymelcloudhome.exceptions import AuthenticationError, ApiError

from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

REQUEST_REFRESH_DELAY = 0.35  # Delay after state change

class MelCloudHomeCoordinator(DataUpdateCoordinator):
    """Coordinator for data updates."""

    def __init__(self, hass: HomeAssistant, config_entry) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            # Debounce prevents immediate refresh after state change
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=REQUEST_REFRESH_DELAY, immediate=False
            ),
        )
        self.client = Client(
            config_entry.data[CONF_TOKEN],
            session=async_get_clientsession(hass),
        )

    async def _async_update_data(self):
        """Fetch data from API."""
        try:
            data = await self.client.async_get_devices_data()
        except AuthenticationError as error:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_error",
            ) from error
        except ApiError as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={"error": str(error)},
            ) from error

        if not data:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="no_data"
            )

        return data
```

### Using Coordinator in Entities

```python
"""Climate platform."""
from homeassistant.components.climate import ClimateEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MelCloudHomeClimate(CoordinatorEntity, ClimateEntity):
    """Climate entity using coordinator."""

    def __init__(self, coordinator, device_id):
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._device_id = device_id

    @property
    def device_data(self):
        """Return device data from coordinator."""
        return self.coordinator.data[self._device_id]

    @property
    def current_temperature(self):
        """Return current temperature."""
        return self.device_data.temperature

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        await self.coordinator.client.set_temperature(
            self._device_id,
            kwargs[ATTR_TEMPERATURE]
        )
        # Request refresh with debounce
        await self.coordinator.async_request_refresh()
```

---

## Error Handling

### Exception Types

```python
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,  # Auth failure - triggers reauth flow
    ConfigEntryNotReady,    # Temporary failure - retry later
    HomeAssistantError,     # General HA error
    ServiceValidationError, # Service call validation
)
```

### Setup Error Handling

```python
# In async_setup_entry:
try:
    devices = await get_devices(token)
except AuthenticationError as ex:
    raise ConfigEntryAuthFailed from ex  # Triggers reauth
except (TimeoutError, ConnectionError) as ex:
    raise ConfigEntryNotReady from ex  # HA retries
```

### Entity Error Handling

```python
# In entity methods:
try:
    await device.set_temperature(temp)
except ConnectionError:
    _LOGGER.warning("Connection failed for %s", self.name)
    self._attr_available = False
```

### Availability Tracking

```python
class YourClimateEntity(ClimateEntity):
    """Climate entity with availability tracking."""

    def __init__(self, device):
        """Initialize."""
        self._available = True

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._available

    async def async_set_temperature(self, **kwargs):
        """Set temperature with error handling."""
        try:
            await self._device.set({"temperature": kwargs[ATTR_TEMPERATURE]})
            self._available = True
        except ConnectionError:
            _LOGGER.warning("Connection failed for %s", self.name)
            self._available = False
            raise
```

---

## Reverse Engineering APIs

### Chrome DevTools MCP Approach (PRIMARY METHOD)

**You have Chrome DevTools MCP available.** This is the best tool for the job. Here's the workflow:

**Step 1: Open melcloudhome.com in Chrome**
```bash
# Just open Chrome normally and navigate to melcloudhome.com
```

**Step 2: Use MCP Tools to Capture Network Traffic**

```
# List open Chrome pages
mcp__chrome-devtools__list_pages

# Select the melcloudhome.com page
mcp__chrome-devtools__select_page (pageIdx: N)

# Interact with the interface (login, change settings)
mcp__chrome-devtools__fill (fill in login form)
mcp__chrome-devtools__click (click buttons, etc.)

# List all network requests
mcp__chrome-devtools__list_network_requests
  → Returns list of all HTTP requests with IDs

# Get detailed request/response data
mcp__chrome-devtools__get_network_request (reqid: N)
  → Returns full headers, payload, response, status
```

**Step 3: Document What You Find**

⚠️ **IMPORTANT:** Watch for these MELCloud Home specifics:

**AWS Cognito Authentication Flow:**
- Initial page may redirect to `MELCLOUD_AUTH_URL` (AWS Cognito)
- Login form is hosted by AWS, not MELCloud
- After login, Cognito redirects back with tokens
- Look for JWT tokens in URL fragment or cookies
- Capture the full OAuth flow (request + redirect + callback)

**What to capture:**
- ✅ AWS Cognito login endpoint and parameters
- ✅ Token response (ID token, access token, refresh token)
- ✅ Token format (JWT - decode to see expiration)
- ✅ Device listing endpoint (API base URL)
- ✅ Control endpoints (set temp, mode, fan, etc.)
- ✅ All request headers (especially User-Agent, Authorization)
- ✅ Response formats (JSON structures)
- ✅ Session cookies (if any)

**Example Workflow:**
1. Navigate to MELCLOUD_URL
2. Observe redirect to AWS Cognito (capture redirect URL)
3. Fill in credentials using MCP
4. Capture Cognito callback with tokens
5. Capture token exchange/validation requests
6. Navigate to A/C control page
7. Change temperature → Capture API request
8. Change mode → Capture API request
9. Repeat for all features

**Benefits of Chrome DevTools MCP:**
- ✅ Automated capture while you interact
- ✅ See exact browser behavior (no proxy weirdness)
- ✅ Get real headers, cookies, auth tokens
- ✅ No SSL certificate issues
- ✅ Can script interactions
- ✅ **Uses real Chrome user-agent (no bot detection)** ⭐

### Manual Browser DevTools (Fallback)

If MCP isn't working, fall back to manual approach:

1. Open browser DevTools (F12)
2. Go to Network tab
3. Filter by XHR/Fetch requests
4. Log in to melcloudhome.com
5. Interact with the web interface
6. Manually copy/paste request details

### Other Tools (Usually NOT Needed)

- **mitmproxy**: Only if you need to intercept non-browser traffic
- **Fiddler**: Windows alternative to mitmproxy
- **Wireshark**: Only for low-level debugging (overkill)

### Building the Python Client

⚠️ **CRITICAL: Must use proper user-agent and handle AWS Cognito tokens**

```python
"""API client for MELCloud Home."""
import os
from datetime import datetime, timedelta
import aiohttp
from typing import Any

# REQUIRED: Chrome Mac user-agent (NEVER omit or change)
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

class MelCloudHomeClient:
    """Client for MELCloud Home API with AWS Cognito authentication."""

    def __init__(
        self,
        username: str,
        password: str,
        session: aiohttp.ClientSession,
    ):
        """Initialize client."""
        self.session = session
        self.base_url = os.getenv("MELCLOUD_URL")
        self.auth_url = os.getenv("MELCLOUD_AUTH_URL")
        self.username = username
        self.password = password

        # AWS Cognito tokens
        self.access_token = None
        self.refresh_token = None
        self.id_token = None
        self.token_expiry = None

    def _get_headers(self, include_auth: bool = True) -> dict:
        """Get standard headers with user-agent."""
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
            "Content-Type": "application/json",
        }
        if include_auth and self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    async def async_login(self) -> dict[str, str]:
        """Login via AWS Cognito and get tokens."""
        # TODO: Implement based on captured Cognito flow
        # This is a placeholder - actual implementation depends on
        # what you capture from the browser
        async with self.session.post(
            f"{self.auth_url}/login",  # Replace with actual Cognito endpoint
            json={
                "username": self.username,
                "password": self.password,
            },
            headers=self._get_headers(include_auth=False),
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()

            # Extract tokens (format depends on Cognito response)
            self.access_token = data["access_token"]
            self.refresh_token = data["refresh_token"]
            self.id_token = data.get("id_token")

            # JWT tokens include expiration - decode to get it
            # For now, assume 1 hour
            self.token_expiry = datetime.now() + timedelta(hours=1)

            return {
                "access_token": self.access_token,
                "refresh_token": self.refresh_token,
            }

    async def _ensure_valid_token(self) -> None:
        """Refresh token if expired."""
        if not self.token_expiry or datetime.now() < self.token_expiry:
            return  # Token still valid

        if not self.refresh_token:
            raise AuthenticationError("No refresh token available")

        await self._refresh_token()

    async def _refresh_token(self) -> None:
        """Refresh access token using refresh token."""
        # TODO: Implement based on captured Cognito refresh flow
        async with self.session.post(
            f"{self.auth_url}/token",
            json={"refresh_token": self.refresh_token},
            headers=self._get_headers(include_auth=False),
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
            self.access_token = data["access_token"]
            self.token_expiry = datetime.now() + timedelta(hours=1)

    async def async_get_devices(self) -> list[dict[str, Any]]:
        """Get list of devices."""
        await self._ensure_valid_token()

        async with self.session.get(
            f"{self.base_url}/devices",  # Replace with actual endpoint
            headers=self._get_headers(),
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def async_set_temperature(
        self,
        device_id: str,
        temperature: float,
    ) -> None:
        """Set device temperature."""
        await self._ensure_valid_token()

        async with self.session.post(
            f"{self.base_url}/devices/{device_id}/temperature",
            json={"temperature": temperature},
            headers=self._get_headers(),
        ) as resp:
            resp.raise_for_status()

class AuthenticationError(Exception):
    """Authentication failed."""
```

### Critical Requirements

⚠️ **MUST DO:**
1. ✅ **Use exact user-agent string** - Never omit or change
2. ✅ **Handle token expiration** - Check before every request
3. ✅ **Implement token refresh** - Use refresh token before expiration
4. ✅ **Parse JWT tokens** - Extract expiration time
5. ✅ **Raise AuthenticationError** - When refresh fails (triggers HA reauth)

⚠️ **NEVER DO:**
1. ❌ Omit User-Agent header
2. ❌ Use generic user-agent like "Python-aiohttp"
3. ❌ Skip token expiration checks
4. ❌ Store only access token (need refresh token too)

### Additional Considerations

- Respect rate limits (implement exponential backoff if needed)
- Use aiohttp for async operations (required for HA)
- Type hint everything for maintainability
- Document all endpoints and payloads discovered
- Test token refresh flow thoroughly

---

## Quality Scale Requirements

### Bronze Tier (Minimum for New Integrations)

**Requirements:**
- ✓ Config flow (UI setup)
- ✓ Unique config entry per account
- ✓ Runtime data storage pattern
- ✓ Entity unique IDs
- ✓ `has_entity_name = True`
- ✓ Basic documentation
- ✓ Test coverage for config flow

**Code Pattern:**
```python
class YourClimate(ClimateEntity):
    _attr_has_entity_name = True
    _attr_name = None  # Use device name

    def __init__(self, device):
        """Initialize."""
        self._attr_unique_id = f"{device.serial}-{device.mac}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.serial)},
            manufacturer="Mitsubishi Electric",
            model=device.model,
            name=device.name,
        )
```

### Silver Tier

**Additional Requirements:**
- ✓ Config entry unloading
- ✓ Log when unavailable
- ✓ Entity unavailable states
- ✓ Reauthentication flow
- ✓ Active code owner
- ✓ Detailed documentation

### Gold Tier

**Additional Requirements:**
- ✓ Entity translations
- ✓ Device class usage
- ✓ Entity categories
- ✓ Diagnostics support
- ✓ Discovery (if applicable)
- ✓ Icon translations
- ✓ Reconfiguration flow

### Platinum Tier

**Additional Requirements:**
- ✓ Fully async dependencies
- ✓ Inject websession (don't create own)
- ✓ Strict typing (type hints everywhere)

---

## Testing Approaches

### Basic Test Structure (Bronze tier)

```python
"""Tests for config flow."""
from unittest.mock import patch
import pytest

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from custom_components.melcloudhome.const import DOMAIN

async def test_form(hass):
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

async def test_form_invalid_auth(hass):
    """Test invalid auth."""
    with patch(
        "custom_components.melcloudhome.config_flow.login",
        side_effect=AuthenticationError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_USERNAME: "test", CONF_PASSWORD: "test"},
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_auth"}

async def test_form_cannot_connect(hass):
    """Test cannot connect error."""
    with patch(
        "custom_components.melcloudhome.config_flow.login",
        side_effect=TimeoutError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_USERNAME: "test", CONF_PASSWORD: "test"},
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}
```

---

## Best Practices

### Code Organization

1. **Separate concerns**: Use coordinator for data, entity for presentation
2. **Type hints**: Use type annotations everywhere (required for Platinum)
3. **Async all the way**: Never use blocking I/O
4. **Use helpers**: Leverage HA's `async_get_clientsession`, don't create your own

### State Management

1. **Don't poll in entities**: Use DataUpdateCoordinator
2. **Debounce updates**: Wait before refreshing after state change
3. **Handle unavailable**: Mark entities unavailable on connection errors
4. **Optimistic updates**: Update state immediately, confirm on next poll

### Error Handling

1. **Specific exceptions**: Use `ConfigEntryAuthFailed` vs `ConfigEntryNotReady`
2. **Log appropriately**: Warning for transient errors, error for serious issues
3. **User-friendly messages**: Use translation keys in exceptions
4. **Graceful degradation**: Continue working with partial data if possible

### Performance

1. **Batch updates**: Update all entities together, not individually
2. **Cache data**: Store in coordinator, don't fetch repeatedly
3. **Parallel requests**: Use `asyncio.gather()` for multiple API calls
4. **Rate limit**: Respect API limits, implement backoff

### Security

1. **Never log credentials**: Don't log passwords or tokens
2. **Use HTTPS**: Always use secure connections
3. **Validate input**: Check user input in config flow
4. **Store tokens securely**: Use HA's encrypted storage if available

---

## Anti-Patterns to Avoid

### Don't Build Tools Before You Need Them

**Anti-pattern:**
```
"Let me create a custom skill for API discovery first"
"I should write a test framework before any code"
"I need a documentation generator before I start"
```

**Why it's wrong:**
- You're building automation for a one-time task
- You don't know what you need yet
- You're procrastinating on the real work

**Do this instead:**
- Just capture the API manually
- Write code first, tests after
- Document as you go

### Don't Over-Engineer the API Client

**Anti-pattern:**
```python
class MelCloudHomeClient:
    """Enterprise-grade API client with retry logic,
    circuit breakers, caching layers, connection pooling..."""
```

**Why it's wrong:**
- You're solving problems you don't have
- More code = more bugs
- You haven't tested basic functionality yet

**Do this instead:**
```python
class MelCloudHomeClient:
    """Simple async API client."""
    async def login(self): ...
    async def get_devices(self): ...
    async def set_temperature(self, device_id, temp): ...
```

Add complexity **only** when you hit actual problems.

### Don't Build for Multiple Integrations

**Anti-pattern:**
```
"This should be a generic framework for all A/C systems"
"Let me make it work with melcloud AND melcloudhome"
"I'll add support for other Mitsubishi systems"
```

**Why it's wrong:**
- YAGNI - You Aren't Gonna Need It
- Makes everything harder to change
- Delays getting anything working

**Do this instead:**
- Build for melcloudhome only
- Hard-code what you need
- Refactor later if you actually need it

### Don't Skip Testing on Real Hardware

**Anti-pattern:**
```
"The code looks good, I'll test it later"
"I'll just mock everything for tests"
"It works in my head"
```

**Why it's wrong:**
- APIs are never what you think they are
- Real devices behave differently than docs
- You'll find bugs immediately

**Do this instead:**
- Test on your actual A/C unit constantly
- Break things and see what happens
- Fix bugs as you find them

### Don't Pursue Perfection

**Anti-pattern:**
```
"It needs to be Platinum tier before I release"
"Every edge case must be handled"
"The code needs more refactoring"
```

**Why it's wrong:**
- Bronze tier is fine for v1
- Edge cases reveal themselves in use
- Working code > perfect code

**Do this instead:**
- Ship Bronze tier
- Fix bugs users report
- Upgrade quality tier later

### The Right Approach

1. **Make it work** - Get basic functionality running
2. **Make it right** - Fix obvious bugs and issues
3. **Make it fast** - Optimize only if needed
4. **Make it good** - Upgrade quality tier over time

**Not:**
1. Design the perfect architecture
2. Build comprehensive tooling
3. Write extensive tests
4. Never actually ship anything

---

## Complete Example

### Minimal Working Climate Entity

```python
"""Climate platform for MELCloud Home."""
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MelCloudHomeConfigEntry
from .coordinator import MelCloudHomeCoordinator

# Map API modes to HA modes
HVAC_MODE_MAP = {
    "heat": HVACMode.HEAT,
    "cool": HVACMode.COOL,
    "auto": HVACMode.HEAT_COOL,
    "fan": HVACMode.FAN_ONLY,
    "dry": HVACMode.DRY,
}

async def async_setup_entry(
    hass: HomeAssistant,
    entry: MelCloudHomeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up climate entities."""
    coordinator: MelCloudHomeCoordinator = entry.runtime_data

    async_add_entities(
        MelCloudHomeClimate(coordinator, device_id)
        for device_id in coordinator.data
    )

class MelCloudHomeClimate(CoordinatorEntity, ClimateEntity):
    """Climate entity for MELCloud Home."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator: MelCloudHomeCoordinator, device_id: str) -> None:
        """Initialize climate entity."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = device_id

    @property
    def device_data(self):
        """Return device data from coordinator."""
        return self.coordinator.data[self._device_id]

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        if not self.device_data.power:
            return HVACMode.OFF
        return HVAC_MODE_MAP.get(self.device_data.mode, HVACMode.AUTO)

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return available HVAC modes."""
        return [
            HVACMode.OFF,
            HVACMode.HEAT,
            HVACMode.COOL,
            HVACMode.HEAT_COOL,
            HVACMode.DRY,
            HVACMode.FAN_ONLY,
        ]

    @property
    def current_temperature(self) -> float | None:
        """Return current temperature."""
        return self.device_data.room_temperature

    @property
    def target_temperature(self) -> float | None:
        """Return target temperature."""
        return self.device_data.target_temperature

    @property
    def fan_mode(self) -> str | None:
        """Return fan mode."""
        return self.device_data.fan_speed

    @property
    def fan_modes(self) -> list[str]:
        """Return available fan modes."""
        return self.device_data.fan_speeds

    @property
    def min_temp(self) -> float:
        """Return minimum temperature."""
        return 16.0

    @property
    def max_temp(self) -> float:
        """Return maximum temperature."""
        return 31.0

    @property
    def target_temperature_step(self) -> float:
        """Return temperature step."""
        return 0.5

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if ATTR_TEMPERATURE not in kwargs:
            return

        await self.coordinator.client.set_temperature(
            self._device_id,
            kwargs[ATTR_TEMPERATURE]
        )
        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.client.set_power(self._device_id, False)
        else:
            # Map HA mode to API mode
            api_mode = {v: k for k, v in HVAC_MODE_MAP.items()}[hvac_mode]
            await self.coordinator.client.set_mode(self._device_id, api_mode)
            if not self.device_data.power:
                await self.coordinator.client.set_power(self._device_id, True)

        await self.coordinator.async_request_refresh()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode."""
        await self.coordinator.client.set_fan_speed(self._device_id, fan_mode)
        await self.coordinator.async_request_refresh()
```

---

## Implementation Steps Summary

### The Pragmatic Path (Do This)

1. **Capture the API** (30 minutes)
   - Open melcloudhome.com in Chrome
   - Use Chrome DevTools MCP to capture requests
   - Document in `.claude/melcloudhome-api.md`

2. **Write Python client** (1-2 hours)
   - Create simple async client with aiohttp
   - Just the basics: login, get devices, set temperature/mode
   - Test it with your A/C

3. **Create HA integration** (2-3 hours)
   - Copy file structure from guide
   - Implement config flow (username/password)
   - Create climate entity with basic features
   - Wire everything together

4. **Test and iterate** (ongoing)
   - Load integration in HA
   - Test with your actual A/C unit
   - Fix bugs as they appear
   - Add more features if needed

5. **Ship it** (Bronze tier is fine)
   - Get it working reliably
   - Document basic setup
   - Use it yourself for a while
   - Improve based on real usage

**Total time: Half a day, not weeks.**

### The Over-Engineering Path (Don't Do This)

1. Design comprehensive API framework
2. Build custom tooling and skills
3. Write extensive test suite
4. Create beautiful documentation
5. Target Platinum tier from day one
6. Never actually finish

**Remember:** Working Bronze-tier code beats perfect Platinum-tier vaporware.

---

## Reference Links

- **Home Assistant Developer Docs**: https://developers.home-assistant.io/
- **Climate Integration**: https://developers.home-assistant.io/docs/core/entity/climate/
- **Integration Quality Scale**: https://developers.home-assistant.io/docs/integration_quality_scale_index/
- **Config Flow**: https://developers.home-assistant.io/docs/config_entries_config_flow_handler/
- **Data Update Coordinator**: https://developers.home-assistant.io/docs/integration_fetching_data/

---

## Next Steps

**Stop reading. Start doing.**

1. **Right now:** Open Chrome and navigate to melcloudhome.com
2. **Tell me when ready:** I'll use Chrome DevTools MCP to capture the API
3. **Then code:** We'll write the integration together
4. **Then test:** On your actual A/C unit
5. **Then ship:** Get it working in your Home Assistant

No more planning. No more tools. Just build it.

Ready? Open Chrome and let's go.
