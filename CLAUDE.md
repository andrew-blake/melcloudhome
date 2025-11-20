# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This repository is the MELCloud Home integration for Home Assistant, distributed via HACS.

**Repository:** <https://github.com/andrew-blake/melcloudhome>

**What's included:**

1. **MELCloud Home Integration** - Custom component with full HVAC control and energy monitoring
2. **API Client** - Bundled API client library in `custom_components/melcloudhome/api/`
3. **Tests** - Comprehensive test suite with pytest and VCR cassettes
4. **Documentation** - Architecture decision records (ADRs), API reference, research notes
5. **Development Tools** - Deployment scripts, debugging utilities

## Remote System Access

The Home Assistant system runs in Docker on a remote server:

```bash
# Connect to the system
ssh ha

# Run commands with sudo
ssh ha "sudo <command>"

# Access containers
ssh ha "sudo docker ps"
ssh ha "sudo docker logs homeassistant --tail 100"
ssh ha "sudo docker exec homeassistant <command>"
```

## Diagnostics and Troubleshooting

When diagnosing issues:

1. **Check container status:** `ssh ha "sudo docker ps"`
2. **View logs:** `ssh ha "sudo docker logs homeassistant --tail 500"`
3. **Filter errors:** `ssh ha "sudo docker logs homeassistant --tail 500 2>&1 | grep -i error | tail -50"`
4. **Check integration files:** `ssh ha "sudo docker exec homeassistant ls -la /config/"`

See `.claude/skills/home-assistant-diagnostics/skill.md` for detailed diagnostic workflows and common issue patterns.

## MELCloud Home Integration Development

### Project Structure

```text
custom_components/melcloudhome/  # Custom component (bundled approach)
├── api/                         # Bundled API client library
│   ├── auth.py                  # AWS Cognito OAuth authentication
│   ├── client.py                # Main API client
│   ├── const.py                 # API constants & enum mappings
│   ├── exceptions.py            # Custom exceptions
│   └── models.py                # Data models
├── climate.py                   # Climate platform (HVAC control)
├── sensor.py                    # Sensor platform (temperature, WiFi, energy)
├── binary_sensor.py             # Binary sensors (error, connection)
├── config_flow.py               # Configuration UI
├── coordinator.py               # Data update coordinator
└── diagnostics.py               # Diagnostic data export

docs/
├── api/                         # API documentation
│   ├── melcloudhome-api-reference.md
│   └── melcloudhome-telemetry-endpoints.md
├── decisions/                   # Architecture Decision Records (ADRs)
├── research/                    # Research and planning documents
└── ROADMAP.md                   # Project roadmap

tests/                           # Test suite with VCR cassettes
tools/                           # Development and deployment tools
openapi.yaml                     # OpenAPI 3.0.3 specification
_claude/                         # Session notes (local only, not in git)
```

### Key Decisions

- **Bundled API Client:** Library code in `api/` subfolder (KISS/YAGNI) - See [ADR-001](docs/decisions/001-bundled-api-client.md)
- **No PyPI Package:** Can migrate later if needed
- **Type Safe:** Using mypy with strict settings
- **Formatted:** Ruff for linting & formatting

### Development Workflow

```bash
# Setup
uv sync                          # Install dependencies
source .venv/bin/activate        # Activate virtual environment

# Code Quality
make format                      # Format with ruff
make lint                        # Lint with ruff
make type-check                  # Type check with mypy
make all                         # Run all checks

# Pre-commit hooks run automatically on git commit

# Deployment & Testing (see tools/README.md for details)
python tools/deploy_custom_component.py melcloudhome          # Deploy to HA
python tools/deploy_custom_component.py melcloudhome --test   # Deploy + test via API
python tools/deploy_custom_component.py melcloudhome --watch  # Deploy + watch logs
```

### Critical API Details

- **User-Agent Required:** Must use Chrome User-Agent or requests blocked
- **String vs Integer Enums:** Control API uses strings, Schedule API uses integers
- **Fan Speeds:** STRINGS ("Auto", "One"-"Five") NOT integers
- **Auto Mode:** "Automatic" NOT "Auto"
- **Rate Limiting:** Minimum 60-second polling interval

See `docs/api/melcloudhome-api-reference.md` for complete API details.

### Deployment & Testing

**Automated Deployment Tool** (Recommended):

The repository includes an automated deployment tool that handles the complete cycle:

```bash
# Deploy to remote HA instance
python tools/deploy_custom_component.py melcloudhome

# Deploy + test via API
python tools/deploy_custom_component.py melcloudhome --test

# Deploy + watch logs
python tools/deploy_custom_component.py melcloudhome --watch
```

The tool automatically:

- Copies integration to remote server via SSH
- Installs into Docker container
- Restarts Home Assistant
- Monitors logs for errors
- Tests entities via API (with `--test`)

**Configuration:** Set `HA_SSH_HOST`, `HA_CONTAINER`, `HA_URL`, and `HA_TOKEN` in `.env`

**Full documentation:** See [tools/README.md](tools/README.md)

**Manual deployment:**

```bash
# Copy to HA config directory
scp -r custom_components/melcloudhome ha:/tmp/
ssh ha "sudo docker cp /tmp/melcloudhome homeassistant:/config/custom_components/"
ssh ha "sudo docker restart homeassistant"
```

## VSCode Configuration

The repository includes VSCode settings that associate `*.yaml` files with the `home-assistant` file type for proper syntax highlighting and validation.

- NEVER work around pre-commit hooks. They are important code quality checks.
