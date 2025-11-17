# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This repository contains:
1. **MELCloud Home Integration** - Custom component for Home Assistant (in development)
2. **Home Assistant Configuration** - Running on remote Docker server
3. **API Documentation** - Complete MELCloud Home API docs in `_claude/`

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

```
custom_components/melcloudhome/  # Custom component (bundled approach)
├── api/                         # Bundled API client library
│   ├── const.py                 # API constants & enum mappings
│   ├── exceptions.py            # Custom exceptions
│   ├── models.py                # Data models
│   ├── auth.py                  # AWS Cognito OAuth (TODO)
│   └── client.py                # Main API client (TODO)
└── [HA integration files]       # TODO

_claude/                         # API documentation (~87% complete)
openapi.yaml                     # OpenAPI 3.0.3 specification
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

See `_claude/melcloudhome-api-reference.md` for complete API details.

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
