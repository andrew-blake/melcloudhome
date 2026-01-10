"""Helper classes for climate platform logic."""

from __future__ import annotations

from homeassistant.components.climate import HVACAction

from .api.models import AirToAirUnit


class HVACActionDeterminer:
    """Determines HVAC action from device state.

    Extracted from climate.py to reduce complexity and improve testability.
    Uses hysteresis (±0.5°C) to avoid state flapping.
    """

    HYSTERESIS_THRESHOLD = 0.5  # °C

    def determine_action(
        self,
        device: AirToAirUnit,
    ) -> HVACAction | None:
        """Determine current HVAC action from device state.

        Args:
            device: AirToAirUnit device to determine action for

        Returns:
            HVACAction representing what the device is actually doing,
            or None if device is not available

        Note: This is polling-based with 60s updates, so may not reflect
        real-time device behavior.
        """
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
            return self._determine_action_without_temps(device.operation_mode)

        return self._determine_action_with_temps(
            device.operation_mode,
            current_temp,
            target_temp,
        )

    def _determine_action_without_temps(self, operation_mode: str) -> HVACAction:
        """Determine action when temperatures unavailable.

        Args:
            operation_mode: MELCloud operation mode string

        Returns:
            Best-guess HVACAction based only on mode
        """
        if operation_mode == "Dry":
            return HVACAction.DRYING
        if operation_mode == "Fan":
            return HVACAction.FAN
        return HVACAction.IDLE

    def _determine_action_with_temps(
        self,
        operation_mode: str,
        current: float,
        target: float,
    ) -> HVACAction:
        """Determine action based on mode and temperatures.

        Args:
            operation_mode: MELCloud operation mode string
            current: Current room temperature in °C
            target: Target temperature in °C

        Returns:
            HVACAction based on mode and temperature difference
        """
        threshold = self.HYSTERESIS_THRESHOLD

        if operation_mode == "Heat":
            # Heating mode: if current is below target (with hysteresis), we're heating
            if current < target - threshold:
                return HVACAction.HEATING
            return HVACAction.IDLE

        if operation_mode == "Cool":
            # Cooling mode: if current is above target (with hysteresis), we're cooling
            if current > target + threshold:
                return HVACAction.COOLING
            return HVACAction.IDLE

        if operation_mode == "Automatic":
            # Auto mode: infer based on which direction we need to go
            if current < target - threshold:
                return HVACAction.HEATING
            if current > target + threshold:
                return HVACAction.COOLING
            return HVACAction.IDLE

        if operation_mode == "Dry":
            return HVACAction.DRYING

        if operation_mode == "Fan":
            return HVACAction.FAN

        # Default fallback
        return HVACAction.IDLE
