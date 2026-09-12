"""Fan platform for MELCloud Home integration.

Exposes ATA fan speed, vane oscillation and unit power as a fan entity.
The climate entity's own fan_modes and swing_modes are deliberately
untouched; ADR-025 records why these controls live here instead.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .api.models import AirToAirUnit, Building
from .const import DOMAIN
from .const_ata import ATA_FAN_SPEEDS, ATAEntityBase, normalize_to_api
from .coordinator import MELCloudHomeCoordinator
from .helpers import create_device_info, with_debounced_refresh
from .protocols import CoordinatorProtocol

_LOGGER = logging.getLogger(__name__)

# ATA_FAN_SPEEDS[0] is "auto", which a percentage cannot express, so it is
# carried as the sole preset instead. The rest are the ordered speed list.
_AUTO_PRESET = ATA_FAN_SPEEDS[0]
_NUMBERED_SPEEDS = ATA_FAN_SPEEDS[1:]

# The vane values oscillation maps onto. "Swing" sweeps; "Auto" is a fixed
# angle chosen by operating mode, which the Mitsubishi MSZ-LN instructions and
# the MELCloud Home manual both document, so reporting Auto as not oscillating
# is true of the hardware.
_VANE_SWING = "Swing"
_VANE_AUTO = "Auto"

# HomeKit streams several set_percentage calls per slider drag (one per
# intermediate position), each preceded by a power-on write. The shared
# write-dedup in control_client_ata compares against coordinator data, which
# stays stale for the whole debounced-refresh window, so it cannot suppress
# these. with_debounced_refresh() defaults to a 2.0s delay; this guard window
# needs to be at least that long to bridge the gap until a refresh lands, plus
# headroom for scheduling and network jitter within the burst itself.
_POWER_ON_GUARD_WINDOW = 3.0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MELCloud Home fan entities."""
    _LOGGER.debug("Setting up MELCloud Home fan platform")

    coordinator: MELCloudHomeCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    entities: list[ATAFan] = []
    for building in coordinator.data.buildings:
        for unit in building.air_to_air_units:
            # A unit reporting no speeds would give speed_count == 0, and
            # FanEntity.percentage_step is 100 / speed_count, so every state
            # update would raise ZeroDivisionError. capabilities itself is
            # never None; from_dict defaults it.
            if unit.capabilities.number_of_fan_speeds < 1:
                _LOGGER.debug("Skipping fan entity for %s: no fan speeds", unit.id[-8:])
                continue
            entities.append(ATAFan(coordinator, unit, building, entry))

    _LOGGER.debug("Created %d fan entities", len(entities))
    async_add_entities(entities)


