"""Diagnostics support for MELCloud Home."""

from __future__ import annotations

import hashlib
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.util import slugify

from .const import DOMAIN
from .coordinator import MELCloudHomeCoordinator
from .diagnostics_ata import serialize_ata_unit
from .diagnostics_atw import serialize_atw_unit

TO_REDACT = {CONF_EMAIL, CONF_PASSWORD, "access_token", "refresh_token", "token_expiry"}


def _real_name_slugs(
    entity: er.RegistryEntry,
    device: dr.DeviceEntry | None,
    area_reg: ar.AreaRegistry,
) -> dict[str, str]:
    """Map each real-name slug that could leak into this entity_id to the
    stable registry id to hash for its placeholder - the area's id when the
    match is area-sourced (shared by every device in that area, so sibling
    devices redact to the same placeholder), the device's id otherwise.

    Never matches against `device.name` - that's always the harmless
    `melcloudhome_xxxx_yyyy` short id, not a real name (see docs/entities.md).
    """
    slugs: dict[str, str] = {}
    if device is not None and device.name_by_user:
        slug = slugify(device.name_by_user)
        if slug:
            slugs[slug] = device.id

    area_id = entity.area_id or (device.area_id if device else None)
    if area_id and (area := area_reg.async_get_area(area_id)) and area.name:
        slug = slugify(area.name)
        if slug:
            slugs[slug] = area.id

    return slugs


def _redact_entity_id(entity_id: str, real_name_slugs: dict[str, str]) -> str:
    """Strip any real-name-derived slug out of an entity_id, if present.

    Real running installs never hit this in the device-name-by-user case -
    `_clear_friendly_device_names` (see __init__.py) clears it before setup -
    but entity_id is set once and never recomputed, so a legacy or
    manually-recreated entity_id (HA's "Recreate entity IDs" action, see
    ADR-013) can still have a real name baked in permanently. The area-name
    case has no equivalent mitigation and can leak on every normal setup.
    """
    domain, _, object_id = entity_id.partition(".")
    for slug, hash_source_id in real_name_slugs.items():
        placeholder = (
            f"redacted_device_{hashlib.sha256(hash_source_id.encode()).hexdigest()[:8]}"
        )
        if object_id == slug:
            return f"{domain}.{placeholder}"
        if object_id.startswith(f"{slug}_"):
            return f"{domain}.{placeholder}{object_id[len(slug) :]}"
    return entity_id


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
    area_reg = ar.async_get(hass)
    entities = er.async_entries_for_config_entry(entity_reg, entry.entry_id)

    # Collect entity states, redacting any real-name-derived segment out of
    # the entity_id key itself (see _redact_entity_id / _real_name_slugs).
    entity_data = {}
    for entity in entities:
        if state := hass.states.get(entity.entity_id):
            attrs = dict(state.attributes)
            attrs.pop("friendly_name", None)
            device = (
                device_reg.async_get(entity.device_id) if entity.device_id else None
            )
            slugs = _real_name_slugs(entity, device, area_reg)
            entity_data[_redact_entity_id(entity.entity_id, slugs)] = {
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
