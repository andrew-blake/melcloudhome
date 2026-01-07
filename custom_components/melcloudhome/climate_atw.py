"""Air-to-Water (Heat Pump) climate platform for MELCloud Home integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature

from .api.models import AirToWaterUnit, Building
from .const import (
    ATW_PRESET_MODES,
    ATW_TEMP_MAX_ZONE,
    ATW_TEMP_MIN_ZONE,
    ATW_TEMP_STEP,
    ATW_TO_HA_PRESET,
    HA_TO_ATW_PRESET,
    ATWEntityBase,
    with_debounced_refresh,
)
from .helpers import create_atw_device_info
from .protocols import CoordinatorProtocol

_LOGGER = logging.getLogger(__name__)


class ATWClimateZone1(
    ATWEntityBase,
    ClimateEntity,  # type: ignore[misc]
):
    """Climate entity for ATW Zone 1.

    Note: HA is not installed in dev environment (aiohttp version conflict).
    Mypy sees HA base classes as 'Any'.
    """

    _attr_has_entity_name = True  # Use device name + entity name pattern
    _attr_translation_key = "melcloudhome"  # For preset mode translations
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = ATW_TEMP_STEP
    _attr_min_temp = ATW_TEMP_MIN_ZONE
    _attr_max_temp = ATW_TEMP_MAX_ZONE

    def __init__(
        self,
        coordinator: CoordinatorProtocol,
        unit: AirToWaterUnit,
        building: Building,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the climate entity for Zone 1."""
        super().__init__(coordinator)
        self._unit_id = unit.id
        self._building_id = building.id
        self._attr_unique_id = f"{unit.id}_zone_1"
        self._entry = entry

        # HVAC modes (ATW is heat-only, use switch for power control)
        self._attr_hvac_modes = [HVACMode.HEAT]

        # Preset modes (NEW: Not used in ATA)
        self._attr_preset_modes = ATW_PRESET_MODES

        # Short entity name (device name provides UUID prefix)
        self._attr_name = "Zone 1"

        # Device info using shared helper (groups with water_heater/sensors)
        self._attr_device_info = create_atw_device_info(unit, building)

        # Supported features
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
        )

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        device = self.get_device()
        if device is None or not device.power:
            return HVACMode.OFF

        # ATW is heat-only
        return HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return current HVAC action (3-way valve aware).

        CRITICAL: Must check if valve is serving THIS specific zone.
        operation_status shows what valve is ACTIVELY doing.
        operation_mode_zone1 shows CONFIGURED mode for Zone 1.

        Valve serves Zone 1 only when: operation_status == operation_mode_zone1
        """
        device = self.get_device()
        if device is None or not device.power:
            return HVACAction.OFF

        # Check if 3-way valve is serving THIS zone (Zone 1)
        # Don't just check "is it on a zone" - check if it's on ZONE 1 specifically
        if device.operation_status == device.operation_mode_zone1:
            # Valve is on Zone 1 - check if heating needed
            current = device.room_temperature_zone1
            target = device.set_temperature_zone1

            if current is not None and target is not None and current < target - 0.5:
                return HVACAction.HEATING
            return HVACAction.IDLE

        # Valve is elsewhere (DHW or Zone 2) - zone shows IDLE even if below target
        return HVACAction.IDLE

    @property
    def current_temperature(self) -> float | None:
        """Return current Zone 1 room temperature."""
        device = self.get_device()
        if device is None:
            return None
        return device.room_temperature_zone1

    @property
    def target_temperature(self) -> float | None:
        """Return target Zone 1 temperature."""
        device = self.get_device()
        if device is None:
            return None
        return device.set_temperature_zone1

    @property
    def preset_mode(self) -> str | None:
        """Return current preset mode."""
        device = self.get_device()
        if device is None:
            return None

        # Map ATW zone mode to HA preset
        return ATW_TO_HA_PRESET.get(device.operation_mode_zone1, "room")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        device = self.get_device()
        if device is None:
            return {}

        return {
            "operation_status": device.operation_status,  # 3-way valve position
            "forced_dhw_active": device.forced_hot_water_mode,
            "zone_heating_available": device.operation_status
            == device.operation_mode_zone1,
            "ftc_model": device.ftc_model,
        }

    @with_debounced_refresh()
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new HVAC mode.

        Note: Only HEAT mode is supported. Use the system power switch to turn off.
        """
        if hvac_mode == HVACMode.HEAT:
            # Turn on the system (HEAT mode)
            await self.coordinator.async_set_power_atw(self._unit_id, True)
        else:
            _LOGGER.warning(
                "Invalid HVAC mode %s for ATW. Only HEAT is supported. Use switch entity for power control.",
                hvac_mode,
            )

    @with_debounced_refresh()
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target Zone 1 temperature."""
        temperature = kwargs.get("temperature")
        if temperature is None:
            return

        # Set Zone 1 temperature
        await self.coordinator.async_set_temperature_zone1(self._unit_id, temperature)

    @with_debounced_refresh()
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode (zone operation strategy).

        room: HeatRoomTemperature (thermostat control)
        flow: HeatFlowTemperature (flow temperature control)
        curve: HeatCurve (weather compensation)
        """
        if preset_mode not in self.preset_modes:
            _LOGGER.warning("Invalid preset mode: %s", preset_mode)
            return

        # Map HA preset to ATW zone mode
        atw_mode = HA_TO_ATW_PRESET.get(preset_mode)
        if atw_mode is None:
            _LOGGER.warning("Unknown preset mode: %s", preset_mode)
            return

        # Set Zone 1 operation mode
        await self.coordinator.async_set_mode_zone1(self._unit_id, atw_mode)
