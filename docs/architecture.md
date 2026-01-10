# MELCloud Home Integration - Architecture Overview

Visual architecture documentation for the MELCloud Home custom integration for Home Assistant.

**Last Updated:** 2026-01-03
**Related:** [ADR-011: Multi-Device-Type Architecture](decisions/011-multi-device-type-architecture.md)

---

## Key Architectural Principles

1. **Single Unified Client** - One `MELCloudHomeClient` handles both Air-to-Air and Air-to-Water devices
2. **Shared Authentication** - AWS Cognito OAuth session shared across all device types
3. **Multi-Type Container** - `UserContext` holds both device types in parallel arrays
4. **Device-Specific Methods** - Method names indicate which device type they control
5. **3-Way Valve Awareness** - A2W architecture reflects physical hardware limitation

---

## 1. System Overview

High-level component architecture showing how Home Assistant entities connect to the MELCloud API through the integration layers.

```mermaid
graph TB
    subgraph "Home Assistant"
        Climate[Climate Entity<br/>A2A Units]
        WaterHeater[Water Heater Entity<br/>A2W DHW]
        Sensors[Sensor Entities<br/>Temps, Status, Energy]
    end

    subgraph "MELCloud Home Integration"
        Coordinator[Update Coordinator<br/>Polling & State Management]

        subgraph "API Client Layer"
            Client[MELCloudHomeClient<br/>Single Unified Client]
            Auth[Authentication<br/>AWS Cognito OAuth]
        end

        subgraph "Models Layer"
            A2AModel[AirToAirUnit<br/>Model]
            A2WModel[AirToWaterUnit<br/>Model]
            Context[UserContext<br/>Multi-Type Container]
        end
    end

    subgraph "MELCloud API"
        UserContextAPI[/api/user/context<br/>SHARED]
        A2AAPI[/api/ataunit/*<br/>A2A Control]
        A2WAPI[/api/atwunit/*<br/>A2W Control]
    end

    Climate --> Coordinator
    WaterHeater --> Coordinator
    Sensors --> Coordinator

    Coordinator --> Client
    Client --> Auth
    Client --> Context

    Context --> A2AModel
    Context --> A2WModel

    Client --> UserContextAPI
    Client --> A2AAPI
    Client --> A2WAPI

    Auth -.session.-> UserContextAPI
    Auth -.session.-> A2AAPI
    Auth -.session.-> A2WAPI
```

**Key Points:**

- **Single coordinator** manages polling for all device types
- **Single client** provides unified API interface
- **Shared auth** handles OAuth for all endpoints
- **UserContext** endpoint returns both device types in one response

---

## 2. Device Type Control Flow

Sequence diagram showing authentication, device discovery, and control operations for both device types.

```mermaid
sequenceDiagram
    participant HA as Home Assistant
    participant Coord as Coordinator
    participant Client as MELCloudHomeClient
    participant API as MELCloud API

    Note over HA,API: Initial Setup
    HA->>Client: login(user, pass)
    Client->>API: OAuth flow (AWS Cognito)
    API-->>Client: Session established

    Note over HA,API: Device Discovery
    Coord->>Client: get_user_context()
    Client->>API: GET /api/user/context
    API-->>Client: { airToAirUnits[], airToWaterUnits[] }
    Client-->>Coord: UserContext (both types)

    Note over HA,API: A2A Control
    HA->>Coord: climate.set_temperature(a2a_id, 22°C)
    Coord->>Client: set_temperature(a2a_id, 22)
    Client->>API: PUT /api/ataunit/{id}
    API-->>Client: 200 OK (empty)

    Note over HA,API: A2W Control
    HA->>Coord: climate.set_temperature(a2w_id, 21°C)
    Coord->>Client: set_zone_temperature(a2w_id, 21)
    Client->>API: PUT /api/atwunit/{id}
    API-->>Client: 200 OK (empty)

    Note over HA,API: A2W DHW Control
    HA->>Coord: water_heater.set_temperature(a2w_id, 50°C)
    Coord->>Client: set_dhw_temperature(a2w_id, 50)
    Client->>API: PUT /api/atwunit/{id}
    API-->>Client: 200 OK (empty)

    Note over HA,API: Periodic State Update
    loop Every 60 seconds
        Coord->>Client: get_user_context()
        Client->>API: GET /api/user/context
        API-->>Client: Current state (all devices)
        Client-->>Coord: Updated state
        Coord->>HA: Update entities
    end
```

