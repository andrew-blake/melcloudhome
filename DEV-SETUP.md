# Development Environment Setup

Quick guide for running Home Assistant with the MELCloud Home integration locally for testing.

## Features

✅ **Auto-setup** - Admin account created automatically (dev/dev)
✅ **Skip onboarding** - No wizard, straight to dashboard
✅ **Mock API server** - Test without real MELCloud hardware
✅ **Hot reload** - Restart HA after code changes
✅ **Debug logging** - Full visibility into integration behavior
✅ **Isolated** - Runs in Docker, doesn't affect your system

## Prerequisites

- Docker
- Docker Compose

## Quick Start

### 1. Start the development environment

```bash
make dev-up
# Or: docker compose -f docker-compose.dev.yml up -d
```

This starts:
- **Mock MELCloud API** on `http://localhost:8080`
- **Home Assistant** on `http://localhost:8123`

### 2. Access Home Assistant

Open your browser to: **http://localhost:8123**

- **Username:** `dev`
- **Password:** `dev`

The onboarding wizard is skipped - you'll go straight to the dashboard.

### 3. Add the MELCloud Home integration

1. Go to **Settings → Devices & Services**
2. Click **+ Add Integration**
3. Search for "MELCloud Home"
4. Configure with mock server:
   - **Email:** `test@example.com` (any email works)
   - **Password:** `test123` (any password works)
   - **Base URL (if prompted):** `http://melcloud-mock:8080`

The mock server will accept any credentials and return sample devices.

## Development Workflow

### After changing integration code:

```bash
# Restart Home Assistant to load changes
make dev-restart

# View logs
make dev-logs
```

**Make commands available:**
- `make dev-up` - Start dev environment
- `make dev-restart` - Restart HA (reload code changes)
- `make dev-logs` - View HA logs
- `make dev-reset` - Reset environment (clear entity registry)
- `make dev-rebuild` - Rebuild mock server image
- `make dev-down` - Stop environment

### View mock server logs:

```bash
docker compose -f docker-compose.dev.yml logs -f melcloud-mock
```

### Reset environment (clear entity registry):

```bash
make dev-reset
```

This stops containers, deletes `dev-config/.storage`, and starts fresh with clean entity registrations.

## Mock Server Details

The mock server provides:
- **2 ATA devices** (Air-to-Air / AC units)
  - Living Room AC
  - Bedroom AC
- **1 ATW device** (Air-to-Water / Heat Pump)
  - House Heat Pump (with Zone 1 + DHW tank)

All devices are stateful - changes persist across API calls.

### Testing API directly:

```bash
# Get all devices
curl http://localhost:8080/api/user/context | jq

# Control ATA device
curl -X PUT http://localhost:8080/api/ataunit/ata-living-room \
  -H "Content-Type: application/json" \
  -d '{"operationMode": "Cool", "setTemperature": 22.5}'

# Control ATW device
curl -X PUT http://localhost:8080/api/atwunit/atw-house-heatpump \
  -H "Content-Type: application/json" \
  -d '{"setTemperatureZone1": 21.0, "forcedHotWaterMode": true}'
```

## Customization

### Change admin credentials:

Create `.env` file:
```bash
HASS_USERNAME=admin
HASS_PASSWORD=mypassword
```

### Run mock server with different port:

Edit `docker-compose.dev.yml` and change the port mapping.

## Troubleshooting

### Port already in use

If port 8123 or 8080 is already in use:

```bash
# Check what's using the port
lsof -ti:8123
lsof -ti:8080

# Kill the process
kill -9 $(lsof -ti:8123)
```

Or change the port in `docker-compose.dev.yml`:
```yaml
ports:
  - "9123:8123"  # Use port 9123 instead
```

### Integration not showing up

1. Check the custom component is mounted:
   ```bash
   docker compose -f docker-compose.dev.yml exec homeassistant \
     ls -la /config/custom_components/melcloudhome
   ```

2. Check logs for errors:
   ```bash
   docker compose -f docker-compose.dev.yml logs homeassistant | grep melcloudhome
   ```

3. Restart Home Assistant:
   ```bash
   docker compose -f docker-compose.dev.yml restart homeassistant
   ```

### Clear all data and start fresh

```bash
make dev-reset
```

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Your Code     │────▶│  Home Assistant  │────▶│  Mock MELCloud  │
│ custom_comp...  │     │   (Container)    │     │   API Server    │
│  (mounted)      │     │   localhost:8123 │     │  localhost:8080 │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                              │
                              ▼
                        ┌──────────────┐
                        │  dev-config/ │
                        │  (volume)    │
                        └──────────────┘
```

## What Gets Auto-Created

On first startup, the init script creates:

- ✅ Admin user account
- ✅ Onboarding completion markers
- ✅ Basic `configuration.yaml`
- ✅ Empty `secrets.yaml`
- ✅ Auth provider configuration
- ✅ Storage files to skip wizard

These files are stored in `dev-config/` and persist between restarts.

## Comparing to Production

**Key differences from your remote HA instance:**

| Aspect | Dev Environment | Production |
|--------|----------------|------------|
| **API endpoint** | Mock server (localhost:8080) | Real MELCloud API |
| **Devices** | 2 ATA + 1 ATW (simulated) | Your actual devices |
| **Data** | In-memory state | Real sensor data |
| **Config** | dev-config/ (local) | Remote server |
| **Auth** | No validation | Real OAuth tokens |

The mock server is perfect for testing integration logic, UI, and state management without physical hardware.

## Next Steps

- Edit code in `custom_components/melcloudhome/`
- Restart HA container to load changes
- Test in UI at http://localhost:8123
- Check logs for errors or debug output
- Commit your changes when ready

Happy developing! 🚀
