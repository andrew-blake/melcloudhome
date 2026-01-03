"""Test fixtures for Air-to-Water (ATW) heat pump units.

Extracted from real API responses captured in HAR files.
Anonymized field names (e.g., "Doeter") have been restored to actual API names (e.g., "Water").
"""

# =============================================================================
# Scenario 1: Normal operation - Heating DHW (forced hot water mode)
# =============================================================================

ATW_UNIT_HEATING_DHW = {
    "id": "unit-001",
    "givenDisplayName": "Heat pump",
    "displayIcon": "Lounge",
    "macAddress": "AA:BB:CC:DD:EE:FF",
    "timeZone": "Europe/Madrid",
    "rssi": -45,
    "ftcModel": 3,
    "isConnected": True,
    "isInError": False,
    "settings": [
        {"name": "Power", "value": "True"},
        {"name": "InStandbyMode", "value": "False"},
        {"name": "OperationMode", "value": "HotWater"},  # Currently heating DHW
        {"name": "HasZone2", "value": "0"},
        {"name": "OperationModeZone1", "value": "HeatCurve"},
        {"name": "RoomTemperatureZone1", "value": "20.5"},
        {"name": "SetTemperatureZone1", "value": "31"},
        {"name": "ProhibitHotWater", "value": "False"},
        {"name": "TankWaterTemperature", "value": "29"},
        {"name": "SetTankWaterTemperature", "value": "60"},
        {"name": "HasCoolingMode", "value": "False"},
        {"name": "ForcedHotWaterMode", "value": "True"},  # DHW priority enabled
        {"name": "IsInError", "value": "False"},
        {"name": "ErrorCode", "value": ""},
    ],
    "schedule": [],
    "scheduleEnabled": True,
    "frostProtection": None,
    "overheatProtection": None,
    "holidayMode": {
        "enabled": False,
        "startDate": "2025-12-11T18:33:10.804",
        "endDate": "2025-12-17T12:00:00",
        "active": False,
    },
    "capabilities": {
        "maxImportPower": 0,
        "maxHeatOutput": 0,
        "temperatureUnit": "",
        "hasHotWater": True,
        "immersionHeaterCapacity": 0,
        "minSetTankTemperature": 0,  # API BUG: Should be 40
        "maxSetTankTemperature": 60,
        "minSetTemperature": 30,  # API BUG: Inverted! Should be 10
        "maxSetTemperature": 50,  # API BUG: Inverted! Should be 30
        "temperatureIncrement": 0,
        "temperatureIncrementOverride": "",
        "hasHalfDegrees": False,
        "hasZone2": False,
        "hasDualRoomTemperature": False,
        "hasThermostatZone1": True,
        "hasThermostatZone2": True,
        "hasHeatZone1": True,
        "hasHeatZone2": False,
        "hasMeasuredEnergyConsumption": False,
        "hasMeasuredEnergyProduction": False,
        "hasEstimatedEnergyConsumption": True,
        "hasEstimatedEnergyProduction": True,
        "ftcModel": 3,
        "refridgerentAddress": 0,
        "hasDemandSideControl": True,
    },
}

# =============================================================================
# Scenario 2: Normal operation - Heating Zone (stopped DHW)
# =============================================================================

