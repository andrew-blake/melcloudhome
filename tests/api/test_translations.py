"""Translation file parity checks.

Every translation file must expose exactly the same keys as en.json —
a missing key silently falls back to the raw key in the HA UI for that
language. Lives in the api tier because it needs neither HA nor Docker.
"""

import json
from pathlib import Path

TRANSLATIONS_DIR = (
    Path(__file__).parents[2] / "custom_components" / "melcloudhome" / "translations"
)


def _key_paths(obj: object, prefix: str = "") -> set[str]:
    """Flatten a translations dict to dotted key paths (leaves excluded)."""
    if not isinstance(obj, dict):
        return set()
    paths = set()
    for key, value in obj.items():
        path = f"{prefix}.{key}" if prefix else key
        paths.add(path)
        paths |= _key_paths(value, path)
    return paths


def test_all_translation_files_match_english_keys() -> None:
    english = _key_paths(
        json.loads((TRANSLATIONS_DIR / "en.json").read_text(encoding="utf-8"))
    )
    assert english, "en.json produced no keys — wrong path?"

    for file in sorted(TRANSLATIONS_DIR.glob("*.json")):
        if file.name == "en.json":
            continue
        keys = _key_paths(json.loads(file.read_text(encoding="utf-8")))
        missing = english - keys
        extra = keys - english
        assert not missing, f"{file.name} missing keys: {sorted(missing)}"
        assert not extra, f"{file.name} extra keys: {sorted(extra)}"
