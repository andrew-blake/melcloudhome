# ADR-006: Adopt Entity Description Pattern for Sensors

**Status:** Accepted
**Date:** 2025-11-17
**Context:** Session 9 - Pre-v1.2 research and planning

## Context

As part of v1.2 development, we're adding a sensor platform to expose:
- Room temperature (for statistics and history)
- Energy consumption (if API provides it)
- WiFi signal strength (diagnostic)
- Other device metrics

During Session 9 research, we analyzed modern Home Assistant sensor implementations and identified the entity description pattern as the current best practice.

## Decision

**We will adopt the entity description dataclass pattern for all sensor entities** in v1.2 and beyond.

## Pattern Definition

```python
from dataclasses import dataclass
from typing import Callable
from homeassistant.components.sensor import SensorEntityDescription

@dataclass
class MELCloudHomeSensorEntityDescription(SensorEntityDescription):
    """Sensor entity description with value extraction."""

    value_fn: Callable[[AirToAirUnit], float | str | None]
    """Function to extract sensor value from unit data."""

    available_fn: Callable[[AirToAirUnit], bool] = lambda x: True
    """Function to determine if sensor is available."""

# Define all sensors declaratively
SENSOR_TYPES: tuple[MELCloudHomeSensorEntityDescription, ...] = (
    MELCloudHomeSensorEntityDescription(
        key="room_temperature",
        translation_key="room_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda unit: unit.room_temperature,
    ),
    MELCloudHomeSensorEntityDescription(
        key="energy_consumed",
        translation_key="energy_consumed",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=lambda unit: unit.energy_consumed if hasattr(unit, "energy_consumed") else None,
        available_fn=lambda unit: hasattr(unit, "energy_consumed") and unit.energy_consumed is not None,
    ),
)
```

## Rationale

### Modern Pattern (2022+)

This pattern was introduced in Home Assistant around 2022 and is now considered the standard for new integrations:

1. **Declarative Configuration**: All sensor metadata defined in one place
2. **Type Safety**: Full type hints with dataclasses
3. **Reduced Boilerplate**: No need to repeat metadata in `__init__`
4. **Easier to Maintain**: Adding sensors is as simple as adding to the tuple
5. **Better Testing**: Can test descriptions separately from entity logic

### Widely Adopted

Used by high-quality integrations:
- Official MELCloud integration (partially)
- Ecobee integration
- Nest integration
- Dozens of modern integrations

### Separation of Concerns

```python
# Metadata (static, declarative)
SENSOR_TYPES = (...)

# Runtime logic (dynamic, imperative)
class MELCloudHomeSensor(CoordinatorEntity, SensorEntity):
    @property
    def native_value(self):
        unit = self.coordinator.get_unit(self._unit_id)
        return self.entity_description.value_fn(unit)
```

Clear separation between:
- **What** the sensor is (metadata)
- **How** it works (logic)

### Extensibility

Easy to add custom fields for integration-specific needs:

```python
@dataclass
class MELCloudHomeSensorEntityDescription(SensorEntityDescription):
    value_fn: Callable[[AirToAirUnit], Any]
    available_fn: Callable[[AirToAirUnit], bool] = lambda x: True
    requires_feature: str | None = None  # Custom field
```

## Implementation Details

### Sensor Entity Structure

```python
class MELCloudHomeSensor(CoordinatorEntity[MELCloudHomeCoordinator], SensorEntity):
    """Representation of a MELCloud Home sensor."""

    entity_description: MELCloudHomeSensorEntityDescription

    def __init__(
        self,
        coordinator: MELCloudHomeCoordinator,
        unit: AirToAirUnit,
        building: Building,
        entry: ConfigEntry,
        description: MELCloudHomeSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description

        # Store IDs for lookups
        self._unit_id = unit.id
        self._building_id = building.id

        # Unique ID: unit_id + sensor key
        self._attr_unique_id = f"{unit.id}_{description.key}"

        # Entity naming
        unit_id_clean = unit.id.replace("-", "")
        key_title = description.key.replace("_", " ").title()
        self._attr_name = f"MELCloud {unit_id_clean[:4]} {unit_id_clean[-4:]} {key_title}"

        # Link to device (climate entity's device)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, unit.id)},
        }

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

        return self.entity_description.available_fn(unit)
```

