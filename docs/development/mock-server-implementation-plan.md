# Mock MELCloud Home API Server - Implementation Plan

**Purpose:** Create a mock API server supporting both Air-to-Air and Air-to-Water devices for development and testing without physical hardware

**Status:** Planning - Not Yet Implemented

**Last Updated:** 2026-01-03

**Architecture Reference:** `docs/architecture.md`

---

## Overview

A lightweight HTTP server that mimics the MELCloud Home API, supporting:

- **Air-to-Air (ATA)** - AC units with HVAC control
- **Air-to-Water (ATW)** - Heat pumps with zone heating + DHW
- **Multi-device scenarios** - Multiple buildings, mixed device types
- **Stateful behavior** - Changes persist across polling cycles
- **Realistic responses** - Exact format matching real API

## Key Design Principles

1. **Single Unified API** - One mock server handles both device types (matches architecture:line 12)
2. **Shared Authentication** - One OAuth session for all devices (matches architecture:line 13)
3. **Multi-Type Responses** - `UserContext` returns both types in parallel arrays (matches architecture:line 14)
4. **Device-Specific Endpoints** - Separate control endpoints for ATA vs ATW (matches architecture:lines 49-50)
5. **3-Way Valve Simulation** - ATW mock reflects physical limitation (matches architecture:line 264)

---

## Scope

### Phase 1: MVP (Initial Implementation)

- ✅ Shared authentication endpoint (no token validation)
- ✅ GET `/api/user/context` returning both ATA and ATW devices
- ✅ PUT `/api/ataunit/{id}` for ATA control
- ✅ PUT `/api/atwunit/{id}` for ATW control
- ✅ ATW 3-way valve behavior simulation (basic)
- ✅ Stateful device state (per-device persistence)
- ✅ Permissive validation (accept all values, log warnings)
- ✅ Console logging of all commands
- ✅ Realistic response formats (from API reference docs)

### Phase 2: Enhancements (Optional)

- 🎯 Temperature drift simulation
- 🎯 Advanced 3-way valve transitions (timing, ramp-up)
- 🎯 Error injection modes
- 🎯 Configuration file for custom devices
- 🎯 Energy consumption endpoints

### Out of Scope

- ❌ Schedule management endpoints
- ❌ WebSocket/real-time updates
- ❌ Persistence to disk (in-memory only)
- ❌ Multi-unit holiday/frost modes (complex batch operations)
- ❌ Automated test integration

---

## File Structure

```
tools/
├── mock_melcloud_server.py      # Main server implementation (NEW)
├── mock_server_config.json      # Optional: configurable devices (FUTURE)
├── deploy_custom_component.py   # Existing - optionally enhanced
└── README.md                    # Update with mock server docs

docs/
└── development/
    └── mock-server-guide.md     # Usage guide (NEW)
```

---

## Data Model

### Device State Storage

```python
from typing import Dict, Any

# Class-based approach (preferred over global dicts)
# Each instance has its own state, making testing and multi-instance scenarios easier

class MockMELCloudServer:
    """Mock server with encapsulated state."""

    def __init__(self):
        self.ata_states: Dict[str, Dict[str, Any]] = {
            "ata-living-room": {
                "name": "Virtual Living Room AC",  # Used in givenDisplayName
                "power": True,
                "operation_mode": "Heat",
                "set_temperature": 21.0,
                "room_temperature": 20.5,
                "set_fan_speed": "Auto",
                "vane_vertical_direction": "Auto",
                "vane_horizontal_direction": "Auto",
                "in_standby_mode": False,
                "is_in_error": False,
            },
            # ... more ATA devices
        }

        self.atw_states: Dict[str, Dict[str, Any]] = {
            "atw-house-heatpump": {
                "name": "House Heat Pump",  # Used in givenDisplayName
                "power": True,
                "operation_mode": "HeatRoomTemperature",  # STATUS: What's heating now
                "operation_mode_zone1": "HeatRoomTemperature",  # CONTROL: How to heat zone
                "set_temperature_zone1": 21.0,
                "room_temperature_zone1": 20.0,
                "set_tank_water_temperature": 50.0,
                "tank_water_temperature": 48.5,
                "forced_hot_water_mode": False,
                "has_zone2": False,
                "in_standby_mode": False,
                "is_in_error": False,
                "ftc_model": 4,  # FTC6 model
            },
            # ... more ATW devices
        }
```

        self.buildings: Dict[str, Dict[str, Any]] = {
            "building-home": {
                "id": "building-home",
                "name": "My Home",
                "timezone": "Europe/London",
                "ata_unit_ids": ["ata-living-room", "ata-bedroom"],
                "atw_unit_ids": ["atw-house-heatpump"],
            },
        }

