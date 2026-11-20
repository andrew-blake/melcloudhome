"""Helper classes for climate platform logic."""

from __future__ import annotations

from homeassistant.components.climate import HVACAction

from .api.models import AirToAirUnit


class HVACActionDeterminer:
    """Determines HVAC action from device state.

    Extracted from climate.py to reduce complexity and improve testability.
    The API reports no heating/cooling state for ATA units, so the action is
    inferred from room temperature against the setpoint.
    """

    # Automatic only: the API doesn't say which way the unit is working, so a
    # reading this close to the setpoint could be either; report idle.
    AUTO_DEADBAND = 0.5  # °C

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
        if operation_mode == "Heat":
            # The unit heats until the reading reaches the setpoint (#404)
            if current < target:
                return HVACAction.HEATING
            return HVACAction.IDLE

        if operation_mode == "Cool":
            if current > target:
                return HVACAction.COOLING
            return HVACAction.IDLE

        if operation_mode == "Automatic":
            threshold = self.AUTO_DEADBAND
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