### Platform Setup

```python
async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MELCloud Home sensor entities."""
    coordinator: MELCloudHomeCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[MELCloudHomeSensor] = []
    for building in coordinator.data.buildings:
        for unit in building.air_to_air_units:
            for description in SENSOR_TYPES:
                if description.available_fn(unit):
                    entities.append(
                        MELCloudHomeSensor(coordinator, unit, building, entry, description)
                    )

    async_add_entities(entities)
```

## Consequences

### Positive

1. **Less Boilerplate**: ~50% reduction in code for sensor platform
2. **Type Safety**: Full type checking with mypy
3. **Maintainability**: Easy to add new sensors
4. **Testability**: Can test descriptions independently
5. **Consistency**: Matches modern HA patterns
6. **Documentation**: Self-documenting with type hints

### Negative

1. **Learning Curve**: Contributors must understand dataclasses
2. **Python 3.10+**: Requires modern Python (already required)
3. **Indirection**: One extra level between sensor and value

### Neutral

1. **Performance**: No meaningful impact (lambdas are fast)
2. **Compatibility**: Standard HA pattern, widely supported

## Examples

### Adding a New Sensor (Easy)

```python
# Just add to the tuple - that's it!
SENSOR_TYPES = (
    # ... existing sensors ...
    MELCloudHomeSensorEntityDescription(
        key="wifi_signal",
        translation_key="wifi_signal",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="dBm",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda unit: unit.wifi_signal_strength,
        available_fn=lambda unit: hasattr(unit, "wifi_signal_strength"),
    ),
)
```

### Conditional Sensors (Feature Detection)

```python
MELCloudHomeSensorEntityDescription(
    key="energy_consumed",
    # ... metadata ...
    available_fn=lambda unit: (
        hasattr(unit, "has_energy_meter")
        and unit.has_energy_meter
        and unit.energy_consumed is not None
    ),
)
```

## Alternatives Considered

### Alternative 1: Traditional Entity Properties

```python
class MELCloudHomeSensor(SensorEntity):
    def __init__(self, ...):
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        # Lots of boilerplate repeated for each sensor type
```

**Rejected because:**
- High code duplication
- Error-prone (easy to forget fields)
- Harder to maintain
- Not type-safe

### Alternative 2: Dictionary-Based Configuration

```python
SENSORS = {
    "room_temperature": {
        "device_class": "temperature",
        "unit": "°C",
        "value_fn": lambda u: u.room_temperature,
    }
}
```

**Rejected because:**
- Not type-safe
- Easy to make typos in keys
- No IDE autocomplete
- Harder to validate

### Alternative 3: Entity Description Pattern (Selected)

**Benefits:**
- Type-safe with dataclasses
- Self-documenting
- Modern HA standard
- Reduces boilerplate

**Selected because:** Best balance of type safety, maintainability, and consistency.

## Migration Path

Since this is a new platform, no migration is needed. Future binary sensor and other platforms should also use entity descriptions.

## References

- [Home Assistant Entity Description Pattern](https://developers.home-assistant.io/docs/core/entity#entity-description)
- [MELCloud Sensor Implementation](https://github.com/home-assistant/core/blob/master/homeassistant/components/melcloud/sensor.py)
- [Ecobee Sensor Implementation](https://github.com/home-assistant/core/blob/master/homeassistant/components/ecobee/sensor.py)
- [Session 9 Research Findings](/_claude/session-9-research-findings.md)

## Notes

This pattern will be used for:
- ✅ Sensor platform (v1.2)
- ✅ Binary sensor platform (v1.2)
- ✅ Future platforms (if any)

The pattern is flexible enough to accommodate MELCloud Home-specific needs while following Home Assistant standards.
