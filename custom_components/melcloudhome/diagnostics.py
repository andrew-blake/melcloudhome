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
from .diagnostics_ata import serialize_ata_unit
from .diagnostics_atw import serialize_atw_unit

TO_REDACT = {CONF_EMAIL, CONF_PASSWORD}


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
                        serialize_ata_unit(unit) for unit in building.air_to_air_units
                    ],
                    "atw_units": [
                        serialize_atw_unit(unit) for unit in building.air_to_water_units
                    ],
                }
                for building in coordinator.data.buildings
            ],
        }

    return diagnostics_data
