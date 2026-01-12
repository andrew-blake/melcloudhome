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
from .const_atw import (
    ATW_PRESET_MODES,
    ATW_TEMP_MAX_ZONE,
    ATW_TEMP_MIN_ZONE,
    ATW_TO_HA_PRESET,
    HA_TO_ATW_PRESET,
    ATWEntityBase,
)
from .helpers import create_atw_device_info, with_debounced_refresh
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

        # HVAC modes (ATW is heat-only, OFF delegates to switch power control)
        self._attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]

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
        operation_status shows what valve is ACTIVELY doing RIGHT NOW.
        operation_mode_zone1 shows CONFIGURED mode for Zone 1.

        API operation_status values (atw-api-reference.md):
        - "Stop" = Idle (target reached, no heating)
        - "HotWater" = Heating DHW tank (not Zone 1)
        - Zone mode string (e.g., "HeatRoomTemperature") = Actively heating that zone

        When operation_status == operation_mode_zone1:
        - Valve is positioned on Zone 1 AND actively heating
        - No temperature check needed - API already indicates active heating
        """
        device = self.get_device()
        if device is None or not device.power:
            return HVACAction.OFF

        # Check what the 3-way valve is doing right now
        # If operation_status is "Stop", system is idle
        if device.operation_status == "Stop":
            return HVACAction.IDLE

        # If valve is on Zone 1 (operation_status == operation_mode_zone1),
        # the system is ACTIVELY HEATING this zone
        if device.operation_status == device.operation_mode_zone1:
            return HVACAction.HEATING

        # Valve is elsewhere (DHW or Zone 2) - this zone is idle
        return HVACAction.IDLE

    @property
    def current_temperature(self) -> float | None:
        """Return current Zone 1 room temperature."""
        device = self.get_device()
        if device is None:
            return None
        return device.room_temperature_zone1

    @property
    def target_temperature_step(self) -> float:
        """Return temperature step based on device capability.

        Respects hasHalfDegrees to avoid breaking MELCloud web UI.
        Even though API accepts 0.5°C values, MELCloud UI cannot display them
        properly when hasHalfDegrees=false (UI goes off scale).

        Validated: Real ATW device with hasHalfDegrees=false breaks MELCloud UI
        when set to values like 21.5°C.
        """
        device = self.get_device()
        if device and device.capabilities:
            return 0.5 if device.capabilities.has_half_degrees else 1.0
        return 1.0  # Safe default

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

        HEAT: Turn on system power
        OFF: Turn off system power (delegates to switch.py logic)

        Note: Climate OFF and switch OFF both call the same power control method.
        This provides standard HA UX while maintaining single responsibility.
        """
        if hvac_mode == HVACMode.HEAT:
            await self.coordinator.async_set_power_atw(self._unit_id, True)
        elif hvac_mode == HVACMode.OFF:
            await self.coordinator.async_set_power_atw(self._unit_id, False)
        else:
            _LOGGER.warning("Invalid HVAC mode %s for ATW", hvac_mode)

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
