# Documentation

## Architecture Decision Records (ADRs)

Key architectural decisions for the MELCloud Home integration:

- [ADR-001: Bundled API Client Architecture](decisions/001-bundled-api-client.md) - Why we bundle the API client instead of separate package

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
