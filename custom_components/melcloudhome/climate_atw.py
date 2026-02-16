"""Air-to-Water (Heat Pump) climate platform for MELCloud Home integration."""

from __future__ import annotations

import logging
from abc import abstractmethod
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
from .helpers import create_device_info, with_debounced_refresh
from .protocols import CoordinatorProtocol

_LOGGER = logging.getLogger(__name__)


class ATWClimateBase(
    ATWEntityBase,
    ClimateEntity,  # type: ignore[misc]
):
    """Base climate entity for ATW zones.

    Shared logic for Zone 1 and Zone 2. Subclasses provide zone-specific
    data access (which fields to read) and control methods (which coordinator
    methods to call).

    Note: HA is not installed in dev environment (aiohttp version conflict).
    Mypy sees HA base classes as 'Any'.
    """

    _attr_has_entity_name = True
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
        zone_number: int,
    ) -> None:
        """Initialize the climate entity for a zone."""
        super().__init__(coordinator)
        self._unit_id = unit.id
        self._building_id = building.id
        self._attr_unique_id = f"{unit.id}_zone_{zone_number}"
        self._entry = entry

        # HVAC modes (dynamic based on cooling capability)
        hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
        if unit.capabilities and unit.capabilities.has_cooling_mode:
            hvac_modes.append(HVACMode.COOL)
        self._attr_hvac_modes = hvac_modes

        # Short entity name (device name provides UUID prefix)
        self._attr_name = f"Zone {zone_number}"

        # Device info using shared helper (groups with water_heater/sensors)
        self._attr_device_info = create_device_info(unit, building)

        # Supported features
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
        )

    # --- Abstract zone-specific properties ---

    @property
    @abstractmethod
    def _zone_operation_mode(self) -> str | None:
        """Return the operation mode for this zone."""

    @property
    @abstractmethod
    def current_temperature(self) -> float | None:
        """Return current room temperature for this zone."""

    @property
    @abstractmethod
    def target_temperature(self) -> float | None:
        """Return target temperature for this zone."""

    @abstractmethod
    async def _async_set_zone_temperature(self, temperature: float) -> None:
        """Set target temperature for this zone."""

    @abstractmethod
    async def _async_set_zone_mode(self, mode: str) -> None:
        """Set operation mode for this zone."""

    # --- Shared properties ---

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        device = self.get_device()
        if device is None or not device.power:
            return HVACMode.OFF

        zone_mode = self._zone_operation_mode
        if zone_mode in ATW_OPERATION_MODES_COOLING:
            return HVACMode.COOL

        return HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return current HVAC action (3-way valve aware).

        CRITICAL: Must check if valve is serving THIS specific zone.
        operation_status shows what valve is ACTIVELY doing RIGHT NOW.

        API operation_status values:
        - "Stop" = Idle (target reached, no heating/cooling)
        - "HotWater" = Heating DHW tank
        - "Heating" = Actively heating zone (no zone distinction in API)
        - "Cooling" = Actively cooling zone (no zone distinction in API)
        """
        device = self.get_device()
        if device is None or not device.power:
            return HVACAction.OFF

        if device.operation_status == "Stop":
            return HVACAction.IDLE

        if device.operation_status == "Heating":
            return HVACAction.HEATING

        if device.operation_status == "Cooling":
            return HVACAction.COOLING

        # Valve is elsewhere (DHW) - this zone is idle
        return HVACAction.IDLE

    @property
    def preset_modes(self) -> list[str]:
        """Return available preset modes (dynamic based on hvac_mode).

        Cooling mode: ["room", "flow"] (2 presets)
        Heating mode: ["room", "flow", "curve"] (3 presets)

        Note: CoolCurve does NOT exist (confirmed from ERSC-VM2D testing)
        """
        if self.hvac_mode == HVACMode.COOL:
            return ["room", "flow"]
        return ATW_PRESET_MODES

    @property
    def target_temperature_step(self) -> float:
        """Return temperature step based on hvac_mode and device capability.

        Cooling mode: Always 1.0°C (confirmed from ERSC-VM2D testing)
        Heating mode: 0.5°C or 1.0°C based on hasHalfDegrees capability

        Note: hasHalfDegrees respected to avoid breaking MELCloud web UI.
        Even though API accepts 0.5°C values, MELCloud UI cannot display them
        properly when hasHalfDegrees=false (UI goes off scale).
        """
        if self.hvac_mode == HVACMode.COOL:
            return 1.0

        device = self.get_device()
        if device and device.capabilities:
            return 0.5 if device.capabilities.has_half_degrees else 1.0
        return 1.0

    @property
    def preset_mode(self) -> str | None:
        """Return current preset mode."""
        device = self.get_device()
        if device is None:
            return None

        return ATW_TO_HA_PRESET.get(self._zone_operation_mode or "", "room")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        device = self.get_device()
        if device is None:
            return {}

        return {
            "operation_status": device.operation_status,
            "forced_dhw_active": device.forced_hot_water_mode,
            "ftc_model": device.ftc_model,
        }

    # --- Shared control methods ---

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

        await self.coordinator.async_set_power_atw(self._unit_id, True)

        if hvac_mode == HVACMode.HEAT:
            current_preset = self.preset_mode or "room"
            heat_mode = HA_TO_ATW_PRESET_HEAT.get(current_preset, "HeatRoomTemperature")
            await self._async_set_zone_mode(heat_mode)

        elif hvac_mode == HVACMode.COOL:
            current_preset = self.preset_mode or "room"
            if current_preset == "curve":
                current_preset = "room"
            cool_mode = HA_TO_ATW_PRESET_COOL.get(current_preset, "CoolRoomTemperature")
            await self._async_set_zone_mode(cool_mode)

        else:
            _LOGGER.warning("Invalid HVAC mode %s for ATW", hvac_mode)

    @with_debounced_refresh()
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get("temperature")
        if temperature is None:
            return
        await self._async_set_zone_temperature(temperature)

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

        if self.hvac_mode == HVACMode.COOL:
            atw_mode = HA_TO_ATW_PRESET_COOL.get(preset_mode)
        else:
            atw_mode = HA_TO_ATW_PRESET_HEAT.get(preset_mode)

        if atw_mode is None:
            _LOGGER.warning("Unknown preset mode: %s", preset_mode)
            return

        await self._async_set_zone_mode(atw_mode)


class ATWClimateZone1(ATWClimateBase):
    """Climate entity for ATW Zone 1."""

    def __init__(
        self,
        coordinator: CoordinatorProtocol,
        unit: AirToWaterUnit,
        building: Building,
        entry: ConfigEntry,
    ) -> None:
        """Initialize Zone 1 climate entity."""
        super().__init__(coordinator, unit, building, entry, zone_number=1)

    @property
    def _zone_operation_mode(self) -> str | None:
        """Return Zone 1 operation mode."""
        device = self.get_device()
        return device.operation_mode_zone1 if device else None

    @property
    def current_temperature(self) -> float | None:
        """Return current Zone 1 room temperature."""
        device = self.get_device()
        return device.room_temperature_zone1 if device else None

    @property
    def target_temperature(self) -> float | None:
        """Return target Zone 1 temperature."""
        device = self.get_device()
        return device.set_temperature_zone1 if device else None

    async def _async_set_zone_temperature(self, temperature: float) -> None:
        """Set Zone 1 temperature."""
        await self.coordinator.async_set_temperature_zone1(self._unit_id, temperature)

    async def _async_set_zone_mode(self, mode: str) -> None:
        """Set Zone 1 operation mode."""
        await self.coordinator.async_set_mode_zone1(self._unit_id, mode)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes (Zone 1 specific).

        Note: zone_heating_available indicates that the system is currently
        heating a zone (any zone). For dual-zone systems, the API does not
        distinguish which specific zone is being heated - both zones will
        show True when operation_status is "Heating".
        """
        attrs = super().extra_state_attributes
        device = self.get_device()
        if device:
            attrs["zone_heating_available"] = device.operation_status == "Heating"
        return attrs


