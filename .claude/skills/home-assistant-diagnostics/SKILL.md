---
name: home-assistant-diagnostics
description: Diagnose Home Assistant errors by connecting via SSH, checking Docker containers, reading logs, and identifying integration issues. Use when the user mentions Home Assistant errors, issues, problems, diagnostics, or when they want to troubleshoot their HA system.
---

# Home Assistant Diagnostics Skill

This skill provides expertise in diagnosing Home Assistant issues via SSH access.

## Connection

### SSH Access

The Home Assistant system is accessible via:
```bash
ssh ha
```

Commands should be run with `sudo` for elevated privileges:
```bash
ssh ha "sudo <command>"
```

### API Access

The Home Assistant API can be accessed locally:
- **Local URL:** `https://homeassistant.local:8123`
- **API Token:** Available in `$HA_API_KEY` environment variable

**Query sensor states:**
```bash
curl -k -H "Authorization: Bearer $HA_API_KEY" \
  "https://homeassistant.local:8123/api/states/sensor.entity_id"
```

Note: Use `-k` flag to skip SSL certificate verification for local access.

### Configuration Management Repository

A local repository is available at `~/Development/home-automation/home-assistant/claude-homeassistant` with validation and diagnostic tools.

**Available Tools:**

All tools should be run from the repository root with venv activated:
```bash
cd ~/Development/home-automation/home-assistant/claude-homeassistant
source venv/bin/activate
```

**1. Entity Explorer** - Search and explore entities from registry
```bash
python tools/entity_explorer.py --search "keyword"
python tools/entity_explorer.py --domain sensor
python tools/entity_explorer.py --area kitchen --full
```

**2. Validation Tools:**
```bash
# Run all validators with comprehensive report
python tools/run_tests.py

# Individual validators
python tools/yaml_validator.py config/
python tools/reference_validator.py config/
python tools/ha_official_validator.py config/
```

**3. Configuration Management:**
```bash
# Pull latest config from HA
make pull

# Push validated config to HA
make push

# Reload HA configuration via API
python tools/reload_config.py
```

**4. Quick Makefile Commands:**
```bash
make entities ARGS='--search zappi'  # Search entities
make validate                         # Run all tests
make backup                          # Backup config
```

**Note:** All API tools now have SSL verification disabled (`verify=False`) for local HTTPS access and will work with self-signed certificates.

## Diagnostic Workflow

When diagnosing Home Assistant issues, follow this workflow:

### 1. Check System Status

**Get system information:**
```bash
ssh ha -t "sudo -i"
# Shows banner with OS version, HA Core version, and IP addresses
```

**List running containers:**
```bash
ssh ha "sudo docker ps"
```

Look for:
- `homeassistant` - Core Home Assistant container
- `hassio_supervisor` - Supervisor container
- Add-on containers (mosquitto, zigbee2mqtt, etc.)
- Container health status

### 2. Examine Logs

**Home Assistant Core logs:**
```bash
ssh ha "sudo docker logs homeassistant --tail 100"
```

**Filter for errors:**
```bash
ssh ha "sudo docker logs homeassistant --tail 500 2>&1 | grep -i error | tail -50"
```

**Specific add-on logs:**
```bash
ssh ha "sudo docker logs <container-name> --tail 100"
```

**Real-time log monitoring:**
```bash
ssh ha "sudo docker logs -f homeassistant"
```

### 3. Analyze Error Patterns

Common error categories:

**Integration/Component Errors:**
- Look for component name in error path (e.g., `homeassistant.components.melcloud`)
- Check for `Error fetching`, `Error handling`, `Error loading`
- Note recurring vs. one-time errors

**Connectivity Issues:**
- Device offline/unreachable errors
- API timeout errors
- DNS resolution failures
- SSL/TLS errors

**Authentication Failures:**
- `401: Unauthorized`
- `403: Forbidden`
- Invalid credentials
- Missing API tokens

**Library/Dependency Errors:**
- `AttributeError`, `ImportError`, `ModuleNotFoundError`
- Version compatibility issues
- Missing dependencies

### 4. Check Integration Status

**View Home Assistant configuration:**
```bash
ssh ha "sudo docker exec homeassistant ls -la /config/"
```

**Check custom components:**
```bash
ssh ha "sudo docker exec homeassistant ls -la /config/custom_components/"
```

**Inspect integration manifest:**
```bash
ssh ha "sudo docker exec homeassistant cat /usr/src/homeassistant/homeassistant/components/<integration>/manifest.json"
```

### 5. Inspect Libraries

**Check installed library:**
```bash
ssh ha "sudo docker exec homeassistant pip show <package-name>"
```

**View library source code:**
```bash
ssh ha "sudo docker exec homeassistant cat /usr/local/lib/python3.13/site-packages/<package>/<file>.py"
```

