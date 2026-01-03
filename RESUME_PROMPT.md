# Resume: Air-to-Water (ATW) Heat Pump API Implementation

**Branch:** `feature/atw-heat-pump-support`
**Status:** Phase 1 in development - API layer implementation
**Date:** 2026-01-03

---

## Prepared Architecture

### 1. Architectural Documentation

**Commit:** `33603fb` - "docs: Add comprehensive Air-to-Water (ATW) heat pump architecture documentation"

**Created:**

- `docs/decisions/011-multi-device-type-architecture.md` - Decision to extend current module
- `docs/api/atw-api-reference.md` - Complete ATW API specification
- `docs/api/device-type-comparison.md` - A2A vs A2W side-by-side reference
- `docs/architecture.md` - System architecture with 4 Mermaid diagrams
- `docs/research/ATW/tested-hardware.md` - EHSCVM2D Hydrokit confirmed
- `docs/research/ATW/learnings-coverage-analysis.md` - Research coverage tracking
- `openapi.yaml` updated to v2.0.0 with ATW endpoints and schemas

**Renamed:**

- `docs/api/melcloudhome-api-reference.md` → `docs/api/ata-api-reference.md`

### 2. Research Artifacts (Committed)

**HAR Files:**

- `docs/research/ATW/melcloudhome_com_recording2_anonymized.har` (107 API calls)
- `docs/research/ATW/melcloudhome_com_recording3_anonymized.har` (30 targeted tests)

**Analysis:**

- `docs/research/ATW/MelCloud_ATW_Complete_API_Documentation.md`
- `docs/research/ATW/MelCloud_ATW_API_Reference.md`

### 3. Key Architectural Decisions

**Decision:** Extend current `MELCloudHomeClient` module (not separate module/package)

**Rationale:**

- 90% API overlap (auth, session, control patterns)
- UserContext endpoint already returns both device types
- Maintains ADR-001 "Bundled API Client" principle
- Natural separation via method naming

**Temperature Strategy:** Use safe hardcoded defaults (10-30°C Zone, 40-60°C DHW)

**OperationMode:** Expose 3-way valve status to users (Stop/HotWater/Zone)

### 4. Key Architectural Decisions

**Design approach:**

- ✅ **Two-phase implementation:** Phase 1 (read-only), Phase 2 (control)
- ✅ **Zone 2:** Stub with validation only (NotImplementedError)
- ✅ **Schedules:** Defer (check HAR files separately for integer mapping)
- ✅ **Telemetry:** Defer to coordinator implementation (not in API client)
- ✅ **Naming:** Rename OperationMode → `operation_status` (avoid confusion)
- ✅ **Capabilities:** Always use hardcoded safe defaults (ignore API values)
- ✅ **Flow Temps:** Defer (only support HeatRoomTemperature mode in Phase 1)
- ✅ **Errors:** Don't implement (match A2A approach - no error log fetching)

---

## Implementation Strategy: Two Phases

### Phase 1: Read-Only Support (THIS PHASE)

**Goal:** Safely parse and display ATW device state

**Scope:**

- Models with parsing logic
- Capabilities with safe defaults
- UserContext integration
- Status reading (all fields including operation_status)
- Zone 1 only (Zone 2 stubbed)
- NO control methods
- NO schedule support
- NO telemetry (deferred to coordinator)

**Benefits:**

- Can test with real hardware before adding control
- Validates model parsing is correct
- De-risks temperature ranges and capabilities
- Allows coordinator development to proceed

### Phase 2: Control Support (LATER)

**Scope:**

- All control methods (power, zone temp, DHW temp, mode, forced DHW)
- Holiday mode and frost protection
- Full validation logic
- Control tests

**Deferred to Future:**

- Zone 2 control (hardware unavailable)
- Flow temperature mode support (advanced feature)
- Schedule creation (integer mapping unknown)
- Telemetry endpoints (coordinator decision)

---

## Phase 1 Implementation Requirements

### 1. Extend `const.py`

**Add ATW-specific constants:**

```python
# ============================================================================
# Air-to-Water (Heat Pump) Constants
# ============================================================================

# API Endpoints - ATW
API_ATW_CONTROL_UNIT = "/api/atwunit/{unit_id}"
API_ATW_ERROR_LOG = "/api/atwunit/{unit_id}/errorlog"
API_ATW_SCHEDULE_CREATE = "/api/atwcloudschedule/{unit_id}"
API_ATW_SCHEDULE_DELETE = "/api/atwcloudschedule/{unit_id}/{schedule_id}"
API_ATW_SCHEDULE_ENABLED = "/api/atwcloudschedule/{unit_id}/enabled"
API_HOLIDAY_MODE = "/api/holidaymode"
API_FROST_PROTECTION = "/api/protection/frost"

# Operation Modes - Zone Control (Control API - Strings)
# These determine HOW the zone is heated
ATW_MODE_HEAT_ROOM_TEMP = "HeatRoomTemperature"  # Thermostat mode
ATW_MODE_HEAT_FLOW_TEMP = "HeatFlowTemperature"  # Direct flow control (DEFERRED)
ATW_MODE_HEAT_CURVE = "HeatCurve"                # Weather compensation

ATW_OPERATION_MODES_ZONE = [
    ATW_MODE_HEAT_ROOM_TEMP,
    ATW_MODE_HEAT_FLOW_TEMP,
    ATW_MODE_HEAT_CURVE,
]

# Operation Status Values (Read-only STATUS field)
# These indicate WHAT the 3-way valve is doing RIGHT NOW
ATW_STATUS_STOP = "Stop"                         # Idle (target reached)
ATW_STATUS_HOT_WATER = "HotWater"                # Heating DHW tank
# Status can also be zone mode string when heating zone

ATW_OPERATION_STATUSES = [
    ATW_STATUS_STOP,
    ATW_STATUS_HOT_WATER,
    ATW_MODE_HEAT_ROOM_TEMP,
    ATW_MODE_HEAT_FLOW_TEMP,
    ATW_MODE_HEAT_CURVE,
]

# Temperature Ranges (Celsius) - SAFE HARDCODED DEFAULTS
# DO NOT use API-reported ranges (known to be unreliable)
ATW_TEMP_MIN_ZONE = 10.0      # Zone 1 minimum (underfloor heating)
ATW_TEMP_MAX_ZONE = 30.0      # Zone 1 maximum (underfloor heating)
ATW_TEMP_MIN_DHW = 40.0       # DHW tank minimum
ATW_TEMP_MAX_DHW = 60.0       # DHW tank maximum
ATW_TEMP_STEP = 0.5           # Temperature increment (most systems)

# Note: Flow temperature ranges DEFERRED (Phase 2)
# ATW_TEMP_MIN_FLOW = 30.0    # Likely range for flow temp mode
# ATW_TEMP_MAX_FLOW = 60.0    # Likely range for flow temp mode
```

