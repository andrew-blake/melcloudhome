"""Air-to-Air (A/C) climate platform for MELCloud Home integration."""

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

from .api.const_ata import TEMP_MAX_HEAT, TEMP_MIN_COOL_DRY, TEMP_MIN_HEAT, TEMP_STEP
from .api.models import AirToAirUnit, Building
from .climate_helpers import HVACActionDeterminer
from .const_ata import (
    FAN_SPEEDS,
    HA_TO_MELCLOUD_MODE,
    MELCLOUD_TO_HA_MODE,
    VANE_HORIZONTAL_POSITIONS,
    VANE_POSITIONS,
    ATAEntityBase,
)
from .helpers import create_device_info, with_debounced_refresh
from .protocols import CoordinatorProtocol

_LOGGER = logging.getLogger(__name__)


class ATAClimate(ATAEntityBase, ClimateEntity):  # type: ignore[misc]
    """Representation of a MELCloud Home climate device."""

    _attr_has_entity_name = True  # Use device name + entity name pattern
    _attr_temperature_unit = "°C"
    _attr_target_temperature_step = TEMP_STEP
    _attr_max_temp = TEMP_MAX_HEAT

    def __init__(
        self,
        coordinator: CoordinatorProtocol,
        unit: AirToAirUnit,
        building: Building,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._unit_id = unit.id
        self._building_id = building.id
        self._attr_unique_id = unit.id
        self._entry = entry

        # Short entity name (device name provides UUID prefix)
        self._attr_name = "Climate"

        # Device info using shared helper
        self._attr_device_info = create_device_info(unit, building)

        # HVAC modes
        self._attr_hvac_modes = [
            HVACMode.OFF,
            HVACMode.HEAT,
            HVACMode.COOL,
            HVACMode.AUTO,
            HVACMode.DRY,
            HVACMode.FAN_ONLY,
        ]

        # Fan speeds
        self._attr_fan_modes = FAN_SPEEDS

        # Swing modes (vertical vane positions)
        self._attr_swing_modes = VANE_POSITIONS

        # HVAC action determiner (extracted for testability)
        self._action_determiner = HVACActionDeterminer()

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        device = self.get_device()
        if device is None or not device.power:
            return HVACMode.OFF

        return MELCLOUD_TO_HA_MODE.get(device.operation_mode, HVACMode.AUTO)

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current HVAC action (what device is actually doing).

        This is inferred from the operation mode and temperature difference.
        Uses hysteresis (±0.5°C) to avoid state flapping.

        Note: This is polling-based with 60s updates, so may not reflect
        real-time device behavior.
        """
        device = self.get_device()
        if device is None:
            return None
        return self._action_determiner.determine_action(device)

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        device = self.get_device()
        return device.room_temperature if device else None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        device = self.get_device()
        return device.set_temperature if device else None

    @property
    def fan_mode(self) -> str | None:
        """Return the current fan mode."""
        device = self.get_device()
        return device.set_fan_speed if device else None

    @property
    def swing_mode(self) -> str | None:
        """Return the current swing mode (vertical vane position)."""
        device = self.get_device()
        return device.vane_vertical_direction if device else None

    @property
    def swing_horizontal_modes(self) -> list[str]:
        """Return the list of available horizontal swing modes."""
        return VANE_HORIZONTAL_POSITIONS

    @property
    def swing_horizontal_mode(self) -> str | None:
        """Return the current horizontal swing mode (horizontal vane position)."""
        device = self.get_device()
        return device.vane_horizontal_direction if device else None

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        # Heat mode allows lower minimum than other modes
        if self.hvac_mode == HVACMode.HEAT:
            return TEMP_MIN_HEAT
        return TEMP_MIN_COOL_DRY

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return the list of supported features."""
        features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )

        device = self.get_device()
        if device is None:
            return features

        # Check capabilities from device
        if device.capabilities:
            if (
                device.capabilities.has_automatic_fan_speed
                or device.capabilities.number_of_fan_speeds > 0
            ):
                features |= ClimateEntityFeature.FAN_MODE
            if device.capabilities.has_swing or device.capabilities.has_air_direction:
                features |= ClimateEntityFeature.SWING_MODE
                features |= ClimateEntityFeature.SWING_HORIZONTAL_MODE

        return features

    @with_debounced_refresh()
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new HVAC mode."""
        if hvac_mode == HVACMode.OFF:
            # Turn off the device
            await self.coordinator.async_set_power(self._unit_id, False)
        else:
            # Turn on and set mode
            await self.coordinator.async_set_power(self._unit_id, True)
            melcloud_mode = HA_TO_MELCLOUD_MODE[hvac_mode]
            await self.coordinator.async_set_mode(self._unit_id, melcloud_mode)

    @with_debounced_refresh()
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get("temperature")
        if temperature is None:
            return

        # Set temperature
        await self.coordinator.async_set_temperature(self._unit_id, temperature)

    @with_debounced_refresh()
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new fan mode."""
        if fan_mode not in self.fan_modes:
            _LOGGER.warning("Invalid fan mode: %s", fan_mode)
            return

        await self.coordinator.async_set_fan_speed(self._unit_id, fan_mode)

    @with_debounced_refresh()
    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new swing mode (vertical vane position)."""
        if swing_mode not in self.swing_modes:
            _LOGGER.warning("Invalid swing mode: %s", swing_mode)
            return

        # Get current horizontal vane position from device, default to "Auto"
        # Handle legacy values (Left, Right, etc.) by defaulting to Auto
        device = self.get_device()
        horizontal = device.vane_horizontal_direction if device else "Auto"
        if horizontal not in self.swing_horizontal_modes:
            _LOGGER.debug(
                "Legacy horizontal position %s, defaulting to Auto", horizontal
            )
            horizontal = "Auto"

        await self.coordinator.async_set_vanes(self._unit_id, swing_mode, horizontal)

    @with_debounced_refresh()
    async def async_set_swing_horizontal_mode(self, swing_horizontal_mode: str) -> None:
        """Set new horizontal swing mode (horizontal vane position)."""
        if swing_horizontal_mode not in self.swing_horizontal_modes:
            _LOGGER.warning("Invalid horizontal swing mode: %s", swing_horizontal_mode)
            return

        # Get current vertical vane position from device, default to "Auto"
        device = self.get_device()
        vertical = device.vane_vertical_direction if device else "Auto"

        await self.coordinator.async_set_vanes(
            self._unit_id, vertical, swing_horizontal_mode
        )

    @with_debounced_refresh()
    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        await self.coordinator.async_set_power(self._unit_id, True)

    @with_debounced_refresh()
    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        await self.coordinator.async_set_power(self._unit_id, False)
