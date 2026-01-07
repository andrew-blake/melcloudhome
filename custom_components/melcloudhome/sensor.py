"""Sensor platform for MELCloud Home integration.

Platform entry point that sets up both ATA and ATW sensor entities.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import MELCloudHomeCoordinator
from .sensor_ata import SENSOR_TYPES, ATASensor
from .sensor_atw import (
    ATW_SENSOR_TYPES,
    ATWSensor,
    _create_sensors_for_unit,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MELCloud Home sensor entities."""
    _LOGGER.debug("Setting up MELCloud Home sensor platform")

    coordinator: MELCloudHomeCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    entities: list[ATASensor | ATWSensor] = []

    # ATA (Air-to-Air) sensors
    for building in coordinator.data.buildings:
        for unit in building.air_to_air_units:
            for description in SENSOR_TYPES:
                # Use should_create_fn if defined, otherwise use available_fn
                create_check = (
                    description.should_create_fn
                    if description.should_create_fn
                    else description.available_fn
                )
                if create_check(unit):
                    entities.append(
                        ATASensor(coordinator, unit, building, entry, description)
                    )

    # ATW (Air-to-Water) sensors (using extracted helper to reduce duplication)
    for building in coordinator.data.buildings:
        for unit in building.air_to_water_units:
            entities.extend(
                _create_sensors_for_unit(
                    coordinator, unit, building, entry, ATW_SENSOR_TYPES
                )
            )

    _LOGGER.debug("Created %d sensor entities", len(entities))
    async_add_entities(entities)