**Do NOT add yet (Phase 2 / Deferred):**

- Schedule mode integer constants (mapping unknown - check HAR files first)
- Zone 2 specific constants
- Flow temperature control constants
- Error code constants

---

### 2. Extend `models.py`

**Add ATW dataclasses with complete parsing logic:**

```python
# ============================================================================
# Air-to-Water (Heat Pump) Models
# ============================================================================

@dataclass
class AirToWaterCapabilities:
    """ATW device capability flags and limits.

    CRITICAL: Always uses safe hardcoded defaults for temperature ranges.
    API-reported ranges are unreliable (known bug history).
    """

    # DHW Support
    has_hot_water: bool = True
    min_set_tank_temperature: float = 40.0  # Safe default (HARDCODED)
    max_set_tank_temperature: float = 60.0  # Safe default (HARDCODED)

    # Zone 1 Support (always present)
    min_set_temperature: float = 10.0       # Zone 1, safe default (HARDCODED)
    max_set_temperature: float = 30.0       # Zone 1, safe default (HARDCODED)
    has_half_degrees: bool = False          # Temperature increment capability

    # Zone 2 Support (usually false)
    has_zone2: bool = False

    # Thermostat Support
    has_thermostat_zone1: bool = True
    has_thermostat_zone2: bool = True       # Capability flag (not actual support)

    # Heating Support
    has_heat_zone1: bool = True
    has_heat_zone2: bool = False

    # Energy Monitoring
    has_measured_energy_consumption: bool = False
    has_measured_energy_production: bool = False
    has_estimated_energy_consumption: bool = True
    has_estimated_energy_production: bool = True

    # FTC Model (controller type)
    ftc_model: int = 3

    # Demand Side Control
    has_demand_side_control: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AirToWaterCapabilities":
        """Create from API response dict.

        ALWAYS uses safe hardcoded temperature defaults.
        API values are parsed but ignored due to known reliability issues.
        """
        if not data:
            return cls()

        # Parse API values but IGNORE temperature ranges (use hardcoded)
        api_min_tank = data.get("minSetTankTemperature", 0)
        api_max_tank = data.get("maxSetTankTemperature", 60)
        api_min_zone = data.get("minSetTemperature", 10)
        api_max_zone = data.get("maxSetTemperature", 30)

        # Log if API values differ from safe defaults (for debugging)
        if api_min_tank != 40 or api_max_tank != 60:
            _LOGGER.debug(
                "API reported DHW range %s-%s°C, using safe default 40-60°C",
                api_min_tank, api_max_tank
            )

        if api_min_zone != 10 or api_max_zone != 30:
            _LOGGER.debug(
                "API reported Zone range %s-%s°C, using safe default 10-30°C",
                api_min_zone, api_max_zone
            )

        return cls(
            has_hot_water=data.get("hasHotWater", True),
            # ALWAYS use safe defaults (not API values)
            min_set_tank_temperature=40.0,
            max_set_tank_temperature=60.0,
            min_set_temperature=10.0,
            max_set_temperature=30.0,
            has_half_degrees=data.get("hasHalfDegrees", False),
            has_zone2=data.get("hasZone2", False),
            has_thermostat_zone1=data.get("hasThermostatZone1", True),
            has_thermostat_zone2=data.get("hasThermostatZone2", True),
            has_heat_zone1=data.get("hasHeatZone1", True),
            has_heat_zone2=data.get("hasHeatZone2", False),
            has_measured_energy_consumption=data.get("hasMeasuredEnergyConsumption", False),
            has_measured_energy_production=data.get("hasMeasuredEnergyProduction", False),
            has_estimated_energy_consumption=data.get("hasEstimatedEnergyConsumption", True),
            has_estimated_energy_production=data.get("hasEstimatedEnergyProduction", True),
            ftc_model=data.get("ftcModel", 3),
            has_demand_side_control=data.get("hasDemandSideControl", True),
        )


@dataclass
class AirToWaterUnit:
    """Air-to-water heat pump unit.

    Represents ONE physical device with TWO functional capabilities:
    - Zone 1: Space heating (underfloor/radiators)
    - DHW: Domestic hot water tank

    CRITICAL: 3-way valve limitation - can only heat Zone OR DHW at a time.
    """

    # Device Identity
    id: str
    name: str

    # Power State
    power: bool
    in_standby_mode: bool

    # Operation Status (READ-ONLY)
    # Indicates WHAT the 3-way valve is doing RIGHT NOW
    # Values: "Stop", "HotWater", or zone mode string
    operation_status: str

    # Zone 1 Control
    operation_mode_zone1: str           # HOW to heat zone (HeatRoomTemperature, etc.)
    set_temperature_zone1: float | None # Target room temperature (10-30°C)
    room_temperature_zone1: float | None # Current room temperature

    # Zone 2 (usually not present)
    has_zone2: bool
    operation_mode_zone2: str | None = None
    set_temperature_zone2: float | None = None
    room_temperature_zone2: float | None = None

    # DHW (Domestic Hot Water)
    set_tank_water_temperature: float | None  # Target DHW temp (40-60°C)
    tank_water_temperature: float | None      # Current DHW temp
    forced_hot_water_mode: bool               # DHW priority enabled

    # Device Status
    is_in_error: bool
    error_code: str | None
    rssi: int | None  # WiFi signal strength

    # Device Info
    ftc_model: int

    # Capabilities
    capabilities: AirToWaterCapabilities

    # Schedule (read-only for now - creation deferred)
    schedule: list[dict[str, Any]] = field(default_factory=list)
    schedule_enabled: bool = False

    # Holiday Mode & Frost Protection (read-only state)
    holiday_mode_enabled: bool = False
    frost_protection_enabled: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AirToWaterUnit":
        """Create from API response dict.

        The API returns device state as a list of name-value pairs in the 'settings' array.
        Example: [{"name": "Power", "value": "True"}, {"name": "SetTemperatureZone1", "value": "21"}, ...]

        This method parses the settings array and handles type conversions.
        """
        # Parse capabilities
        capabilities_data = data.get("capabilities", {})
        capabilities = AirToWaterCapabilities.from_dict(capabilities_data)

        # Parse settings array into dict for easy access
        settings_list = data.get("settings", [])
        settings = {item["name"]: item["value"] for item in settings_list}

        # Helper: Parse boolean from string
        def parse_bool(value: str | bool | None) -> bool:
            if isinstance(value, bool):
                return value
            if value is None:
                return False
            return str(value).lower() == "true"

        # Helper: Parse float from string
        def parse_float(value: str | float | None) -> float | None:
            if value is None or value == "":
                return None
            try:
                return float(value)
            except (ValueError, TypeError):
                return None

        # Helper: Parse int from string
        def parse_int(value: str | int | None) -> int | None:
            if value is None or value == "":
                return None
            try:
                return int(value)
            except (ValueError, TypeError):
                return None

        # Extract Zone 2 flag
        has_zone2 = parse_bool(settings.get("HasZone2", "False"))

        # Parse schedule (basic parsing - creation not supported yet)
        schedule_data = data.get("schedule", [])

        # Parse holiday mode and frost protection
        holiday_data = data.get("holidayMode", {})
        holiday_enabled = holiday_data.get("enabled", False) if holiday_data else False

        frost_data = data.get("frostProtection", {})
        frost_enabled = frost_data.get("enabled", False) if frost_data else False

        return cls(
            # Identity
            id=data["id"],
            name=data.get("givenDisplayName", "Unknown"),

            # Power
            power=parse_bool(settings.get("Power")),
            in_standby_mode=parse_bool(settings.get("InStandbyMode")),

            # Operation Status (READ-ONLY)
            # CRITICAL: This is "OperationMode" in API but renamed to avoid confusion
            # with operationModeZone1 (which is the control field)
            operation_status=settings.get("OperationMode", "Stop"),

            # Zone 1
            operation_mode_zone1=settings.get("OperationModeZone1", "HeatRoomTemperature"),
            set_temperature_zone1=parse_float(settings.get("SetTemperatureZone1")),
            room_temperature_zone1=parse_float(settings.get("RoomTemperatureZone1")),

            # Zone 2 (if present)
            has_zone2=has_zone2,
            operation_mode_zone2=settings.get("OperationModeZone2") if has_zone2 else None,
            set_temperature_zone2=parse_float(settings.get("SetTemperatureZone2")) if has_zone2 else None,
            room_temperature_zone2=parse_float(settings.get("RoomTemperatureZone2")) if has_zone2 else None,

            # DHW
            set_tank_water_temperature=parse_float(settings.get("SetTankWaterTemperature")),
            tank_water_temperature=parse_float(settings.get("TankWaterTemperature")),
            forced_hot_water_mode=parse_bool(settings.get("ForcedHotWaterMode")),

            # Status
            is_in_error=parse_bool(settings.get("IsInError")),
            error_code=settings.get("ErrorCode") if settings.get("ErrorCode") else None,
            rssi=data.get("rssi"),

            # Device Info
            ftc_model=data.get("ftcModel", 3),

            # Capabilities
            capabilities=capabilities,

            # Schedule (read-only)
            schedule=schedule_data,
            schedule_enabled=data.get("scheduleEnabled", False),

            # Holiday Mode & Frost Protection
            holiday_mode_enabled=holiday_enabled,
            frost_protection_enabled=frost_enabled,
        )
```

