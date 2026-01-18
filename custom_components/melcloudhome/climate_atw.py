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
    ATW_OPERATION_MODES_COOLING,
    ATW_PRESET_MODES,
    ATW_TEMP_MAX_ZONE,
    ATW_TEMP_MIN_ZONE,
    ATW_TO_HA_PRESET,
    HA_TO_ATW_PRESET_COOL,
    HA_TO_ATW_PRESET_HEAT,
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

        # HVAC modes (dynamic based on cooling capability)
        hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
        if unit.capabilities and unit.capabilities.has_cooling_mode:
            hvac_modes.append(HVACMode.COOL)
        self._attr_hvac_modes = hvac_modes

        # Preset modes (dynamic - see preset_modes property)

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

        # Check if in cooling mode
        if device.operation_mode_zone1 in ATW_OPERATION_MODES_COOLING:
            return HVACMode.COOL

        return HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return current HVAC action (3-way valve aware).

        CRITICAL: Must check if valve is serving THIS specific zone.
        operation_status shows what valve is ACTIVELY doing RIGHT NOW.
        operation_mode_zone1 shows CONFIGURED mode for Zone 1.

        API operation_status values:
        - "Stop" = Idle (target reached, no heating)
        - "HotWater" = Heating DHW tank (not Zone 1)
        - "Heating" = Actively heating zone
        """
        device = self.get_device()
        if device is None or not device.power:
            return HVACAction.OFF

        # Check what the 3-way valve is doing right now
        # If operation_status is "Stop", system is idle
        if device.operation_status == "Stop":
            return HVACAction.IDLE

        # API returns "Heating" when actively heating zone
        if device.operation_status == "Heating":
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
    def preset_modes(self) -> list[str]:
        """Return available preset modes (dynamic based on hvac_mode).

        Cooling mode: ["room", "flow"] (2 presets)
        Heating mode: ["room", "flow", "curve"] (3 presets)

        Note: CoolCurve does NOT exist (confirmed from ERSC-VM2D testing)
        """
        if self.hvac_mode == HVACMode.COOL:
            return ["room", "flow"]  # Only 2 presets for cooling
        return ATW_PRESET_MODES  # All 3 presets for heating

    @property
    def target_temperature_step(self) -> float:
        """Return temperature step based on hvac_mode and device capability.

        Cooling mode: Always 1.0°C (confirmed from ERSC-VM2D testing)
        Heating mode: 0.5°C or 1.0°C based on hasHalfDegrees capability

        Note: hasHalfDegrees respected to avoid breaking MELCloud web UI.
        Even though API accepts 0.5°C values, MELCloud UI cannot display them
        properly when hasHalfDegrees=false (UI goes off scale).
        """
        # Cooling mode always uses 1.0°C steps
        if self.hvac_mode == HVACMode.COOL:
            return 1.0

        # Heating mode respects hasHalfDegrees capability
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

        HEAT: Turn on system power and set heating mode
        COOL: Turn on system power and set cooling mode
        OFF: Turn off system power (delegates to switch.py logic)

        Note: Climate OFF and switch OFF both call the same power control method.
        This provides standard HA UX while maintaining single responsibility.
        """
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.async_set_power_atw(self._unit_id, False)
            return

        # Turn on power for HEAT or COOL
        await self.coordinator.async_set_power_atw(self._unit_id, True)

        # Set appropriate operation mode
        if hvac_mode == HVACMode.HEAT:
            # Preserve current preset if valid for heating, else default to room
            current_preset = self.preset_mode or "room"
            heat_mode = HA_TO_ATW_PRESET_HEAT.get(current_preset, "HeatRoomTemperature")
            await self.coordinator.async_set_mode_zone1(self._unit_id, heat_mode)

        elif hvac_mode == HVACMode.COOL:
            # Preserve preset if valid for cooling, else default to room
            current_preset = self.preset_mode or "room"
            if current_preset == "curve":
                # Curve doesn't exist for cooling, default to room
                current_preset = "room"
            cool_mode = HA_TO_ATW_PRESET_COOL.get(current_preset, "CoolRoomTemperature")
            await self.coordinator.async_set_mode_zone1(self._unit_id, cool_mode)

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

        Mode-specific presets:
        - Heating: room, flow, curve
        - Cooling: room, flow (no curve)

        Presets map to different API modes depending on hvac_mode:
        - room: HeatRoomTemperature or CoolRoomTemperature
        - flow: HeatFlowTemperature or CoolFlowTemperature
        - curve: HeatCurve (heating only)
        """
        if preset_mode not in self.preset_modes:
            _LOGGER.warning(
                "Invalid preset mode %s for hvac_mode %s", preset_mode, self.hvac_mode
            )
            return

        # Map preset to appropriate API mode based on current hvac_mode
        if self.hvac_mode == HVACMode.COOL:
            atw_mode = HA_TO_ATW_PRESET_COOL.get(preset_mode)
        else:
            atw_mode = HA_TO_ATW_PRESET_HEAT.get(preset_mode)

        if atw_mode is None:
            _LOGGER.warning("Unknown preset mode: %s", preset_mode)
            return

        # Set Zone 1 operation mode
        await self.coordinator.async_set_mode_zone1(self._unit_id, atw_mode)