**Key Points:**

- **Single login** serves all devices
- **UserContext returns both** device types in one call
- **Device type determines** which control endpoint used
- **Empty 200 responses** for all control commands
- **Periodic polling** updates state for all devices

---

## 3. Data Model Relationships

Class diagram showing how models are structured and related.

```mermaid
classDiagram
    class MELCloudHomeClient {
        -MELCloudHomeAuth auth
        -UserContext user_context
        +login(user, pass) bool
        +logout() None
        +get_user_context() UserContext
        +set_temperature(id, temp) None [A2A]
        +set_mode(id, mode) None [A2A]
        +set_fan_speed(id, speed) None [A2A]
        +set_zone_temperature(id, temp) None [A2W]
        +set_dhw_temperature(id, temp) None [A2W]
        +set_zone_mode(id, mode) None [A2W]
        +set_forced_hot_water(id, enabled) None [A2W]
        +set_holiday_mode(...) None [A2W]
        +set_frost_protection(...) None [A2W]
    }

    class MELCloudHomeAuth {
        -ClientSession session
        -str access_token
        +login(user, pass) bool
        +logout() None
        +get_session() ClientSession
        +is_authenticated bool
    }

    class UserContext {
        +str id
        +str email
        +List~Building~ buildings
        +get_all_air_to_air_units() List
        +get_all_air_to_water_units() List
        +get_unit_by_id(id) Unit
    }

    class Building {
        +str id
        +str name
        +str timezone
        +List~AirToAirUnit~ air_to_air_units
        +List~AirToWaterUnit~ air_to_water_units
    }

    class AirToAirUnit {
        +str id
        +str name
        +bool power
        +str operation_mode
        +float set_temperature
        +float room_temperature
        +str set_fan_speed
        +str vane_vertical_direction
        +str vane_horizontal_direction
        +bool in_standby_mode
        +bool is_in_error
        +DeviceCapabilities capabilities
        +List~Schedule~ schedule
    }

    class AirToWaterUnit {
        +str id
        +str name
        +bool power
        +str operation_mode [STATUS]
        +str operation_mode_zone1
        +float set_temperature_zone1
        +float room_temperature_zone1
        +float set_tank_water_temperature
        +float tank_water_temperature
        +bool forced_hot_water_mode
        +bool has_zone2
        +bool is_in_error
        +int ftc_model
        +AirToWaterCapabilities capabilities
        +List~ATWSchedule~ schedule
    }

    class DeviceCapabilities {
        +int number_of_fan_speeds
        +float min_temp_heat
        +float max_temp_heat
        +bool has_half_degree_increments
        +bool has_cool_operation_mode
        +bool has_heat_operation_mode
        +bool has_swing
    }

    class AirToWaterCapabilities {
        +bool has_hot_water
        +float min_set_tank_temperature
        +float max_set_tank_temperature
        +float min_set_temperature
        +float max_set_temperature
        +bool has_zone2
        +bool has_thermostat_zone1
        +bool has_measured_energy_consumption
        +int ftc_model
    }

    MELCloudHomeClient --> MELCloudHomeAuth
    MELCloudHomeClient --> UserContext
    UserContext --> Building
    Building --> AirToAirUnit
    Building --> AirToWaterUnit
    AirToAirUnit --> DeviceCapabilities
    AirToWaterUnit --> AirToWaterCapabilities
```

**Key Points:**

- **Single client class** with device-specific methods
- **Separate model classes** for each device type
- **Separate capability classes** (different fields)
- **UserContext** as multi-type container
- **Building** holds both unit type arrays

---

## 4. A2W 3-Way Valve Behavior

State diagram illustrating the Air-to-Water heat pump's 3-way valve operation and how it affects the `OperationMode` status field.