## Design Decisions

### 1. Permissive Validation Approach

**Decision:** Accept all control values without validation, log warnings for suspicious values

**Rationale:**

- Simpler implementation
- Useful for testing edge cases in integration
- Mock server shouldn't block development
- Integration's own validation is what matters

**Implementation:**

```python
if body.get("setTemperature") is not None:
    temp = body["setTemperature"]
    state["set_temperature"] = temp

    # Warn but don't reject
    if temp < 10 or temp > 35:
        print(f"   ⚠️  Temperature {temp}°C outside typical range (10-35°C)")
```

### 2. No Authentication Validation

**Decision:** Accept all requests without checking authorization tokens

**Rationale:**

- Local development tool only
- Simplifies implementation
- No security concerns (localhost only)
- Integration can test auth flow with real API

**Note:** Login endpoint returns valid-looking tokens for integration compatibility, but subsequent requests don't validate them.

### 3. Class-Based Architecture

**Decision:** Use class-based approach with instance state, not global variables

**Rationale:**

- Better encapsulation
- Easier to test (can create multiple instances)
- Can reset state without restarting server
- More Pythonic

### 4. Default Device Configuration

**Decision:** Include 2 ATA + 1 ATW device in 1 building by default

**Default Setup:**

```python
Building: "My Home"
├── ATA: "Virtual Living Room AC" (ata-living-room)
├── ATA: "Virtual Bedroom AC" (ata-bedroom)
└── ATW: "House Heat Pump" (atw-house-heatpump)
```

**Rationale:**

- Realistic multi-device scenario
- Tests ATA climate entities (multiple)
- Tests ATW climate + water_heater entities
- Tests discovery with mixed device types
- Not overwhelming (3 devices total)

### 5. Command-Line Arguments

**Decision:** Support `--port` and `--host` arguments

**Usage:**

```bash
python tools/mock_melcloud_server.py              # Default: 0.0.0.0:8080
python tools/mock_melcloud_server.py --port 9090  # Custom port
python tools/mock_melcloud_server.py --host 127.0.0.1 --port 8888  # Custom both
```

**Rationale:**

- `--port`: Essential if default port (8080) is in use
- `--host`: Useful for controlling network access (localhost only vs network-wide)
- No `--config` in MVP: Keeps implementation simple, can add later if needed

---

## Implementation Steps

### Step 1: Core Server Setup

**File:** `tools/mock_melcloud_server.py`

```python
from aiohttp import web
import json
import asyncio
from typing import Any, Dict

class MockMELCloudServer:
    """Mock MELCloud Home API server supporting ATA and ATW devices."""

    def __init__(self):
        self.ata_states = self._init_ata_devices()
        self.atw_states = self._init_atw_devices()
        self.buildings = self._init_buildings()

    def _init_ata_devices(self) -> Dict[str, Dict[str, Any]]:
        """Initialize default ATA device states."""
        return {
            "ata-living-room": {...},
            "ata-bedroom": {...},
        }

    def _init_atw_devices(self) -> Dict[str, Dict[str, Any]]:
        """Initialize default ATW device states."""
        return {
            "atw-house-heatpump": {...},
        }

    def _init_buildings(self) -> Dict[str, Dict[str, Any]]:
        """Initialize building structure."""
        return {...}

    def create_app(self) -> web.Application:
        """Create aiohttp application with routes."""
        app = web.Application()

        # Authentication
        app.router.add_post('/api/auth/login', self.handle_login)
        app.router.add_post('/api/login', self.handle_login)

        # Device discovery (SHARED endpoint - returns both types)
        app.router.add_get('/api/user/context', self.handle_user_context)

        # Device control (SEPARATE endpoints per type)
        app.router.add_put('/api/ataunit/{unit_id}', self.handle_ata_control)
        app.router.add_put('/api/atwunit/{unit_id}', self.handle_atw_control)

        return app
```

### Step 2: Authentication Handler

**Same for both device types** (shared OAuth session):

```python
async def handle_login(self, request: web.Request) -> web.Response:
    """Mock OAuth login endpoint.

    Architecture: Shared authentication for all device types (architecture:line 13)

    Note: No token validation in subsequent requests (design decision).
    Returns valid-looking tokens for integration compatibility.
    """
    body = await request.json()

    # Accept any credentials for testing (permissive approach)
    if body.get("email") and body.get("password"):
        print(f"🔐 Login: {body.get('email')} (mock - always succeeds)")
        return web.json_response({
            "access_token": "mock-access-token-abc123",
            "refresh_token": "mock-refresh-token-xyz789",
            "expires_in": 3600,
            "token_type": "Bearer"
        })

    return web.json_response(
        {"error": "invalid_credentials"},
        status=401
    )
```