**Update Building model:**

```python
@dataclass
class Building:
    """Building containing units."""

    id: str
    name: str
    air_to_air_units: list[AirToAirUnit] = field(default_factory=list)
    air_to_water_units: list[AirToWaterUnit] = field(default_factory=list)  # ADD THIS

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Building":
        """Create from API response dict."""
        # Parse A2A units (existing)
        a2a_units_data = data.get("airToAirUnits", [])
        a2a_units = [AirToAirUnit.from_dict(u) for u in a2a_units_data]

        # Parse A2W units (NEW)
        a2w_units_data = data.get("airToWaterUnits", [])
        a2w_units = [AirToWaterUnit.from_dict(u) for u in a2w_units_data]

        return cls(
            id=data["id"],
            name=data.get("name", "Unknown"),
            air_to_air_units=a2a_units,
            air_to_water_units=a2w_units,  # ADD THIS
        )
```

**Update UserContext model:**

```python
@dataclass
class UserContext:
    """User context containing all buildings and devices."""

    buildings: list[Building] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UserContext":
        """Create from API response dict."""
        buildings_data = data.get("buildings", [])
        buildings = [Building.from_dict(b) for b in buildings_data]

        return cls(buildings=buildings)

    def get_all_units(self) -> list[AirToAirUnit]:
        """Get all A2A units across all buildings."""
        units = []
        for building in self.buildings:
            units.extend(building.air_to_air_units)
        return units

    def get_all_air_to_air_units(self) -> list[AirToAirUnit]:
        """Get all A2A units across all buildings (explicit method name)."""
        return self.get_all_units()

    def get_all_air_to_water_units(self) -> list[AirToWaterUnit]:
        """Get all A2W units across all buildings."""
        units = []
        for building in self.buildings:
            units.extend(building.air_to_water_units)
        return units

    def get_unit_by_id(self, unit_id: str) -> AirToAirUnit | None:
        """Get A2A unit by ID."""
        for unit in self.get_all_units():
            if unit.id == unit_id:
                return unit
        return None

    def get_air_to_water_unit_by_id(self, unit_id: str) -> AirToWaterUnit | None:
        """Get A2W unit by ID."""
        for unit in self.get_all_air_to_water_units():
            if unit.id == unit_id:
                return unit
        return None
```

