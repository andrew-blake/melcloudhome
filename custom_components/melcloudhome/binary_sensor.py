"""Binary sensor platform for MELCloud Home integration.

Platform entry point that sets up both ATA and ATW binary sensor entities.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .binary_sensor_ata import (
    ATA_BINARY_SENSOR_TYPES,
    ATABinarySensor,
)
from .binary_sensor_atw import (
    ATW_BINARY_SENSOR_TYPES,
    ATWBinarySensor,
)
from .const import DOMAIN
from .coordinator import MELCloudHomeCoordinator

_LOGGER = logging.getLogger(__name__)


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
            for description in ATA_BINARY_SENSOR_TYPES:
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

    # Account-level real-time updates connectivity sensor (one per entry)
    if coordinator.ws_enabled:
        async_add_entities([WebSocketConnectivitySensor(coordinator, entry)])


class WebSocketConnectivitySensor(
    CoordinatorEntity[MELCloudHomeCoordinator],  # type: ignore[misc]
    BinarySensorEntity,  # type: ignore[misc]
):
    """Reports whether the real-time WebSocket connection is up.

    Account-level (one per config entry), attached to a service device.
    Always available: it reports connectivity itself.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "realtime_updates"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, coordinator: MELCloudHomeCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the connectivity sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_realtime_updates"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="MELCloud Home",
            manufacturer="Mitsubishi Electric",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def is_on(self) -> bool:
        """Return true if the WebSocket is connected."""
        return bool(self.coordinator.ws_connected)

    @property
    def available(self) -> bool:
        """Always available — this entity reports connectivity itself."""
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the timestamp of the last received delta."""
        return {"last_delta_at": self.coordinator.ws_last_delta_at}
