# Documentation

## Architecture Decision Records (ADRs)

Key architectural decisions for the MELCloud Home integration:

- [ADR-001: Bundled API Client Architecture](decisions/001-bundled-api-client.md) - Why we bundle the API client instead of separate package
- [ADR-002: Authentication Refresh Strategy](decisions/002-authentication-refresh-strategy.md) - Session management approach
- [ADR-003: Entity Naming Strategy](decisions/003-entity-naming-strategy.md) - Stable entity ID generation
- [ADR-004: Integration Refactoring](decisions/004-integration-refactoring.md) - Separation of concerns
- [ADR-005: Divergence from Official MELCloud](decisions/005-divergence-from-official-melcloud.md) - Why we target different API
- [ADR-006: Entity Description Pattern](decisions/006-entity-description-pattern.md) - Sensor/binary_sensor implementation
- [ADR-007: Defer WebSocket Implementation](decisions/007-defer-websocket-implementation.md) - Real-time updates deferral
- [ADR-008: Energy Monitoring Architecture](decisions/008-energy-monitoring-architecture.md) - Energy tracking with persistence
- [ADR-009: Reconfigure Password-Only](decisions/009-reconfigure-password-only.md) - Config flow password updates
- [ADR-010: Entity ID Prefix Change](decisions/010-entity-id-prefix-change.md) - Breaking change for stable IDs
- [ADR-011: Multi-Device-Type Architecture](decisions/011-multi-device-type-architecture.md) - ATA/ATW unified client (facade pattern)
- [ADR-012: ATW Entity Architecture](decisions/012-atw-entity-architecture.md) - Power control and entity design for heat pumps
- [ADR-013: Automatic Friendly Device Names](decisions/013-automatic-friendly-device-names.md) - UX improvement via name_by_user
- [ADR-014: ATW Telemetry Sensors](decisions/014-atw-telemetry-sensors.md) - Flow/return temperature sensors implementation
- [ADR-015: Skip ATW Energy Monitoring](decisions/015-skip-atw-energy-monitoring.md) - Initial decision to skip energy (SUPERSEDED by ADR-016)
- [ADR-016: Implement ATW Energy Monitoring](decisions/016-implement-atw-energy-monitoring.md) - Energy monitoring with capability-based detection (ERSC-VM2D)

## Architecture

- [Architecture Overview](architecture.md) - High-level system architecture with visual diagrams: multi-device-type patterns, ATW entity design, 3-way valve behavior, API layer structure

## Quality Reviews

- [Integration Review](integration-review.md) - Best practices compliance assessment
- [Testing Strategy](testing-strategy.md) - Testing approach and philosophy

## OpenAPI Specification

- [openapi.yaml](../openapi.yaml) - Complete OpenAPI 3.0.3 specification for MELCloud Home API
