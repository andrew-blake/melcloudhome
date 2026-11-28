# ADR-030: Follow Home Assistant's Naming Model

**Status:** Accepted
**Date:** 2026-11-24
**Supersedes:** [ADR-003](003-entity-naming-strategy.md) (device name "{building} {unit}", building as suggested area), [ADR-010](010-entity-id-prefix-change.md) (the `melcloudhome_` entity ID prefix), [ADR-013](013-automatic-friendly-device-names.md) (friendly names written into `name_by_user`)
**Amends:** [ADR-009](009-reconfigure-password-only.md) (its entity ID note)
**Relates to:** [ADR-025](025-homekit-fan-entity.md) (the fan's name "A/C fan", now translated with its meaning kept), [ADR-012](012-atw-entity-architecture.md) (its entity table), [ADR-024](024-entry-scoped-energy-storage.md) (the storage key in diagnostics)
**Decision Makers:** @andrew-blake

## Context

ADR-003 named each device "{building} {unit}" and suggested the building as its area. The first release, v1.0.0, then built entity IDs from the unit's UUID (`climate.melcloud_0efc_76db`), "for stability across building/room renames in MELCloud Home". It named each entity after the short ID and let Home Assistant derive the ID; it never set `entity_id`. ADR-010 changed the prefix to `melcloudhome_`. v2.0.0 named the device with the short ID (`melcloudhome_a1b2_9abc`) and let Home Assistant build IDs from it.

To show a friendly name on top of that, the integration wrote "{building} {unit}" into the device's user-rename field (`name_by_user`, ADR-013). Home Assistant builds new IDs from that field too, so every startup erased it before the entities loaded and wrote it back afterwards (#38, #53). No ADR recorded this.

Home Assistant changes broke the arrangement (#403):

- **2026.6** puts the device's area in front of new entity IDs. The integration suggested the building as the area, so fresh installs got `climate.my_home_melcloudhome_a1b2_9abc_climate`.
- **2026.8** lets users choose which parts make up new entity IDs. The post-setup dialog rebuilds a device's IDs when the user renames the device or changes its area.
- **2026.11** puts the device name in front of every entity name. Its registry upgrade saves a renamed entity's old label (`compat_name`), but any write to a device's `name_by_user` or `name` clears that saved label on every entity of the device. The per-startup erase and restore is such a write. Measured on a real upgrade from 2026.10.4: an entity renamed "Lounge AC" showed "My Home Living Room AC Lounge AC" after the first 2026.11 boot. Re-entering the name doesn't bring it back.

Diagnostics redaction found entity IDs by the `melcloudhome_` text. IDs the dialog rebuilt don't contain it, so they reached the diagnostics output with the building and the user's device name in them (measured). The output also carried every unit's and building's full MELCloud ID.

Home Assistant's developer guidance says who owns what:

- "In most cases, integrations should not set entity_id at all", and "Home Assistant will generate it automatically." ([Entity IDs with mismatched domains are deprecated](https://contributors.home-assistant.io/blog/2026/04/07/entity-id-mismatched-domain-deprecated))
- "Users can choose which parts Home Assistant uses for new entity IDs. Because of that, never rely on a specific entity ID in your integration: look entities up by their unique ID in the entity registry." ([Entity naming](https://contributors.home-assistant.io/core/entities/naming/))
- "The main feature of a device gets the name None, so it takes the name of the device itself." ([has-entity-name rule](https://contributors.home-assistant.io/core/quality-scale/has-entity-name/))
- "Don't hard code an English name. Set a translation_key instead." ([Entity naming](https://contributors.home-assistant.io/core/entities/naming/))
- In the device registry, `name` is "The name of the device" and `name_by_user` is "The name the user gave it". For `serial_number`: "Unlike a serial number in identifiers, it does not have to be unique." ([Device registry](https://contributors.home-assistant.io/core/integrations/device-registry/))

Home Assistant now provides the stability v1.0.0 wanted: a registered entity keeps its ID, whatever the device or building is called later.

## Decision

**Home Assistant and the user own entity IDs and names. The integration supplies names, identity and translations.**

- **No entity sets its own `entity_id`.** The integration doesn't promise an ID format. Its code and tools find entities by unique ID or through the device registry.
- **The integration never writes `name_by_user`, and stops erasing it on startup.**
- **A new device is named after its unit, once, before its entities exist.** Before platform setup, the integration creates the device of each unit that has none yet, and passes the unit's name. Platform setup passes no name, so Home Assistant never changes a device's name afterwards. Existing devices keep their name, label and area. The name carries no building: the integration often sees units through guest shares, so it can't reliably tell when a building is needed to tell two units apart.
- **The main feature of an air conditioner, its climate entity, takes the device's name.** A heat pump has no single main feature (one climate per zone, plus the tank), so its entities keep their names.
- **Entity names come from translation keys.** The fan, system power switch, tank and zone names were hard-coded English and are now translated. Translations keep each name's meaning: in every language the fan's name says it belongs to the air conditioner (ADR-025).
- **Every device carries `serial_number` = `melcloudhome_{first4}_{last4}`.** It's not a hardware serial number. It's the short form of the unit's MELCloud ID, the same string older installs show in their entity IDs, so users can tell units apart and match a device to old automations. Adding it to existing devices is one registry update per device, on the first startup after the upgrade, and leaves saved labels intact (measured).
- **New devices get no suggested area.** A building isn't a room. Existing devices keep their area.
- **Diagnostics carry no names and no full IDs.** Entities are keyed by domain and unique ID, with the unit ID inside it replaced by the unit's short ID. Unit IDs appear as the short ID; building IDs as a one-way hash that keeps the same value across dumps. One account identifier stays for now: the energy storage key (ADR-024) ends in a hash of the account email, which support uses to find the storage file. Replacing it is tracked separately.

## Consequences

- **The lost-label bug is fixed.** Saved old labels survive the first 2026.11 boot and every boot after it.
- **Existing entity IDs don't change.** Measured for every entity class whose name changes, on the oldest and newest supported Home Assistant.
- **Fresh installs get Home Assistant's format,** for example `climate.living_room_ac` and `water_heater.heat_pump_tank`. Translated names appear in the install's language, and any area the user assigns joins the ID.
- **Two units with the same name in different buildings** get identical labels and a `_2` ID. The user renames one.
- **On existing installs, a climate entity of an air conditioner that the user hasn't renamed loses " Climate" from its label.** Voice assistants and dashboards that show the default name follow, and so may the HomeKit accessory after a restart. IDs and automations don't change. If the user set an area on that entity itself, Home Assistant 2026.11 raises a repair, because an entity without a name of its own can't have its own area: moving the area to the device or naming the entity clears it.
- **Entities that appear later on existing installs get Home Assistant's format too.** On Home Assistant 2026.6 or later, on any install that kept the suggested building area, that repeats the building: `sensor.my_home_my_home_living_room_ac_energy`, from the area plus the label earlier versions wrote. Earlier code gave such entities `sensor.my_home_melcloudhome_a1b2_9abc_energy`, which isn't the documented format either. Before 2026.6 earlier code gave the documented `sensor.melcloudhome_a1b2_9abc_energy`, and now the entity is named from the device label: `sensor.my_home_living_room_ac_energy`. Users can change either by editing the entity ID in the entity's settings.
- **Units added after the upgrade are named after the unit and get no area,** next to older devices labelled "{building} {unit}".
- **Re-adding the integration renames its devices to the unit name.** Home Assistant forgets a removed device's name but restores its label, area and entity IDs. Saved old labels don't survive a re-add in any case.
- **A label the user resets shows the device's own name.** That's the unit name on new devices and `melcloudhome_a1b2_9abc` on existing ones. Renaming existing devices would clear their entities' saved labels, so they keep that name.
- **Users whose saved labels were already cleared can't get them back.**
- **Two config entries that see the same unit are unsupported.** That happens when an owner account and a guest account are both added. Their entities' unique IDs already clash, so the second entry fails to set them up. On Home Assistant before 2026.11, device lookup isn't scoped to a config entry, so the second entry's first setup also renames the first entry's device to the unit name. From 2026.11 each entry has its own device.
- **Diagnostics can't be matched to MELCloud by full ID any more.** Units appear under their short ID, the serial number on the device page, so a dump still matches a user's devices and older entity IDs. Buildings appear under a one-way pseudonym.
- **The documentation stops promising an ID format.** It points users to the device page and the serial number.

## Departures from Home Assistant's guidance

- **`DeviceInfo` carries no name; the integration sets it once, when it creates the device.** The device docs and the Gold `devices` rule put the name in `DeviceInfo`, and the docs reserve registering a device directly for devices without entities. There it updates the registry whenever it differs, and on 2026.11 that clears saved labels on existing devices. Setting the name once protects them. As a side effect, renaming a unit in the MELCloud app doesn't reach Home Assistant.
- **`serial_number` holds the short unit ID.** It isn't a hardware serial number. Home Assistant allows a non-unique value, and no rule covers a non-serial one.
- **What would revisit it:** Home Assistant offering a supported way to name a device once, or changing how it treats a `DeviceInfo` without a name; a hardware serial number appearing in the MELCloud API; or the oldest supported Home Assistant reaching 2026.9, whose child devices fit heat pump zones better.
