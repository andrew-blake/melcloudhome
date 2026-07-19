"""Shared constants for the MELCloud Home integration.

Device-specific constants are in const_ata.py and const_atw.py.
"""

from datetime import timedelta
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from .api.models import AirToAirUnit, AirToWaterUnit

# =================================================================
# Shared Constants
# =================================================================

# Domain and update interval (shared by all device types)
DOMAIN = "melcloudhome"
UPDATE_INTERVAL = timedelta(seconds=60)
PLATFORMS = ["climate"]

# Configuration keys
CONF_DEBUG_MODE = "debug_mode"

# Options keys
# Real-time WebSocket updates (accelerator over polling — issue #174).
# Default ON since v2.4.0 (ADR-019 amendment); the option is an opt-out.
CONF_ENABLE_WEBSOCKET = "enable_websocket"
DEFAULT_ENABLE_WEBSOCKET = True

# Energy polling configuration
UPDATE_INTERVAL_ENERGY = timedelta(minutes=30)
DATA_LOOKBACK_HOURS_ENERGY = 48

# Sanity ceiling for a single hourly energy reading (kWh). The MELCloud cloud
# API has been observed to occasionally return corrupt values around 65536 *
# 100 Wh (~6553.6 kWh) for one hour, consistent with a 16-bit counter wrap on
# the device side (see GitHub issue #161). No residential ATA/ATW unit can
# plausibly draw this much power in an hour, so readings above this ceiling
# are rejected rather than accumulated.
MAX_PLAUSIBLE_HOURLY_ENERGY_KWH = 100.0

# Retention window (hours) for persisted per-hour delta-tracking entries.
# A poll only ever fetches the last DATA_LOOKBACK_HOURS_ENERGY hours from
# the API, so once a stored hour_values entry falls outside that window it
# can never be looked up again - keeping it is pure unbounded storage
# growth. The multiplier gives a buffer for extended HA downtime (e.g. a
# multi-day outage) without losing legitimate delta-tracking state.
HOUR_VALUE_RETENTION_HOURS = DATA_LOOKBACK_HOURS_ENERGY * 3

# Telemetry polling configuration
UPDATE_INTERVAL_TELEMETRY = timedelta(minutes=60)  # Hourly (temps change slowly)
DATA_LOOKBACK_HOURS_TELEMETRY = 4  # Sparse data, 4 hours sufficient

# Outdoor temperature polling configuration (ATA devices)
UPDATE_INTERVAL_OUTDOOR_TEMP = timedelta(minutes=30)

# ATW telemetry measures
ATW_TELEMETRY_MEASURES = [
    "flow_temperature",
    "return_temperature",
    "flow_temperature_zone1",
    "return_temperature_zone1",
    "flow_temperature_boiler",
    "return_temperature_boiler",
    "rssi",  # WiFi signal strength in dBm
]

# ATW telemetry measures for Zone 2 devices only
ATW_TELEMETRY_MEASURES_ZONE2 = [
    "flow_temperature_zone2",
    "return_temperature_zone2",
]

# Type alias for any device unit (ATA or ATW)
DeviceUnit = Union["AirToAirUnit", "AirToWaterUnit"]

__all__ = [
    "ATW_TELEMETRY_MEASURES",
    "ATW_TELEMETRY_MEASURES_ZONE2",
    "CONF_DEBUG_MODE",
    "CONF_ENABLE_WEBSOCKET",
    "DATA_LOOKBACK_HOURS_ENERGY",
    "DATA_LOOKBACK_HOURS_TELEMETRY",
    "DEFAULT_ENABLE_WEBSOCKET",
    "DOMAIN",
    "HOUR_VALUE_RETENTION_HOURS",
    "MAX_PLAUSIBLE_HOURLY_ENERGY_KWH",
    "PLATFORMS",
    "UPDATE_INTERVAL",
    "UPDATE_INTERVAL_ENERGY",
    "UPDATE_INTERVAL_OUTDOOR_TEMP",
    "UPDATE_INTERVAL_TELEMETRY",
    "DeviceUnit",
]