**Do NOT add yet (Phase 2 / Deferred):**

- `ATWSchedule` dataclass (schedule creation deferred)
- Flow temperature fields (deferred)
- Telemetry fields (deferred to coordinator)

---

### 3. Extend `client.py` (Phase 1: Read-Only)

**Add helper methods for fetching ATW units:**

```python
class MELCloudHomeClient:
    """Client for MELCloud Home API."""

    # ... existing methods ...

    # ========================================================================
    # Air-to-Water (Heat Pump) Methods - Phase 1: Read-Only
    # ========================================================================

    async def get_air_to_water_units(self) -> list[AirToWaterUnit]:
        """
        Get all air-to-water units across all buildings.

        This is a convenience method that fetches user context
        and returns a flat list of all A2W devices.

        Returns:
            List of all air-to-water units

        Raises:
            AuthenticationError: If not authenticated
            ApiError: If API request fails
        """
        context = await self.get_user_context()
        return context.get_all_air_to_water_units()

    async def get_air_to_water_unit(self, unit_id: str) -> AirToWaterUnit | None:
        """
        Get a specific A2W unit by ID.

        Args:
            unit_id: Device ID (UUID)

        Returns:
            Device if found, None otherwise

        Raises:
            AuthenticationError: If not authenticated
            ApiError: If API request fails
        """
        context = await self.get_user_context()
        return context.get_air_to_water_unit_by_id(unit_id)
```

**Do NOT add yet (Phase 2):**

- Control methods (set_zone_temperature, set_dhw_temperature, etc.)
- Holiday mode / frost protection methods
- Any PUT/POST requests

---

## Phase 1 Testing Requirements

### Unit Tests: Model Parsing

Create `tests/api/test_atw_models.py`:

**Test coverage:**

```python
# Test AirToWaterCapabilities
- test_capabilities_from_dict_with_all_fields
- test_capabilities_from_dict_with_missing_fields_uses_defaults
- test_capabilities_always_uses_safe_temperature_defaults
- test_capabilities_logs_warning_when_api_values_differ
- test_capabilities_from_empty_dict_returns_defaults

# Test AirToWaterUnit
- test_unit_from_dict_parses_all_fields
- test_unit_from_dict_parses_settings_array
- test_unit_from_dict_converts_string_booleans
- test_unit_from_dict_converts_string_floats
- test_unit_from_dict_handles_missing_optional_fields
- test_unit_from_dict_parses_zone2_when_present
- test_unit_from_dict_parses_zone2_when_absent
- test_unit_from_dict_parses_holiday_mode
- test_unit_from_dict_parses_frost_protection
- test_unit_from_dict_handles_error_state
- test_operation_status_vs_operation_mode_zone1_distinct

# Test Building
- test_building_parses_both_a2a_and_a2w_units

# Test UserContext
- test_user_context_get_all_air_to_water_units
- test_user_context_get_air_to_water_unit_by_id
- test_user_context_handles_no_atw_units
```

**Use HAR file data for test fixtures:**

- Extract real API responses from `docs/research/ATW/melcloudhome_com_recording2_anonymized.har`
- Create fixtures with actual device data
- Test edge cases (missing fields, null values, etc.)

---

## Phase 2 Implementation Requirements (LATER)

### Control Methods

Add to `client.py`:

