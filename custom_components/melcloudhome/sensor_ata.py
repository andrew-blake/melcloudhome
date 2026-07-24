"""Air-to-Air (A/C) sensor platform for MELCloud Home integration."""

from __future__ import annotations

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
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api.models import AirToAirUnit, Building
from .helpers import initialize_entity_base
from .protocols import CoordinatorProtocol


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


ATA_SENSOR_TYPES: tuple[ATASensorEntityDescription, ...] = (
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
    # Outdoor temperature - ambient temperature from outdoor unit sensor
    # Only created for devices where outdoor sensor detected during capability discovery
    # Updates every 30 minutes via trendsummary API endpoint
    ATASensorEntityDescription(
        key="outdoor_temperature",
        translation_key="outdoor_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda unit: unit.outdoor_temperature,
        available_fn=lambda unit: unit.outdoor_temperature is not None,
        should_create_fn=lambda unit: unit.has_outdoor_temp_sensor,
    ),
    # Protection mode setpoints - separate sensors so the thresholds are visible
    # as first-class entities in the frontend, not just tucked away as attributes
    # on the frost_protection/overheat_protection binary sensors.
    ATASensorEntityDescription(
        key="frost_protection_min",
        translation_key="frost_protection_min",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda unit: (
            unit.frost_protection.min if unit.frost_protection else None
        ),
        should_create_fn=lambda unit: unit.frost_protection is not None,
    ),
    ATASensorEntityDescription(
        key="frost_protection_max",
        translation_key="frost_protection_max",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda unit: (
            unit.frost_protection.max if unit.frost_protection else None
        ),
        should_create_fn=lambda unit: unit.frost_protection is not None,
    ),
    ATASensorEntityDescription(
        key="overheat_protection_min",
        translation_key="overheat_protection_min",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda unit: (
            unit.overheat_protection.min if unit.overheat_protection else None
        ),
        should_create_fn=lambda unit: unit.overheat_protection is not None,
    ),
    ATASensorEntityDescription(
        key="overheat_protection_max",
        translation_key="overheat_protection_max",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda unit: (
            unit.overheat_protection.max if unit.overheat_protection else None
        ),
        should_create_fn=lambda unit: unit.overheat_protection is not None,
    ),
    # Holiday mode window - raw ISO strings as observed from the API, exposed
    # as-is rather than parsed into a UTC-aware datetime / TIMESTAMP device
    # class (unlike outdoor-temp's recorded_at - see #173 - which is confirmed
    # UTC). Live-tested 2026-07-23: set a start time "1 hour from now" on a
    # device physically in Europe/Rome; the raw value matched Rome's local
    # wall clock at that moment, not UTC. The building object's own `timezone`
    # field (e.g. "Europe/Athens" on this account) looked like it might
    # explain the offset but was a coincidence - Athens is UTC+1 ahead of
    # Rome, which happens to cancel out a "+1 hour" test value - and does not
    # reliably describe what these fields mean. No safe general conversion
    # is known, so left as a naive passthrough string.
    ATASensorEntityDescription(
        key="holiday_mode_start_date",
        translation_key="holiday_mode_start_date",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda unit: (
            unit.holiday_mode.start_date if unit.holiday_mode else None
        ),
        should_create_fn=lambda unit: unit.holiday_mode is not None,
    ),
    ATASensorEntityDescription(
        key="holiday_mode_end_date",
        translation_key="holiday_mode_end_date",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda unit: unit.holiday_mode.end_date if unit.holiday_mode else None,
        should_create_fn=lambda unit: unit.holiday_mode is not None,
    ),
)


class ATASensor(CoordinatorEntity[CoordinatorProtocol], SensorEntity):  # type: ignore[misc]
    """Representation of a MELCloud Home sensor.

    Note: type: ignore[misc] required because HA is not installed in dev environment
    (aiohttp version conflict). Mypy sees HA base classes as 'Any'.
    """

    _attr_has_entity_name = True  # Use device name + entity name pattern
    entity_description: ATASensorEntityDescription

    def __init__(
        self,
        coordinator: CoordinatorProtocol,
        unit: AirToAirUnit,
        building: Building,
        entry: ConfigEntry,
        description: ATASensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        initialize_entity_base(self, unit, building, entry, description)

    @property
    def native_value(self) -> float | str | None:
        """Return the sensor value."""
        device = self.coordinator.get_ata_device(self._unit_id)
        if device is None:
            return None
        return self.entity_description.value_fn(device)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False

        device = self.coordinator.get_ata_device(self._unit_id)
        if device is None:
            return False

        # Check if device is in error state
        if device.is_in_error:
            return False

        return self.entity_description.available_fn(device)
