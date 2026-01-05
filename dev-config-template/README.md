# Dev Config Template

This directory contains a clean snapshot of the Home Assistant dev environment **after user onboarding**.

## What's Included

- **User Account:** dev / dev (already created)
- **Onboarding:** Completed (skipped wizard)
- **State:** Clean initial state, ready to add integration

**Note:** The integration is NOT yet configured. You'll need to add it via UI:
1. Go to Settings → Devices & Services
2. Click "+ Add Integration"
3. Search for "MELCloud Home"
4. Configure with any credentials (mock server accepts anything)

## Usage

This snapshot is automatically restored when you run:

```bash
make dev-reset
```

This is much faster than `make dev-reset-full` which wipes everything and requires re-creating the user and configuring the integration.

## When to Update

Update this snapshot when you want to change the baseline dev environment (e.g., after adding new entities or configuration):

```bash
# Make your changes in dev environment
# Then snapshot the current state:
rm -rf dev-config-template/.storage
mkdir -p dev-config-template/.storage
cp -r dev-config/.storage/* dev-config-template/.storage/
git add dev-config-template/
git commit -m "Update dev environment snapshot"
```

## Files

- `.storage/` - All Home Assistant state files
  - `auth` - User credentials (dev/dev)
  - `core.config_entries` - Integration configuration
  - `core.entity_registry` - Entity registrations
  - `core.device_registry` - Device registrations
  - `onboarding` - Onboarding completion state
  - And other HA system files
