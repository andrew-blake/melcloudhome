# Common Home Assistant Error Patterns

## Integration-Specific Errors

### Shelly Devices
```
Error fetching <device-name> data: An error occurred while retrieving data from <device>
Error running connected events for device <device>
Error fetching <device> data: An error occurred while reconnecting to <device>
```

**Causes:**
- Device offline or powered off
- Network connectivity issues
- WiFi signal too weak
- Device firmware issues
- IP address changed

**Solutions:**
- Check device power and network connection
- Verify device is reachable via ping
- Check WiFi signal strength
- Reboot device
- Update device firmware
- Reserve IP address in DHCP

### MELCloud / MELCloud Home
```
AttributeError: 'NoneType' object has no attribute 'get'
401: Unauthorized
Error: unauthorized: missing or invalid API token
```

**Causes:**
- Wrong MELCloud domain (app.melcloud.com vs melcloudhome.com)
- Invalid credentials
- Library doesn't support MELCloud Home
- API authentication changes

**Solutions:**
- Verify credentials work on correct domain
- Check if using MELCloud (old) or MELCloud Home (new)
- MELCloud Home is not currently supported in HA
- Consider Protoart WiFi adapter for MELCloud Home devices

### Octopus Energy
```
Error requesting <meter>_previous_consumption_and_rates data: Cannot connect to host api.octopus.energy:443 ssl:default [Timeout while contacting DNS servers]
```

**Causes:**
- Temporary DNS issues
- Network connectivity problems
- API service temporarily down

**Solutions:**
- Usually resolves automatically
- Check DNS configuration if persistent
- Verify internet connectivity

### Zigbee2MQTT
```
Error: Failed to connect to the adapter
MQTT connection lost
Device not responding
```

**Causes:**
- Zigbee coordinator disconnected
- MQTT broker down
- Device out of range
- Interference on Zigbee channel

**Solutions:**
- Check Zigbee coordinator USB connection
- Restart Mosquitto broker
- Move devices closer to coordinator
- Change Zigbee channel if interference

## Python/Library Errors

### AttributeError
```
AttributeError: 'NoneType' object has no attribute 'X'
```

**Causes:**
- Library bug - missing null checks
- API response format changed
- Unexpected API error response

**Solutions:**
- Check library version and known issues
- Look for library updates or patches
- Report bug to library maintainer
- Create workaround/patch if urgent

### ImportError / ModuleNotFoundError
```
ImportError: cannot import name 'X' from 'Y'
ModuleNotFoundError: No module named 'X'
```

**Causes:**
- Missing dependency
- Wrong library version
- Incompatible Python version
- Library not installed

**Solutions:**
- Install missing dependency
- Update to compatible library version
- Check manifest.json requirements

### TimeoutError
```
TimeoutError: [Errno 110] Connection timed out
asyncio.exceptions.TimeoutError
```

**Causes:**
- Network connectivity issues
- Device/service not responding
- Firewall blocking connection
- DNS resolution problems

**Solutions:**
- Check network connectivity
- Verify device/service is online
- Check firewall rules
- Test DNS resolution

## Authentication Errors

### 401 Unauthorized
```
401: Unauthorized
Error: unauthorized: missing or invalid API token
```

**Causes:**
- Wrong credentials
- Expired token
- Missing API token configuration
- Token not properly configured

**Solutions:**
- Verify credentials in external service
- Reconfigure integration with fresh credentials
- Check for API token in configuration
- Generate new API token if needed

### 403 Forbidden
```
403: Forbidden
Access denied
```

**Causes:**
- Insufficient permissions
- Account suspended
- API key restrictions
- IP address blocked

**Solutions:**
- Check account status in external service
- Verify API key permissions
- Check for IP restrictions
- Contact service provider

## Docker/System Errors

### Container Not Running
```
Error response from daemon: Container X is not running
```

**Causes:**
- Container crashed
- Configuration error
- Resource exhaustion
- Dependency missing

**Solutions:**
- Check container logs: `docker logs <container>`
- Restart container: `docker restart <container>`
- Check system resources
- Verify configuration

### Permission Denied
```
PermissionError: [Errno 13] Permission denied
```

**Causes:**
- File permissions incorrect
- Running without necessary privileges
- SELinux/AppArmor restrictions

**Solutions:**
- Check file ownership and permissions
- Use sudo for privileged operations
- Review security policy restrictions

## Configuration Errors

### Integration Not Found
```
Integration 'X' not found
homeassistant.loader.IntegrationNotFound
```

**Causes:**
- Integration not installed
- Custom component not loaded
- Typo in integration name
- HACS not properly installed

**Solutions:**
- Install integration via HACS or UI
- Verify custom_components directory
- Restart Home Assistant
- Check spelling of integration name

### Invalid Configuration
```
Invalid config for [X]
Setup failed for X: Integration failed to initialize
```

**Causes:**
- Syntax error in configuration.yaml
- Missing required fields
- Invalid values
- Deprecated configuration format

**Solutions:**
- Check configuration.yaml syntax
- Verify all required fields present
- Check integration documentation
- Use configuration validation tools

## Network Errors

### DNS Errors
```
Cannot connect to host X:443 ssl:default [Timeout while contacting DNS servers]
gaierror: [Errno -2] Name or service not known
```

**Causes:**
- DNS server issues
- Network connectivity problems
- Domain doesn't exist
- DNS cache issues

**Solutions:**
- Check DNS configuration
- Test DNS resolution: `nslookup domain.com`
- Try alternative DNS (8.8.8.8, 1.1.1.1)
- Clear DNS cache

### Connection Refused
```
ConnectionRefusedError: [Errno 111] Connection refused
```

**Causes:**
- Service not running
- Wrong port
- Firewall blocking connection
- Service bound to wrong interface

**Solutions:**
- Verify service is running
- Check correct port number
- Review firewall rules
- Check service binding (localhost vs 0.0.0.0)