ATW_UNIT_HEATING_ZONE = {
    "id": "unit-002",
    "givenDisplayName": "Ground floor heating",
    "displayIcon": "Lounge",
    "macAddress": "AA:BB:CC:DD:EE:01",
    "timeZone": "Europe/Madrid",
    "rssi": -52,
    "ftcModel": 3,
    "isConnected": True,
    "isInError": False,
    "settings": [
        {"name": "Power", "value": "True"},
        {"name": "InStandbyMode", "value": "False"},
        {"name": "OperationMode", "value": "HeatRoomTemperature"},  # Heating zone
        {"name": "HasZone2", "value": "0"},
        {"name": "OperationModeZone1", "value": "HeatRoomTemperature"},
        {"name": "RoomTemperatureZone1", "value": "21"},
        {"name": "SetTemperatureZone1", "value": "22"},
        {"name": "ProhibitHotWater", "value": "False"},
        {"name": "TankWaterTemperature", "value": "50"},
        {"name": "SetTankWaterTemperature", "value": "50"},
        {"name": "HasCoolingMode", "value": "False"},
        {"name": "ForcedHotWaterMode", "value": "False"},
        {"name": "IsInError", "value": "False"},
        {"name": "ErrorCode", "value": ""},
    ],
    "schedule": [],
    "scheduleEnabled": False,
    "frostProtection": None,
    "overheatProtection": None,
    "holidayMode": {
        "enabled": False,
        "startDate": None,
        "endDate": None,
        "active": False,
    },
    "capabilities": {
        "hasHotWater": True,
        "minSetTankTemperature": 40,
        "maxSetTankTemperature": 60,
        "minSetTemperature": 10,
        "maxSetTemperature": 30,
        "hasHalfDegrees": False,
        "hasZone2": False,
        "hasThermostatZone1": True,
        "hasThermostatZone2": True,
        "hasHeatZone1": True,
        "hasHeatZone2": False,
        "hasMeasuredEnergyConsumption": False,
        "hasMeasuredEnergyProduction": False,
        "hasEstimatedEnergyConsumption": True,
        "hasEstimatedEnergyProduction": True,
        "ftcModel": 3,
        "hasDemandSideControl": True,
    },
}

# =============================================================================
# Scenario 3: Idle (target reached)
# =============================================================================

ATW_UNIT_IDLE = {
    "id": "unit-003",
    "givenDisplayName": "Heat pump",
    "displayIcon": "Lounge",
    "macAddress": "AA:BB:CC:DD:EE:02",
    "timeZone": "Europe/Madrid",
    "rssi": -48,
    "ftcModel": 3,
    "isConnected": True,
    "isInError": False,
    "settings": [
        {"name": "Power", "value": "True"},
        {"name": "InStandbyMode", "value": "False"},
        {"name": "OperationMode", "value": "Stop"},  # Idle - targets reached
        {"name": "HasZone2", "value": "0"},
        {"name": "OperationModeZone1", "value": "HeatRoomTemperature"},
        {"name": "RoomTemperatureZone1", "value": "22"},
        {"name": "SetTemperatureZone1", "value": "22"},
        {"name": "ProhibitHotWater", "value": "False"},
        {"name": "TankWaterTemperature", "value": "50"},
        {"name": "SetTankWaterTemperature", "value": "50"},
        {"name": "HasCoolingMode", "value": "False"},
        {"name": "ForcedHotWaterMode", "value": "False"},
        {"name": "IsInError", "value": "False"},
        {"name": "ErrorCode", "value": ""},
    ],
    "schedule": [],
    "scheduleEnabled": False,
    "frostProtection": None,
    "overheatProtection": None,
    "holidayMode": {
        "enabled": False,
        "startDate": None,
        "endDate": None,
        "active": False,
    },
    "capabilities": {
        "hasHotWater": True,
        "minSetTankTemperature": 40,
        "maxSetTankTemperature": 60,
        "minSetTemperature": 10,
        "maxSetTemperature": 30,
        "hasHalfDegrees": False,
        "hasZone2": False,
        "hasThermostatZone1": True,
        "hasThermostatZone2": True,
        "hasHeatZone1": True,
        "hasHeatZone2": False,
        "ftcModel": 3,
        "hasDemandSideControl": True,
    },
}

# =============================================================================
# Scenario 4: With Zone 2
# =============================================================================

