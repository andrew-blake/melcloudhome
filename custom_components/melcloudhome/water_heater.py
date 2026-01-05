"""Water heater platform for MELCloud Home integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.water_heater import (
    STATE_ECO,
    STATE_PERFORMANCE,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api.models import AirToWaterUnit, Building
from .const import (
    ATW_TEMP_MAX_DHW,
    ATW_TEMP_MIN_DHW,
    DOMAIN,
    WATER_HEATER_FORCED_DHW_TO_HA,
    WATER_HEATER_HA_TO_FORCED_DHW,
    create_atw_device_info,
    create_atw_entity_name,
)
from .coordinator import MELCloudHomeCoordinator

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
    CoordinatorEntity[MELCloudHomeCoordinator],  # type: ignore[misc]
    WaterHeaterEntity,  # type: ignore[misc]
):
    """Water heater entity for ATW DHW tank.

    Note: type: ignore[misc] required because HA is not installed in dev environment
    (aiohttp version conflict). Mypy sees HA base classes as 'Any'.
    """

    _attr_has_entity_name = False  # Use explicit naming for stable entity IDs
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = ATW_TEMP_MIN_DHW
    _attr_max_temp = ATW_TEMP_MAX_DHW

    def __init__(
        self,
        coordinator: MELCloudHomeCoordinator,
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

        # Generate entity name using shared helper
        self._attr_name = create_atw_entity_name(unit, "Tank")

        # Device info using shared helper (groups with climate/sensors)
        self._attr_device_info = create_atw_device_info(unit, building)

        # Supported features
        self._attr_supported_features = (
            WaterHeaterEntityFeature.TARGET_TEMPERATURE
            | WaterHeaterEntityFeature.OPERATION_MODE
            | WaterHeaterEntityFeature.ON_OFF
        )

        # Operation modes
        self._attr_operation_list = [STATE_ECO, STATE_PERFORMANCE]

    @property
    def _device(self) -> AirToWaterUnit | None:
        """Get the current device from coordinator data - O(1) cached lookup."""
        return self.coordinator.get_atw_unit(self._unit_id)  # type: ignore[no-any-return]

    @property
    def _building(self) -> Building | None:
        """Get the current building from coordinator data - O(1) cached lookup."""
        return self.coordinator.get_building_for_atw_unit(self._unit_id)  # type: ignore[no-any-return]

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False

        device = self._device
        if device is None:
            return False

        # Check if device is in error state
        return not device.is_in_error

    @property
    def current_temperature(self) -> float | None:
        """Return current DHW tank temperature."""
        device = self._device
        if device is None:
            return None
        return device.tank_water_temperature

    @property
    def target_temperature(self) -> float | None:
        """Return target DHW tank temperature."""
        device = self._device
        if device is None:
            return None
        return device.set_tank_water_temperature

    @property
    def current_operation(self) -> str | None:
        """Return current operation mode (eco or performance)."""
        device = self._device
        if device is None:
            return None

        # Map forced_hot_water_mode to HA operation mode
        mode: str = WATER_HEATER_FORCED_DHW_TO_HA.get(
            device.forced_hot_water_mode, STATE_ECO
        )
        return mode

    @property
    def is_on(self) -> bool | None:
        """Return True if water heater (and system) is on."""
        device = self._device
        if device is None:
            return None
        return device.power

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        device = self._device
        if device is None:
            return {}

        return {
            "operation_status": device.operation_status,
            "forced_dhw_active": device.forced_hot_water_mode,
            "zone_heating_suspended": device.forced_hot_water_mode,  # When DHW has priority
            "ftc_model": device.ftc_model,
        }

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target DHW tank temperature."""
        temperature = kwargs.get("temperature")
        if temperature is None:
            return

        # Validate temperature range
        if temperature < self.min_temp or temperature > self.max_temp:
            _LOGGER.warning(
                "DHW temperature %.1f is out of range (%.1f-%.1f)",
                temperature,
                self.min_temp,
                self.max_temp,
            )
            return

        # Set DHW temperature
        await self.coordinator.async_set_dhw_temperature(self._unit_id, temperature)

        # Request debounced refresh to avoid race conditions
        await self.coordinator.async_request_refresh_debounced()

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new operation mode (eco or performance).

        eco: Normal balanced operation
        performance: DHW priority mode (forces hot water)
        """
        if operation_mode not in self.operation_list:
            _LOGGER.warning("Invalid operation mode: %s", operation_mode)
            return

        # Map HA operation mode to forced_hot_water_mode
        forced_dhw = WATER_HEATER_HA_TO_FORCED_DHW.get(operation_mode, False)
        await self.coordinator.async_set_forced_hot_water(self._unit_id, forced_dhw)

        # Request debounced refresh to avoid race conditions
        await self.coordinator.async_request_refresh_debounced()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the water heater (entire ATW system) on."""
        await self.coordinator.async_set_power_atw(self._unit_id, True)

        # Request debounced refresh to avoid race conditions
        await self.coordinator.async_request_refresh_debounced()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the water heater (entire ATW system) off.

        Note: This powers off the entire ATW system (matches official MELCloud app).
        Both water_heater and climate entities can control system power.
        """
        await self.coordinator.async_set_power_atw(self._unit_id, False)

        # Request debounced refresh to avoid race conditions
        await self.coordinator.async_request_refresh_debounced()