class ATWClimateZone2(ATWClimateBase):
    """Climate entity for ATW Zone 2.

    Only created when device capabilities report has_zone2=True.
    """

    def __init__(
        self,
        coordinator: CoordinatorProtocol,
        unit: AirToWaterUnit,
        building: Building,
        entry: ConfigEntry,
    ) -> None:
        """Initialize Zone 2 climate entity."""
        super().__init__(coordinator, unit, building, entry, zone_number=2)

    @property
    def _zone_operation_mode(self) -> str | None:
        """Return Zone 2 operation mode."""
        device = self.get_device()
        return device.operation_mode_zone2 if device else None

    @property
    def current_temperature(self) -> float | None:
        """Return current Zone 2 room temperature."""
        device = self.get_device()
        return device.room_temperature_zone2 if device else None

    @property
    def target_temperature(self) -> float | None:
        """Return target Zone 2 temperature."""
        device = self.get_device()
        return device.set_temperature_zone2 if device else None

    async def _async_set_zone_temperature(self, temperature: float) -> None:
        """Set Zone 2 temperature."""
        await self.coordinator.async_set_temperature_zone2(self._unit_id, temperature)

    async def _async_set_zone_mode(self, mode: str) -> None:
        """Set Zone 2 operation mode."""
        await self.coordinator.async_set_mode_zone2(self._unit_id, mode)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes (Zone 2 specific).

        Note: zone_heating_available indicates that the system is currently
        heating a zone (any zone). For dual-zone systems, the API does not
        distinguish which specific zone is being heated - both zones will
        show True when operation_status is "Heating".
        """
        attrs = super().extra_state_attributes
        device = self.get_device()
        if device:
            attrs["zone_heating_available"] = device.operation_status == "Heating"
        return attrs
