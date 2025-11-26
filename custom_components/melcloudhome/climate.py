"""Climate platform for MELCloud Home integration."""

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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api.const import TEMP_MAX_HEAT, TEMP_MIN_COOL_DRY, TEMP_MIN_HEAT, TEMP_STEP
from .api.models import AirToAirUnit, Building
from .const import (
    DOMAIN,
    FAN_SPEEDS,
    HA_TO_MELCLOUD_MODE,
    MELCLOUD_TO_HA_MODE,
    VANE_HORIZONTAL_POSITIONS,
    VANE_POSITIONS,
)
from .coordinator import MELCloudHomeCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MELCloud Home climate entities."""
    coordinator: MELCloudHomeCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    entities = []
    for building in coordinator.data.buildings:
        for unit in building.air_to_air_units:
            entities.append(MELCloudHomeClimate(coordinator, unit, building, entry))

    async_add_entities(entities)


class MELCloudHomeClimate(CoordinatorEntity[MELCloudHomeCoordinator], ClimateEntity):
    """Representation of a MELCloud Home climate device."""

    _attr_has_entity_name = False  # Use explicit naming for stable entity IDs
    _attr_temperature_unit = "°C"
    _attr_target_temperature_step = TEMP_STEP
    _attr_max_temp = TEMP_MAX_HEAT

    def __init__(
        self,
        coordinator: MELCloudHomeCoordinator,
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

        # Generate stable entity ID from unit ID (format: melcloudhome_0efc_76db)
        # Using first 4 and last 4 chars of UUID for stability + traceability
        unit_id_clean = unit.id.replace("-", "")  # Remove dashes from UUID

        # Set entity name (HA will normalize this to entity_id)
        # Format: "MELCloudHome 0efc 76db" -> entity_id: "climate.melcloudhome_0efc_76db"
        self._attr_name = f"MELCloudHome {unit_id_clean[:4]} {unit_id_clean[-4:]}"

        # Device info (modern HA pattern)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unit.id)},
            name=f"{building.name} {unit.name}",
            manufacturer="Mitsubishi Electric",
            model="Air-to-Air Heat Pump (via MELCloud Home)",
            suggested_area=building.name,
        )

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

    @property
    def _device(self) -> AirToAirUnit | None:
        """Get the current device from coordinator data - O(1) cached lookup."""
        return self.coordinator.get_unit(self._unit_id)  # type: ignore[no-any-return]

    @property
    def _building(self) -> Building | None:
        """Get the current building from coordinator data - O(1) cached lookup."""
        return self.coordinator.get_building_for_unit(self._unit_id)  # type: ignore[no-any-return]

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
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        device = self._device
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
        device = self._device
        if device is None:
            return None

        # If powered off, return OFF
        if not device.power:
            return HVACAction.OFF

        # Get current and target temperatures
        current_temp = device.room_temperature
        target_temp = device.set_temperature

        # If we don't have temperature data, can't infer action reliably
        if current_temp is None or target_temp is None:
            # Return best guess based on mode
            if device.operation_mode == "Dry":
                return HVACAction.DRYING
            if device.operation_mode == "Fan":
                return HVACAction.FAN
            return HVACAction.IDLE

        # Hysteresis threshold to avoid flapping
        threshold = 0.5

        # Determine action based on mode and temperature difference
        if device.operation_mode == "Heat":
            # Heating mode: if current is below target (with hysteresis), we're heating
            if current_temp < target_temp - threshold:
                return HVACAction.HEATING
            return HVACAction.IDLE

        if device.operation_mode == "Cool":
            # Cooling mode: if current is above target (with hysteresis), we're cooling
            if current_temp > target_temp + threshold:
                return HVACAction.COOLING
            return HVACAction.IDLE

        if device.operation_mode == "Automatic":
            # Auto mode: infer based on which direction we need to go
            if current_temp < target_temp - threshold:
                return HVACAction.HEATING
            if current_temp > target_temp + threshold:
                return HVACAction.COOLING
            return HVACAction.IDLE

        if device.operation_mode == "Dry":
            return HVACAction.DRYING

        if device.operation_mode == "Fan":
            return HVACAction.FAN

        # Default fallback
        return HVACAction.IDLE

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        device = self._device
        return device.room_temperature if device else None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        device = self._device
        return device.set_temperature if device else None

    @property
    def fan_mode(self) -> str | None:
        """Return the current fan mode."""
        device = self._device
        return device.set_fan_speed if device else None

    @property
    def swing_mode(self) -> str | None:
        """Return the current swing mode (vertical vane position)."""
        device = self._device
        return device.vane_vertical_direction if device else None

    @property
    def swing_horizontal_modes(self) -> list[str]:
        """Return the list of available horizontal swing modes."""
        return VANE_HORIZONTAL_POSITIONS

    @property
    def swing_horizontal_mode(self) -> str | None:
        """Return the current horizontal swing mode (horizontal vane position)."""
        device = self._device
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

        device = self._device
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

        # Request debounced refresh to avoid race conditions
        await self.coordinator.async_request_refresh_debounced()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get("temperature")
        if temperature is None:
            return

        # Validate temperature range
        if temperature < self.min_temp or temperature > self.max_temp:
            _LOGGER.warning(
                "Temperature %.1f is out of range (%.1f-%.1f)",
                temperature,
                self.min_temp,
                self.max_temp,
            )
            return

        # Set temperature
        await self.coordinator.async_set_temperature(self._unit_id, temperature)

        # Request debounced refresh to avoid race conditions
        await self.coordinator.async_request_refresh_debounced()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new fan mode."""
        if fan_mode not in self.fan_modes:
            _LOGGER.warning("Invalid fan mode: %s", fan_mode)
            return

        await self.coordinator.async_set_fan_speed(self._unit_id, fan_mode)

        # Request debounced refresh to avoid race conditions
        await self.coordinator.async_request_refresh_debounced()

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new swing mode (vertical vane position)."""
        if swing_mode not in self.swing_modes:
            _LOGGER.warning("Invalid swing mode: %s", swing_mode)
            return

        # Get current horizontal vane position from device, default to "Auto"
        # Handle legacy values (Left, Right, etc.) by defaulting to Auto
        device = self._device
        horizontal = device.vane_horizontal_direction if device else "Auto"
        if horizontal not in self.swing_horizontal_modes:
            _LOGGER.debug(
                "Legacy horizontal position %s, defaulting to Auto", horizontal
            )
            horizontal = "Auto"

        await self.coordinator.async_set_vanes(self._unit_id, swing_mode, horizontal)

        # Request debounced refresh to avoid race conditions
        await self.coordinator.async_request_refresh_debounced()

    async def async_set_swing_horizontal_mode(self, swing_horizontal_mode: str) -> None:
        """Set new horizontal swing mode (horizontal vane position)."""
        if swing_horizontal_mode not in self.swing_horizontal_modes:
            _LOGGER.warning("Invalid horizontal swing mode: %s", swing_horizontal_mode)
            return

        # Get current vertical vane position from device, default to "Auto"
        device = self._device
        vertical = device.vane_vertical_direction if device else "Auto"

        await self.coordinator.async_set_vanes(
            self._unit_id, vertical, swing_horizontal_mode
        )

        # Request debounced refresh to avoid race conditions
        await self.coordinator.async_request_refresh_debounced()

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        await self.coordinator.async_set_power(self._unit_id, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        await self.coordinator.async_set_power(self._unit_id, False)
        await self.coordinator.async_request_refresh()