### Step 3: User Context Handler (Multi-Type Response)

**Critical:** Returns BOTH ATA and ATW devices in one response (architecture:line 100)

```python
async def handle_user_context(self, request: web.Request) -> web.Response:
    """GET /api/user/context - Returns all devices (both types).

    Architecture: Multi-type container (architecture:line 14)
    Format: {buildings: [{airToAirUnits: [...], airToWaterUnits: [...]}]}
    """

    buildings_response = []

    for building_id, building in self.buildings.items():
        # Build ATA units array
        ata_units = []
        for unit_id in building["ata_unit_ids"]:
            state = self.ata_states[unit_id]
            ata_units.append({
                "id": unit_id,
                "givenDisplayName": state.get("name", unit_id),
                "rssi": -45,
                "scheduleEnabled": False,
                "settings": self._build_ata_settings(unit_id),
                "capabilities": self._get_ata_capabilities(),
                "schedule": []
            })

        # Build ATW units array
        atw_units = []
        for unit_id in building["atw_unit_ids"]:
            state = self.atw_states[unit_id]
            atw_units.append({
                "id": unit_id,
                "givenDisplayName": state.get("name", unit_id),
                "rssi": -42,
                "scheduleEnabled": False,
                "settings": self._build_atw_settings(unit_id),
                "capabilities": self._get_atw_capabilities(),
                "schedule": []
            })

        buildings_response.append({
            "id": building_id,
            "name": building["name"],
            "timezone": building["timezone"],
            "airToAirUnits": ata_units,      # ATA devices
            "airToWaterUnits": atw_units,    # ATW devices
        })

    return web.json_response({
        "buildings": buildings_response
    })
```

### Step 4: ATA Control Handler

**Format:** From `docs/api/ata-api-reference.md`

```python
async def handle_ata_control(self, request: web.Request) -> web.Response:
    """PUT /api/ataunit/{unit_id} - Control ATA device.

    Architecture: Device-specific endpoint (architecture:line 49)
    Reference: docs/api/ata-api-reference.md
    """
    unit_id = request.match_info.get('unit_id')
    body = await request.json()

    if unit_id not in self.ata_states:
        return web.json_response(
            {"error": f"Device {unit_id} not found"},
            status=404
        )

    print(f"\n🌡️  ATA Control: {unit_id}")
    print(f"   {json.dumps(body, indent=2)}")

    state = self.ata_states[unit_id]

    # Update state based on non-null values (sparse update pattern)
    # Permissive: Accept all values, warn if suspicious

    if body.get("power") is not None:
        state["power"] = body["power"]
        print(f"   ✅ Power: {body['power']}")

    if body.get("operationMode") is not None:
        mode = body["operationMode"]
        valid_modes = ["Heat", "Cool", "Automatic", "Dry", "Fan"]
        if mode not in valid_modes:
            print(f"   ⚠️  Unusual operation mode: {mode}")
        state["operation_mode"] = mode
        print(f"   ✅ Mode: {mode}")

    if body.get("setTemperature") is not None:
        temp = body["setTemperature"]
        if temp < 10 or temp > 35:
            print(f"   ⚠️  Temperature {temp}°C outside typical range (10-35°C)")
        state["set_temperature"] = temp
        print(f"   ✅ Temperature: {temp}°C")

    if body.get("setFanSpeed") is not None:
        state["set_fan_speed"] = body["setFanSpeed"]
        print(f"   ✅ Fan: {body['setFanSpeed']}")

    if body.get("vaneVerticalDirection") is not None:
        state["vane_vertical_direction"] = body["vaneVerticalDirection"]
        print(f"   ✅ Vertical Vane: {body['vaneVerticalDirection']}")

    if body.get("vaneHorizontalDirection") is not None:
        state["vane_horizontal_direction"] = body["vaneHorizontalDirection"]
        print(f"   ✅ Horizontal Vane: {body['vaneHorizontalDirection']}")

    if body.get("inStandbyMode") is not None:
        state["in_standby_mode"] = body["inStandbyMode"]
        print(f"   ✅ Standby: {body['inStandbyMode']}")

    # Real API returns 200 with empty body
    return web.Response(status=200, body=b"")
```

### Step 5: ATW Control Handler

**Format:** From `docs/api/atw-api-reference.md`

