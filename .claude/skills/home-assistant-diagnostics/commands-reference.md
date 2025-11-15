# Home Assistant SSH Commands Reference

## Quick Start

```bash
# Connect to Home Assistant
ssh ha

# Get system info with banner
ssh ha -t "sudo -i"

# Run command with sudo
ssh ha "sudo <command>"
```

## Docker Commands

### Container Management

```bash
# List all containers
ssh ha "sudo docker ps"

# List all containers (including stopped)
ssh ha "sudo docker ps -a"

# Restart a container
ssh ha "sudo docker restart <container-name>"

# Stop a container
ssh ha "sudo docker stop <container-name>"

# Start a container
ssh ha "sudo docker start <container-name>"

# Remove a container
ssh ha "sudo docker rm <container-name>"
```

### Container Logs

```bash
# View last 100 lines of logs
ssh ha "sudo docker logs homeassistant --tail 100"

# View last 500 lines
ssh ha "sudo docker logs homeassistant --tail 500"

# Follow logs in real-time
ssh ha "sudo docker logs -f homeassistant"

# View logs with timestamps
ssh ha "sudo docker logs -t homeassistant --tail 100"

# View logs for specific add-on
ssh ha "sudo docker logs addon_a0d7b954_vscode --tail 100"
```

### Filtering Logs

```bash
# Show only errors
ssh ha "sudo docker logs homeassistant --tail 500 2>&1 | grep -i error"

# Show errors from last 100 lines
ssh ha "sudo docker logs homeassistant --tail 500 2>&1 | grep -i error | tail -50"

# Show warnings
ssh ha "sudo docker logs homeassistant --tail 500 2>&1 | grep -i warning"

# Search for specific integration
ssh ha "sudo docker logs homeassistant 2>&1 | grep -i melcloud"

# Show context around errors (5 lines before, 30 after)
ssh ha "sudo docker logs homeassistant 2>&1 | grep -A 30 -B 5 'melcloud'"

# Show multiple patterns
ssh ha "sudo docker logs homeassistant 2>&1 | grep -E 'error|warning|failed'"
```

### Container Inspection

```bash
# Inspect container details
ssh ha "sudo docker inspect homeassistant"

# Get container IP address
ssh ha "sudo docker inspect -f '{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}' homeassistant"

# Check container stats (CPU, memory)
ssh ha "sudo docker stats --no-stream"

# Check specific container stats
ssh ha "sudo docker stats homeassistant --no-stream"
```

## Home Assistant Container Commands

### Execute Commands Inside Container

```bash
# Execute command in homeassistant container
ssh ha "sudo docker exec homeassistant <command>"

# Interactive shell (bash)
ssh ha "sudo docker exec -it homeassistant bash"

# List files in config directory
ssh ha "sudo docker exec homeassistant ls -la /config/"

# List custom components
ssh ha "sudo docker exec homeassistant ls -la /config/custom_components/"

# Check Python version
ssh ha "sudo docker exec homeassistant python3 --version"
```

### Python Package Management

```bash
# List installed packages
ssh ha "sudo docker exec homeassistant pip list"

# Show specific package info
ssh ha "sudo docker exec homeassistant pip show <package-name>"

# Search for package
ssh ha "sudo docker exec homeassistant pip list | grep <keyword>"

# Check package location
ssh ha "sudo docker exec homeassistant python3 -c 'import <module>; print(<module>.__file__)'"

# Import and check version
ssh ha "sudo docker exec homeassistant python3 -c 'import <module>; print(<module>.__version__)'"
```

### File Operations

```bash
# Read file
ssh ha "sudo docker exec homeassistant cat /path/to/file"

# View first N lines
ssh ha "sudo docker exec homeassistant head -n 50 /path/to/file"

# View last N lines
ssh ha "sudo docker exec homeassistant tail -n 50 /path/to/file"

# Search in file
ssh ha "sudo docker exec homeassistant grep 'pattern' /path/to/file"

# List directory
ssh ha "sudo docker exec homeassistant ls -la /path/to/directory/"

# Find files
ssh ha "sudo docker exec homeassistant find /path -name '*.py'"
```

### Check Integration Files

```bash
# View integration manifest
ssh ha "sudo docker exec homeassistant cat /usr/src/homeassistant/homeassistant/components/<integration>/manifest.json"

# List integration files
ssh ha "sudo docker exec homeassistant ls -la /usr/src/homeassistant/homeassistant/components/<integration>/"

# View integration source
ssh ha "sudo docker exec homeassistant cat /usr/src/homeassistant/homeassistant/components/<integration>/<file>.py"

# View library source
ssh ha "sudo docker exec homeassistant cat /usr/local/lib/python3.13/site-packages/<library>/<file>.py"
```

## System Commands

### Network Diagnostics

```bash
# Ping device
ssh ha "ping -c 4 <ip-address>"

# DNS lookup
ssh ha "nslookup <domain>"

# Check open ports
ssh ha "sudo netstat -tulpn | grep LISTEN"

# Check network interfaces
ssh ha "ip addr show"

# Test HTTP connection
ssh ha "curl -I http://<ip-address>:port"
```

### System Information

```bash
# Check disk usage
ssh ha "df -h"

# Check memory usage
ssh ha "free -h"

# Check running processes
ssh ha "ps aux"

# Check system uptime
ssh ha "uptime"

# Check kernel version
ssh ha "uname -a"
```

### Home Assistant Supervisor (if API token available)

```bash
# Get HA info
ssh ha "sudo ha info"

# Get core info
ssh ha "sudo ha core info"

# Get supervisor info
ssh ha "sudo ha supervisor info"

# List add-ons
ssh ha "sudo ha addons"

# Check for updates
ssh ha "sudo ha available-updates"

# Resolution center
ssh ha "sudo ha resolution info"
```

## Common Diagnostic Flows

### Quick Error Check

```bash
# Get latest errors from homeassistant
ssh ha "sudo docker logs homeassistant --tail 500 2>&1 | grep -i error | tail -20"
```

### Integration Diagnostics

```bash
# Check specific integration logs
INTEGRATION="melcloud"
ssh ha "sudo docker logs homeassistant 2>&1 | grep -i $INTEGRATION | tail -50"
```

### Device Connectivity Check

```bash
# Check if device is reachable
ssh ha "ping -c 4 192.168.1.100"

# Check logs for device errors
ssh ha "sudo docker logs homeassistant 2>&1 | grep '192.168.1.100' | tail -20"
```

### Container Health Check

```bash
# Check all container status
ssh ha "sudo docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.State}}'"

# Check unhealthy containers
ssh ha "sudo docker ps -a --filter health=unhealthy"
```

### Library Investigation

```bash
# Find and examine library
LIBRARY="pymelcloud"
ssh ha "sudo docker exec homeassistant ls -la /usr/local/lib/python3.13/site-packages/ | grep $LIBRARY"
ssh ha "sudo docker exec homeassistant cat /usr/local/lib/python3.13/site-packages/$LIBRARY/__init__.py | head -50"
```

## Tips

1. **Always use sudo** for docker commands on Home Assistant OS
2. **Use grep with -i** for case-insensitive searches
3. **Redirect stderr with 2>&1** when grepping logs to catch all output
4. **Use --tail** to limit output and speed up commands
5. **Check timestamps** with `docker logs -t` to understand when errors occur
6. **Use -A and -B with grep** to see context around matches
7. **Pipe to tail** after grep to limit output: `grep pattern | tail -50`
