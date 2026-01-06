#!/usr/bin/env python3
"""Compare entity/device registries before and after upgrade."""

import json
import sys
from pathlib import Path
from typing import Any, cast


def load_registry(path: Path) -> dict[str, Any]:
    """Load registry JSON file."""
    with path.open() as f:
        return cast(dict[str, Any], json.load(f))


def compare_entities(before: dict, after: dict) -> None:
    """Compare entity registries."""
    before_entities = {e["entity_id"]: e for e in before["data"]["entities"]}
    after_entities = {e["entity_id"]: e for e in after["data"]["entities"]}

    melcloud_before = {k: v for k, v in before_entities.items() if "melcloudhome" in k}
    melcloud_after = {k: v for k, v in after_entities.items() if "melcloudhome" in k}

    print("=" * 80)
    print("ENTITY REGISTRY COMPARISON")
    print("=" * 80)
    print(f"\nTotal entities: {len(before_entities)} → {len(after_entities)}")
    print(f"MELCloud entities: {len(melcloud_before)} → {len(melcloud_after)}")

    # Check for added/removed entities
    added = set(melcloud_after.keys()) - set(melcloud_before.keys())
    removed = set(melcloud_before.keys()) - set(melcloud_after.keys())

    if added:
        print(f"\n❌ ADDED ENTITIES ({len(added)}):")
        for entity_id in sorted(added):
            print(f"  + {entity_id}")

    if removed:
        print(f"\n❌ REMOVED ENTITIES ({len(removed)}):")
        for entity_id in sorted(removed):
            print(f"  - {entity_id}")

    if not added and not removed:
        print("\n✅ No entities added or removed")

    # Compare common entities
    common = set(melcloud_before.keys()) & set(melcloud_after.keys())
    print(f"\n📊 COMPARING {len(common)} COMMON ENTITIES:")

    changes = []
    for entity_id in sorted(common):
        before_e = melcloud_before[entity_id]
        after_e = melcloud_after[entity_id]

        entity_changes = {}

        # Check name change
        if before_e.get("name") != after_e.get("name"):
            entity_changes["name"] = (before_e.get("name"), after_e.get("name"))

        # Check device_id (should NOT change)
        if before_e.get("device_id") != after_e.get("device_id"):
            entity_changes["device_id"] = (
                before_e.get("device_id"),
                after_e.get("device_id"),
            )

        # Check unique_id (should NOT change)
        if before_e.get("unique_id") != after_e.get("unique_id"):
            entity_changes["unique_id"] = (
                before_e.get("unique_id"),
                after_e.get("unique_id"),
            )

        if entity_changes:
            changes.append((entity_id, entity_changes))

    if changes:
        print("\nCHANGES DETECTED:")
        for entity_id, entity_changes in changes:
            print(f"\n  {entity_id}:")
            for field, (old, new) in entity_changes.items():
                if field == "name":
                    print(f"    {field:12} : '{old}' → '{new}'")
                else:
                    print(f"    ❌ {field:12} : CHANGED (should be stable!)")
                    print(f"       before: {old}")
                    print(f"       after:  {new}")
    else:
        print("  ✅ No changes in entity attributes (except names)")


def compare_devices(before: dict, after: dict) -> None:
    """Compare device registries."""
    before_devices = {d["id"]: d for d in before["data"]["devices"]}
    after_devices = {d["id"]: d for d in after["data"]["devices"]}

    # Filter MELCloud devices
    def is_melcloud(device):
        return any("melcloudhome" in str(id) for id in device.get("identifiers", []))

    melcloud_before = {k: v for k, v in before_devices.items() if is_melcloud(v)}
    melcloud_after = {k: v for k, v in after_devices.items() if is_melcloud(v)}

    print("\n" + "=" * 80)
    print("DEVICE REGISTRY COMPARISON")
    print("=" * 80)
    print(f"\nTotal devices: {len(before_devices)} → {len(after_devices)}")
    print(f"MELCloud devices: {len(melcloud_before)} → {len(melcloud_after)}")

    # Check device IDs stability
    if set(melcloud_before.keys()) != set(melcloud_after.keys()):
        print("\n❌ DEVICE IDS CHANGED:")
        added = set(melcloud_after.keys()) - set(melcloud_before.keys())
        removed = set(melcloud_before.keys()) - set(melcloud_after.keys())
        if added:
            print(f"  Added: {added}")
        if removed:
            print(f"  Removed: {removed}")
    else:
        print("\n✅ Device IDs stable")

    # Compare device names
    print("\n📊 DEVICE NAME CHANGES:")
    for device_id in sorted(set(melcloud_before.keys()) & set(melcloud_after.keys())):
        before_name = melcloud_before[device_id].get("name", "N/A")
        after_name = melcloud_after[device_id].get("name", "N/A")

        if before_name != after_name:
            print(f"  {device_id[:8]}... : '{before_name}' → '{after_name}'")


def main():
    """Run comparison."""
    scenario = sys.argv[1] if len(sys.argv) > 1 else "scenario-a-real-api"

    base_dir = Path("dev-config-snapshots") / scenario
    before_dir = base_dir / "prod-baseline"
    after_dir = base_dir / "post-upgrade-v2.0.0"

    print("\n" + "=" * 80)
    print(f"MELCloud Home: Upgrade Verification Report - {scenario.upper()}")
    print("=" * 80)
    print(f"Before: {before_dir}")
    print(f"After:  {after_dir}")

    # Load registries
    before_entities = load_registry(before_dir / "entity_registry.json")
    after_entities = load_registry(after_dir / "entity_registry.json")
    before_devices = load_registry(before_dir / "device_registry.json")
    after_devices = load_registry(after_dir / "device_registry.json")

    # Compare
    compare_entities(before_entities, after_entities)
    compare_devices(before_devices, after_devices)

    print("\n" + "=" * 80)
    print("END OF REPORT")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