```python
async def handle_atw_control(self, request: web.Request) -> web.Response:
    """PUT /api/atwunit/{unit_id} - Control ATW device.

    Architecture: Device-specific endpoint (architecture:line 50)
    Reference: docs/api/atw-api-reference.md
    3-Way Valve: architecture:line 264-305
    """
    unit_id = request.match_info.get('unit_id')
    body = await request.json()

    if unit_id not in self.atw_states:
        return web.json_response(
            {"error": f"Device {unit_id} not found"},
            status=404
        )

    print(f"\n♨️  ATW Control: {unit_id}")
    print(f"   {json.dumps(body, indent=2)}")

    state = self.atw_states[unit_id]

    # Update state based on non-null values
    if body.get("power") is not None:
        state["power"] = body["power"]
        print(f"   ✅ Power: {body['power']}")

    if body.get("setTemperatureZone1") is not None:
        state["set_temperature_zone1"] = body["setTemperatureZone1"]
        print(f"   ✅ Zone 1 Target: {body['setTemperatureZone1']}°C")

    if body.get("operationModeZone1") is not None:
        state["operation_mode_zone1"] = body["operationModeZone1"]
        print(f"   ✅ Zone 1 Mode: {body['operationModeZone1']}")

    if body.get("setTankWaterTemperature") is not None:
        state["set_tank_water_temperature"] = body["setTankWaterTemperature"]
        print(f"   ✅ DHW Target: {body['setTankWaterTemperature']}°C")

    if body.get("forcedHotWaterMode") is not None:
        state["forced_hot_water_mode"] = body["forcedHotWaterMode"]
        print(f"   ✅ Forced DHW: {body['forcedHotWaterMode']}")

    # Update operation_mode STATUS based on 3-way valve logic
    self._update_atw_operation_mode(unit_id)

    # Real API returns 200 with empty body
    return web.Response(status=200, body=b"")


def _update_atw_operation_mode(self, unit_id: str):
    """Update ATW operation_mode STATUS field based on 3-way valve logic.

    Architecture: 3-way valve behavior (architecture:line 39-44, 264-305)

    Logic:
    - If forced_hot_water_mode: "HotWater"
    - Else if DHW < target: "HotWater"
    - Else if Zone < target: operation_mode_zone1 value
    - Else: "Stop"

    Critical: operation_mode is STATUS (read-only), not control parameter
    """
    state = self.atw_states[unit_id]

    if not state["power"]:
        state["operation_mode"] = "Stop"
        return

    # Forced DHW mode takes priority
    if state["forced_hot_water_mode"]:
        state["operation_mode"] = "HotWater"
        return

    # Check if DHW needs heating
    dhw_needs_heat = state["tank_water_temperature"] < state["set_tank_water_temperature"]

    # Check if Zone 1 needs heating
    zone_needs_heat = state["room_temperature_zone1"] < state["set_temperature_zone1"]

    if dhw_needs_heat:
        state["operation_mode"] = "HotWater"
    elif zone_needs_heat:
        state["operation_mode"] = state["operation_mode_zone1"]
    else:
        state["operation_mode"] = "Stop"
```

### Step 6: Build Settings Arrays

**ATA Settings Format:**

```python
def _build_ata_settings(self, unit_id: str) -> list[dict]:
    """Build ATA settings array from state dict.

    Format: Array of {name, value} pairs (ata-api-reference.md:line 138)
    Boolean values as strings: "True"/"False"

    Note: Returns minimal field set for MVP. Real API returns 20+ fields.
    Add more fields (WiFi status, error codes, etc.) as needed.
    """
    state = self.ata_states[unit_id]
    return [
        {"name": "Power", "value": str(state["power"])},
        {"name": "OperationMode", "value": state["operation_mode"]},
        {"name": "SetTemperature", "value": str(state["set_temperature"])},
        {"name": "RoomTemperature", "value": str(state["room_temperature"])},
        {"name": "SetFanSpeed", "value": state["set_fan_speed"]},
        {"name": "VaneVerticalDirection", "value": state["vane_vertical_direction"]},
        {"name": "VaneHorizontalDirection", "value": state["vane_horizontal_direction"]},
        {"name": "InStandbyMode", "value": str(state["in_standby_mode"])},
        {"name": "IsInError", "value": str(state["is_in_error"])},
    ]
```

**ATW Settings Format:**

