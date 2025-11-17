"""The MELCloud Home integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

from .api.client import MELCloudHomeClient
from .api.exceptions import ApiError, AuthenticationError

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MELCloud Home from a config entry."""
    from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
    from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

    from .const import DOMAIN
    from .coordinator import MELCloudHomeCoordinator

    email = entry.data[CONF_EMAIL]
    password = entry.data[CONF_PASSWORD]

    platforms: list[Platform] = [Platform.CLIMATE]

    # Create API client
    client = MELCloudHomeClient()

    # Attempt initial login
    try:
        await client.login(email, password)
    except AuthenticationError as err:
        _LOGGER.error("Authentication failed for %s: %s", email, err)
        raise ConfigEntryAuthFailed(
            "Invalid credentials. Please reconfigure the integration."
        ) from err
    except ApiError as err:
        _LOGGER.error("Failed to connect to MELCloud Home: %s", err)
        raise ConfigEntryNotReady(
            "Unable to connect to MELCloud Home. Please try again later."
        ) from err

    # Create coordinator
    coordinator = MELCloudHomeCoordinator(hass, client, email, password)

    # Fetch initial data
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        await client.close()
        raise ConfigEntryNotReady(
            "Failed to fetch initial data. Please try again later."
        ) from err

    # Store coordinator
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, platforms)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    from homeassistant.const import Platform

    from .const import DOMAIN
    from .coordinator import MELCloudHomeCoordinator

    platforms: list[Platform] = [Platform.CLIMATE]

    # Unload platforms
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, platforms):
        # Close client and clean up
        coordinator: MELCloudHomeCoordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.async_shutdown()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok  # type: ignore[no-any-return]