```mermaid
stateDiagram-v2
    [*] --> Stop: power=false or all targets reached
    Stop --> HeatingZone1: Zone 1 temp < target
    Stop --> HeatingDHW: DHW temp < target

    HeatingZone1 --> Stop: Zone 1 target reached
    HeatingZone1 --> HeatingDHW: forcedHotWaterMode=true
    HeatingZone1 --> HeatingDHW: DHW priority triggered

    HeatingDHW --> Stop: DHW target reached
    HeatingDHW --> HeatingZone1: DHW complete & Zone 1 needs heat

    note right of Stop
        OperationMode status: "Stop"

        No active heating
        All targets reached or power off
    end note

    note right of HeatingDHW
        OperationMode status: "HotWater"

        3-way valve directed to DHW tank
        Zone 1 heating suspended
    end note

    note right of HeatingZone1
        OperationMode status:
        Shows current zone mode

        - "HeatRoomTemperature"
        - "HeatFlowTemperature"
        - "HeatCurve"

        3-way valve directed to Zone 1
        DHW heating suspended
    end note
```

**Critical Understanding:**

1. **Physical Limitation:** Heat pump can only heat ONE thing at a time
   - 3-way valve directs hot water to either Zone 1 OR DHW tank
   - Cannot heat both simultaneously

2. **OperationMode is STATUS:**
   - Read-only field showing current valve position
   - Automatically determined by system
   - NOT a control parameter

3. **Control vs Status:**
   - **Control:** `operationModeZone1` = HOW to heat zone (user sets)
   - **Status:** `OperationMode` = WHAT is heating NOW (system reports)

4. **Forced Hot Water Mode:**
   - When enabled: DHW gets priority
   - Zone 1 suspended until DHW reaches target
   - Then automatically switches back to zone heating

5. **Summer Mode Workaround:**
   - Set Zone 1 target to minimum (10°C)
   - Room temp > target, so no zone heating
   - System only heats DHW as needed

---

## 5. HA Entity Responsibility Boundaries

**Reference:** [ADR-012: ATW Entity Architecture](decisions/012-atw-entity-architecture.md) for detailed power control architecture and implementation examples.

### Entity Responsibilities

**ATW (Air-to-Water) Heat Pump Entities:**

| Entity Type | Controls | Does NOT Control |
|-------------|----------|------------------|
| **switch** | • System power (ON/OFF)<br/>• Entire heat pump system | • Zone temperatures<br/>• DHW settings |
| **climate (zone)** | • Zone target temperature<br/>• Zone heating method (presets)<br/>• HVAC mode (HEAT/OFF delegates to power) | • Other zones<br/>• DHW tank settings |
| **water_heater** | • DHW tank temperature<br/>• DHW operation mode (eco/performance) | • **System power** (read-only)<br/>• Zone settings |

**Key Architectural Decisions:**

1. **Switch = Primary Power Control**
   - Single obvious control point for system power
   - Standard HA pattern for binary states

2. **Climate OFF = Power Delegation**
   - Climate OFF delegates to same power control method as switch
   - Maintains standard HA UX (users expect climate OFF to turn off heating)
   - No duplicate logic (Single Responsibility Principle)

3. **Water Heater = DHW Control Only**
   - No turn_on/turn_off methods (power state is read-only)
   - Focuses on DHW-specific settings
   - Clearer responsibility boundaries

**Rationale:**

- **Physical Reality:** Heat pump is ONE device with one power supply
- **Single Responsibility:** Each entity has one clear purpose
- **User Clarity:** Switch is obvious place for system power control
- **Standard HA UX:** Climate OFF works as expected (delegates to power control)

### 3-Way Valve Status Visibility

The 3-way valve position is exposed to users via:

1. **water_heater state attributes:**
   - `operation_status` - Current valve position ("HotWater", "HeatRoomTemperature", etc.)
   - `zone_heating_suspended` - Boolean (true when valve directed to DHW)

2. **Dedicated sensor:**
   - `sensor.{device_name}_operation_status` - Human-readable status
   - States: "idle", "heating_dhw", "heating_zone_1", "heating_zone_2"

3. **climate.hvac_action:**
   - Shows IDLE when valve is on DHW (even if zone temp below target)
   - Shows HEATING only when valve actually on this zone

**This visibility is critical for users to understand heat pump behavior.**

---

## 6. API Layer Structure

### File Organization