```python
def _build_atw_settings(self, unit_id: str) -> list[dict]:
    """Build ATW settings array from state dict.

    Format: Array of {name, value} pairs (atw-api-reference.md:line 66)
    Note: OperationMode is STATUS field (what's heating now)

    Note: Returns minimal field set for MVP. Real API returns 25+ fields:
    - FlowTemperature, ReturnTemperature, OutdoorTemperature
    - IdleZone1, IdleZone2
    - Holiday mode, Prohibit flags
    Add more as integration needs them.
    """
    state = self.atw_states[unit_id]
    return [
        {"name": "Power", "value": str(state["power"])},
        {"name": "OperationMode", "value": state["operation_mode"]},  # STATUS
        {"name": "OperationModeZone1", "value": state["operation_mode_zone1"]},  # CONTROL
        {"name": "SetTemperatureZone1", "value": str(state["set_temperature_zone1"])},
        {"name": "RoomTemperatureZone1", "value": str(state["room_temperature_zone1"])},
        {"name": "SetTankWaterTemperature", "value": str(state["set_tank_water_temperature"])},
        {"name": "TankWaterTemperature", "value": str(state["tank_water_temperature"])},
        {"name": "ForcedHotWaterMode", "value": str(state["forced_hot_water_mode"])},
        {"name": "HasZone2", "value": str(int(state["has_zone2"]))},  # 0 or 1
        {"name": "InStandbyMode", "value": str(state["in_standby_mode"])},
        {"name": "IsInError", "value": str(state["is_in_error"])},
        {"name": "FTCModel", "value": str(state["ftc_model"])},
    ]
```

### Step 7: Device Capabilities

**ATA Capabilities:**

```python
def _get_ata_capabilities(self) -> dict:
    """Get ATA device capabilities.

    Reference: ata-api-reference.md:line 474
    """
    return {
        "numberOfFanSpeeds": 5,
        "minTempHeat": 10.0,
        "maxTempHeat": 31.0,
        "minTempCoolDry": 16.0,
        "maxTempCoolDry": 31.0,
        "minTempAutomatic": 16.0,
        "maxTempAutomatic": 31.0,
        "hasHalfDegreeIncrements": True,
        "hasExtendedTemperatureRange": True,
        "hasAutomaticFanSpeed": True,
        "hasSwing": True,
        "hasAirDirection": True,
        "hasCoolOperationMode": True,
        "hasHeatOperationMode": True,
        "hasAutoOperationMode": True,
        "hasDryOperationMode": True,
        "hasStandby": False,
    }
```

**ATW Capabilities:**

```python
def _get_atw_capabilities(self) -> dict:
    """Get ATW device capabilities.

    Reference: atw-api-reference.md
    """
    return {
        "hasHotWater": True,
        "minSetTankTemperature": 40.0,
        "maxSetTankTemperature": 60.0,
        "minSetTemperature": 10.0,
        "maxSetTemperature": 30.0,
        "hasHalfDegrees": True,
        "hasZone2": False,
        "hasThermostatZone1": True,
        "hasHeatZone1": True,
        "hasMeasuredEnergyConsumption": True,
        "hasEstimatedEnergyConsumption": False,
        "ftcModel": 4,  # FTC6
    }
```

---

## Console Logging

### Startup Message

```
🚀 Starting Mock MELCloud Home API Server
================================================================
Server running at: http://0.0.0.0:8080

📋 Configure Home Assistant with:
   Email: test@example.com (any credentials work)
   Password: test123

🏢 Buildings:
   📍 My Home (building-home)

🔌 Mock Devices:
   🌡️  ATA (Air-to-Air) - 2 devices:
       • Virtual Living Room AC (ata-living-room)
       • Virtual Bedroom AC (ata-bedroom)

   ♨️  ATW (Air-to-Water) - 1 device:
       • House Heat Pump (atw-house-heatpump)
         - Zone 1: Space heating (20.0°C → 21.0°C)
         - DHW Tank: Hot water (48.5°C → 50.0°C)

💡 Tip: Use --port and --host to customize server address

Press Ctrl+C to stop
================================================================
```

### Control Command Logging

```
🌡️  ATA Control: ata-living-room
   {
     "power": null,
     "operationMode": "Cool",
     "setTemperature": 22.0,
     ...
   }
   ✅ Mode: Cool
   ✅ Temperature: 22.0°C

📊 State: Power=True, Mode=Cool, Target=22.0°C, Current=20.5°C

---

♨️  ATW Control: atw-house-heatpump
   {
     "setTemperatureZone1": 21.0,
     "forcedHotWaterMode": true,
     ...
   }
   ✅ Zone 1 Target: 21.0°C
   ✅ Forced DHW: True

📊 State: Zone1=20.0°C→21.0°C, DHW=48.5°C→50.0°C
   🔄 3-Way Valve: → DHW TANK (Forced Hot Water Mode)
   ⚠️  Zone 1 heating suspended
```

---

