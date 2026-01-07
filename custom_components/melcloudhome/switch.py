"""Switch platform for MELCloud Home integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api.models import AirToWaterUnit, Building
from .const import (
    DOMAIN,
    ATWEntityBase,
    with_debounced_refresh,
)
from .coordinator import MELCloudHomeCoordinator
from .helpers import create_atw_device_info
from .protocols import CoordinatorProtocol

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MELCloud Home switch entities."""
    _LOGGER.debug("Setting up MELCloud Home switch platform")

    coordinator: MELCloudHomeCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    entities = []
    for building in coordinator.data.buildings:
        for unit in building.air_to_water_units:
            entities.append(ATWSystemPowerSwitch(coordinator, unit, building, entry))

    _LOGGER.debug("Created %d switch entities", len(entities))
    async_add_entities(entities)


class ATWSystemPowerSwitch(ATWEntityBase, SwitchEntity):  # type: ignore[misc]
    """Switch entity for ATW system power control.

    Controls the entire ATW heat pump system (all zones and DHW).
    This is the single point of control for system power, following SRP.

    Note: type: ignore[misc] required because HA is not installed in dev environment
    (aiohttp version conflict). Mypy sees HA base classes as 'Any'.
    """

    _attr_has_entity_name = True  # Use device name + entity name pattern

    def __init__(
        self,
        coordinator: CoordinatorProtocol,
        unit: AirToWaterUnit,
        building: Building,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the switch entity."""
        super().__init__(coordinator)
        self._unit_id = unit.id
        self._building_id = building.id
        self._attr_unique_id = f"{unit.id}_system_power"
        self._entry = entry

        # Short entity name (device name provides UUID prefix)
        self._attr_name = "System Power"

        # Device info using shared helper (groups with climate/water_heater/sensors)
        self._attr_device_info = create_atw_device_info(unit, building)

    @property
    def is_on(self) -> bool | None:
        """Return true if the system is on."""
        device = self.get_device()
        if device is None:
            return None
        return device.power

    @with_debounced_refresh()
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the ATW system on."""
        await self.coordinator.async_set_power_atw(self._unit_id, True)

    @with_debounced_refresh()
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the ATW system off."""
        await self.coordinator.async_set_power_atw(self._unit_id, False)