```
custom_components/melcloudhome/api/
├── __init__.py          # Package exports
├── auth.py              # AWS Cognito OAuth (shared)
├── exceptions.py        # Custom exceptions (shared)
├── client.py            # Facade pattern - composes ata/atw clients
├── client_ata.py        # ATA-specific control methods
├── client_atw.py        # ATW-specific control methods
├── const_shared.py      # Shared constants (User-Agent, endpoints)
├── const_ata.py         # ATA-specific constants (modes, fan speeds)
├── const_atw.py         # ATW-specific constants (zone modes, temp ranges)
├── models.py            # Shared models (Building, UserContext)
├── models_ata.py        # ATA-specific models (AirToAirUnit)
├── models_atw.py        # ATW-specific models (AirToWaterUnit)
└── parsing.py           # Shared parsing utilities
```

### Separation Strategy

**Facade pattern with composition:**

```python
# Main client provides unified interface
client = MELCloudHomeClient()

# ATA methods (via client.ata facade)
await client.ata.set_temperature(unit_id, temp)
await client.ata.set_mode(unit_id, mode)
await client.ata.set_fan_speed(unit_id, speed)

# ATW methods (via client.atw facade)
await client.atw.set_temperature_zone1(unit_id, temp)
await client.atw.set_dhw_temperature(unit_id, temp)
await client.atw.set_power(unit_id, power)
await client.atw.set_forced_hot_water(unit_id, enabled)
```

**Rationale:** Facade pattern provides single entry point while maintaining clean separation. See [ADR-011](decisions/011-multi-device-type-architecture.md) "Implementation Evolution" section for details.

---

## Home Assistant Entity Mapping

### Air-to-Air Units

**Entities created per A2A unit:**

- `climate.melcloudhome_{name}` - Main climate control
- `sensor.melcloudhome_{name}_room_temperature` - Current temp
- `sensor.melcloudhome_{name}_wifi_signal` - RSSI
- `sensor.melcloudhome_{name}_energy` - Energy consumption (if available)

### Air-to-Water Units

**Entities created per A2W unit:**

**Primary Control:**
- `switch.melcloudhome_{name}_system_power` - System power (ON/OFF)

**Climate & Water Heating:**
- `climate.melcloudhome_{name}_zone_1` - Zone 1 heating control
- `water_heater.melcloudhome_{name}_tank` - DHW tank control (no power control)

**Temperature Sensors:**
- `sensor.melcloudhome_{name}_zone_1_temperature` - Zone 1 room temp
- `sensor.melcloudhome_{name}_tank_temperature` - DHW tank temp

**Status Sensors:**
- `sensor.melcloudhome_{name}_operation_status` - 3-way valve position

**Binary Sensors:**
- `binary_sensor.melcloudhome_{name}_error` - Error state
- `binary_sensor.melcloudhome_{name}_connection` - Connection status
- `binary_sensor.melcloudhome_{name}_forced_dhw_active` - Forced DHW mode active

---

## 2. Device Type Control Flow

Sequence diagram showing complete flow from authentication through control operations.

```mermaid
sequenceDiagram
    participant HA as Home Assistant
    participant Coord as Coordinator
    participant Client as MELCloudHomeClient
    participant API as MELCloud API

    Note over HA,API: Initial Setup
    HA->>Client: login(user, pass)
    Client->>API: OAuth flow (AWS Cognito)
    API-->>Client: Session established

    Note over HA,API: Device Discovery
    Coord->>Client: get_user_context()
    Client->>API: GET /api/user/context
    API-->>Client: { airToAirUnits[], airToWaterUnits[] }
    Client-->>Coord: UserContext (both types)

    Note over HA,API: A2A Control
    HA->>Coord: climate.set_temperature(a2a_id, 22°C)
    Coord->>Client: set_temperature(a2a_id, 22)
    Client->>API: PUT /api/ataunit/{id}<br/>{"setTemperature": 22, ...nulls...}
    API-->>Client: 200 OK (empty)

    Note over HA,API: A2W Zone Control
    HA->>Coord: climate.set_temperature(a2w_id, 21°C)
    Coord->>Client: set_zone_temperature(a2w_id, 21)
    Client->>API: PUT /api/atwunit/{id}<br/>{"setTemperatureZone1": 21, ...nulls...}
    API-->>Client: 200 OK (empty)

    Note over HA,API: A2W DHW Control
    HA->>Coord: water_heater.set_temperature(a2w_id, 50°C)
    Coord->>Client: set_dhw_temperature(a2w_id, 50)
    Client->>API: PUT /api/atwunit/{id}<br/>{"setTankWaterTemperature": 50, ...nulls...}
    API-->>Client: 200 OK (empty)

    Note over HA,API: A2W Priority Mode
    HA->>Coord: switch.turn_on(forced_hot_water)
    Coord->>Client: set_forced_hot_water(a2w_id, True)
    Client->>API: PUT /api/atwunit/{id}<br/>{"forcedHotWaterMode": true, ...nulls...}
    API-->>Client: 200 OK (empty)

    Note over HA,API: Periodic State Update
    loop Every 60 seconds
        Coord->>Client: get_user_context()
        Client->>API: GET /api/user/context
        API-->>Client: Current state (all devices)
        Client-->>Coord: Updated state
        Coord->>HA: Update all entities
    end
```