ATW_UNIT_WITH_ZONE2 = {
    "id": "unit-004",
    "givenDisplayName": "Multi-zone heat pump",
    "displayIcon": "Lounge",
    "macAddress": "AA:BB:CC:DD:EE:03",
    "timeZone": "Europe/Madrid",
    "rssi": -50,
    "ftcModel": 3,
    "isConnected": True,
    "isInError": False,
    "settings": [
        {"name": "Power", "value": "True"},
        {"name": "InStandbyMode", "value": "False"},
        {"name": "OperationMode", "value": "HeatRoomTemperature"},
        {"name": "HasZone2", "value": "1"},  # Zone 2 present
        {"name": "OperationModeZone1", "value": "HeatRoomTemperature"},
        {"name": "RoomTemperatureZone1", "value": "21"},
        {"name": "SetTemperatureZone1", "value": "22"},
        {"name": "OperationModeZone2", "value": "HeatRoomTemperature"},  # Zone 2
        {"name": "RoomTemperatureZone2", "value": "19"},
        {"name": "SetTemperatureZone2", "value": "20"},
        {"name": "ProhibitHotWater", "value": "False"},
        {"name": "TankWaterTemperature", "value": "48"},
        {"name": "SetTankWaterTemperature", "value": "50"},
        {"name": "HasCoolingMode", "value": "False"},
        {"name": "ForcedHotWaterMode", "value": "False"},
        {"name": "IsInError", "value": "False"},
        {"name": "ErrorCode", "value": ""},
    ],
    "schedule": [],
    "scheduleEnabled": False,
    "frostProtection": None,
    "overheatProtection": None,
    "holidayMode": {
        "enabled": False,
        "startDate": None,
        "endDate": None,
        "active": False,
    },
    "capabilities": {
        "hasHotWater": True,
        "minSetTankTemperature": 40,
        "maxSetTankTemperature": 60,
        "minSetTemperature": 10,
        "maxSetTemperature": 30,
        "hasHalfDegrees": False,
        "hasZone2": True,  # Zone 2 supported
        "hasThermostatZone1": True,
        "hasThermostatZone2": True,
        "hasHeatZone1": True,
        "hasHeatZone2": True,  # Zone 2 heating
        "ftcModel": 3,
        "hasDemandSideControl": True,
    },
}

# =============================================================================
# Scenario 5: Error state
# =============================================================================

ATW_UNIT_ERROR = {
    "id": "unit-005",
    "givenDisplayName": "Heat pump",
    "displayIcon": "Lounge",
    "macAddress": "AA:BB:CC:DD:EE:04",
    "timeZone": "Europe/Madrid",
    "rssi": -55,
    "ftcModel": 3,
    "isConnected": True,
    "isInError": True,
    "settings": [
        {"name": "Power", "value": "True"},
        {"name": "InStandbyMode", "value": "False"},
        {"name": "OperationMode", "value": "Stop"},
        {"name": "HasZone2", "value": "0"},
        {"name": "OperationModeZone1", "value": "HeatRoomTemperature"},
        {"name": "RoomTemperatureZone1", "value": "18"},
        {"name": "SetTemperatureZone1", "value": "22"},
        {"name": "ProhibitHotWater", "value": "False"},
        {"name": "TankWaterTemperature", "value": "30"},
        {"name": "SetTankWaterTemperature", "value": "50"},
        {"name": "HasCoolingMode", "value": "False"},
        {"name": "ForcedHotWaterMode", "value": "False"},
        {"name": "IsInError", "value": "True"},  # Error state
        {"name": "ErrorCode", "value": "E4"},  # Error code E4
    ],
    "schedule": [],
    "scheduleEnabled": False,
    "frostProtection": None,
    "overheatProtection": None,
    "holidayMode": {
        "enabled": False,
        "startDate": None,
        "endDate": None,
        "active": False,
    },
    "capabilities": {
        "hasHotWater": True,
        "minSetTankTemperature": 40,
        "maxSetTankTemperature": 60,
        "minSetTemperature": 10,
        "maxSetTemperature": 30,
        "hasHalfDegrees": False,
        "hasZone2": False,
        "ftcModel": 3,
        "hasDemandSideControl": True,
    },
}

# =============================================================================
# Scenario 6: Half-degree increments support
# =============================================================================

