"""Diagnostics support for MELCloud Home."""

from __future__ import annotations

import hashlib
import re
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

TO_REDACT = {CONF_EMAIL, CONF_PASSWORD, "access_token", "refresh_token", "token_expiry"}

_ENTITY_ID_PREFIX = re.compile(r"^(.+)_(?=melcloudhome_)")


def _redact_entity_id(
    entity_id: str, device_id: str | None, area_id: str | None
) -> str:
    """Redact any real-name prefix before the never-name-derived "melcloudhome_"
    marker, regardless of what put it there. Hashes area_id over device_id when
    available so sibling devices share a placeholder; hashes an id rather than
    the name itself since a real name is guessable via dictionary attack."""
    domain, _, object_id = entity_id.partition(".")
    match = _ENTITY_ID_PREFIX.match(object_id)
    if not match or device_id is None:
        return entity_id
    hash_source = area_id or device_id
    placeholder = (
        f"redacted_device_{hashlib.sha256(hash_source.encode()).hexdigest()[:8]}"
    )
    return f"{domain}.{placeholder}_{object_id[match.end() :]}"


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

    # Collect entity states, redacting any real-name prefix out of the
    # entity_id key itself (see _redact_entity_id).
    entity_data = {}
    for entity in entities:
        if state := hass.states.get(entity.entity_id):
            attrs = dict(state.attributes)
            attrs.pop("friendly_name", None)
            device = (
                device_reg.async_get(entity.device_id) if entity.device_id else None
            )
            area_id = entity.area_id or (device.area_id if device else None)
            redacted_id = _redact_entity_id(entity.entity_id, entity.device_id, area_id)
            entity_data[redacted_id] = {
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
        },
        "websocket": coordinator.ws_diagnostics(),
        "entities": entity_data,
    }

    # Add coordinator data if available
    if coordinator.data:
        diagnostics_data["user_context"] = {
            "buildings": [
                {
                    "id": building.id,
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
