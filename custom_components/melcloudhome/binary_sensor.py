"""Binary sensor platform for MELCloud Home integration."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api.models import AirToAirUnit, Building
from .const import DOMAIN
from .coordinator import MELCloudHomeCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class MELCloudHomeBinarySensorEntityDescription(
    BinarySensorEntityDescription  # type: ignore[misc]
):
    """Binary sensor entity description with value extraction."""

    value_fn: Callable[[AirToAirUnit], bool]
    """Function to extract binary sensor value from unit data."""

    available_fn: Callable[[AirToAirUnit], bool] = lambda x: True
    """Function to determine if sensor is available."""


BINARY_SENSOR_TYPES: tuple[MELCloudHomeBinarySensorEntityDescription, ...] = (
    # Error state - indicates if device is in error condition
    MELCloudHomeBinarySensorEntityDescription(
        key="error_state",
        translation_key="error_state",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda unit: unit.is_in_error,
    ),
    # Connection state - indicates if device is connected and responding
    # This will be handled differently as it depends on coordinator status
    MELCloudHomeBinarySensorEntityDescription(
        key="connection_state",
        translation_key="connection_state",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda unit: True,  # Connection is determined by coordinator
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MELCloud Home binary sensor entities."""
    coordinator: MELCloudHomeCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    entities: list[MELCloudHomeBinarySensor] = []
    for building in coordinator.data.buildings:
        for unit in building.air_to_air_units:
            for description in BINARY_SENSOR_TYPES:
                entities.append(
                    MELCloudHomeBinarySensor(
                        coordinator, unit, building, entry, description
                    )
                )

    if entities:
        units_count = len(
            [u for b in coordinator.data.buildings for u in b.air_to_air_units]
        )
        _LOGGER.debug(
            "Setting up %d binary sensor entities for %d units",
            len(entities),
            units_count,
        )

    async_add_entities(entities)


class MELCloudHomeBinarySensor(
    CoordinatorEntity[MELCloudHomeCoordinator],  # type: ignore[misc]
    BinarySensorEntity,  # type: ignore[misc]
):
    """Representation of a MELCloud Home binary sensor."""

    entity_description: MELCloudHomeBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: MELCloudHomeCoordinator,
        unit: AirToAirUnit,
        building: Building,
        entry: ConfigEntry,
        description: MELCloudHomeBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._unit_id = unit.id
        self._building_id = building.id
        self._entry = entry

        # Unique ID: unit_id + sensor key
        self._attr_unique_id = f"{unit.id}_{description.key}"

        # Generate stable entity ID from unit ID
        # Format: binary_sensor.melcloud_0efc_76db_error_state
        unit_id_clean = unit.id.replace("-", "")
        key_clean = description.key

        # Entity name (HA will normalize this to entity_id)
        self._attr_name = f"MELCloud {unit_id_clean[:4]} {unit_id_clean[-4:]} {key_clean.replace('_', ' ').title()}"

        # Link to device (same device as climate entity)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, unit.id)},
        }

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        # For connection state, we check coordinator status
        if self.entity_description.key == "connection_state":
            return bool(self.coordinator.last_update_success)

        # For other sensors, use the value function
        unit = self.coordinator.get_unit(self._unit_id)
        if unit is None:
            return False
        return bool(self.entity_description.value_fn(unit))

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Connection sensor is always available (it reports connection status)
        if self.entity_description.key == "connection_state":
            return True

        # For other sensors, check coordinator status
        if not self.coordinator.last_update_success:
            return False

        unit = self.coordinator.get_unit(self._unit_id)
        if unit is None:
            return False

        return self.entity_description.available_fn(unit)
