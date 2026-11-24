"""Diagnostics support for MELCloud Home."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DOMAIN
from .coordinator import MELCloudHomeCoordinator
from .diagnostics_ata import serialize_ata_unit
from .diagnostics_atw import serialize_atw_unit
from .diagnostics_shared import pseudonymize_building_id
from .helpers import short_unit_id

TO_REDACT = {CONF_EMAIL, CONF_PASSWORD, "access_token", "refresh_token", "token_expiry"}


def _entity_key(
    entity: er.RegistryEntry, device: dr.DeviceEntry | None, entry_id: str
) -> str:
    """Key an entity by its unique ID, never by its entity_id (ADR-030).

    entity_ids belong to HA and the user, so they can hold any building, unit
    or area name. The unit's UUID inside the unique ID becomes its short ID.
    The account device's identifier is the config entry's local ULID, which
    is not sensitive, so its entities keep their unique ID.
    """
    unique_id = entity.unique_id
    for domain, unit_id in device.identifiers if device else ():
        if domain == DOMAIN and unit_id != entry_id:
            unique_id = unique_id.replace(unit_id, short_unit_id(unit_id))
    return f"{entity.domain}.{unique_id}"


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: MELCloudHomeCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    # Get all entities for this config entry
    entity_reg = er.async_get(hass)
    device_reg = dr.async_get(hass)
    entities = er.async_entries_for_config_entry(entity_reg, entry.entry_id)

    # Collect entity states, keyed by unique ID (see _entity_key).
    entity_data = {}
    for entity in entities:
        if state := hass.states.get(entity.entity_id):
            attrs = dict(state.attributes)
            attrs.pop("friendly_name", None)
            device = (
                device_reg.async_get(entity.device_id) if entity.device_id else None
            )
            entity_data[_entity_key(entity, device, entry.entry_id)] = {
                "state": state.state,
                "attributes": attrs,
            }

    # Build diagnostic data
    diagnostics_data = {
        "entry": {
            "title": "***REDACTED***",
            "data": async_redact_data(entry.data, TO_REDACT),
            "version": entry.version,
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "update_interval": coordinator.update_interval.total_seconds()
            if coordinator.update_interval
            else None,
            # The account hash in the key is one-way; without this a support
            # request cannot tell which .storage energy file is this entry's
            "energy_storage_keys": {
                "ata": coordinator.energy_tracker.storage_key,
                "atw": coordinator.energy_tracker_atw.storage_key,
            },
        },
        "websocket": coordinator.ws_diagnostics(),
        "entities": entity_data,
    }

    # Add coordinator data if available
    if coordinator.data:
        diagnostics_data["user_context"] = {
            "buildings": [
                {
                    "id": pseudonymize_building_id(building.id),
                    "name": f"Building-{i + 1}",
                    "ata_unit_count": len(building.air_to_air_units),
                    "atw_unit_count": len(building.air_to_water_units),
                    "ata_units": [
                        serialize_ata_unit(unit) for unit in building.air_to_air_units
                    ],
                    "atw_units": [
                        serialize_atw_unit(unit) for unit in building.air_to_water_units
                    ],
                }
                for i, building in enumerate(coordinator.data.buildings)
            ],
        }

    return diagnostics_data
