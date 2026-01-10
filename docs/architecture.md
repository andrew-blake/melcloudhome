# MELCloud Home Integration - Architecture Overview

Visual architecture documentation for the MELCloud Home custom integration for Home Assistant.

**Last Updated:** 2026-01-03
**Related:** [ADR-011: Multi-Device-Type Architecture](decisions/011-multi-device-type-architecture.md)

**Terminology:** This document uses **ATA** (Air-to-Air) and **ATW** (Air-to-Water) as primary abbreviations. Diagrams may use shortened forms (A2A/A2W) for space efficiency.

---

## Key Architectural Principles

1. **Single Unified Client** - One `MELCloudHomeClient` handles both Air-to-Air and Air-to-Water devices
2. **Shared Authentication** - AWS Cognito OAuth session shared across all device types
3. **Multi-Type Container** - `UserContext` holds both device types in parallel arrays
4. **Device-Specific Methods** - Method names indicate which device type they control
5. **3-Way Valve Awareness** - ATW architecture reflects physical hardware limitation

---

## System Overview

High-level component architecture showing how Home Assistant entities connect to the MELCloud API through the integration layers.

```mermaid
graph LR
    subgraph "Home Assistant"
        Climate[Climate Entity<br/>A2A Units]
        WaterHeater[Water Heater Entity<br/>A2W DHW]
        Sensors[Sensor Entities<br/>Temps, Status, Energy]
    end

    subgraph "MELCloud Home Integration"
        Coordinator[Update Coordinator<br/>Polling & State Management]

        subgraph "Control Client Layer"
            ControlATA[ATAControlClient<br/>Session Recovery & Dedup]
            ControlATW[ATWControlClient<br/>Session Recovery & Dedup]
        end

        subgraph "Models Layer"
            A2AModel[AirToAirUnit<br/>Model]
            A2WModel[AirToWaterUnit<br/>Model]
            Context[UserContext<br/>Multi-Type Container]
        end
        subgraph "API Client Layer"
            Client[MELCloudHomeClient<br/>Single Unified Client]
        end

    end
    subgraph "MELCloud API"
        UserContextAPI["GET /api/user/context<br/>(SHARED)"]
        A2AAPI["PUT /api/ataunit/*<br/>(A2A Control)"]
        A2WAPI["PUT /api/atwunit/*<br/>(A2W Control)"]
    end
    subgraph "AWS Cognito"
        Auth[Authentication<br/>AWS Cognito OAuth]
    end

    Climate --> Coordinator
    WaterHeater --> Coordinator
    Sensors --> Coordinator

    Coordinator -->|ATA operations| ControlATA
    Coordinator -->|ATW operations| ControlATW
    ControlATA --> Client
    ControlATW --> Client
    Client --> Auth
    Client --> Context

    Context --> A2AModel
    Context --> A2WModel

    Client --> UserContextAPI
    Client --> A2AAPI
    Client --> A2WAPI
```

**Key Points:**

- **Single coordinator** manages polling for all device types
- **Control client layer** provides deduplication, retry logic, and session recovery
- **Single API client** provides unified interface to MELCloud API
- **Shared auth** handles OAuth for all endpoints
- **UserContext** endpoint returns both device types in one response

---

## ATW Entity Architecture

Air-to-Water heat pumps present a unique challenge: one physical device with multiple control aspects (system power, zone heating, DHW). See [ADR-012](decisions/012-atw-entity-architecture.md) for full rationale.

**Entity Responsibilities:**

| Entity | Controls | Rationale |
|--------|----------|-----------|
| **switch** | System power (ON/OFF) | Primary power control point. Standard HA pattern for system-level on/off. |
| **climate** | Zone temperature & heating method | Zone-specific control. HVAC mode OFF delegates to switch. |
| **water_heater** | DHW temperature & mode | DHW-specific control. Power state is read-only. |

**Key Point:** Heat pump is ONE device with one power supply. Switch controls system power. Climate and water_heater control their respective subsystems when the system is on.

**3-Way Valve Status:** Users can monitor valve position via `sensor.{device}_operation_status` (idle/heating_dhw/heating_zone_1) and `climate.hvac_action` (shows IDLE when valve on DHW).

---

## API Layer Structure

