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

## Quality Reviews

- [Integration Review](integration-review.md) - Best practices compliance assessment
- [Testing Strategy](testing-strategy.md) - Testing approach and philosophy

## OpenAPI Specification

- [openapi.yaml](../openapi.yaml) - Complete OpenAPI 3.0.3 specification for MELCloud Home API
