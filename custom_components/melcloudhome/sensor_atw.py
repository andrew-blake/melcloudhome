"""Air-to-Water (Heat Pump) sensor platform for MELCloud Home integration."""

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

from .api.models import AirToWaterUnit, Building
from .helpers import initialize_entity_base
from .protocols import CoordinatorProtocol

_LOGGER = logging.getLogger(__name__)


def _has_energy_consumption_capability(unit: AirToWaterUnit) -> bool:
    """Check if unit has energy consumption capability (measured or estimated)."""
    return (
        unit.capabilities.has_estimated_energy_consumption
        or unit.capabilities.has_measured_energy_consumption
    )


def _has_energy_production_capability(unit: AirToWaterUnit) -> bool:
    """Check if unit has energy production capability (measured or estimated)."""
    return (
        unit.capabilities.has_estimated_energy_production
        or unit.capabilities.has_measured_energy_production
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
    # Telemetry sensors (flow/return temperatures from telemetry API)
    # HA auto-creates statistics for MEASUREMENT sensors (validated via spike)
    ATWSensorEntityDescription(
        key="flow_temperature",
        translation_key="flow_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda unit: unit.telemetry.get("flow_temperature"),
        available_fn=lambda unit: unit.telemetry.get("flow_temperature") is not None,
    ),
    ATWSensorEntityDescription(
        key="return_temperature",
        translation_key="return_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda unit: unit.telemetry.get("return_temperature"),
        available_fn=lambda unit: unit.telemetry.get("return_temperature") is not None,
    ),
    ATWSensorEntityDescription(
        key="flow_temperature_zone1",
        translation_key="flow_temperature_zone1",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda unit: unit.telemetry.get("flow_temperature_zone1"),
        available_fn=lambda unit: unit.telemetry.get("flow_temperature_zone1")
        is not None,
    ),
    ATWSensorEntityDescription(
        key="return_temperature_zone1",
        translation_key="return_temperature_zone1",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda unit: unit.telemetry.get("return_temperature_zone1"),
        available_fn=lambda unit: unit.telemetry.get("return_temperature_zone1")
        is not None,
    ),
    ATWSensorEntityDescription(
        key="flow_temperature_boiler",
        translation_key="flow_temperature_boiler",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda unit: unit.telemetry.get("flow_temperature_boiler"),
        available_fn=lambda unit: unit.telemetry.get("flow_temperature_boiler")
        is not None,
    ),
    ATWSensorEntityDescription(
        key="return_temperature_boiler",
        translation_key="return_temperature_boiler",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda unit: unit.telemetry.get("return_temperature_boiler"),
        available_fn=lambda unit: unit.telemetry.get("return_temperature_boiler")
        is not None,
    ),
    # WiFi signal strength - diagnostic sensor for connectivity troubleshooting
    # Shows received signal strength indication (RSSI) in dBm
    # Typical range: -30 (excellent) to -90 (poor)
    ATWSensorEntityDescription(
        key="wifi_signal",
        translation_key="wifi_signal",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda unit: unit.telemetry.get("rssi"),
        should_create_fn=lambda unit: True,
        available_fn=lambda unit: unit.telemetry.get("rssi") is not None,
    ),
    # Energy monitoring sensors
    # Created if device has energy capability (measured or estimated), even if no initial data
    # Becomes available once energy data is fetched (polls every 30 minutes)
    ATWSensorEntityDescription(
        key="energy_consumed",
        translation_key="energy_consumed",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=lambda unit: unit.energy_consumed,
        should_create_fn=_has_energy_consumption_capability,
        available_fn=lambda unit: unit.energy_consumed is not None,
    ),
    ATWSensorEntityDescription(
        key="energy_produced",
        translation_key="energy_produced",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=lambda unit: unit.energy_produced,
        should_create_fn=_has_energy_production_capability,
        available_fn=lambda unit: unit.energy_produced is not None,
    ),
    ATWSensorEntityDescription(
        key="cop",
        translation_key="cop",
        device_class=None,  # COP is dimensionless
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=None,
        value_fn=lambda unit: unit.cop,
        should_create_fn=_has_energy_consumption_capability,  # COP requires consumption data
        available_fn=lambda unit: unit.cop is not None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ATW sensor platform."""
    coordinator: CoordinatorProtocol = hass.data[entry.domain][entry.entry_id]

    entities = []
    for building in coordinator.data.buildings:
        for unit in building.air_to_water_units:
            entities.extend(
                _create_sensors_for_unit(
                    coordinator, unit, building, entry, ATW_SENSOR_TYPES
                )
            )

    async_add_entities(entities)
    _LOGGER.info("Created %d ATW sensor(s)", len(entities))


def _create_sensors_for_unit(
    coordinator: CoordinatorProtocol,
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


class ATWSensor(CoordinatorEntity[CoordinatorProtocol], SensorEntity):  # type: ignore[misc]
    """Representation of a MELCloud Home ATW sensor.

    Note: type: ignore[misc] required because HA is not installed in dev environment
    (aiohttp version conflict). Mypy sees HA base classes as 'Any'.
    """

    _attr_has_entity_name = True  # Use device name + entity name pattern
    entity_description: ATWSensorEntityDescription

    def __init__(
        self,
        coordinator: CoordinatorProtocol,
        unit: AirToWaterUnit,
        building: Building,
        entry: ConfigEntry,
        description: ATWSensorEntityDescription,
    ) -> None:
        """Initialize the ATW sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        initialize_entity_base(self, unit, building, entry, description)

    @property
    def native_value(self) -> float | str | None:
        """Return the sensor value."""
        device = self.coordinator.get_atw_device(self._unit_id)
        if device is None:
            return None

        return self.entity_description.value_fn(device)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False

        device = self.coordinator.get_atw_device(self._unit_id)
        if device is None:
            return False

        # Check if device is in error state
        if device.is_in_error:
            return False

        return self.entity_description.available_fn(device)