Files are organized by device type: `client_ata.py` (Air-to-Air), `client_atw.py` (Air-to-Water), with shared code in `client.py`, `auth.py`, and `models.py`. The `MELCloudHomeClient` composes device-specific facades (`client.ata`, `client.atw`) using the facade pattern. See [ADR-011](decisions/011-multi-device-type-architecture.md) for implementation details.

---

## Entity ID Strategy

All entities use UUID-based device names for stable entity IDs (format: `melcloudhome_{short_id}_{entity_type}` where short_id is first 4 + last 4 chars of UUID). Friendly device names are set via `name_by_user` in device registry.

**ATA (Air-to-Air):** `climate`, temperature/energy sensors, error/connection binary sensors

**ATW (Air-to-Water):** `switch` (system power), `climate` (zones), `water_heater` (DHW), temperature sensors, operation status sensor, error/connection/forced-DHW binary sensors

---

## Device Type Control Flow

Sequence diagram showing complete flow from authentication through control operations, including the control client layer that handles retry logic and session recovery.

```mermaid
sequenceDiagram
    participant HA as Home Assistant
    participant Coord as Coordinator
    participant CtrlClient as ControlClient<br/>(ATA/ATW)
    participant APIClient as MELCloudHomeClient
    participant API as MELCloud API

    Note over HA,API: Initial Setup
    HA->>APIClient: login(user, pass)
    APIClient->>API: OAuth flow (AWS Cognito)
    API-->>APIClient: Session established

    Note over HA,API: Device Discovery
    Coord->>APIClient: get_user_context()
    APIClient->>API: GET /api/user/context
    API-->>APIClient: { airToAirUnits[], airToWaterUnits[] }
    APIClient-->>Coord: UserContext (both types)

    Note over HA,API: A2A Control (with retry)
    HA->>Coord: climate.set_temperature(a2a_id, 22°C)
    Coord->>CtrlClient: control_client.async_set_temperature(a2a_id, 22)
    CtrlClient->>CtrlClient: Check if value changed<br/>(skip if duplicate)
    CtrlClient->>APIClient: client.ata.set_temperature(a2a_id, 22)
    APIClient->>API: PUT /api/ataunit/{id}<br/>{"setTemperature": 22, ...nulls...}
    alt Session Expired
        API-->>APIClient: 401 Unauthorized
        APIClient-->>CtrlClient: SessionExpiredError
        CtrlClient->>APIClient: Re-authenticate
        CtrlClient->>APIClient: Retry set_temperature
        APIClient->>API: PUT /api/ataunit/{id}
    end
    API-->>APIClient: 200 OK (empty)
    APIClient-->>CtrlClient: Success
    CtrlClient->>Coord: Debounced refresh (2s delay)

    Note over HA,API: A2W Zone Control (similar retry logic)
    HA->>Coord: climate.set_temperature(a2w_id, 21°C)
    Coord->>CtrlClient: control_client.async_set_temperature_zone1(a2w_id, 21)
    CtrlClient->>APIClient: client.atw.set_temperature_zone1(a2w_id, 21)
    APIClient->>API: PUT /api/atwunit/{id}<br/>{"setTemperatureZone1": 21, ...nulls...}
    API-->>APIClient: 200 OK (empty)

    Note over HA,API: Periodic State Update
    loop Every 60 seconds
        Coord->>APIClient: get_user_context()
        APIClient->>API: GET /api/user/context
        API-->>APIClient: Current state (all devices)
        APIClient-->>Coord: Updated state
        Coord->>HA: Update all entities
    end
```

**Control Client Responsibilities:**
- **Session recovery**: Automatically re-authenticates and retries on 401 errors
- **Deduplication**: Skips API calls when value hasn't changed
- **Debounced refresh**: Coordinates state refresh with 2-second delay for rapid calls
- **HA-specific validation**: Checks zone availability, temperature ranges

---

## Integration Layer Architecture

Shows the control client layer that sits between the coordinator and API client, providing session recovery and HA-specific logic.

