"""Air-to-Air (A/C) sensor platform for MELCloud Home integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

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
from .api.parsing import Reading
from .helpers import (
    initialize_entity_base,
    sensor_native_value,
    sensor_state_attributes,
)
from .protocols import CoordinatorProtocol


@dataclass(frozen=True, kw_only=True)
class ATASensorEntityDescription(SensorEntityDescription):  # type: ignore[misc]
    """Sensor entity description with value extraction.

    Note: type: ignore[misc] required because HA is not installed in dev environment
    (aiohttp version conflict). Mypy sees SensorEntityDescription as 'Any'.
    """

    value_fn: Callable[[AirToAirUnit], float | str | None] | None = None
    """Extract the sensor value. Mutually exclusive with reading_fn."""

    reading_fn: Callable[[AirToAirUnit], Reading | None] | None = None
    """Extract a value that carries its own recording time.

    Setting this instead of value_fn marks the sensor as fed by a slow-cadence
    poll: the state comes from the reading's value and a `last_reading`
    attribute is added automatically (issue #200).
    """

    should_create_fn: Callable[[AirToAirUnit], bool] = lambda x: True
    """Whether to create the sensor at all.

    Must test something stable about the unit (a capability, a model trait) - never
    a value that comes and goes, because creation is only evaluated once at setup.
    A transient missing value reads as state `unknown`; it never gates creation.
    """


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
    ),
    # Energy consumption sensor
    # Created if device has energy meter capability, even if no initial data
    # Reads unknown until energy data is fetched (polls every 30 minutes)
    ATASensorEntityDescription(
        key="energy",  # Entity ID: sensor.melcloud_*_energy
        translation_key="energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=lambda unit: unit.energy_consumed,
        should_create_fn=lambda unit: unit.capabilities.has_energy_consumed_meter,
    ),
    # Outdoor temperature - ambient temperature from outdoor unit sensor
    # Updates every 30 minutes via trendsummary API endpoint
    ATASensorEntityDescription(
        key="outdoor_temperature",
        translation_key="outdoor_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        # Always created; "unknown" until a reading arrives.
        # last_reading surfaces staleness: idle units stop uploading (#152/#171).
        reading_fn=lambda unit: unit.outdoor_temp_reading,
    ),
    # Protection mode setpoints - separate sensors so the thresholds are visible
    # as first-class entities in the frontend, not just tucked away as attributes
    # on the frost_protection/overheat_protection binary sensors.
    # No state_class: these are configured thresholds, not measurements that
    # accumulate meaningful long-term statistics.
    ATASensorEntityDescription(
        key="frost_protection_min",
        translation_key="frost_protection_min",
        device_class=SensorDeviceClass.TEMPERATURE,
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
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda unit: (
            unit.overheat_protection.max if unit.overheat_protection else None
        ),
        should_create_fn=lambda unit: unit.overheat_protection is not None,
    ),
    # Holiday mode timestamps are local wall time, not UTC (verified
    # 2026-07-23 Italy, 2026-07-28 UK; submitter and device were co-located
    # both times, so device-local vs submitter-local is undetermined). The
    # building `timezone` field is unreliable, so no safe conversion exists -
    # exposed as raw strings, no TIMESTAMP device class.
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
        return sensor_native_value(self.entity_description, device)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes."""
        if self.entity_description.reading_fn is None:
            return None

        device = self.coordinator.get_ata_device(self._unit_id)
        if device is None:
            return None
        return sensor_state_attributes(self.entity_description, device)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False

        device = self.coordinator.get_ata_device(self._unit_id)
        if device is None:
            return False

        # Check if device is in error state
        return not device.is_in_error
