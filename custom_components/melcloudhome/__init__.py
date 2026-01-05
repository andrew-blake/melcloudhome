"""The MELCloud Home integration.

NOTE: This module uses lazy imports (imports inside functions) for Home Assistant
modules to allow testing the API client independently. Home Assistant has strict
dependency pinning that conflicts with our aiohttp version, so HA is not installed
in the dev environment. Integration testing happens via deployment to actual HA.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

from .api.client import MELCloudHomeClient

_LOGGER = logging.getLogger(__name__)


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

            # Find current device IDs from API
            current_ids: set[str] = set()
            for building in coordinator.data.buildings:
                for unit in building.air_to_air_units:
                    current_ids.add(unit.id)

            # Detect new devices
            new_device_ids = current_ids - known_ids

            if new_device_ids:
                # Get names of new devices
                new_device_names = [
                    unit.name
                    for building in coordinator.data.buildings
                    for unit in building.air_to_air_units
                    if unit.id in new_device_ids
                ]

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

    # Initialize known device IDs from first fetch
    known_device_ids: set[str] = set()
    for building in coordinator.data.buildings:
        for unit in building.air_to_air_units:
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

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, platforms)

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