```mermaid
graph TD
    Coordinator[MELCloudHomeCoordinator]
    ControlATA[ATAControlClient]
    ControlATW[ATWControlClient]
    APIClient[MELCloudHomeClient]
    ATAAPI[ATAClient Facade<br/>client.ata.*]
    ATWAPI[ATWClient Facade<br/>client.atw.*]

    Coordinator -->|ATA controls| ControlATA
    Coordinator -->|ATW controls| ControlATW
    ControlATA -->|API calls| APIClient
    ControlATW -->|API calls| APIClient
    APIClient --> ATAAPI
    APIClient --> ATWAPI

    style ControlATA fill:#fff4e1,stroke:#f9a825
    style ControlATW fill:#f0ffe1,stroke:#7cb342
    style APIClient fill:#e1f5ff,stroke:#039be5

    note1[Control Layer:<br/>- Session retry<br/>- Deduplication<br/>- Validation]
    note2[API Layer:<br/>- HTTP/auth<br/>- Device facades]

    ControlATA -.-> note1
    ControlATW -.-> note1
    APIClient -.-> note2
```

**Key Points:**
- **Two separate control client files**: `control_client_ata.py` and `control_client_atw.py`
- **Integration-level concerns**: Session recovery, retry logic, state deduplication
- **API-level concerns**: HTTP communication, authentication, device-type facades
- **Coordinator delegates**: All control operations go through control clients, never directly to API client

---

## Multi-Device Architecture

Showing the facade pattern and model relationships. Facade pattern provides device-type-specific control via `client.ata` and `client.atw`.

```mermaid
classDiagram
    class MELCloudHomeClient {
        +ATAControlClient ata
        +ATWControlClient atw
        +login() / logout()
        +get_user_context()
    }

    class ATAControlClient {
        <<facade>>
        +set_temperature()
        +set_mode()
        +set_fan_speed()
        +set_power()
    }

    class ATWControlClient {
        <<facade>>
        +set_temperature_zone1()
        +set_temperature_dhw()
        +set_operation_mode_zone1()
        +set_forced_hot_water()
        +set_power()
    }

    class MELCloudHomeAuth {
        <<authentication>>
        +login() / logout()
        +is_authenticated
    }

    class UserContext {
        +buildings List~Building~
        +get_all_air_to_air_units()
        +get_all_air_to_water_units()
    }

    class Building {
        +air_to_air_units List
        +air_to_water_units List
    }

    class AirToAirUnit {
        +power / operation_mode
        +temperatures / fan_speed
        +vane_directions
        +capabilities
    }

    class AirToWaterUnit {
        +power
        +operation_mode [STATUS]
        +operation_mode_zone1 [CONTROL]
        +zone temperatures
        +dhw temperatures
        +capabilities
    }

    class DeviceCapabilities {
        +temperature ranges
        +fan speeds
        +operation modes
    }

    class AirToWaterCapabilities {
        +temperature ranges
        +has_zone2
        +has_hot_water
    }

    MELCloudHomeClient --> MELCloudHomeAuth : uses
    MELCloudHomeClient --> ATAControlClient : composes
    MELCloudHomeClient --> ATWControlClient : composes
    ATAControlClient ..> MELCloudHomeClient : delegates
    ATWControlClient ..> MELCloudHomeClient : delegates
    MELCloudHomeClient --> UserContext : caches
    UserContext --> Building : contains
    Building --> AirToAirUnit : has many
    Building --> AirToWaterUnit : has many
    AirToAirUnit --> DeviceCapabilities : has one
    AirToWaterUnit --> AirToWaterCapabilities : has one
```

**Key Architectural Points:**

- **Facade Pattern:** `MELCloudHomeClient` composes `ATAControlClient` and `ATWControlClient` facades
- **Unified Entry Point:** Single client import, device-specific methods via `client.ata.*` and `client.atw.*`
- **Multi-Type Container:** `UserContext` holds both device types discovered from `/api/user/context`
- **Shared Authentication:** Single OAuth session serves all device types
- **Capabilities-Driven:** Each device has capabilities object defining valid operations/ranges

---

## ATW 3-Way Valve Behavior

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


## Related Documentation

- **ADR-011:** [Multi-Device-Type Architecture](decisions/011-multi-device-type-architecture.md)
- **ATA API Reference:** [ata-api-reference.md](api/ata-api-reference.md)
- **ATW API Reference:** [atw-api-reference.md](api/atw-api-reference.md)
- **Device Comparison:** [device-type-comparison.md](api/device-type-comparison.md)
- **OpenAPI Spec:** [../openapi.yaml](../openapi.yaml)
