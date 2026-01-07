"""Air-to-Air (A/C) binary sensor platform for MELCloud Home integration."""

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
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api.models import AirToAirUnit, Building
from .helpers import initialize_entity_base
from .protocols import CoordinatorProtocol

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class ATABinarySensorEntityDescription(
    BinarySensorEntityDescription  # type: ignore[misc]
):
    """Binary sensor entity description with value extraction.

    Note: type: ignore[misc] required because HA is not installed in dev environment
    (aiohttp version conflict). Mypy sees BinarySensorEntityDescription as 'Any'.
    """

    value_fn: Callable[[AirToAirUnit], bool]
    """Function to extract binary sensor value from unit data."""

    available_fn: Callable[[AirToAirUnit], bool] = lambda x: True
    """Function to determine if sensor is available."""


BINARY_SENSOR_TYPES: tuple[ATABinarySensorEntityDescription, ...] = (
    # Error state - indicates if device is in error condition
    ATABinarySensorEntityDescription(
        key="error_state",
        translation_key="error_state",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda unit: unit.is_in_error,
    ),
    # Connection state - indicates if device is connected and responding
    # This will be handled differently as it depends on coordinator status
    ATABinarySensorEntityDescription(
        key="connection_state",
        translation_key="connection_state",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda unit: True,  # Connection is determined by coordinator
    ),
)


class ATABinarySensor(
    CoordinatorEntity[CoordinatorProtocol],  # type: ignore[misc]
    BinarySensorEntity,  # type: ignore[misc]
):
    """Representation of a MELCloud Home binary sensor.

    Note: type: ignore[misc] required because HA is not installed in dev environment
    (aiohttp version conflict). Mypy sees HA base classes as 'Any'.
    """

    _attr_has_entity_name = True  # Use device name + entity name pattern
    entity_description: ATABinarySensorEntityDescription

    def __init__(
        self,
        coordinator: CoordinatorProtocol,
        unit: AirToAirUnit,
        building: Building,
        entry: ConfigEntry,
        description: ATABinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        initialize_entity_base(self, unit, building, entry, description)

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        # For connection state, we check coordinator status
        if self.entity_description.key == "connection_state":
            return bool(self.coordinator.last_update_success)

        # For other sensors, use the value function
        device = self.coordinator.get_device(self._unit_id)
        if device is None:
            return False
        return bool(self.entity_description.value_fn(device))

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Connection sensor is always available (it reports connection status)
        if self.entity_description.key == "connection_state":
            return True

        # For other sensors, check coordinator status
        if not self.coordinator.last_update_success:
            return False

        device = self.coordinator.get_device(self._unit_id)
        if device is None:
            return False

        return self.entity_description.available_fn(device)
