"""The MELCloud Home integration.

NOTE: This module uses lazy imports (imports inside functions) for Home Assistant
modules to allow testing the API client independently. Home Assistant has strict
dependency pinning that conflicts with our aiohttp version, so HA is not installed
in the dev environment. Integration testing happens via deployment to actual HA.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .coordinator import MELCloudHomeCoordinator

from .api.client import MELCloudHomeClient

_LOGGER = logging.getLogger(__name__)

# Pattern for auto-generated device names (used by device name migration)
UUID_DEVICE_NAME_PATTERN = re.compile(r"^melcloudhome_[0-9a-f]{4}_[0-9a-f]{4}$")


def _create_discovery_listener(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> Callable[[], None]:
    """Create a listener that detects new devices and triggers reload.

    NOTE: This must be a sync function - DataUpdateCoordinator calls
    listeners synchronously. Async work is scheduled via async_create_task.
    """
    from homeassistant.config_entries import ConfigEntryState

    from .const import DOMAIN

    def _device_discovery_listener() -> None:
        """Check for new devices and reload if found."""
        try:
            entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
            if not entry_data:
                return

            coordinator = entry_data["coordinator"]
            known_ids: set[str] = entry_data["known_device_ids"]

            if not coordinator.data:
                return

            # Find current device IDs from API (both ATA and ATW)
            current_ids: set[str] = set()
            for building in coordinator.data.buildings:
                for unit in building.air_to_air_units:
                    current_ids.add(unit.id)
                for unit in building.air_to_water_units:
                    current_ids.add(unit.id)

            # Detect new devices
            new_device_ids = current_ids - known_ids

            if new_device_ids:
                # Get names of new devices (check both ATA and ATW)
                new_device_names = []
                for building in coordinator.data.buildings:
                    for unit in building.air_to_air_units:
                        if unit.id in new_device_ids:
                            new_device_names.append(f"{unit.name} (ATA)")
                    for unit in building.air_to_water_units:
                        if unit.id in new_device_ids:
                            new_device_names.append(f"{unit.name} (ATW)")

                _LOGGER.info(
                    "Discovered %d new device(s): %s",
                    len(new_device_ids),
                    new_device_names,
                )

                # Show persistent notification (async call scheduled from sync listener)
                async def _notify_and_reload() -> None:
                    """Create notification and reload integration."""
                    await hass.services.async_call(
                        "persistent_notification",
                        "create",
                        {
                            "message": f"New device(s) discovered: {', '.join(new_device_names)}. "
                            "The integration will reload to add them.",
                            "title": "MELCloud Home",
                            "notification_id": f"melcloudhome_new_devices_{entry.entry_id}",
                        },
                    )
                    # Trigger reload if entry still loaded
                    if entry.state == ConfigEntryState.LOADED:
                        await hass.config_entries.async_reload(entry.entry_id)

                # Update known devices before reload (prevents infinite loop)
                known_ids.update(new_device_ids)

                # Schedule notification and reload
                hass.async_create_task(_notify_and_reload())

            # Handle removed devices (log only, no reload)
            removed_device_ids = known_ids - current_ids
            if removed_device_ids:
                _LOGGER.warning(
                    "Device(s) no longer found in MELCloud account: %s",
                    removed_device_ids,
                )
                known_ids.difference_update(removed_device_ids)

        except Exception:
            _LOGGER.exception("Error in device discovery listener")

    return _device_discovery_listener


async def _clear_friendly_device_names(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: MELCloudHomeCoordinator,
) -> None:
    """Clear name_by_user from devices before platform setup.

    This ensures that when entities are created during platform setup,
    they use the UUID-based device name (from 'name' field) for entity IDs,
    not the friendly name_by_user.

    Only clears name_by_user if it matches the API-based friendly name,
    preserving user customizations.

    We'll restore name_by_user after platform setup for friendly UI display.
    """
    from homeassistant.helpers import device_registry as dr

    from .const import DOMAIN

    device_reg = dr.async_get(hass)

    # Build mapping: unit_id -> friendly_name from API
    friendly_names: dict[str, str] = {}
    for building in coordinator.data.buildings:
        for unit in building.air_to_air_units:
            friendly_names[unit.id] = f"{building.name} {unit.name}"
        for unit in building.air_to_water_units:
            friendly_names[unit.id] = f"{building.name} {unit.name}"

    # Find all devices for this integration
    cleared_count = 0
    for device in device_reg.devices.values():
        # Check if device belongs to this config entry
        if entry.entry_id not in device.config_entries:
            continue

        # Get unit_id from identifiers
        unit_id = None
        for identifier in device.identifiers:
            if identifier[0] == DOMAIN:
                unit_id = identifier[1]
                break

        if unit_id is None:
            continue

        # Skip if name doesn't match UUID pattern
        if not UUID_DEVICE_NAME_PATTERN.match(device.name):
            continue

        # Only clear if name_by_user matches the API friendly name
        # This preserves user customizations
        expected_friendly_name = friendly_names.get(unit_id)
        if (
            device.name_by_user is not None
            and expected_friendly_name
            and device.name_by_user == expected_friendly_name
        ):
            device_reg.async_update_device(
                device.id,
                name_by_user=None,
            )
            cleared_count += 1
            _LOGGER.debug(
                "Cleared name_by_user from device: %s (was: %s)",
                device.name,
                device.name_by_user,
            )

    if cleared_count > 0:
        _LOGGER.info(
            "Cleared name_by_user from %d device(s) before platform setup",
            cleared_count,
        )


async def _migrate_device_names(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: MELCloudHomeCoordinator,
) -> None:
    """Set friendly display names on devices after platform setup.

    This runs AFTER entities are created, so entity IDs use UUID-based device names.
    Setting name_by_user after entity creation keeps entity IDs stable while
    providing friendly device names in the UI.
    """
    from homeassistant.helpers import device_registry as dr

    from .const import DOMAIN

    device_reg = dr.async_get(hass)

    # Build mapping: unit_id -> friendly_name
    friendly_names: dict[str, str] = {}

    for building in coordinator.data.buildings:
        # ATA devices (Air-to-Air)
        for unit in building.air_to_air_units:
            friendly_names[unit.id] = f"{building.name} {unit.name}"

        # ATW devices (Air-to-Water)
        for unit in building.air_to_water_units:
            friendly_names[unit.id] = f"{building.name} {unit.name}"

    # Set name_by_user on all devices with UUID names
    migrated_count = 0
    for device in device_reg.devices.values():
        # Check if device belongs to this config entry
        if entry.entry_id not in device.config_entries:
            continue

        # Get unit_id from identifiers
        unit_id = None
        for identifier in device.identifiers:
            if identifier[0] == DOMAIN:
                unit_id = identifier[1]
                break

        if unit_id is None:
            continue

        # Skip if name doesn't match UUID pattern
        if not UUID_DEVICE_NAME_PATTERN.match(device.name):
            continue

        # Get friendly name from mapping
        friendly_name = friendly_names.get(unit_id)
        if not friendly_name:
            _LOGGER.warning(
                "Cannot migrate device %s: unit %s not found in coordinator data",
                device.id,
                unit_id,
            )
            continue

        # Skip if user has customized the name
        # If name_by_user exists and doesn't match expected friendly name, user customized it
        if device.name_by_user is not None and device.name_by_user != friendly_name:
            _LOGGER.debug(
                "Preserving user customization: %s (device_id=%s)",
                device.name_by_user,
                device.id[:8],
            )
            continue

        # Set name_by_user (will be used for UI display, NOT entity IDs)
        device_reg.async_update_device(
            device.id,
            name_by_user=friendly_name,
        )
        migrated_count += 1
        _LOGGER.debug(
            "Set friendly name: %s -> %s (device_id=%s)",
            device.name,
            friendly_name,
            device.id[:8],
        )

    if migrated_count > 0:
        _LOGGER.info("Set friendly names on %d device(s)", migrated_count)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MELCloud Home from a config entry."""
    # Lazy imports - see module docstring for explanation
    from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
    from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

    from .const import CONF_DEBUG_MODE, DOMAIN
    from .coordinator import MELCloudHomeCoordinator

    email = entry.data[CONF_EMAIL]
    password = entry.data[CONF_PASSWORD]
    debug_mode = entry.data.get(CONF_DEBUG_MODE, False)

    platforms: list[Platform] = [
        Platform.BINARY_SENSOR,
        Platform.CLIMATE,
        Platform.SENSOR,
        Platform.SWITCH,
        Platform.WATER_HEATER,
    ]

    # Create API client and coordinator
    # Note: Coordinator will handle authentication on first refresh
    client = MELCloudHomeClient(debug_mode=debug_mode)
    coordinator = MELCloudHomeCoordinator(hass, client, email, password)

    # Fetch initial data (coordinator handles login automatically)
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryAuthFailed:
        # Re-raise auth failures for HA to handle
        await client.close()
        raise
    except Exception as err:
        await client.close()
        raise ConfigEntryNotReady(
            "Failed to fetch initial data. Please try again later."
        ) from err

    # Set up energy polling
    await coordinator.async_setup()

    # Initialize known device IDs from first fetch (both ATA and ATW)
    known_device_ids: set[str] = set()
    for building in coordinator.data.buildings:
        for unit in building.air_to_air_units:
            known_device_ids.add(unit.id)
        for unit in building.air_to_water_units:
            known_device_ids.add(unit.id)

    _LOGGER.info("Initial device discovery: %d device(s) found", len(known_device_ids))

    # Store coordinator and known device IDs
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "known_device_ids": known_device_ids,
    }

    # Register force refresh service (domain-level, refreshes all coordinators)
    # Note: Handler defined inside function to match lazy import pattern
    # The has_service check prevents re-registration, so only first handler is used
    from homeassistant.core import ServiceCall

    async def handle_force_refresh(_call: ServiceCall) -> None:
        """Handle force refresh service call."""
        for entry_data in hass.data[DOMAIN].values():
            if isinstance(entry_data, dict) and "coordinator" in entry_data:
                await entry_data["coordinator"].async_refresh()
        _LOGGER.debug("Forced refresh for %s coordinator(s)", len(hass.data[DOMAIN]))

    # Register service if not already registered
    if not hass.services.has_service(DOMAIN, "force_refresh"):
        hass.services.async_register(
            DOMAIN,
            "force_refresh",
            handle_force_refresh,
            schema=None,  # No parameters
        )

    # Clear name_by_user from existing devices BEFORE platform setup
    # This ensures new entities use UUID-based device names for entity IDs
    # Only clears if name_by_user matches API friendly name (preserves user customizations)
    await _clear_friendly_device_names(hass, entry, coordinator)

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, platforms)

    # Set friendly names on devices AFTER platform setup
    # Entity IDs are now locked in with UUID prefixes, this only affects UI display
    await _migrate_device_names(hass, entry, coordinator)

    # Set up coordinator listener for new device discovery
    entry.async_on_unload(
        coordinator.async_add_listener(_create_discovery_listener(hass, entry))
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Lazy imports - see module docstring for explanation
    from homeassistant.const import Platform

    from .const import DOMAIN
    from .coordinator import MELCloudHomeCoordinator

    platforms: list[Platform] = [
        Platform.BINARY_SENSOR,
        Platform.CLIMATE,
        Platform.SENSOR,
        Platform.SWITCH,
        Platform.WATER_HEATER,
    ]

    # Unload platforms
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, platforms):
        # Close client and clean up
        entry_data = hass.data[DOMAIN].pop(entry.entry_id)
        coordinator: MELCloudHomeCoordinator = entry_data["coordinator"]
        await coordinator.async_shutdown()

        # Unregister service if no entries remain
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, "force_refresh")
            hass.data.pop(DOMAIN)

    return unload_ok  # type: ignore[no-any-return]
