# Custom Component Development Tools

## Automated Deployment & Testing

### `deploy_custom_component.py`

Automates the complete deployment cycle for custom Home Assistant integrations:
- Copies component to remote HA instance
- Installs into Docker container
- Restarts Home Assistant
- Monitors logs for errors
- Tests via API (optional)

### Prerequisites

1. **SSH access** to Home Assistant host
2. **Docker** running Home Assistant
3. **API token** (optional, for testing)

### Setup

1. Configure `.env` file in project root:
   ```bash
   # Required for deployment
   HA_SSH_HOST=ha                    # SSH hostname
   HA_CONTAINER=homeassistant        # Docker container name

   # Optional for API testing
   HA_URL=https://homeassistant.local:8123
   HA_TOKEN=your_long_lived_token_here
   ```

2. Get API token (optional):
   - Open Home Assistant → Profile
   - Scroll to "Long-Lived Access Tokens"
   - Create token and add to `.env`

### Usage

**Basic deployment:**
```bash
python tools/deploy_custom_component.py melcloudhome
```

**Deploy + API testing:**
```bash
python tools/deploy_custom_component.py melcloudhome --test
```

**Deploy + watch logs:**
```bash
python tools/deploy_custom_component.py melcloudhome --watch
```

**Deploy different component:**
```bash
python tools/deploy_custom_component.py my_other_integration
```

### What It Does

1. ✅ **Copy** - Uses `rsync` to copy `custom_components/[name]/` to remote server
2. ✅ **Install** - Copies files into container at `/config/custom_components/[name]/`
3. ✅ **Restart** - Restarts the Home Assistant Docker container
4. ✅ **Monitor** - Waits for HA to initialize and checks logs
5. ✅ **Verify** - Detects if integration loaded successfully or has errors
6. ✅ **Test** - (Optional) Tests entities via REST API if `--test` flag used
7. ✅ **Watch** - (Optional) Streams live logs if `--watch` flag used

### Example Output

```
🚀 Deploying melcloudhome to Home Assistant...

📦 Copying files to ha...
✓ Files copied
📋 Installing into container...
✓ Installed into container
🔄 Restarting Home Assistant...
✓ Container restarted
⏳ Waiting for Home Assistant to initialize...
✓ Home Assistant initialized

🔍 Checking integration logs...
✓ Integration detected in logs

📋 Recent integration logs:
   INFO custom_components.melcloudhome: Setting up MELCloud Home v2
   INFO custom_components.melcloudhome.climate: Found 3 climate entities

✅ Deployment complete!

Next steps:
1. Open Home Assistant UI: https://homeassistant.local:8123
2. Configuration → Integrations → Add Integration
3. Search for 'melcloudhome' and configure
```

### Error Detection

The tool automatically detects and highlights errors:

```
🔍 Checking integration logs...
✓ Integration detected in logs

❌ ERRORS DETECTED:
   ERROR custom_components.melcloudhome: Failed to load climate platform
   Traceback (most recent call last):
   ...
```

### Development Workflow

Fast iterative development cycle:

```bash
# 1. Make code changes
vim custom_components/melcloudhome/climate.py

# 2. Deploy and test
python tools/deploy_custom_component.py melcloudhome --test

# 3. Check results in logs or UI

# 4. Repeat!
```

### API Testing Features

When using `--test` flag, the tool:
- Connects to Home Assistant REST API
- Lists all entities from your integration
- Shows entity states and attributes
- Verifies integration is working

Example output:
```
🧪 Testing integration via API...
✓ Found 3 entity(s)
   • climate.home_living_room_heatpump: heat
   • climate.home_kitchen_heatpump: cool
   • climate.home_bedroom_heatpump: off
```

### Troubleshooting

**SSH connection fails:**
```bash
# Test SSH access
ssh ha "echo 'Connection OK'"

# Check SSH config
cat ~/.ssh/config
```

**Container not found:**
```bash
# List containers
ssh ha "sudo docker ps -a"

# Update HA_CONTAINER in .env if different
```

**API testing fails:**
```bash
# Verify HA_URL is correct
curl -k https://homeassistant.local:8123/api/

# Verify token is valid
# Regenerate token in HA UI if needed
```

**Integration not loading:**
- Check logs with `--watch` flag
- Look for Python syntax errors
- Verify all required files exist
- Check manifest.json is valid

### Integration with Existing Tools

This tool follows the same patterns as other HA tools in this project:
- Loads `.env` from project root
- Uses same environment variables (`HA_URL`, `HA_TOKEN`)
- Compatible with existing `claude-homeassistant/` tools
- Same color-coded output style

### Related Tools

See also:
- `claude-homeassistant/tools/reload_config.py` - Reload HA config without restart
- `claude-homeassistant/tools/ha_api_diagnostic.py` - Comprehensive API testing
- `claude-homeassistant/tools/entity_explorer.py` - Explore entities in detail

## Other Tools

### `test_auth.py`
Test MELCloud Home authentication (for API client development).

### Future Tools
- Integration validation
- Entity testing
- Performance profiling