**Find libraries:**
```bash
ssh ha "sudo docker exec homeassistant ls -la /usr/local/lib/python3.13/site-packages/ | grep <keyword>"
```

### 6. Debug Sensor States

**Check if entity exists in registry:**
```bash
ssh ha "sudo docker exec homeassistant cat /config/.storage/core.entity_registry | jq -r '.data.entities[] | select(.entity_id == \"sensor.entity_id\")'"
```

**Check current state:**
```bash
ssh ha "sudo docker exec homeassistant cat /config/.storage/core.restore_state | jq -r '.data[] | select(.state.entity_id == \"sensor.entity_id\") | .state'"
```

**Query live state via API:**
```bash
curl -k -H "Authorization: Bearer $HA_API_KEY" \
  "https://homeassistant.local:8123/api/states/sensor.entity_id" | jq '.'
```

**Python script to check multiple sensors:**
```python
import os, requests, json
requests.packages.urllib3.disable_warnings()

HA_URL = 'https://homeassistant.local:8123'
HA_TOKEN = os.getenv('HA_API_KEY')
headers = {'Authorization': f'Bearer {HA_TOKEN}'}

response = requests.get(f'{HA_URL}/api/states/sensor.entity_id',
                       headers=headers, verify=False)
print(json.dumps(response.json(), indent=2))
```

### 7. Template Sensor Debugging

When template sensors aren't working:

1. **Check entity registry** - Verify sensor was created with correct entity_id
2. **Add unique_id** - Template sensors need `unique_id` to persist after restarts
3. **Verify input entities** - Check that all referenced entities exist and have valid states
4. **Check for unavailable states** - If input is unavailable, template may not evaluate
5. **Review template syntax** - Ensure Jinja2 syntax is correct
6. **Check logs** - Look for template rendering errors

**Common template issues:**
```yaml
# ❌ Missing unique_id - won't persist
- sensor:
    - name: "My Template"
      state: "{{ states('sensor.input') }}"

# ✅ With unique_id - persists properly
- sensor:
    - name: "My Template"
      unique_id: my_template_sensor
      state: "{{ states('sensor.input') }}"
```

## Analysis Guidelines

### Prioritize Errors

1. **Critical** - System-wide failures, core component crashes
2. **High** - Integration failures affecting multiple devices
3. **Medium** - Single device connectivity issues
4. **Low** - Cosmetic issues, deprecated warnings

### Pattern Recognition

- **Recurring errors** - Ongoing issues (device offline, API timeout)
- **Burst errors** - Multiple errors in short time (configuration attempt)
- **One-time errors** - Transient issues (network hiccup)

### Root Cause Analysis

1. **Read the full stack trace** - Don't just look at the last line
2. **Identify the source** - Core HA, integration, or library?
3. **Check timestamps** - When did it start? How often?
4. **Look for related errors** - Multiple symptoms of one issue?
5. **Verify external dependencies** - API services, network, devices

## Common Issues and Solutions

### Device Connectivity
- Check device power and network
- Verify IP addresses
- Test network connectivity with ping
- Check WiFi signal strength

### Integration Authentication
- Verify credentials in external service
- Check for API changes or service updates
- Look for library bugs in GitHub issues
- Consider library version compatibility

### Library Bugs
- Check library version
- Search GitHub issues for known bugs
- Look for recent commits/fixes
- Consider patching or using alternative integration

### Docker Issues
- Check container health status
- Restart specific containers: `ssh ha "sudo docker restart <container>"`
- Check resource usage: CPU, memory, disk

## Reporting

When reporting findings to the user:

1. **Summarize errors** by category and severity
2. **Identify root causes** when possible
3. **Provide specific recommendations** with commands or steps
4. **Prioritize actions** - what to fix first
5. **Offer to investigate further** specific issues

## Best Practices

- Always check last 100-500 log lines first
- Use grep to filter relevant errors
- Check timestamps to understand error frequency
- Verify external services are accessible
- Consider recent changes (updates, config changes)
- Don't just read errors - analyze patterns and causes

## Key Integrations

### Octopus Energy
- Custom component for UK energy provider
- Intelligent dispatching for EV charging
- Entity format: `binary_sensor.octopus_energy_[device_id]_intelligent_dispatching`
- Common issues: API connectivity, entity ID changes after updates

### MyEnergi (Zappi/Eddi)
- Custom component for EV chargers and solar diverters
- Key sensors: `plug_status`, `status`, `power_ct_internal_load`
- Entity format: `sensor.myenergi_zappi_[serial]_[sensor_type]`
- Integration may go offline if devices lose connectivity

### Solar/Energy Management
- Template sensors aggregate multiple inverter outputs
- Powerwall integration for battery management
- Automations coordinate charging with cheap rate periods

### Configuration Location
- Remote: `/config/` on HA Docker container
- Local: `~/Development/home-automation/home-assistant/claude-homeassistant/config/`
- Sync: Use `make pull` to download, `make push` to upload with validation
