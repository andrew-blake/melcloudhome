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

from .api.models import AirToAirUnit, AirToWaterUnit, Building
from .const import DOMAIN, initialize_entity_base
from .coordinator import MELCloudHomeCoordinator
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


@dataclass(frozen=True, kw_only=True)
class ATWBinarySensorEntityDescription(
    BinarySensorEntityDescription  # type: ignore[misc]
):
    """ATW binary sensor entity description with value extraction.

    Note: type: ignore[misc] required because HA is not installed in dev environment
    (aiohttp version conflict). Mypy sees BinarySensorEntityDescription as 'Any'.
    """

    value_fn: Callable[[AirToWaterUnit], bool]
    """Function to extract binary sensor value from unit data."""

    available_fn: Callable[[AirToWaterUnit], bool] = lambda x: True
    """Function to determine if sensor is available."""


ATW_BINARY_SENSOR_TYPES: tuple[ATWBinarySensorEntityDescription, ...] = (
    # Error state - indicates if device is in error condition
    ATWBinarySensorEntityDescription(
        key="error_state",
        translation_key="error_state",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda unit: unit.is_in_error,
    ),
    # Connection state - indicates if device is connected and responding
    ATWBinarySensorEntityDescription(
        key="connection_state",
        translation_key="connection_state",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda unit: True,  # Connection is determined by coordinator
    ),
    # Forced DHW active - indicates when DHW has priority over zones
    ATWBinarySensorEntityDescription(
        key="forced_dhw_active",
        translation_key="forced_dhw_active",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda unit: unit.forced_hot_water_mode,
    ),
)


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


class ATWBinarySensor(
    CoordinatorEntity[CoordinatorProtocol],  # type: ignore[misc]
    BinarySensorEntity,  # type: ignore[misc]
):
    """Representation of a MELCloud Home ATW binary sensor.

    Note: type: ignore[misc] required because HA is not installed in dev environment
    (aiohttp version conflict). Mypy sees HA base classes as 'Any'.
    """

    _attr_has_entity_name = True  # Use device name + entity name pattern
    entity_description: ATWBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: CoordinatorProtocol,
        unit: AirToWaterUnit,
        building: Building,
        entry: ConfigEntry,
        description: ATWBinarySensorEntityDescription,
    ) -> None:
        """Initialize the ATW binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        initialize_entity_base(self, unit, building, entry, description)

    @property
    def is_on(self) -> bool | None:
        """Return the binary sensor value."""
        device = self.coordinator.get_atw_device(self._unit_id)
        if device is None:
            return None

        return self.entity_description.value_fn(device)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Connection sensor is always available (it reports connection status)
        if self.entity_description.key == "connection_state":
            return True

        # For other sensors, check coordinator status
        if not self.coordinator.last_update_success:
            return False

        device = self.coordinator.get_atw_device(self._unit_id)
        if device is None:
            return False

        return self.entity_description.available_fn(device)
