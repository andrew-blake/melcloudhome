"""Helper functions for MELCloud Home integration.

This module contains utility functions for entity initialization
and device info creation. Previously these were in const.py but are now
organized separately for better code organization.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.device_registry import DeviceInfo

from .api.models import AirToWaterUnit
from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.helpers.update_coordinator import CoordinatorEntity

    from .api.models import AirToAirUnit, Building

    # Type alias for units that work with generic helpers
    DeviceUnit = AirToAirUnit | AirToWaterUnit


# =================================================================
# Shared Decorator
# =================================================================


def with_debounced_refresh(
    delay: float = 2.0,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator for automatic debounced refresh after service calls.

    Eliminates manual refresh calls in every service method (Issue #10).
    Prevents race conditions from rapid service calls.

    Args:
        delay: Seconds to wait before refreshing (default 2.0)

    Usage:
        @with_debounced_refresh()
        async def async_set_temperature(self, **kwargs):
            temperature = kwargs.get("temperature")
            await self.coordinator.async_set_temperature(self._unit_id, temperature)
            # Refresh happens automatically - no manual call needed
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            result = await func(self, *args, **kwargs)
            await self.coordinator.async_request_refresh_debounced(delay)
            return result

        return wrapper

    return decorator


def create_device_info(unit: DeviceUnit, building: Building) -> DeviceInfo:
    """Create standardized device info for ATA or ATW devices.

    All entities for the same device MUST use identical identifiers
    to be grouped under one device in the Home Assistant UI.

    Works for both AirToAirUnit and AirToWaterUnit - automatically
    determines correct model string based on unit type.

    Args:
        unit: ATA or ATW device object
        building: Building containing the device

    Returns:
        DeviceInfo dict with identifiers, name, manufacturer, model, area
    """
    # Extract UUID fragments for stable device naming
    unit_id_clean = unit.id.replace("-", "")
    device_name = f"melcloudhome_{unit_id_clean[:4]}_{unit_id_clean[-4:]}"

    # Determine model string based on device type
    if isinstance(unit, AirToWaterUnit):
        model = "Air-to-Water Heat Pump (Ecodan via MELCloud Home)"
    else:  # AirToAirUnit
        model = "Air-to-Air Heat Pump (via MELCloud Home)"

    return DeviceInfo(
        identifiers={(DOMAIN, unit.id)},
        name=device_name,
        manufacturer="Mitsubishi Electric",
        model=model,
        suggested_area=building.name,
    )


def initialize_entity_base(
    entity: CoordinatorEntity,
    unit: DeviceUnit,
    building: Building,
    entry: ConfigEntry,
    description: Any,
) -> None:
    """Initialize common entity attributes for sensors and binary sensors.

    Extracts common initialization pattern used by ATASensor, ATWSensor,
    ATABinarySensor, and ATWBinarySensor to eliminate code duplication.

    Sets the following entity attributes:
    - _unit_id: Device unit ID for coordinator lookups
    - _building_id: Building ID for coordinator lookups
    - _entry: Config entry reference
    - _attr_unique_id: Stable unique identifier (unit_id + description key)
    - _attr_device_info: Device information for grouping in HA UI

    Does NOT set _attr_name: every description passed here declares a
    translation_key, and an explicit _attr_name would take precedence over
    it, silently defeating translation (#240). Callers without a
    translation_key would fall back to HA's raw entity-key display -
    add one instead of reintroducing a generated name here.

    Args:
        entity: Entity instance to initialize (ATASensor, ATWSensor, etc.)
        unit: ATA or ATW device object
        building: Building containing the device
        entry: Home Assistant config entry
        description: Entity description with 'key' attribute

    Example:
        >>> def __init__(self, coordinator, unit, building, entry, description):
        ...     super().__init__(coordinator)
        ...     self.entity_description = description
        ...     initialize_entity_base(self, unit, building, entry, description)

    Note:
        This preserves the existing unique_id format (unit_id + key) so that
        already-registered entities keep their entity_id stable across
        restarts - HA looks entities up by unique_id and does not regenerate
        entity_id for them. This has no bearing on brand-new registrations,
        which get entity_id derived fresh from the current name (see above).
        Do not modify the unique_id format.
    """
    # Store IDs for coordinator lookups
    entity._unit_id = unit.id
    entity._building_id = building.id
    entity._entry = entry

    # Generate unique_id: unit_id + sensor key
    # CRITICAL: Do not change this format - it would break existing entity IDs
    entity._attr_unique_id = f"{unit.id}_{description.key}"

    # Device info using shared helper
    entity._attr_device_info = create_device_info(unit, building)


# =================================================================
# Sensor Value / Attribute Accessors
# =================================================================


def sensor_native_value(description: Any, device: Any) -> float | str | None:
    """Read a sensor's state from whichever accessor its description defines."""
    if description.reading_fn is not None:
        reading = description.reading_fn(device)
        return reading.value if reading else None
    return description.value_fn(device) if description.value_fn else None


def sensor_state_attributes(description: Any, device: Any) -> dict[str, Any] | None:
    """Build a sensor's attributes, adding last_reading when it has provenance.

    last_reading separates a value that is genuinely steady from one frozen by
    a poll that stopped succeeding (issue #200, ADR-022). Deliberately absent
    from context-sourced sensors, which are refetched every 60s.

    Present-but-null when a reading-backed sensor has no reading yet, so
    templates can rely on the key existing.
    """
    if description.reading_fn is None:
        return None
    reading = description.reading_fn(device)
    return {"last_reading": reading.recorded_at.isoformat() if reading else None}
