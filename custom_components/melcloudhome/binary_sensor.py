"""Binary sensor platform for MELCloud Home integration.

Platform entry point that sets up both ATA and ATW binary sensor entities.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .binary_sensor_ata import (
    BINARY_SENSOR_TYPES,
    ATABinarySensor,
)
from .binary_sensor_atw import (
    ATW_BINARY_SENSOR_TYPES,
    ATWBinarySensor,
)
from .const import DOMAIN
from .coordinator import MELCloudHomeCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MELCloud Home binary sensor entities."""
    _LOGGER.debug("Setting up MELCloud Home binary sensor platform")

    coordinator: MELCloudHomeCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    entities: list[ATABinarySensor | ATWBinarySensor] = []

    # ATA (Air-to-Air) binary sensors
    for building in coordinator.data.buildings:
        for unit in building.air_to_air_units:
            for description in BINARY_SENSOR_TYPES:
                entities.append(
                    ATABinarySensor(coordinator, unit, building, entry, description)
                )

    # ATW (Air-to-Water) binary sensors
    for building in coordinator.data.buildings:
        for unit in building.air_to_water_units:
            for description in ATW_BINARY_SENSOR_TYPES:
                entities.append(
                    ATWBinarySensor(coordinator, unit, building, entry, description)
                )

    _LOGGER.debug("Created %d binary sensor entities", len(entities))
    async_add_entities(entities)
