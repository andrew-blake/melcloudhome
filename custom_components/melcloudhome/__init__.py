"""The MELCloud Home integration.

NOTE: This module uses lazy imports (imports inside functions) for Home Assistant
modules to allow testing the API client independently. Home Assistant has strict
dependency pinning that conflicts with our aiohttp version, so HA is not installed
in the dev environment. Integration testing happens via deployment to actual HA.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

from .api.client import MELCloudHomeClient

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MELCloud Home from a config entry."""
    # Lazy imports - see module docstring for explanation
    from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
    from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

    from .const import DOMAIN
    from .coordinator import MELCloudHomeCoordinator

    email = entry.data[CONF_EMAIL]
    password = entry.data[CONF_PASSWORD]

    platforms: list[Platform] = [
        Platform.BINARY_SENSOR,
        Platform.CLIMATE,
        Platform.SENSOR,
    ]

    # Create API client and coordinator
    # Note: Coordinator will handle authentication on first refresh
    client = MELCloudHomeClient()
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

    # Store coordinator in per-entry dict (supports future Phase 2 additions)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {"coordinator": coordinator}

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
