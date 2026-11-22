"""Home Assistant test helpers from whichever test package is installed.

The latest-HA run uses the official ``pytest-homeassistant`` (HA 2026.11+,
Python 3.14). The floor run uses ``pytest-homeassistant-custom-component``
0.13.269 (HA 2025.8.0, Python 3.13), which won't install on 3.14. Both
register their pytest plugin through an entry point; only the import path
differs. Delete this module when the hacs.json floor reaches HA 2026.11.
"""

from importlib.util import find_spec

if find_spec("pytest_homeassistant") is not None:
    from pytest_homeassistant.common import (
        MockConfigEntry,
        async_fire_time_changed,
    )
else:
    from pytest_homeassistant_custom_component.common import (  # type: ignore[no-redef,unused-ignore]
        MockConfigEntry,
        async_fire_time_changed,
    )

__all__ = ["MockConfigEntry", "async_fire_time_changed"]