## API Compliance Checklist

### ATA (Air-to-Air) Requirements

**From:** `docs/api/ata-api-reference.md`

- ✅ Operation modes: "Heat", "Cool", "Automatic" (NOT "Auto"), "Dry", "Fan"
- ✅ Fan speeds: STRINGS "Auto", "One", "Two", "Three", "Four", "Five" (NOT integers)
- ✅ Vane vertical: "Auto", "Swing", "One"-"Five"
- ✅ Vane horizontal: "Auto", "Swing", "Left", "LeftCentre", "Centre", "RightCentre", "Right"
- ✅ Temperature range: 10.0-31.0°C (Heat), 16.0-31.0°C (Cool/Dry/Auto)
- ✅ Temperature increments: 0.5°C supported
- ✅ Settings format: Array of {name, value} pairs
- ✅ Boolean values: Strings "True"/"False"
- ✅ PUT response: 200 with empty body

### ATW (Air-to-Water) Requirements

**From:** `docs/api/atw-api-reference.md`

- ✅ Operation modes (Zone 1): "HeatRoomTemperature", "HeatFlowTemperature", "HeatCurve"
- ✅ Operation mode (STATUS): "Stop", "HotWater", or zone mode value
- ✅ Zone 1 temperature range: 10.0-30.0°C
- ✅ DHW temperature range: 40.0-60.0°C
- ✅ Temperature increments: 0.5°C or 1.0°C depending on device
- ✅ Forced hot water mode: Boolean
- ✅ Zone 2: Only if hasZone2=true
- ✅ Settings format: Array of {name, value} pairs
- ✅ Boolean values: Strings "True"/"False"
- ✅ HasZone2: Integer 0 or 1
- ✅ PUT response: 200 with empty body

### Shared Requirements

- ✅ Authentication: Accept any credentials, return OAuth tokens
- ✅ GET /api/user/context: Return both airToAirUnits and airToWaterUnits arrays
- ✅ Sparse updates: Only update non-null fields
- ✅ Case sensitivity: Exact string matching for all values

---

## Usage Examples

### Start Server

```bash
# Default: 0.0.0.0:8080
python tools/mock_melcloud_server.py

# Custom port
python tools/mock_melcloud_server.py --port 9090

# Custom host (localhost only)
python tools/mock_melcloud_server.py --host 127.0.0.1

# Both custom
python tools/mock_melcloud_server.py --host 127.0.0.1 --port 8888
```

### Configure HA Integration

**Option 1:** Add `base_url` support to integration config flow

**Option 2:** Use hosts file redirect

```bash
sudo echo "127.0.0.1 melcloudhome.com" >> /etc/hosts
```

**Option 3:** SSH tunnel for remote HA

```bash
ssh -L 80:localhost:8080 ha
```

### Test ATA Control

```bash
# Set ATA temperature
curl -X PUT http://localhost:8080/api/ataunit/ata-living-room \
  -H "Content-Type: application/json" \
  -d '{
    "power": null,
    "operationMode": "Cool",
    "setFanSpeed": null,
    "vaneHorizontalDirection": null,
    "vaneVerticalDirection": null,
    "setTemperature": 22.5,
    "temperatureIncrementOverride": null,
    "inStandbyMode": null
  }'

# Verify state
curl http://localhost:8080/api/user/context | \
  jq '.buildings[0].airToAirUnits[0].settings'
```

### Test ATW Control

```bash
# Set ATW zone temperature
curl -X PUT http://localhost:8080/api/atwunit/atw-house-heatpump \
  -H "Content-Type: application/json" \
  -d '{
    "power": null,
    "setTemperatureZone1": 21.0,
    "setTemperatureZone2": null,
    "operationModeZone1": null,
    "operationModeZone2": null,
    "setTankWaterTemperature": null,
    "forcedHotWaterMode": null,
    "setHeatFlowTemperatureZone1": null,
    "setCoolFlowTemperatureZone1": null,
    "setHeatFlowTemperatureZone2": null,
    "setCoolFlowTemperatureZone2": null
  }'

# Set DHW temperature
curl -X PUT http://localhost:8080/api/atwunit/atw-house-heatpump \
  -H "Content-Type: application/json" \
  -d '{
    "setTankWaterTemperature": 50.0,
    ...all others null...
  }'

# Enable forced hot water mode
curl -X PUT http://localhost:8080/api/atwunit/atw-house-heatpump \
  -H "Content-Type: application/json" \
  -d '{
    "forcedHotWaterMode": true,
    ...all others null...
  }'
```

---

## Architecture Compliance

This implementation follows the architecture defined in `docs/architecture.md`:

