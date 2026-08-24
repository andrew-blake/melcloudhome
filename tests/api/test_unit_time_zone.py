"""Units expose the IANA timezone the API reports for them.

Report endpoints stamp points in this zone, so it is the input the client needs
to compute a correct reading age. Real values seen on prod 2026-08-24:
Europe/Stockholm, Europe/Skopje, Europe/London.
"""

import copy

from custom_components.melcloudhome.api.models_ata import AirToAirUnit
from custom_components.melcloudhome.api.models_atw import AirToWaterUnit
from tests.api.fixtures.atw_fixtures import ATW_UNIT_HEATING_DHW


def _ata_data() -> dict:
    return {
        "id": "test-unit-id",
        "givenDisplayName": "Test Unit",
        "settings": [],
        "capabilities": {},
    }


def test_atw_unit_parses_time_zone():
    data = copy.deepcopy(ATW_UNIT_HEATING_DHW)
    data["timeZone"] = "Europe/Stockholm"
    unit = AirToWaterUnit.from_dict(data)
    assert unit.time_zone == "Europe/Stockholm"


def test_atw_unit_time_zone_is_none_when_absent():
    data = copy.deepcopy(ATW_UNIT_HEATING_DHW)
    data.pop("timeZone", None)
    unit = AirToWaterUnit.from_dict(data)
    assert unit.time_zone is None


def test_ata_unit_parses_time_zone():
    data = _ata_data()
    data["timeZone"] = "Europe/London"
    unit = AirToAirUnit.from_dict(data)
    assert unit.time_zone == "Europe/London"


def test_ata_unit_time_zone_is_none_when_absent():
    unit = AirToAirUnit.from_dict(_ata_data())
    assert unit.time_zone is None
