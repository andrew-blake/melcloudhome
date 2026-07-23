"""Air-to-Air (A/C) binary sensor platform for MELCloud Home integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

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

    attributes_fn: Callable[[AirToAirUnit], dict[str, Any]] | None = None
    """Function to extract extra state attributes from unit data."""

    should_create_fn: Callable[[AirToAirUnit], bool] | None = None
    """Function to determine if sensor should be created. If None, uses available_fn."""


ATA_BINARY_SENSOR_TYPES: tuple[ATABinarySensorEntityDescription, ...] = (
    # Error state - indicates if device is in error condition
    ATABinarySensorEntityDescription(
        key="error_state",
        translation_key="error_state",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda unit: unit.is_in_error,
        attributes_fn=lambda unit: {"error_code": unit.error_code},
    ),
    # Connection state - indicates if device is connected and responding
    # This will be handled differently as it depends on coordinator status
    ATABinarySensorEntityDescription(
        key="connection_state",
        translation_key="connection_state",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda unit: True,  # Connection is determined by coordinator
    ),
    # Protection modes - only created once a unit has ever had the mode configured
    # (the API leaves these objects null until then, then persists them even when disabled)
    # State reflects "enabled" (armed/configured) - the everyday question a user
    # checks in HA - not "active" (currently engaging), which stays off unless the
    # room has actually crossed the threshold; "active" is exposed as an attribute.
    ATABinarySensorEntityDescription(
        key="frost_protection",
        translation_key="frost_protection",
        value_fn=lambda unit: bool(
            unit.frost_protection and unit.frost_protection.enabled
        ),
        should_create_fn=lambda unit: unit.frost_protection is not None,
        attributes_fn=lambda unit: (
            {
                "active": unit.frost_protection.active,
                "min": unit.frost_protection.min,
                "max": unit.frost_protection.max,
            }
            if unit.frost_protection
            else {}
        ),
    ),
    ATABinarySensorEntityDescription(
        key="overheat_protection",
        translation_key="overheat_protection",
        value_fn=lambda unit: bool(
            unit.overheat_protection and unit.overheat_protection.enabled
        ),
        should_create_fn=lambda unit: unit.overheat_protection is not None,
        attributes_fn=lambda unit: (
            {
                "active": unit.overheat_protection.active,
                "min": unit.overheat_protection.min,
                "max": unit.overheat_protection.max,
            }
            if unit.overheat_protection
            else {}
        ),
    ),
    ATABinarySensorEntityDescription(
        key="holiday_mode",
        translation_key="holiday_mode",
        value_fn=lambda unit: bool(unit.holiday_mode and unit.holiday_mode.enabled),
        should_create_fn=lambda unit: unit.holiday_mode is not None,
        attributes_fn=lambda unit: (
            {
                "active": unit.holiday_mode.active,
                "start_date": unit.holiday_mode.start_date,
                "end_date": unit.holiday_mode.end_date,
            }
            if unit.holiday_mode
            else {}
        ),
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
        device = self.coordinator.get_ata_device(self._unit_id)
        if device is None:
            return False
        return bool(self.entity_description.value_fn(device))

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes."""
        if self.entity_description.attributes_fn is None:
            return None

        device = self.coordinator.get_ata_device(self._unit_id)
        if device is None:
            return None
        return self.entity_description.attributes_fn(device)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Connection sensor is always available (it reports connection status)
        if self.entity_description.key == "connection_state":
            return True

        # For other sensors, check coordinator status
        if not self.coordinator.last_update_success:
            return False

        device = self.coordinator.get_ata_device(self._unit_id)
        if device is None:
            return False

        return self.entity_description.available_fn(device)
