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

### 2.1. Enable Advanced Mode (Required for Development Mode)

To see the "Connect to Mock Server" option during integration setup:

1. Click your profile name (bottom left corner)
2. Enable **Advanced Mode** toggle
3. Click **Update** to save

**Why required?** The "Connect to Mock Server" option is hidden from regular users to prevent accidental connection to mock API in production. Advanced Mode is the standard Home Assistant pattern for developer-only features.

**Technical details:** See `config_flow.py` - checkbox only shown when `user_input.get("show_advanced_options")` is True.

Without Advanced Mode enabled, the "Connect to Mock Server" checkbox will be hidden (production behavior).

### 3. Add the MELCloud Home integration

**Prerequisites:** Enable Advanced Mode in your profile (see step 2.1)

1. Go to **Settings → Devices & Services**
2. Click **+ Add Integration**
3. Search for "MELCloud Home"
4. Configure with mock server:
   - **Email:** `test@example.com` (any email works)
   - **Password:** `test123` (any password works)
   - **Connect to Mock Server:** ☑️ **Enable** (only visible with Advanced Mode on)

The "Connect to Mock Server" checkbox connects to the mock server instead of production MELCloud API. The mock server will accept any credentials and return sample devices.

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
- `make dev-snapshot SNAPSHOT=path` - Save current state to snapshot
- `make dev-restore-snapshot SNAPSHOT=path` - Restore from saved snapshot
- `make dev-rebuild` - Rebuild mock server image
- `make dev-down` - Stop environment

### View mock server logs:

```bash
docker compose -f docker-compose.dev.yml logs -f melcloud-mock
```

### Reset environment (restore to clean snapshot):

```bash
make dev-reset
```

This restores the dev environment to a clean snapshot with:
- User account already created (dev/dev)
- Onboarding completed

You'll need to add the integration through the UI (Settings → Devices & Services).
Much faster than creating the user account from scratch!

### Save and restore snapshots:

**Save current state:**

Capture the current running environment state to a snapshot:

```bash
# Save current state with a descriptive name
make dev-snapshot SNAPSHOT=dev-config-snapshots/my-test-state

# Example: Save baseline before testing
make dev-snapshot SNAPSHOT=dev-config-snapshots/baseline-v1.3.4
```

**What gets saved:**
- Complete `.storage` directory (all entity/device registries, auth, etc.)
- Separate copies of entity and device registries for easy inspection

**Restore from snapshot:**

Restore a previously saved configuration:

```bash
# Restore from your saved snapshot
make dev-restore-snapshot SNAPSHOT=dev-config-snapshots/my-test-state

# Example: Restore baseline for comparison
make dev-restore-snapshot SNAPSHOT=dev-config-snapshots/baseline-v1.3.4
```

**Use cases:**
- Save state before/after major changes for comparison testing
- Create known-good checkpoints during development
- Revert to a baseline after testing
- Switch between different test configurations
- Upgrade verification testing (save before, compare after)

**Notes:**
- Snapshot command requires Home Assistant container to be running
- Restore command stops containers, restores state, starts only HA (not mock server)
- Use `make dev-up` after restore if you need the mock server

### Complete reset (wipe everything):

```bash
make dev-reset-full
```

This completely wipes the environment and starts from scratch. You'll need to create the user and configure the integration again.

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
make dev-reset       # Restore to clean snapshot (fast)
make dev-reset-full  # Complete wipe (slow)
```

### "Connect to Mock Server" checkbox not visible

**Symptom:** Can't see the "Connect to Mock Server" checkbox when adding the integration.

**Solution:** Enable Advanced Mode in your Home Assistant profile:
1. Click your profile (bottom left)
2. Enable "Advanced Mode" toggle
3. Return to integration setup

The "Connect to Mock Server" field is hidden by default to prevent production users from accidentally enabling it.

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
