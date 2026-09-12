"""Fan platform for MELCloud Home integration.

Exposes ATA fan speed, vane oscillation and unit power as a fan entity.
The climate entity's own fan_modes and swing_modes are deliberately
untouched; ADR-025 records why these controls live here instead.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later
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
# these. with_debounced_refresh() defaults to a 2.0s delay, and that timer is
# shared with the control client and restarted by every WebSocket delta, so the
# stale window has no fixed upper bound -- during a busy drag it can outlast
# this guard. Three seconds covers the ordinary case (one refresh delay plus the
# deferred speed write, with headroom for scheduling and network jitter) without
# claiming to cover every case: when it is outlasted, the only consequence is
# one redundant power-on write, which the API accepts on a running unit.
_POWER_ON_GUARD_WINDOW = 3.0

# How long a slider position must stand still before it is written. Overlapping
# speed writes are applied by the server in arrival order, not issue order, so a
# burst can land on an earlier value than the one the user released on (#318):
# a drag ending on Three wrote Two, Three, Three, Three and settled on Two.
# Sending only the final position makes that race impossible. The writes in that
# production log were ~260ms apart, so the window has to be comfortably wider
# than that or the timer fires mid-drag and the burst is back; 0.5s is roughly
# double the measured gap and still reads as immediate at the tile.
_SPEED_DEBOUNCE_WINDOW = 0.5


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

        # Pending debounced speed write; see _SPEED_DEBOUNCE_WINDOW.
        self._cancel_speed_write: CALLBACK_TYPE | None = None
        self._pending_percentage: int | None = None

        # Named for the air conditioner: a Home app user who did not install
        # the integration should not read this as a room fan.
        self._attr_name = "A/C fan"
        self._attr_device_info = create_device_info(unit, building)

        # Slider resolution comes from this. The HomeKit bridge uses
        # 100 / speed_count as its step, giving one detent per real speed.
        speeds = unit.capabilities.number_of_fan_speeds
        self._ordered_speeds = _NUMBERED_SPEEDS[:speeds]
        self._attr_speed_count = len(self._ordered_speeds)

        # Percentage of the last numbered speed seen, so that while the unit
        # is in auto, percentage (below) can report it instead of None. See
        # _handle_coordinator_update and percentage. Seeded from the unit this
        # entity was constructed with -- itself the coordinator's first fetch,
        # not a write of ours -- so a unit that starts on a numbered speed and
        # is switched straight to auto on the very next update still has
        # something to resume. Stays None if the unit starts in auto: nothing
        # has been seen yet, so percentage keeps returning None (ADR-025).
        self._last_numbered_percentage: int | None = None
        initial_speed = (unit.set_fan_speed or "").lower()
        if initial_speed in self._ordered_speeds:
            self._last_numbered_percentage = ordered_list_item_to_percentage(
                self._ordered_speeds, initial_speed
            )

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

        While the unit is in auto, no numbered speed is commanded -- the auto
        preset carries that state instead -- so this reports the percentage of
        the last numbered speed seen (see _handle_coordinator_update), letting
        HomeKit's Manual/Auto toggle resume the speed the user was actually on
        instead of falling back to its own hard-coded 50%. None only if no
        numbered speed has ever been seen.
        """
        device = self.get_device()
        if device is None or device.set_fan_speed is None:
            return None
        speed = device.set_fan_speed.lower()
        if speed == _AUTO_PRESET:
            return self._last_numbered_percentage
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

    def _handle_coordinator_update(self) -> None:
        """Remember the last numbered speed seen, then update entity state.

        The commanded speed can change from the climate entity's fan_mode
        dropdown, the vendor's own app, or a service call -- none of which are
        calls into this entity, so they all arrive here rather than through a
        write this class made itself. ATAEntityBase (CoordinatorEntity) does
        not override this hook, so this is the only place that sees every one
        of those paths; super() below reaches CoordinatorEntity's default
        implementation directly and still writes the state.
        """
        device = self.get_device()
        if device is not None and device.set_fan_speed is not None:
            speed = device.set_fan_speed.lower()
            if speed in self._ordered_speeds:
                self._last_numbered_percentage = ordered_list_item_to_percentage(
                    self._ordered_speeds, speed
                )
        super()._handle_coordinator_update()

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

        The deadline is armed before the write is awaited, not after. HomeKit's
        bridge dispatches each service call as its own un-awaited task and HA
        takes no per-entity lock, so calls genuinely interleave at the await
        below; arming afterwards lets every call that arrives while the first
        power-on is in flight past the check and issue its own. Arming first
        would, on its own, make a *failed* power-on suppress the retry that
        follows it, so the deadline is put back if the write raises.
        """
        if (
            guard
            and self._power_on_guard_until is not None
            and time.monotonic() < self._power_on_guard_until
        ):
            return

        device = self.get_device()
        self._power_on_guard_until = time.monotonic() + _POWER_ON_GUARD_WINDOW
        try:
            if device and device.operation_mode:
                await self.coordinator.async_set_power_and_mode(
                    self._unit_id, True, device.operation_mode
                )
            else:
                await self.coordinator.async_set_power(self._unit_id, True)
        except Exception:
            self._power_on_guard_until = None
            raise

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
            # Dragging to the zero detent is an explicit power-off, which
            # invalidates the guard's premise; see async_turn_off.
            self._power_on_guard_until = None
            await self.coordinator.async_set_power(self._unit_id, False)
            return
        await self._async_power_on(guard=guard)
        speed = percentage_to_ordered_list_item(self._ordered_speeds, percentage)
        await self.coordinator.async_set_fan_speed(
            self._unit_id, normalize_to_api(speed)
        )

    def _cancel_pending_speed_write(self) -> None:
        """Drop any speed write still waiting on the debounce timer."""
        if self._cancel_speed_write is not None:
            self._cancel_speed_write()
            self._cancel_speed_write = None

    async def _async_write_pending_percentage(self, _now: datetime) -> None:
        """Write the slider position the user actually settled on.

        The refresh is requested here rather than by @with_debounced_refresh on
        async_set_percentage, because that decorator starts its own (separately
        debounced) timer when the *service call* returns, which is before this
        write has even been issued. Requesting it after the write keeps the poll
        downstream of the thing it is meant to observe.

        The refresh runs even when the write raises: this is a timer callback,
        so there is no service call left to report the failure to, and without a
        refresh the tile would keep showing the speed that was never written
        until the next poll. The exception still propagates and is logged by the
        job that runs this callback.
        """
        self._cancel_speed_write = None
        percentage = self._pending_percentage
        if percentage is None:
            return
        self._pending_percentage = None
        try:
            await self._async_apply_percentage(percentage, guard=True)
        finally:
            await self.coordinator.async_request_refresh_debounced()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the fan speed.

        Implemented rather than inherited: HomeKit's slider has a zero detent,
        and FanEntity.async_set_percentage routes zero to async_turn_off()
        without returning, so it would power the unit down and then also send a
        speed. Zero means unit power off here, and nothing else.

        Only the speed write is debounced; the power-on stays immediate so the
        unit starts the moment a drag begins rather than half a second later.
        Deferring zero along with the rest is deliberate: dragging *through* the
        zero detent on the way up no longer powers the unit off en route.

        guard=True here (and only here): a slider drag calls this repeatedly in
        quick succession, each preceded by a power-on, and the shared write-
        dedup can't catch the repeats because it reads coordinator data that
        stays stale for the whole debounced-refresh window. fan.turn_on does
        not set guard, so it always powers on regardless of a recent drag.

        The pending value and its timer are taken before the power-on is
        awaited. HomeKit's bridge dispatches each call as its own un-awaited
        task and HA takes no per-entity lock, so a call that suspends on the
        power-on request resumes after a newer one has already run: writing the
        pending value afterwards would let the older slider position overwrite
        the newer one and win the timer, which is exactly the #318 symptom.
        Claiming it first means the last call to *enter* this method owns the
        write, whatever order the awaits finish in.
        """
        self._pending_percentage = percentage
        self._cancel_pending_speed_write()
        self._cancel_speed_write = async_call_later(
            self.hass, _SPEED_DEBOUNCE_WINDOW, self._async_write_pending_percentage
        )
        if percentage > 0:
            await self._async_power_on(guard=True)

    async def async_will_remove_from_hass(self) -> None:
        """Cancel a pending speed write so nothing fires after removal."""
        self._cancel_pending_speed_write()
        await super().async_will_remove_from_hass()

    @with_debounced_refresh()
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Hand speed selection back to the unit."""
        self._cancel_pending_speed_write()
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

        Applied immediately, not debounced: an explicit service call is a
        deliberate single command, not a drag. Same reasoning that has turn_on
        bypass the power-on guard. It does supersede a pending drag write, which
        would otherwise land afterwards and undo it.
        """
        self._cancel_pending_speed_write()
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

        The power-on guard is dropped here. It is armed whenever a guarded
        power-on runs, including when the shared write-dedup skipped the API
        call because the unit was already on -- so a slider drag on a running
        unit leaves it armed for three seconds without any power write having
        happened. Turning the unit off inside that window and dragging the
        slider straight back up would then hit set_percentage alone (the bridge
        sends Active and RotationSpeed together and skips fan.turn_on), the
        guard would suppress the power-on, and the unit would stay off with a
        speed write landing on it. An explicit power-off invalidates the
        premise the guard rests on, so it stops applying.
        """
        self._cancel_pending_speed_write()
        self._power_on_guard_until = None
        await self.coordinator.async_set_power(self._unit_id, False)
