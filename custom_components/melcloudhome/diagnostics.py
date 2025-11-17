"""Diagnostics support for MELCloud Home."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .coordinator import MELCloudHomeCoordinator

TO_REDACT = {CONF_EMAIL, CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: MELCloudHomeCoordinator = hass.data[DOMAIN][entry.entry_id]

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
            "last_update_time": coordinator.last_update_success_time.isoformat()
            if coordinator.last_update_success_time
            else None,
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
                    "unit_count": len(building.air_to_air_units),
                    "units": [
                        {
                            "id": unit.id,
                            "name": unit.name,
                            "model": unit.model,
                            "power": unit.power,
                            "operation_mode": unit.operation_mode,
                            "set_temperature": unit.set_temperature,
                            "room_temperature": unit.room_temperature,
                            "set_fan_speed": unit.set_fan_speed,
                            "vane_vertical_direction": unit.vane_vertical_direction,
                            "vane_horizontal_direction": unit.vane_horizontal_direction,
                            "has_energy_consumed_meter": unit.has_energy_consumed_meter,
                        }
                        for unit in building.air_to_air_units
                    ],
                }
                for building in coordinator.data.buildings
            ],
        }

    return diagnostics_data