```python
async def set_zone_temperature(self, unit_id: str, temperature: float) -> None:
    """Set Zone 1 target room temperature (HeatRoomTemperature mode only).

    IMPORTANT: Only works in HeatRoomTemperature mode.
    For HeatFlowTemperature mode, use set_zone_flow_temperature() (not yet implemented).

    Args:
        unit_id: Device ID (UUID)
        temperature: Target room temperature in Celsius (10.0-30.0, 0.5° increments)

    Raises:
        AuthenticationError: If not authenticated
        ApiError: If API request fails
        ValueError: If temperature is out of range or wrong increment
    """
    # Validate range
    if not ATW_TEMP_MIN_ZONE <= temperature <= ATW_TEMP_MAX_ZONE:
        raise ValueError(
            f"Temperature must be between {ATW_TEMP_MIN_ZONE} and {ATW_TEMP_MAX_ZONE}°C"
        )

    # Check increment
    if (temperature / ATW_TEMP_STEP) % 1 != 0:
        raise ValueError(f"Temperature must be in {ATW_TEMP_STEP}° increments")

    # Build sparse payload (only changed field + nulls)
    payload = {
        "power": None,
        "setTemperatureZone1": temperature,
        "setTemperatureZone2": None,
        "operationModeZone1": None,
        "operationModeZone2": None,
        "setTankWaterTemperature": None,
        "forcedHotWaterMode": None,
        "setHeatFlowTemperatureZone1": None,
        "setCoolFlowTemperatureZone1": None,
        "setHeatFlowTemperatureZone2": None,
        "setCoolFlowTemperatureZone2": None,
    }

    await self._api_request(
        "PUT",
        f"/api/atwunit/{unit_id}",
        json=payload,
    )

async def set_dhw_temperature(self, unit_id: str, temperature: float) -> None:
    """Set DHW tank target temperature.

    Args:
        unit_id: Device ID (UUID)
        temperature: Target DHW temperature in Celsius (40.0-60.0)

    Raises:
        AuthenticationError: If not authenticated
        ApiError: If API request fails
        ValueError: If temperature is out of range
    """
    # Validate range
    if not ATW_TEMP_MIN_DHW <= temperature <= ATW_TEMP_MAX_DHW:
        raise ValueError(
            f"DHW temperature must be between {ATW_TEMP_MIN_DHW} and {ATW_TEMP_MAX_DHW}°C"
        )

    # Build sparse payload
    payload = {
        "power": None,
        "setTemperatureZone1": None,
        "setTemperatureZone2": None,
        "operationModeZone1": None,
        "operationModeZone2": None,
        "setTankWaterTemperature": temperature,
        "forcedHotWaterMode": None,
        "setHeatFlowTemperatureZone1": None,
        "setCoolFlowTemperatureZone1": None,
        "setHeatFlowTemperatureZone2": None,
        "setCoolFlowTemperatureZone2": None,
    }

    await self._api_request(
        "PUT",
        f"/api/atwunit/{unit_id}",
        json=payload,
    )

async def set_zone_mode(self, unit_id: str, mode: str) -> None:
    """Set Zone 1 operation mode.

    IMPORTANT: Only HeatRoomTemperature mode fully supported in Phase 1.
    HeatFlowTemperature and HeatCurve modes are accepted but flow temp control
    is not yet implemented.

    Args:
        unit_id: Device ID (UUID)
        mode: Operation mode - "HeatRoomTemperature", "HeatFlowTemperature", or "HeatCurve"

    Raises:
        AuthenticationError: If not authenticated
        ApiError: If API request fails
        ValueError: If mode is invalid
    """
    if mode not in ATW_OPERATION_MODES_ZONE:
        raise ValueError(
            f"Invalid mode: {mode}. Must be one of {ATW_OPERATION_MODES_ZONE}"
        )

    # Build sparse payload
    payload = {
        "power": None,
        "setTemperatureZone1": None,
        "setTemperatureZone2": None,
        "operationModeZone1": mode,
        "operationModeZone2": None,
        "setTankWaterTemperature": None,
        "forcedHotWaterMode": None,
        "setHeatFlowTemperatureZone1": None,
        "setCoolFlowTemperatureZone1": None,
        "setHeatFlowTemperatureZone2": None,
        "setCoolFlowTemperatureZone2": None,
    }

    await self._api_request(
        "PUT",
        f"/api/atwunit/{unit_id}",
        json=payload,
    )

async def set_forced_hot_water(self, unit_id: str, enabled: bool) -> None:
    """Enable/disable DHW priority mode.

    When enabled, the heat pump prioritizes DHW heating over zone heating.
    Automatically returns to normal operation when DHW reaches target temperature.

    Args:
        unit_id: Device ID (UUID)
        enabled: True to enable DHW priority, False to disable

    Raises:
        AuthenticationError: If not authenticated
        ApiError: If API request fails
    """
    # Build sparse payload
    payload = {
        "power": None,
        "setTemperatureZone1": None,
        "setTemperatureZone2": None,
        "operationModeZone1": None,
        "operationModeZone2": None,
        "setTankWaterTemperature": None,
        "forcedHotWaterMode": enabled,
        "setHeatFlowTemperatureZone1": None,
        "setCoolFlowTemperatureZone1": None,
        "setHeatFlowTemperatureZone2": None,
        "setCoolFlowTemperatureZone2": None,
    }

    await self._api_request(
        "PUT",
        f"/api/atwunit/{unit_id}",
        json=payload,
    )

async def set_power_atw(self, unit_id: str, power: bool) -> None:
    """Turn A2W device on or off.

    Args:
        unit_id: Device ID (UUID)
        power: True to turn on, False to turn off

    Raises:
        AuthenticationError: If not authenticated
        ApiError: If API request fails
    """
    # Build sparse payload
    payload = {
        "power": power,
        "setTemperatureZone1": None,
        "setTemperatureZone2": None,
        "operationModeZone1": None,
        "operationModeZone2": None,
        "setTankWaterTemperature": None,
        "forcedHotWaterMode": None,
        "setHeatFlowTemperatureZone1": None,
        "setCoolFlowTemperatureZone1": None,
        "setHeatFlowTemperatureZone2": None,
        "setCoolFlowTemperatureZone2": None,
    }

    await self._api_request(
        "PUT",
        f"/api/atwunit/{unit_id}",
        json=payload,
    )

async def set_holiday_mode(
    self,
    unit_ids: list[str],
    enabled: bool,
    start_date: str,
    end_date: str,
) -> None:
    """Configure holiday mode for multiple ATW units.

    Args:
        unit_ids: List of A2W device IDs (UUIDs)
        enabled: True to enable holiday mode, False to disable
        start_date: ISO 8601 datetime string (e.g., "2026-01-10T10:00:00")
        end_date: ISO 8601 datetime string (e.g., "2026-01-20T18:00:00")

    Raises:
        AuthenticationError: If not authenticated
        ApiError: If API request fails
    """
    payload = {
        "enabled": enabled,
        "startDate": start_date,
        "endDate": end_date,
        "units": {
            "ATW": unit_ids
        }
    }

    await self._api_request(
        "POST",
        "/api/holidaymode",
        json=payload,
    )

async def set_frost_protection(
    self,
    unit_ids: list[str],
    enabled: bool,
    min_temp: float,
    max_temp: float,
) -> None:
    """Configure frost protection for multiple ATW units.

    Args:
        unit_ids: List of A2W device IDs (UUIDs)
        enabled: True to enable frost protection, False to disable
        min_temp: Minimum temperature (°C)
        max_temp: Maximum temperature (°C)

    Raises:
        AuthenticationError: If not authenticated
        ApiError: If API request fails
    """
    payload = {
        "enabled": enabled,
        "min": min_temp,
        "max": max_temp,
        "units": {
            "ATW": unit_ids
        }
    }

    await self._api_request(
        "POST",
        "/api/protection/frost",
        json=payload,
    )
```