---

## 3. Data Model Relationships

Class diagram showing the structure of models and their relationships.

```mermaid
classDiagram
    class MELCloudHomeClient {
        -MELCloudHomeAuth auth
        -UserContext user_context
        +login(user, pass) bool
        +logout() None
        +close() None
        +is_authenticated bool
        +get_user_context() UserContext
        +get_devices() List~AirToAirUnit~
        +get_device(id) AirToAirUnit
        +set_temperature(id, temp) [A2A]
        +set_mode(id, mode) [A2A]
        +set_fan_speed(id, speed) [A2A]
        +set_vane_vertical(id, dir) [A2A]
        +set_vane_horizontal(id, dir) [A2A]
        +set_zone_temperature(id, temp) [A2W]
        +set_dhw_temperature(id, temp) [A2W]
        +set_zone_mode(id, mode) [A2W]
        +set_forced_hot_water(id, enabled) [A2W]
        +set_holiday_mode(ids, ...) [A2W]
        +set_frost_protection(ids, ...) [A2W]
    }

    class MELCloudHomeAuth {
        -ClientSession session
        -str access_token
        -str refresh_token
        +login(user, pass) bool
        +logout() None
        +get_session() ClientSession
        +is_authenticated bool
    }

    class UserContext {
        +str id
        +str email
        +str firstname
        +str lastname
        +List~Building~ buildings
        +get_all_air_to_air_units() List~AirToAirUnit~
        +get_all_air_to_water_units() List~AirToWaterUnit~
        +get_unit_by_id(id) AirToAirUnit|AirToWaterUnit
    }

    class Building {
        +str id
        +str name
        +str timezone
        +List~AirToAirUnit~ air_to_air_units
        +List~AirToWaterUnit~ air_to_water_units
    }

    class AirToAirUnit {
        +str id
        +str name
        +bool power
        +str operation_mode
        +float set_temperature
        +float room_temperature
        +str set_fan_speed
        +str vane_vertical_direction
        +str vane_horizontal_direction
        +bool in_standby_mode
        +bool is_in_error
        +int rssi
        +DeviceCapabilities capabilities
        +List~Schedule~ schedule
        +bool schedule_enabled
    }

    class AirToWaterUnit {
        +str id
        +str name
        +bool power
        +str operation_mode [STATUS ONLY]
        +str operation_mode_zone1
        +float set_temperature_zone1
        +float room_temperature_zone1
        +float set_tank_water_temperature
        +float tank_water_temperature
        +bool forced_hot_water_mode
        +bool has_zone2
        +bool in_standby_mode
        +bool is_in_error
        +int ftc_model
        +int rssi
        +AirToWaterCapabilities capabilities
        +List~ATWSchedule~ schedule
        +bool schedule_enabled
    }

    class DeviceCapabilities {
        +int number_of_fan_speeds
        +float min_temp_heat
        +float max_temp_heat
        +float min_temp_cool_dry
        +float max_temp_cool_dry
        +bool has_half_degree_increments
        +bool has_swing
        +bool has_cool_operation_mode
        +bool has_heat_operation_mode
    }

    class AirToWaterCapabilities {
        +bool has_hot_water
        +float min_set_tank_temperature
        +float max_set_tank_temperature
        +float min_set_temperature
        +float max_set_temperature
        +bool has_half_degrees
        +bool has_zone2
        +bool has_thermostat_zone1
        +bool has_heat_zone1
        +bool has_measured_energy_consumption
        +bool has_estimated_energy_consumption
        +int ftc_model
    }

    MELCloudHomeClient --> MELCloudHomeAuth : uses
    MELCloudHomeClient --> UserContext : caches
    UserContext --> Building : contains
    Building --> AirToAirUnit : has many
    Building --> AirToWaterUnit : has many
    AirToAirUnit --> DeviceCapabilities : has one
    AirToWaterUnit --> AirToWaterCapabilities : has one
```

