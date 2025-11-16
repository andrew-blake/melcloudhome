# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a Home Assistant configuration repository for a home automation system running on a remote server accessible via SSH.

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

## VSCode Configuration

The repository includes VSCode settings that associate `*.yaml` files with the `home-assistant` file type for proper syntax highlighting and validation.
