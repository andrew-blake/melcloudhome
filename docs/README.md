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

## Integration Comparisons

- [LG ThinQ vs MELCloud Home](lg-thinq-comparison.md) - Architecture comparison with official HA integration

## API Documentation

Complete API documentation is in the `_claude/` directory:

- **melcloudhome-api-reference.md** - Control API with UI-verified parameters
- **melcloudhome-schedule-api.md** - Schedule management CRUD operations
- **melcloudhome-telemetry-endpoints.md** - Monitoring and reporting APIs
- **melcloudhome-knowledge-gaps.md** - Known gaps and testing plan (~87% coverage)
- **NEXT-STEPS.md** - Project status and roadmap

## OpenAPI Specification

- **openapi.yaml** - Complete OpenAPI 3.0.3 specification
- View at: http://localhost:8080/scalar-docs.html (when server running)

## Project Status

See [NEXT-STEPS.md](../_claude/NEXT-STEPS.md) for current implementation status and roadmap.
