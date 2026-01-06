"""Sensor platform for MELCloud Home integration."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfEnergy,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api.models import AirToAirUnit, AirToWaterUnit, Building
from .const import DOMAIN, create_device_info
from .coordinator import MELCloudHomeCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class ATASensorEntityDescription(SensorEntityDescription):  # type: ignore[misc]
    """Sensor entity description with value extraction.

    Note: type: ignore[misc] required because HA is not installed in dev environment
    (aiohttp version conflict). Mypy sees SensorEntityDescription as 'Any'.
    """

    value_fn: Callable[[AirToAirUnit], float | str | None]
    """Function to extract sensor value from unit data."""

    available_fn: Callable[[AirToAirUnit], bool] = lambda x: True
    """Function to determine if sensor is available."""

    should_create_fn: Callable[[AirToAirUnit], bool] | None = None
    """Function to determine if sensor should be created. If None, uses available_fn."""


SENSOR_TYPES: tuple[ATASensorEntityDescription, ...] = (
    # Room temperature - for statistics and history
    # Climate entity has this as an attribute, but separate sensor enables long-term statistics
    ATASensorEntityDescription(
        key="room_temperature",
        translation_key="room_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda unit: unit.room_temperature,
        available_fn=lambda unit: unit.room_temperature is not None,
    ),
    # WiFi signal strength - diagnostic sensor for connectivity troubleshooting
    # Shows received signal strength indication (RSSI) in dBm
    # Typical range: -30 (excellent) to -90 (poor)
    ATASensorEntityDescription(
        key="wifi_signal",
        translation_key="wifi_signal",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda unit: unit.rssi,
        available_fn=lambda unit: unit.rssi is not None,
    ),
    # Energy consumption sensor
    # Created if device has energy meter capability, even if no initial data
    # Becomes available once energy data is fetched (polls every 30 minutes)
    ATASensorEntityDescription(
        key="energy",  # Entity ID: sensor.melcloud_*_energy
        translation_key="energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=lambda unit: unit.energy_consumed,
        should_create_fn=lambda unit: unit.capabilities.has_energy_consumed_meter,
        available_fn=lambda unit: unit.energy_consumed is not None,
    ),
)


@dataclass(frozen=True, kw_only=True)
class ATWSensorEntityDescription(SensorEntityDescription):  # type: ignore[misc]
    """ATW sensor entity description with value extraction.

    Note: type: ignore[misc] required because HA is not installed in dev environment
    (aiohttp version conflict). Mypy sees SensorEntityDescription as 'Any'.
    """

    value_fn: Callable[[AirToWaterUnit], float | str | None]
    """Function to extract sensor value from unit data."""

    available_fn: Callable[[AirToWaterUnit], bool] = lambda x: True
    """Function to determine if sensor is available."""

    should_create_fn: Callable[[AirToWaterUnit], bool] | None = None
    """Function to determine if sensor should be created. If None, uses available_fn."""


ATW_SENSOR_TYPES: tuple[ATWSensorEntityDescription, ...] = (
    # Zone 1 room temperature
    ATWSensorEntityDescription(
        key="zone_1_temperature",
        translation_key="zone_1_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda unit: unit.room_temperature_zone1,
        should_create_fn=lambda unit: True,
        available_fn=lambda unit: unit.room_temperature_zone1 is not None,
    ),
    # Tank water temperature
    ATWSensorEntityDescription(
        key="tank_temperature",
        translation_key="tank_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda unit: unit.tank_water_temperature,
        should_create_fn=lambda unit: True,
        available_fn=lambda unit: unit.tank_water_temperature is not None,
    ),
    # Operation status (3-way valve position - raw API values)
    ATWSensorEntityDescription(
        key="operation_status",
        translation_key="operation_status",
        device_class=None,  # Categorical (not numeric)
        value_fn=lambda unit: unit.operation_status,  # Raw: "Stop", "HotWater", "HeatRoomTemperature", etc.
    ),
)


def _create_sensors_for_unit(
    coordinator: MELCloudHomeCoordinator,
    unit: AirToWaterUnit,
    building: Building,
    entry: ConfigEntry,
    descriptions: tuple[ATWSensorEntityDescription, ...],
) -> list[ATWSensor]:
    """Create sensors for a single ATW unit (extracted pattern to reduce duplication).

    Args:
        coordinator: Data update coordinator
        unit: ATW unit to create sensors for
        building: Building containing the unit
        entry: Config entry
        descriptions: Tuple of sensor descriptions to create

    Returns:
        List of ATWSensor instances
    """
    entities = []
    for description in descriptions:
        # Use should_create_fn if defined, otherwise use available_fn
        create_check: Callable[[AirToWaterUnit], bool] = (
            description.should_create_fn
            if description.should_create_fn
            else description.available_fn
        )
        if create_check(unit):
            entities.append(ATWSensor(coordinator, unit, building, entry, description))
    return entities


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


class ATASensor(CoordinatorEntity[MELCloudHomeCoordinator], SensorEntity):  # type: ignore[misc]
    """Representation of a MELCloud Home sensor.

    Note: type: ignore[misc] required because HA is not installed in dev environment
    (aiohttp version conflict). Mypy sees HA base classes as 'Any'.
    """

    _attr_has_entity_name = True  # Use device name + entity name pattern
    entity_description: ATASensorEntityDescription

    def __init__(
        self,
        coordinator: MELCloudHomeCoordinator,
        unit: AirToAirUnit,
        building: Building,
        entry: ConfigEntry,
        description: ATASensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._unit_id = unit.id
        self._building_id = building.id
        self._entry = entry

        # Unique ID: unit_id + sensor key
        self._attr_unique_id = f"{unit.id}_{description.key}"

        # Convert description key to friendly name
        short_name = description.key.replace("_", " ").title()

        # Fix acronyms to proper capitalization
        acronym_fixes = {
            "Dhw": "DHW",  # Domestic Hot Water
            "Wifi": "WiFi",  # WiFi signal
            "Ftc": "FTC",  # FTC model numbers
        }
        for incorrect, correct in acronym_fixes.items():
            short_name = short_name.replace(incorrect, correct)

        self._attr_name = short_name

        # Device info using shared helper
        self._attr_device_info = create_device_info(unit, building)

    @property
    def native_value(self) -> float | str | None:
        """Return the sensor value."""
        unit = self.coordinator.get_unit(self._unit_id)
        if unit is None:
            return None
        return self.entity_description.value_fn(unit)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False

        unit = self.coordinator.get_unit(self._unit_id)
        if unit is None:
            return False

        # Check if device is in error state
        if unit.is_in_error:
            return False

        return self.entity_description.available_fn(unit)


class ATWSensor(CoordinatorEntity[MELCloudHomeCoordinator], SensorEntity):  # type: ignore[misc]
    """Representation of a MELCloud Home ATW sensor.

    Note: type: ignore[misc] required because HA is not installed in dev environment
    (aiohttp version conflict). Mypy sees HA base classes as 'Any'.
    """

    _attr_has_entity_name = True  # Use device name + entity name pattern
    entity_description: ATWSensorEntityDescription

    def __init__(
        self,
        coordinator: MELCloudHomeCoordinator,
        unit: AirToWaterUnit,
        building: Building,
        entry: ConfigEntry,
        description: ATWSensorEntityDescription,
    ) -> None:
        """Initialize the ATW sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._unit_id = unit.id
        self._building_id = building.id
        self._entry = entry

        # Unique ID: unit_id + sensor key
        self._attr_unique_id = f"{unit.id}_{description.key}"

        # Convert description key to friendly name
        short_name = description.key.replace("_", " ").title()

        # Fix acronyms to proper capitalization
        acronym_fixes = {
            "Dhw": "DHW",  # Domestic Hot Water
            "Wifi": "WiFi",  # WiFi signal
            "Ftc": "FTC",  # FTC model numbers
        }
        for incorrect, correct in acronym_fixes.items():
            short_name = short_name.replace(incorrect, correct)

        self._attr_name = short_name

        # Device info using shared helper
        self._attr_device_info = create_device_info(unit, building)

    @property
    def native_value(self) -> float | str | None:
        """Return the sensor value."""
        unit = self.coordinator.get_atw_unit(self._unit_id)
        if unit is None:
            return None

        return self.entity_description.value_fn(unit)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False

        unit = self.coordinator.get_atw_unit(self._unit_id)
        if unit is None:
            return False

        # Check if device is in error state
        if unit.is_in_error:
            return False

        return self.entity_description.available_fn(unit)