### Phase 2 Testing

Create `tests/api/test_atw_client.py`:

**Test coverage:**

```python
# Control method tests
- test_set_zone_temperature_valid
- test_set_zone_temperature_out_of_range_raises_error
- test_set_zone_temperature_wrong_increment_raises_error
- test_set_zone_temperature_builds_sparse_payload
- test_set_dhw_temperature_valid
- test_set_dhw_temperature_out_of_range_raises_error
- test_set_zone_mode_valid
- test_set_zone_mode_invalid_raises_error
- test_set_forced_hot_water
- test_set_power_atw
- test_holiday_mode_multiple_units
- test_frost_protection_multiple_units

# Validation tests
- test_temperature_validation_enforces_hardcoded_ranges
- test_mode_validation_only_accepts_three_modes
- test_sparse_payload_has_only_changed_field_plus_nulls
```

---

## Deferred Features (Not in Phase 1 or 2)

### Zone 2 Support

**Status:** Stubbed with validation

**Implementation:**

```python
async def set_zone2_temperature(self, unit_id: str, temperature: float) -> None:
    """Set Zone 2 target temperature.

    NOT YET IMPLEMENTED: Test hardware does not have Zone 2.

    Raises:
        NotImplementedError: Zone 2 control not yet supported
    """
    # Check capability first
    unit = await self.get_air_to_water_unit(unit_id)
    if unit and not unit.has_zone2:
        raise ValueError("This unit does not support Zone 2")

    raise NotImplementedError(
        "Zone 2 control not yet implemented. "
        "Test hardware unavailable for validation."
    )
```

### Flow Temperature Control

**Status:** Deferred (advanced feature)

**Reason:** HeatFlowTemperature mode requires:

- Different API parameter (`setHeatFlowTemperatureZone1`)
- Different temperature range (likely 30-60°C)
- Mode-aware validation logic
- Testing with systems using flow temp mode

**Most users use HeatRoomTemperature mode** - implement flow temp support only if requested.

### Schedule Creation

**Status:** Deferred (integer mapping unknown)

**Action Required:**

1. Search HAR files for schedule creation examples
2. Determine integer mapping: 0/1/2 → HeatRoomTemperature/HeatFlowTemperature/HeatCurve
3. If found, implement in Phase 2
4. If not found, leave as read-only

**Read-only support in Phase 1:** Schedule list is parsed and available in model.

### Telemetry Endpoints

**Status:** Deferred to coordinator

**Reason:**

