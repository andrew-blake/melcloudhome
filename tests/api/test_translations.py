"""Translation file parity checks.

Every translation file must expose exactly the same keys as en.json —
a missing key silently falls back to the raw key in the HA UI for that
language. Lives in the api tier because it needs neither HA nor Docker.
"""

import json
import re
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


def test_english_covers_every_config_flow_string() -> None:
    """Parity above only compares against en.json — this checks en.json itself.

    Keys listed here are the step IDs, abort reasons and error codes
    ``config_flow.py`` can actually return.
    """
    config = json.loads((TRANSLATIONS_DIR / "en.json").read_text(encoding="utf-8"))[
        "config"
    ]

    assert set(config["step"]) >= {"user", "reauth_confirm", "reconfigure"}
    assert set(config["abort"]) >= {
        "already_configured",
        "reauth_successful",
        "reconfigure_successful",
    }
    assert set(config["error"]) >= {
        "invalid_auth",
        "cannot_connect",
        "service_unavailable",
        "unknown",
    }


def _leaves(obj: object, prefix: str = "") -> dict[str, str]:
    """Flatten a translations dict to {dotted path: string}."""
    if isinstance(obj, str):
        return {prefix: obj}
    leaves: dict[str, str] = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            leaves |= _leaves(value, f"{prefix}.{key}" if prefix else key)
    return leaves


def _placeholders(text: str) -> set[str]:
    return set(re.findall(r"\{(\w+)\}", text))


def test_every_translation_keeps_the_english_placeholders() -> None:
    """HA drops a translated string whose placeholders differ, and logs an ERROR.

    helpers/translation.py compares each string's placeholder set with the
    English one; key parity alone can't see a translated {zone} gone missing.
    """
    english = _leaves(
        json.loads((TRANSLATIONS_DIR / "en.json").read_text(encoding="utf-8"))
    )
    for file in sorted(TRANSLATIONS_DIR.glob("*.json")):
        strings = _leaves(json.loads(file.read_text(encoding="utf-8")))
        for path, text in strings.items():
            assert _placeholders(text) == _placeholders(english[path]), (
                f"{file.name} {path}: {text!r}"
            )


def test_zone_presets_live_under_the_zone_key() -> None:
    """ATW zones (translation_key "zone") own the presets; ATA climate has none.

    Key parity passes even if the presets never moved, so pin where they are.
    """
    presets = {"room", "flow", "curve"}
    english = json.loads((TRANSLATIONS_DIR / "en.json").read_text(encoding="utf-8"))
    icons = json.loads(
        (TRANSLATIONS_DIR.parent / "icons.json").read_text(encoding="utf-8")
    )
    for climate in (english["entity"]["climate"], icons["entity"]["climate"]):
        zone_states = climate["zone"]["state_attributes"]["preset_mode"]["state"]
        assert set(zone_states) == presets
        assert "preset_mode" not in climate["melcloudhome"]["state_attributes"]
