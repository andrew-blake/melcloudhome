# ADR-024: Energy Storage Is Scoped Per Account

**Status:** Accepted
**Date:** 2026-08-30
**Relates to:** [ADR-008](008-energy-monitoring-architecture.md) (the energy architecture whose storage this scopes)
**Decision Makers:** @andrew-blake

---

## Context

The energy ledger was persisted under one storage key per device type
(`melcloudhome_energy_data`, `melcloudhome_energy_data_atw`), keyed per
integration rather than per config entry. An install with two MELCloud
accounts therefore had two coordinators sharing one `.storage` file: each
entry's save wrote its own in-memory snapshot, which held the *other*
account's units frozen at whatever the shared file contained when that entry
started. Every save by one entry rolled the other account's totals backwards
([issue #290](https://github.com/andrew-blake/melcloudhome/issues/290)).
`total_increasing` sensors then booked each backwards jump as a meter reset,
corrupting long-term statistics.

## Decision

### Storage key scheme

Each tracker's storage key is the device-type stem plus a per-account suffix:
`melcloudhome_energy_data_<hash>` / `melcloudhome_energy_data_atw_<hash>`,
where `<hash>` is the first 12 hex characters of the SHA-256 of the config
entry's `unique_id` (the lowercased account email, set in `config_flow.py`).
Derivation lives in `account_storage_suffix()` in `energy_tracker_base.py`.

- **Not `entry_id`:** it changes when a user removes and re-adds the
  integration, which would orphan accumulated energy history for every user
  who does that. The account hash survives a re-add, and ADR-009 pins the
  email across reconfigure, so the key is stable for the life of the account.
- **Null cases are never stringified.** Hashing `str(None)` would give every
  such entry the same key and rebuild #290 under a nicer filename. A
  `unique_id` of `None` falls back to `entry_id` (unique per entry); a missing
  config entry (test-only; production always passes one) gets a fixed
  sentinel.
- The hash buys tidiness, not secrecy: `.storage/core.config_entries` holds
  the email in plaintext anyway. Because it is one-way, the resolved keys are
  exposed in config-entry diagnostics (`energy_storage_keys`) so a support
  request can identify its own files.

### Migration contract

`EnergyTrackerBase.async_setup` performs a one-shot migration by swapping the
*source* of the loaded payload, so the existing parse path (including the
v1.3.4 → v2.0 format conversion) applies unchanged to adopted data:

1. Load the per-account key. `None` (file absent) means never migrated.
2. If never migrated, load the legacy shared key instead and adopt its
   contents **wholesale** — no filtering by unit ownership.
3. Save under the per-account key **unconditionally**, even when nothing was
   adopted, so the key exists and migration never re-runs.

Each clause carries weight:

- **The guard is `is None`, not truthiness.** An empty-but-present file is
  normal steady state: `ATWEnergyTracker.async_update_energy_data` saves
  after its unit loop regardless of whether any unit was processed, so every
  ATA-only install rewrites an empty ATW file every 30 minutes. A truthiness
  guard would re-migrate those installs on every start, and a re-migration
  after accumulation lands the legacy values as an upward jump that
  `total_increasing` books as real consumption.
- **No ownership filtering.** Ownership could only be a snapshot of
  `coordinator.data` at the moment migration runs. Guest shares lapse and
  return, so a unit absent from that one response would lose its history
  irreversibly. A co-tenant's stale keys in the adopted file are the lesser
  cost: they cannot surface as entities (entities are built from coordinator
  data, not storage), and if such a unit later joins this account the bounded
  phantom jump is identical to the pre-fix shared-file behaviour.
- **The save is unconditional** because the neighbouring self-heal save is
  conditional on the cleaner reporting changes; copying that idiom would
  leave the new key unwritten on clean installs, and a restart within the
  next poll interval would re-migrate from the frozen legacy file, dropping
  everything accumulated in between. `_save_energy_data` swallows write
  failures, so a failed migration save re-migrates on the next start; the
  loss is bounded by one poll interval and accepted.
- **The legacy file is read, never written or deleted.** It is the rollback
  safety net for a one-shot, silent, irreversible transformation of user
  data: the worst case is "the old file is still there", not "the data is
  gone". Read-only access is also what makes concurrent migration of two
  entries safe — both read, neither mutates.

### What the migration does not do

- **It does not repair existing damage.** At migration time the tracker's
  in-memory state is empty, so there is no correct value to compare a stored
  one against; any repair would be guesswork applied to user data. Users
  already affected need `recorder/adjust_sum_statistics`, and the upgrade
  restart itself shows one final backwards jump (both entries adopt the same
  co-mingled legacy content) — release notes must say both.
- **No `async_remove_entry` cleanup.** Deleting the per-account file on
  entry removal would destroy history on a remove/re-add, which is exactly
  the property keying on the account hash exists to protect. The absence of
  cleanup is deliberate, not an omission.

## Consequences

- Two config entries can no longer corrupt each other's totals; each
  account's ledger survives remove/re-add.
- One stale legacy `.storage` file remains per install. Deleting it is a
  separate decision for a later release, constrained by the contract above:
  such a release must not land before every user has restarted at least once
  on this version (the file-existence guard means an unmigrated entry still
  needs the legacy file), and must not race two entries (entry A deleting
  after its own migration could starve entry B's).
- Migration failure is silent by construction: the file-existence guard was
  chosen over an `async_migrate_entry` config-entry version bump, which
  would have been one-shot by construction and able to fail loudly, but
  couples energy storage to the entry schema version. The trade is recorded
  here rather than discovered later.
- One INFO log line (`Migrated energy storage from <legacy> to <new>
  (<n> unit(s))`) is the only forensic trail that migration ran.