### 1. Single Unified Client Pattern

- ✅ One mock server handles both device types (architecture:line 12)
- ✅ Method differentiation by endpoint, not separate servers

### 2. Shared Authentication

- ✅ One OAuth session serves all devices (architecture:line 13)
- ✅ Same login endpoint for both types

### 3. Multi-Type Container

- ✅ UserContext returns both `airToAirUnits[]` and `airToWaterUnits[]` (architecture:line 14)
- ✅ Single GET endpoint returns all devices (architecture:line 77)

### 4. Device-Specific Methods

- ✅ Separate control endpoints: `/api/ataunit/*` vs `/api/atwunit/*` (architecture:lines 49-50)
- ✅ Different request payloads per device type

### 5. 3-Way Valve Awareness

- ✅ ATW mock simulates valve behavior (architecture:line 264-305)
- ✅ `operation_mode` reflects current heating target (STATUS)
- ✅ `operation_mode_zone1` is the control parameter
- ✅ Forced DHW mode prioritizes hot water

---

## Testing Plan

### Manual Testing Checklist

**Server Startup:**

- [ ] Server starts without errors
- [ ] Welcome message displays correctly
- [ ] Both ATA and ATW devices listed

**Authentication:**

- [ ] Login endpoint accepts credentials
- [ ] Returns valid OAuth token structure

**Device Discovery:**

- [ ] GET /api/user/context returns valid JSON
- [ ] Both `airToAirUnits` and `airToWaterUnits` arrays present
- [ ] Settings arrays formatted correctly
- [ ] Capabilities present for both types

**ATA Control:**

- [ ] Can set temperature
- [ ] Can change operation mode
- [ ] Can change fan speed
- [ ] Can adjust vane positions
- [ ] State persists across polls
- [ ] Console logs commands clearly

**ATW Control:**

- [ ] Can set zone 1 temperature
- [ ] Can set DHW temperature
- [ ] Can change zone operation mode
- [ ] Can toggle forced hot water mode
- [ ] 3-way valve status updates correctly
- [ ] State persists across polls
- [ ] Console logs commands clearly

**Home Assistant Integration:**

- [ ] HA can connect to mock server
- [ ] All ATA devices discovered
- [ ] All ATW devices discovered
- [ ] ATA climate entities work
- [ ] ATW climate entities work
- [ ] ATW water_heater entities work
- [ ] State changes reflected in HA UI

---

## Future Enhancements

### Phase 2: Advanced Behavior Simulation

**Temperature Drift:**

```python
async def simulate_temperature_drift():
    """Simulate realistic temperature changes over time."""
    while True:
        await asyncio.sleep(60)  # Every minute

        # ATA: Move room temp toward target
        for unit_id, state in self.ata_states.items():
            if state["power"] and state["room_temperature"] != state["set_temperature"]:
                diff = state["set_temperature"] - state["room_temperature"]
                state["room_temperature"] += 0.1 if diff > 0 else -0.1

        # ATW: Simulate 3-way valve heating
        for unit_id, state in self.atw_states.items():
            if not state["power"]:
                continue

            if state["operation_mode"] == "HotWater":
                # Heating DHW, zone cools naturally
                if state["tank_water_temperature"] < state["set_tank_water_temperature"]:
                    state["tank_water_temperature"] += 0.2
                state["room_temperature_zone1"] -= 0.05  # Natural cooling

            elif state["operation_mode"] in ["HeatRoomTemperature", "HeatFlowTemperature", "HeatCurve"]:
                # Heating zone, DHW cools naturally
                if state["room_temperature_zone1"] < state["set_temperature_zone1"]:
                    state["room_temperature_zone1"] += 0.1
                state["tank_water_temperature"] -= 0.05  # Natural cooling
```

**Error Injection:**

```python
async def handle_ata_control_with_errors(self, request):
    """Version with random error injection for testing."""
    import random

    # 5% chance of server error
    if random.random() < 0.05:
        return web.json_response({"error": "Internal server error"}, status=500)

    # 2% chance of auth error
    if random.random() < 0.02:
        return web.json_response({"error": "Unauthorized"}, status=401)

    # Normal processing
    return await self.handle_ata_control(request)
```

**Configuration File Support:**

```python
def load_config(config_path: str = "tools/mock_server_config.json"):
    """Load device configuration from JSON file."""
    with open(config_path) as f:
        config = json.load(f)

    # Build state dicts from config
    # Allows users to customize devices without editing code
```

### Phase 3: Advanced Features