- A2W has 9 telemetry measures (vs A2A's 3)
- Each measure requires separate API call
- Coordinator needs to decide which measures to fetch
- Model should not include real-time telemetry fields

**API client provides:** UserContext with current state (temps from settings array)

---

## Critical Implementation Notes

### 1. 3-Way Valve Limitation

**Physical constraint:** Device can only heat Zone OR DHW, never both.

**API behavior:**

- `operation_status` reflects current valve position (Stop/HotWater/zone mode)
- User sets targets for BOTH zone and DHW
- System automatically balances based on priorities
- `forcedHotWaterMode` overrides normal priority

**Code implications:**

- `operation_status` is READ-ONLY (never send in control requests)
- Don't validate that zone + DHW are mutually exclusive (system handles this)
- Document the limitation clearly in docstrings

### 2. Temperature Validation Strategy

**Always use hardcoded safe defaults:**

```python
Zone 1 room temp:  10.0 - 30.0°C (underfloor heating)
DHW tank temp:     40.0 - 60.0°C
Increment:         0.5°C (most systems)
```

**Never trust API-reported ranges:**

- Known bug history: API initially reported 30-50°C for Zone 1 (wrong)
- Bug was fixed but demonstrates unreliability
- Commercial systems might have different ranges (but API doesn't differentiate)

**Validation in client.py:**

- Validate BEFORE sending to API
- Raise ValueError with clear message
- Log warnings when API values differ from safe defaults

### 3. Sparse Update Pattern

**All control methods send:**

- ONE changed field with actual value
- ALL other fields set to `null`

**Example:** Setting zone temperature:

```python
payload = {
    "power": None,                          # Not changing
    "setTemperatureZone1": 21,              # CHANGING THIS
    "setTemperatureZone2": None,            # Not changing
    "operationModeZone1": None,             # Not changing
    "operationModeZone2": None,             # Not changing
    "setTankWaterTemperature": None,        # Not changing
    "forcedHotWaterMode": None,             # Not changing
    "setHeatFlowTemperatureZone1": None,    # Not changing (flow mode deferred)
    "setCoolFlowTemperatureZone1": None,    # Not changing (not used)
    "setHeatFlowTemperatureZone2": None,    # Not changing (zone 2 deferred)
    "setCoolFlowTemperatureZone2": None,    # Not changing (not used)
}
```

**Pattern matches A2A:** Same approach already used successfully.

### 4. String vs Integer Enums

**Control API (PUT /api/atwunit):** Uses STRINGS

```python
"operationModeZone1": "HeatRoomTemperature"  # String
```

**Schedule API (POST /api/atwcloudschedule):** Uses INTEGERS

```python
"operationModeZone1": 0  # Integer (mapping unknown - deferred)
```

**This matches A2A behavior** where operation modes and fan speeds have separate mappings for control vs schedule.

### 5. Settings Array Parsing

**API format:**

```json
{
  "settings": [
    {"name": "Power", "value": "True"},
    {"name": "SetTemperatureZone1", "value": "21"},
    {"name": "OperationMode", "value": "Stop"}
  ]
}
```

**Parsing requirements:**

- Convert array to dict: `{item["name"]: item["value"]}`
- Handle type conversions: string "True" → bool, string "21" → float
- Handle missing values: use None for optional fields
- Handle empty strings: convert to None
- Distinguish between control and status fields

**Critical:** `OperationMode` in settings is STATUS (renamed to `operation_status` in model).

### 6. Model Field Naming

**Renamed to avoid confusion:**

- API: `OperationMode` (status) → Model: `operation_status`
- API: `OperationModeZone1` (control) → Model: `operation_mode_zone1`

**Clear distinction:**

- `operation_status` = WHAT is heating NOW (read-only, 3-way valve position)
- `operation_mode_zone1` = HOW to heat zone (control field)

### 7. Capabilities Parsing

**Always log when overriding API values:**

```python
if api_min_zone != 10 or api_max_zone != 30:
    _LOGGER.debug(
        "API reported Zone range %s-%s°C, using safe default 10-30°C",
        api_min_zone, api_max_zone
    )
```

**Rationale:** Helps debugging if API values change or if user has unusual system.

---

## Testing Strategy

### Phase 1 Tests (Models & Parsing)

**Scope:** Unit tests for model parsing only

**Fixtures:** Extract from HAR files

- `docs/research/ATW/melcloudhome_com_recording2_anonymized.har`
- Look for `/api/user/context` responses
- Create test fixtures with real device data

**Test categories:**

1. **Happy path:** All fields present, valid data
2. **Missing fields:** Optional fields absent
3. **Edge cases:** Empty strings, null values, zero values
4. **Type conversion:** String "True" → bool, string "21.5" → float
5. **Safe defaults:** API reports suspicious values, uses hardcoded defaults
6. **Zone 2:** Present vs absent
7. **Error state:** IsInError=True, ErrorCode present

**Reference:** Follow patterns in `tests/api/test_models_parsing.py` (A2A)

### Phase 2 Tests (Control Methods)

**Scope:** Unit tests for control request building

**Mock strategy:** Mock `_api_request` method, verify payload

**Test categories:**

1. **Validation:** Temperature ranges, mode values
2. **Sparse payloads:** Only changed field + nulls
3. **Error handling:** ValueError for invalid inputs
4. **Multi-unit:** Holiday mode, frost protection

**Reference:** Follow patterns in `tests/api/test_client_control.py` (A2A)

### Integration Tests (Home Assistant)

**Scope:** Test through HA core interfaces

**CRITICAL RULES:**

- ✅ Test through `hass.states` and `hass.services` ONLY
- ✅ Mock `MELCloudHomeClient` at API boundary
- ✅ Use `hass.config_entries.async_setup()` for setup
- ❌ NEVER import or test coordinator/entity classes directly
- ❌ NEVER assert coordinator methods were called
- ❌ NEVER manipulate `coordinator.data` directly

**Reference:** Follow patterns in `tests/integration/test_init.py` (A2A)

**Deferred:** Integration tests wait until coordinator/entities are implemented (later PR).

---

## Key Reference Documents

**Must read before implementing:**

1. `docs/api/atw-api-reference.md` - Complete API specification
2. `docs/decisions/011-multi-device-type-architecture.md` - Architectural decision
3. `docs/architecture.md` - System architecture diagrams
4. `docs/api/device-type-comparison.md` - A2A vs A2W differences

**Existing A2A implementation to reference:**

1. `custom_components/melcloudhome/api/models.py` - Model patterns (lines 65-256)
2. `custom_components/melcloudhome/api/client.py` - Control method patterns (lines 169-379)
3. `custom_components/melcloudhome/api/const.py` - Constant organization
4. `tests/api/test_models_parsing.py` - Model testing patterns
5. `tests/api/test_client_control.py` - Control testing patterns

---

## Files to Modify

### Phase 1: Read-Only Support

**API Layer:**

- `custom_components/melcloudhome/api/const.py` - Add ATW constants (endpoints, modes, temp ranges)
- `custom_components/melcloudhome/api/models.py` - Add ATW models (AirToWaterUnit, AirToWaterCapabilities)
- `custom_components/melcloudhome/api/models.py` - Update Building class (add air_to_water_units)
- `custom_components/melcloudhome/api/models.py` - Update UserContext class (add ATW helper methods)
- `custom_components/melcloudhome/api/client.py` - Add ATW read methods (get_air_to_water_units, etc.)

**Tests:**

- `tests/api/test_atw_models.py` - NEW: ATW model parsing tests
- Update test fixtures if needed

### Phase 2: Control Support

**API Layer:**

- `custom_components/melcloudhome/api/client.py` - Add ATW control methods (6 methods + 2 multi-unit methods)

**Tests:**

- `tests/api/test_atw_client.py` - NEW: ATW control method tests

---

## Design Goals

1. **Follow A2A patterns** - Same validation, same sparse updates, same error handling
2. **Clear separation** - Method names make device type obvious
3. **Type safety** - Proper type hints, dataclass validation
4. **Safe defaults** - Hardcoded temperature ranges (don't trust API)
5. **Testability** - Follow HA testing best practices
6. **Progressive implementation** - Phase 1 validates before Phase 2 adds control
7. **Explicit deferral** - Clear NotImplementedError for Zone 2, flow temps, schedules

---

## Out of Scope (For Later)

**Not in API client layer:**

- Home Assistant coordinator modifications
- Climate platform for ATW
- Water heater platform for DHW
- Sensor entities
- Configuration flow updates
- HACS manifest updates

**Focus:** API client layer only. Coordinator/entities are separate PRs.

---

## Context from GitHub Discussion #26

**User:** @pwa-2025
**System:** EHSCVM2D Hydrokit (FTC Model 3)
**Use case:** Vacation home in Spain, guest management
**Primary mode:** HeatRoomTemperature
**Typical temps:** Zone 22-23°C, DHW 50°C

**Key insight:**
> "The switch that I thought was the DHW on/off is actually a function to set the priority of DHW heating over heating (zone1). When enabled, the ATW heats DHW until it reaches the set temperature, then switches to automatic operation mode."

This clarified that `forcedHotWaterMode` is a priority toggle, not an on/off switch.

---

## Quick Start Commands

```bash
# You're on the right branch
git branch  # Should show: feature/atw-heat-pump-support

# Review the architecture docs (if needed)
cat docs/decisions/011-multi-device-type-architecture.md
cat docs/api/atw-api-reference.md
cat docs/api/device-type-comparison.md

# Phase 1 Implementation Order:
# 1. Add ATW constants to const.py
# 2. Add ATW models to models.py (AirToWaterCapabilities, AirToWaterUnit)
# 3. Update Building and UserContext models in models.py
# 4. Add ATW read methods to client.py (get_air_to_water_units, etc.)
# 5. Write tests in tests/api/test_atw_models.py

# Run tests as you go
pytest tests/api/test_atw_models.py -v
make test
make type-check
make lint
make all

# When Phase 1 is complete and tested:
# - Create PR for review
# - Test with real hardware
# - Validate parsing is correct
# - Then proceed to Phase 2 (control methods)
```

---

## Questions to Consider During Implementation

### 1. HAR File Analysis (Before Phase 2)

**Action:** Search HAR files for schedule examples

- Look for POST requests to `/api/atwcloudschedule/{unitId}`
- Check `operationModeZone1` field in schedule payloads
- Determine if mapping is 0/1/2 or different

**If found:** Add schedule creation to Phase 2
**If not found:** Leave as read-only, document as deferred

### 2. Holiday Mode / Frost Protection Validation

**Question:** Should we validate that only ATW units are passed to these methods?

**Recommendation:** Yes - add validation:

```python
async def set_holiday_mode(self, unit_ids: list[str], ...):
    # Validate all units are ATW
    context = await self.get_user_context()
    all_atw_ids = {u.id for u in context.get_all_air_to_water_units()}
    for unit_id in unit_ids:
        if unit_id not in all_atw_ids:
            raise ValueError(f"Unit {unit_id} is not an ATW device")
```

### 3. Model Import Organization

**Question:** How to organize imports in models.py?

**Recommendation:** Use section comments:

```python
# ============================================================================
# Air-to-Air (A/C) Models
# ============================================================================

@dataclass
class DeviceCapabilities:
    ...

# ============================================================================
# Air-to-Water (Heat Pump) Models
# ============================================================================

@dataclass
class AirToWaterCapabilities:
    ...

# ============================================================================
# Shared Models
# ============================================================================

@dataclass
class Building:
    ...
```

---

## Success Criteria

### Phase 1 Complete When (Branch Implementation)

**Status:** Implemented in `feature/atw-heat-pump-support` branch, not yet merged to main

1. ✅ `AirToWaterCapabilities` model with hardcoded safe defaults
2. ✅ `AirToWaterUnit` model parses HAR file data correctly
3. ✅ Settings array parsing handles all type conversions
4. ✅ `operation_status` clearly distinct from `operation_mode_zone1`
5. ✅ `Building` and `UserContext` updated with ATW support
6. ✅ Helper methods fetch ATW units
7. ✅ Unit tests pass (31 tests, model parsing, safe defaults)
8. ✅ Type checking passes (mypy)
9. ✅ Follows A2A patterns (structure, naming, error handling)
10. ✅ Zone 2 fields present but control raises NotImplementedError
11. ✅ No control methods added yet (read-only only)

**Next:** Create PR, test with real hardware, then proceed to Phase 2

### Phase 2 Complete When

1. ✅ All control methods implemented (6 methods + 2 multi-unit)
2. ✅ Temperature validation (10-30°C Zone, 40-60°C DHW)
3. ✅ Mode validation (3 zone modes)
4. ✅ Sparse update pattern for all control methods
5. ✅ Holiday mode and frost protection methods
6. ✅ Unit tests pass (control methods, request building, validation)
7. ✅ Type checking passes (mypy)
8. ✅ Integration tests (when coordinator implemented)

---

## Risk Mitigation

### Risk: Model parsing is incorrect

**Mitigation:** Phase 1 focuses solely on parsing, test with real hardware before Phase 2

### Risk: Temperature ranges are wrong for some systems

**Mitigation:** Use conservative defaults, log API values for debugging

### Risk: Zone 2 implementation is incomplete

**Mitigation:** Explicit NotImplementedError with clear message

### Risk: Schedule integer mapping is unknown

**Mitigation:** Check HAR files first, defer if not found, implement when known

### Risk: Control methods damage equipment

**Mitigation:**

- Only use values observed in official UI
- Validate before sending to API
- Two-phase implementation (parse first, control second)
- Test thoroughly with real hardware in Phase 2

---

## Final Notes

**Keep it simple:** This is Phase 1 - read-only support only. Control comes in Phase 2 after validation.

**Safe defaults:** Temperature ranges are ALWAYS hardcoded (10-30°C, 40-60°C). Never trust API values.

**Document unknowns:** Schedule integer mapping is deferred - check HAR files separately.

**Test thoroughly:** Model parsing is critical due to complex settings array structure.

**3-way valve:** Remember this is a physical limitation - document clearly in code comments.

**Two phases:** Phase 1 proves the models are correct. Phase 2 adds control with confidence.

Good luck with Phase 1! The architecture is solid, the documentation is comprehensive, and the path is clear. Start with constants, then models, then tests.
