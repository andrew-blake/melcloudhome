"""Diagnostics support for MELCloud Home."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .api.models import AirToAirUnit, AirToWaterUnit
from .const import DOMAIN
from .coordinator import MELCloudHomeCoordinator

TO_REDACT = {CONF_EMAIL, CONF_PASSWORD}


def _serialize_ata_unit(unit: AirToAirUnit) -> dict[str, Any]:
    """Serialize ATA unit for diagnostics."""
    return {
        "id": unit.id,
        "name": unit.name,
        "power": unit.power,
        "operation_mode": unit.operation_mode,
        "set_temperature": unit.set_temperature,
        "room_temperature": unit.room_temperature,
        "set_fan_speed": unit.set_fan_speed,
        "vane_vertical_direction": unit.vane_vertical_direction,
        "vane_horizontal_direction": unit.vane_horizontal_direction,
        "has_energy_consumed_meter": (
            unit.capabilities.has_energy_consumed_meter if unit.capabilities else None
        ),
    }


def _serialize_atw_unit(unit: AirToWaterUnit) -> dict[str, Any]:
    """Serialize ATW unit for diagnostics."""
    return {
        "id": unit.id,
        "name": unit.name,
        "power": unit.power,
        "in_standby_mode": unit.in_standby_mode,
        "operation_mode_zone1": unit.operation_mode_zone1,
        "set_temperature_zone1": unit.set_temperature_zone1,
        "room_temperature_zone1": unit.room_temperature_zone1,
        "operation_mode_zone2": unit.operation_mode_zone2 if unit.has_zone2 else None,
        "set_temperature_zone2": unit.set_temperature_zone2 if unit.has_zone2 else None,
        "room_temperature_zone2": unit.room_temperature_zone2
        if unit.has_zone2
        else None,
        "tank_water_temperature": unit.tank_water_temperature,
        "set_tank_water_temperature": unit.set_tank_water_temperature,
        "forced_hot_water_mode": unit.forced_hot_water_mode,
        "has_zone2": unit.has_zone2,
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: MELCloudHomeCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    # Get all entities for this config entry
    entity_reg = er.async_get(hass)
    entities = er.async_entries_for_config_entry(entity_reg, entry.entry_id)

    # Collect entity states
    entity_data = {}
    for entity in entities:
        if state := hass.states.get(entity.entity_id):
            entity_data[entity.entity_id] = {
                "state": state.state,
                "attributes": dict(state.attributes),
            }

    # Build diagnostic data
    diagnostics_data = {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(entry.data, TO_REDACT),
            "version": entry.version,
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "update_interval": coordinator.update_interval.total_seconds()
            if coordinator.update_interval
            else None,
        },
        "entities": entity_data,
    }

    # Add coordinator data if available
    if coordinator.data:
        diagnostics_data["user_context"] = {
            "buildings": [
                {
                    "id": building.id,
                    "name": building.name,
                    "ata_unit_count": len(building.air_to_air_units),
                    "atw_unit_count": len(building.air_to_water_units),
                    "ata_units": [
                        _serialize_ata_unit(unit) for unit in building.air_to_air_units
                    ],
                    "atw_units": [
                        _serialize_atw_unit(unit)
                        for unit in building.air_to_water_units
                    ],
                }
                for building in coordinator.data.buildings
            ],
        }

    return diagnostics_data