ATW_UNIT_HALF_DEGREES = {
    "id": "unit-006",
    "givenDisplayName": "Heat pump",
    "displayIcon": "Lounge",
    "macAddress": "AA:BB:CC:DD:EE:05",
    "timeZone": "Europe/Madrid",
    "rssi": -47,
    "ftcModel": 3,
    "isConnected": True,
    "isInError": False,
    "settings": [
        {"name": "Power", "value": "True"},
        {"name": "InStandbyMode", "value": "False"},
        {"name": "OperationMode", "value": "HeatRoomTemperature"},
        {"name": "HasZone2", "value": "0"},
        {"name": "OperationModeZone1", "value": "HeatRoomTemperature"},
        {"name": "RoomTemperatureZone1", "value": "21.5"},  # Half degree
        {"name": "SetTemperatureZone1", "value": "22.5"},  # Half degree
        {"name": "ProhibitHotWater", "value": "False"},
        {"name": "TankWaterTemperature", "value": "49.5"},
        {"name": "SetTankWaterTemperature", "value": "50"},
        {"name": "HasCoolingMode", "value": "False"},
        {"name": "ForcedHotWaterMode", "value": "False"},
        {"name": "IsInError", "value": "False"},
        {"name": "ErrorCode", "value": ""},
    ],
    "schedule": [],
    "scheduleEnabled": False,
    "frostProtection": None,
    "overheatProtection": None,
    "holidayMode": {
        "enabled": False,
        "startDate": None,
        "endDate": None,
        "active": False,
    },
    "capabilities": {
        "hasHotWater": True,
        "minSetTankTemperature": 40,
        "maxSetTankTemperature": 60,
        "minSetTemperature": 10,
        "maxSetTemperature": 30,
        "hasHalfDegrees": True,  # Supports 0.5° increments
        "hasZone2": False,
        "ftcModel": 3,
        "hasDemandSideControl": True,
    },
}

# =============================================================================
# Complete UserContext responses
# =============================================================================

USER_CONTEXT_SINGLE_ATW_UNIT = {
    "id": "user-001",
    "firstname": "John",
    "lastname": "Doe",
    "email": "john@example.com",
    "language": "en",
    "country": "ES",
    "buildings": [
        {
            "id": "building-001",
            "name": "Home",
            "timezone": "Europe/Madrid",
            "airToAirUnits": [],
            "airToWaterUnits": [ATW_UNIT_HEATING_DHW],
        }
    ],
}

USER_CONTEXT_MULTIPLE_ATW_UNITS = {
    "id": "user-002",
    "buildings": [
        {
            "id": "building-001",
            "name": "Ground floor",
            "timezone": "Europe/Madrid",
            "airToAirUnits": [],
            "airToWaterUnits": [ATW_UNIT_HEATING_ZONE, ATW_UNIT_WITH_ZONE2],
        },
        {
            "id": "building-002",
            "name": "First floor",
            "timezone": "Europe/Madrid",
            "airToAirUnits": [],
            "airToWaterUnits": [ATW_UNIT_IDLE],
        },
    ],
}

USER_CONTEXT_MIXED_UNITS = {
    "id": "user-003",
    "buildings": [
        {
            "id": "building-001",
            "name": "Home",
            "timezone": "Europe/Madrid",
            "airToAirUnits": [
                {
                    "id": "a2a-001",
                    "givenDisplayName": "Bedroom A/C",
                    "settings": [
                        {"name": "Power", "value": "True"},
                        {"name": "OperationMode", "value": "Heat"},
                        {"name": "SetTemperature", "value": "22"},
                    ],
                    "capabilities": {},
                }
            ],
            "airToWaterUnits": [ATW_UNIT_HEATING_ZONE],
        }
    ],
}

USER_CONTEXT_NO_ATW_UNITS = {
    "id": "user-004",
    "buildings": [
        {
            "id": "building-001",
            "name": "Apartment",
            "timezone": "Europe/London",
            "airToAirUnits": [
                {
                    "id": "a2a-001",
                    "givenDisplayName": "Living room",
                    "settings": [],
                    "capabilities": {},
                }
            ],
            "airToWaterUnits": [],  # No ATW units
        }
    ],
}
