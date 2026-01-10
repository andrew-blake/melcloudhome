"""Water heater platform for MELCloud Home integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api.models import AirToWaterUnit, Building
from .const import DOMAIN
from .const_atw import (
    ATW_TEMP_MAX_DHW,
    ATW_TEMP_MIN_DHW,
    WATER_HEATER_FORCED_DHW_TO_HA,
    WATER_HEATER_HA_TO_FORCED_DHW,
    ATWEntityBase,
)
from .coordinator import MELCloudHomeCoordinator
from .helpers import create_atw_device_info, with_debounced_refresh
from .protocols import CoordinatorProtocol

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MELCloud Home water heater entities."""
    _LOGGER.debug("Setting up MELCloud Home water heater platform")

    coordinator: MELCloudHomeCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    entities = []
    for building in coordinator.data.buildings:
        for unit in building.air_to_water_units:
            entities.append(ATWWaterHeater(coordinator, unit, building, entry))

    _LOGGER.debug("Created %d water heater entities", len(entities))
    async_add_entities(entities)


class ATWWaterHeater(
    ATWEntityBase,
    WaterHeaterEntity,  # type: ignore[misc]
):
    """Water heater entity for ATW DHW tank.

    Note: type: ignore[misc] required because HA is not installed in dev environment
    (aiohttp version conflict). Mypy sees HA base classes as 'Any'.
    """

    _attr_has_entity_name = True  # Use device name + entity name pattern
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = ATW_TEMP_MIN_DHW
    _attr_max_temp = ATW_TEMP_MAX_DHW

    def __init__(
        self,
        coordinator: CoordinatorProtocol,
        unit: AirToWaterUnit,
        building: Building,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the water heater entity."""
        super().__init__(coordinator)
        self._unit_id = unit.id
        self._building_id = building.id
        self._attr_unique_id = f"{unit.id}_tank"
        self._entry = entry

        # Short entity name (device name provides UUID prefix)
        self._attr_name = "Tank"

        # Device info using shared helper (groups with climate/sensors)
        self._attr_device_info = create_atw_device_info(unit, building)

        # Supported features (use switch for power control)
        self._attr_supported_features = (
            WaterHeaterEntityFeature.TARGET_TEMPERATURE
            | WaterHeaterEntityFeature.OPERATION_MODE
        )

        # Operation modes (match MELCloud Home app terminology)
        # Capitalized directly - translations don't work for water_heater in custom integrations
        self._attr_operation_list = ["Auto", "Force DHW"]

    @property
    def current_temperature(self) -> float | None:
        """Return current DHW tank temperature."""
        device = self.get_device()
        if device is None:
            return None
        return device.tank_water_temperature

    @property
    def target_temperature(self) -> float | None:
        """Return target DHW tank temperature."""
        device = self.get_device()
        if device is None:
            return None
        return device.set_tank_water_temperature

    @property
    def current_operation(self) -> str | None:
        """Return current operation mode (auto or force_dhw)."""
        device = self.get_device()
        if device is None:
            return None

        # Map forced_hot_water_mode to operation mode
        mode: str = WATER_HEATER_FORCED_DHW_TO_HA.get(
            device.forced_hot_water_mode, "Auto"
        )
        return mode

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        device = self.get_device()
        if device is None:
            return {}

        return {
            "operation_status": device.operation_status,
            "forced_dhw_active": device.forced_hot_water_mode,
            "zone_heating_suspended": device.forced_hot_water_mode,  # When DHW has priority
            "ftc_model": device.ftc_model,
        }

    @with_debounced_refresh()
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target DHW tank temperature."""
        temperature = kwargs.get("temperature")
        if temperature is None:
            return

        # Set DHW temperature
        await self.coordinator.async_set_dhw_temperature(self._unit_id, temperature)

    @with_debounced_refresh()
    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new operation mode (Auto or Force DHW).

        Auto: Normal balanced operation, zone heating priority
        Force DHW: DHW priority mode, forces hot water heating
        """
        if operation_mode not in self.operation_list:
            _LOGGER.warning("Invalid operation mode: %s", operation_mode)
            return

        # Map HA operation mode to forced_hot_water_mode
        forced_dhw = WATER_HEATER_HA_TO_FORCED_DHW.get(operation_mode, False)
        await self.coordinator.async_set_forced_hot_water(self._unit_id, forced_dhw)