class ATAFan(ATAEntityBase, FanEntity):  # type: ignore[misc]
    """Fan entity for an ATA unit's blower and vertical vane.

    Note: type: ignore[misc] required because HA is not installed in dev
    environment (aiohttp version conflict). Mypy sees HA base classes as 'Any'.
    """

    _attr_translation_key = "melcloudhome"  # For preset mode translations

    def __init__(
        self,
        coordinator: CoordinatorProtocol,
        unit: AirToAirUnit,
        building: Building,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the fan entity."""
        super().__init__(coordinator)
        self._unit_id = unit.id
        self._building_id = building.id
        self._entry = entry
        self._attr_unique_id = f"{unit.id}_ac_fan"
        self._attr_preset_modes = [_AUTO_PRESET]

        # monotonic() deadline until which a *guarded* power-on is suppressed;
        # see _POWER_ON_GUARD_WINDOW and _async_power_on.
        self._power_on_guard_until: float | None = None

        # Named for the air conditioner: a Home app user who did not install
        # the integration should not read this as a room fan.
        self._attr_name = "A/C fan"
        self._attr_device_info = create_device_info(unit, building)

        # Slider resolution comes from this. The HomeKit bridge uses
        # 100 / speed_count as its step, giving one detent per real speed.
        speeds = unit.capabilities.number_of_fan_speeds
        self._ordered_speeds = _NUMBERED_SPEEDS[:speeds]
        self._attr_speed_count = len(self._ordered_speeds)

        # Oscillation writes vaneVerticalDirection, so only offer it where the
        # hardware has a vane. Same gate the climate entity puts on SWING_MODE.
        features = (
            FanEntityFeature.SET_SPEED
            | FanEntityFeature.TURN_ON
            | FanEntityFeature.TURN_OFF
        )
        if unit.capabilities.has_swing or unit.capabilities.has_air_direction:
            features |= FanEntityFeature.OSCILLATE
        self._attr_supported_features = features

    @property
    def is_on(self) -> bool | None:
        """Return true if the unit is powered on."""
        device = self.get_device()
        if device is None:
            return None
        return device.power

    @property
    def percentage(self) -> int | None:
        """Return the commanded speed as a percentage.

        None while the unit is in auto, because no numbered speed is
        commanded then; the auto preset carries that state instead.
        """
        device = self.get_device()
        if device is None or device.set_fan_speed is None:
            return None
        speed = device.set_fan_speed.lower()
        if speed not in self._ordered_speeds:
            return None
        return ordered_list_item_to_percentage(  # type: ignore[no-any-return]
            self._ordered_speeds, speed
        )

    @property
    def preset_mode(self) -> str | None:
        """Return "auto" while the unit picks its own speed."""
        device = self.get_device()
        if device is None or device.set_fan_speed is None:
            return None
        if device.set_fan_speed.lower() == _AUTO_PRESET:
            return _AUTO_PRESET
        return None

    @property
    def oscillating(self) -> bool | None:
        """Return true while the vane is sweeping."""
        device = self.get_device()
        if device is None or device.vane_vertical_direction is None:
            return None
        return device.vane_vertical_direction == _VANE_SWING

    @with_debounced_refresh()
    async def async_oscillate(self, oscillating: bool) -> None:
        """Start or stop the vane sweeping."""
        await self.coordinator.async_set_vane_vertical(
            self._unit_id, _VANE_SWING if oscillating else _VANE_AUTO
        )

    async def _async_power_on(self, *, guard: bool = False) -> None:
        """Power the unit on without disturbing its operation mode.

        A bare power write sends operationMode=null, which can trigger a
        mode-conflict fault on multi-zone outdoor units. The mode is only
        omitted when the device reports none to preserve.

        guard=True suppresses the write entirely while a previous guarded (or
        unguarded) power-on is still within _POWER_ON_GUARD_WINDOW, to collapse
        the repeated power-on writes a HomeKit slider drag issues. It is opt-in
        per call site rather than a blanket check inside this method, so
        fan.turn_on -- called with guard left False -- always powers on: the
        guard exists to tame set_percentage's drag burst, not to make the
        documented service unreliable.
        """
        if (
            guard
            and self._power_on_guard_until is not None
            and time.monotonic() < self._power_on_guard_until
        ):
            return

        device = self.get_device()
        if device and device.operation_mode:
            await self.coordinator.async_set_power_and_mode(
                self._unit_id, True, device.operation_mode
            )
        else:
            await self.coordinator.async_set_power(self._unit_id, True)
        self._power_on_guard_until = time.monotonic() + _POWER_ON_GUARD_WINDOW

    async def _async_apply_percentage(
        self, percentage: int, *, guard: bool = False
    ) -> None:
        """Apply a slider position: zero powers off, anything else sets a speed.

        The unit is powered on as well as sped up, because the HomeKit bridge
        sends Active=1 and RotationSpeed in one write when the slider is dragged
        up on an off tile, and then deliberately skips fan.turn_on on the
        assumption that a SET_SPEED fan powers itself on. The control client
        skips a write the device already satisfies, so on an already-running
        unit this costs no extra API call. guard is forwarded to
        _async_power_on; see that method and async_set_percentage.
        """
        if percentage == 0:
            await self.coordinator.async_set_power(self._unit_id, False)
            return
        await self._async_power_on(guard=guard)
        speed = percentage_to_ordered_list_item(self._ordered_speeds, percentage)
        await self.coordinator.async_set_fan_speed(
            self._unit_id, normalize_to_api(speed)
        )

    @with_debounced_refresh()
    async def async_set_percentage(self, percentage: int) -> None:
        """Set the fan speed.

        Implemented rather than inherited: HomeKit's slider has a zero detent,
        and FanEntity.async_set_percentage routes zero to async_turn_off()
        without returning, so it would power the unit down and then also send a
        speed. Zero means unit power off here, and nothing else.

        guard=True here (and only here): a slider drag calls this repeatedly in
        quick succession, each preceded by a power-on, and the shared write-
        dedup can't catch the repeats because it reads coordinator data that
        stays stale for the whole debounced-refresh window. fan.turn_on does
        not set guard, so it always powers on regardless of a recent drag.
        """
        await self._async_apply_percentage(percentage, guard=True)

    @with_debounced_refresh()
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Hand speed selection back to the unit."""
        await self.coordinator.async_set_fan_speed(
            self._unit_id, normalize_to_api(preset_mode)
        )

    @with_debounced_refresh()
    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Power the unit on, optionally at a given speed or preset.

        percentage=0 is permitted by the service schema and means the same here
        as it does to fan.set_percentage: power off.
        """
        if preset_mode is not None:
            await self._async_power_on()
            await self.coordinator.async_set_fan_speed(
                self._unit_id, normalize_to_api(preset_mode)
            )
        elif percentage is not None:
            await self._async_apply_percentage(percentage)
        else:
            await self._async_power_on()

    @with_debounced_refresh()
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Power the unit off.

        An air conditioner has no "fan off, unit running" state, so this is the
        only thing off can mean. ADR-025 records that this is deliberate, and
        that HomeKit shows the button whether or not the feature is declared.
        """
        await self.coordinator.async_set_power(self._unit_id, False)