- [ ] Zone 2 support for ATW (if hasZone2=true)
- [ ] Energy consumption endpoints
- [ ] Schedule data in responses
- [ ] Web UI for monitoring requests
- [ ] HTTP request logging to file
- [ ] Docker container
- [ ] Multiple building support

---

## Implementation Checklist

### Core Implementation

- [ ] Create `tools/mock_melcloud_server.py`
- [ ] Implement MockMELCloudServer class
- [ ] Add ATA device state storage
- [ ] Add ATW device state storage
- [ ] Add building structure
- [ ] Implement authentication handler
- [ ] Implement user context handler (multi-type)
- [ ] Implement ATA control handler
- [ ] Implement ATW control handler
- [ ] Implement ATW 3-way valve logic (Phase 1 - MVP)
- [ ] Add permissive validation with warnings
- [ ] Add ATA settings builder
- [ ] Add ATW settings builder
- [ ] Add ATA capabilities
- [ ] Add ATW capabilities
- [ ] Add console logging with startup banner
- [ ] Add command-line arguments (`--port`, `--host`)
- [ ] Add default device configuration (2 ATA, 1 ATW, 1 building)

### Testing

- [ ] Test authentication endpoint
- [ ] Test user context returns both types
- [ ] Test ATA control endpoint
- [ ] Test ATW control endpoint
- [ ] Test state persistence across polls
- [ ] Test with real HA instance
- [ ] Verify all ATA entities discovered
- [ ] Verify all ATW entities discovered
- [ ] Verify ATA control works via HA UI
- [ ] Verify ATW control works via HA UI
- [ ] Verify ATW 3-way valve behavior

### Documentation

- [ ] Write `docs/development/mock-server-guide.md`
- [ ] Update `tools/README.md`
- [ ] Update `CLAUDE.md`
- [ ] Add usage examples to repository README

### Optional Enhancements

- [ ] Add temperature drift simulation
- [ ] Add error injection modes
- [ ] Add configuration file support
- [ ] Integrate with deployment tool
- [ ] Add Zone 2 support

---

## Dependencies

**Minimal - only standard library + aiohttp:**

```python
# Standard library
import asyncio
import json
import argparse
from typing import Any, Dict

# Already in pyproject.toml
from aiohttp import web
```

No additional dependencies required.

---

## Estimated Effort

- **Core implementation (both ATA + ATW):** 4-6 hours
- **Testing & debugging:** 2-3 hours
- **Documentation:** 1-2 hours
- **Optional enhancements:** 2-4 hours per feature

**Total MVP:** ~7-11 hours

---

## Success Criteria

### Minimum Viable Product

✅ Developer can start mock server with one command
✅ Server displays both ATA and ATW devices available
✅ No authentication validation required (permissive for development)
✅ Accepts all control values (warns if suspicious)
✅ HA integration can connect to mock server
✅ Mock ATA devices appear in HA as climate entities
✅ Mock ATW devices appear in HA as climate + water_heater entities
✅ Controlling ATA devices via HA UI works
✅ Controlling ATW devices via HA UI works
✅ ATW shows correct operation_mode status (basic 3-way valve logic)
✅ State changes visible in next poll
✅ Console shows clear feedback of all commands with warnings

### Stretch Goals

🎯 Multiple devices of each type tracked independently
🎯 Multiple buildings supported
🎯 ATW 3-way valve behavior simulated realistically
🎯 Temperature drift simulation
🎯 Error injection for testing error handling
🎯 Configuration file for custom devices

---

## Key Design Decisions

### 1. Why single server for both types?

- Matches real API architecture (single endpoint)
- Simpler deployment (one process)
- Shared authentication realistic
- Single `UserContext` response

### 2. Why separate control endpoints?

- Matches real API structure
- Different payload formats
- Device-specific validation
- Clear separation of concerns

### 3. Why simulate 3-way valve?

- Critical for ATW understanding
- Reflects physical hardware limitation
- Helps test HA entity state updates
- Educational for developers

### 4. Why in-memory state only?

- Simpler implementation
- Restart = fresh state (predictable)
- Sufficient for development
- Can add persistence later

### 5. Why no Zone 2 initially?

- Most devices don't have Zone 2
- Adds complexity
- Can add incrementally
- Focus on common case first

---

## References

- **Architecture:** `docs/architecture.md`
- **ATA API Reference:** `docs/api/ata-api-reference.md`
- **ATW API Reference:** `docs/api/atw-api-reference.md`
- **Data Models:** `custom_components/melcloudhome/api/models.py`
- **Client Implementation:** `custom_components/melcloudhome/api/client.py`
- **ADR-011:** `docs/decisions/011-multi-device-type-architecture.md`