---

## 4. A2W 3-Way Valve Behavior

State diagram showing how the Air-to-Water heat pump's 3-way valve determines what gets heated and how this affects the `OperationMode` status field.

```mermaid
stateDiagram-v2
    [*] --> Stop: power=false OR all targets reached
    Stop --> HeatingZone1: Zone 1 temp < target
    Stop --> HeatingDHW: DHW temp < target

    HeatingZone1 --> Stop: Zone 1 target reached
    HeatingZone1 --> HeatingDHW: forcedHotWaterMode=true
    HeatingZone1 --> HeatingDHW: DHW priority triggered

    HeatingDHW --> Stop: DHW target reached AND Zone 1 not needed
    HeatingDHW --> HeatingZone1: DHW complete AND Zone 1 needs heat

    note right of Stop
        OperationMode status: "Stop"

        No active heating
        - Power is off, OR
        - All targets reached

        3-way valve: IDLE
    end note

    note right of HeatingDHW
        OperationMode status: "HotWater"

        Currently heating DHW tank
        Zone 1 heating suspended

        3-way valve: → DHW TANK
    end note

    note right of HeatingZone1
        OperationMode status:
        Shows current zone control mode

        - "HeatRoomTemperature"
        - "HeatFlowTemperature"
        - "HeatCurve"

        3-way valve: → ZONE 1
    end note
```

### Physical System

```
Heat Pump → [3-Way Valve] → Zone 1 Heating
                    ↓
              DHW Tank Heating

Only ONE output active at a time
```

### Control Implications

**User sets:**

- `setTemperatureZone1`: 21°C (target)
- `setTankWaterTemperature`: 50°C (target)
- `forcedHotWaterMode`: false (no priority)
- `operationModeZone1`: "HeatRoomTemperature" (HOW to heat)

**System decides:**

- Current room temp: 19°C (< 21°C target) → needs heating
- Current DHW temp: 48°C (< 50°C target) → needs heating
- No forced mode → automatic balancing
- **OperationMode shows what's happening RIGHT NOW**

**Example sequence:**

1. System heats Zone 1 → `OperationMode: "HeatRoomTemperature"`
2. Zone reaches 21°C → switches to DHW
3. System heats DHW → `OperationMode: "HotWater"`
4. DHW reaches 50°C → switches back
5. Both at target → `OperationMode: "Stop"`

---

## Design Patterns

### 1. Sparse Update Pattern

Both device types use sparse updates:

```python
# Only change what you want to change
payload = {
    "power": None,              # No change
    "setTemperature": 22.0,     # Change this
    "operationMode": None,      # No change
    # ... all others: None
}
```

### 2. Capabilities-Driven Logic

```python
# Check capabilities before controlling
if unit.capabilities.has_zone2:
    # Zone 2 control
    await client.set_zone2_temperature(unit.id, 20.0)
```

### 3. Type-Safe Methods

```python
# A2A-specific methods won't work on A2W units
# A2W-specific methods won't work on A2A units
# No risk of cross-contamination
```

### 4. Multi-Device Discovery

```python
context = await client.get_user_context()

# Iterate all device types
for unit in context.get_all_air_to_air_units():
    # Setup A2A climate entity

for unit in context.get_all_air_to_water_units():
    # Setup A2W climate + water_heater entities
```

---

## Related Documentation

- **ADR-011:** [Multi-Device-Type Architecture](decisions/011-multi-device-type-architecture.md)
- **A2A API Reference:** [ata-api-reference.md](api/ata-api-reference.md)
- **A2W API Reference:** [atw-api-reference.md](api/atw-api-reference.md)
- **Device Comparison:** [device-type-comparison.md](api/device-type-comparison.md)
- **OpenAPI Spec:** [../openapi.yaml](../openapi.yaml)
