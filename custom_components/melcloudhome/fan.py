"""Fan platform for MELCloud Home integration.

Exposes ATA fan speed, vane oscillation and unit power as a fan entity.
The climate entity's own fan_modes and swing_modes are deliberately
untouched; ADR-025 records why these controls live here instead.
"""

from __future__ import annotations

import logging
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

    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )

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

        # Named for the air conditioner: a Home app user who did not install
        # the integration should not read this as a room fan.
        self._attr_name = "A/C fan"
        self._attr_device_info = create_device_info(unit, building)

        # Slider resolution comes from this. The HomeKit bridge uses
        # 100 / speed_count as its step, giving one detent per real speed.
        speeds = unit.capabilities.number_of_fan_speeds
        self._ordered_speeds = _NUMBERED_SPEEDS[:speeds]
        self._attr_speed_count = len(self._ordered_speeds)

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

    @with_debounced_refresh()
    async def async_set_percentage(self, percentage: int) -> None:
        """Set the fan speed.

        Implemented rather than inherited: HomeKit's slider has a zero detent,
        and FanEntity.async_set_percentage routes zero to async_turn_off()
        without returning, so it would power the unit down and then also send a
        speed. Zero means unit power off here, and nothing else.
        """
        if percentage == 0:
            await self.coordinator.async_set_power(self._unit_id, False)
            return
        speed = percentage_to_ordered_list_item(self._ordered_speeds, percentage)
        await self.coordinator.async_set_fan_speed(
            self._unit_id, normalize_to_api(speed)
        )

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
        """Power the unit on, optionally at a given speed."""
        await self.coordinator.async_set_power(self._unit_id, True)
        if preset_mode is not None:
            await self.coordinator.async_set_fan_speed(
                self._unit_id, normalize_to_api(preset_mode)
            )
        elif percentage:
            speed = percentage_to_ordered_list_item(self._ordered_speeds, percentage)
            await self.coordinator.async_set_fan_speed(
                self._unit_id, normalize_to_api(speed)
            )

    @with_debounced_refresh()
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Power the unit off.

        An air conditioner has no "fan off, unit running" state, so this is the
        only thing off can mean. ADR-025 records that this is deliberate, and
        that HomeKit shows the button whether or not the feature is declared.
        """
        await self.coordinator.async_set_power(self._unit_id, False)
