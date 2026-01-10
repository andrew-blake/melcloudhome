"""Climate platform for MELCloud Home integration.

Platform entry point that sets up both ATA and ATW climate entities.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .climate_ata import ATAClimate
from .climate_atw import ATWClimateZone1
from .const import DOMAIN
from .coordinator import MELCloudHomeCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MELCloud Home climate entities."""
    _LOGGER.debug("Setting up MELCloud Home climate platform")

    coordinator: MELCloudHomeCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    entities = []

    # ATA (Air-to-Air) climate entities
    for building in coordinator.data.buildings:
        for unit in building.air_to_air_units:
            entities.append(ATAClimate(coordinator, unit, building, entry))

    # ATW (Air-to-Water) climate entities - Zone 1 only (Zone 2 not currently implemented)
    for building in coordinator.data.buildings:
        for unit in building.air_to_water_units:
            # Zone 1 - always created
            entities.append(ATWClimateZone1(coordinator, unit, building, entry))

    _LOGGER.debug("Created %d climate entities", len(entities))
    async_add_entities(entities)
