#!/usr/bin/env python3
"""Mock MELCloud Home API Server

A lightweight HTTP server that mimics the MELCloud Home API for development and testing.
Supports both Air-to-Air (ATA) and Air-to-Water (ATW) devices.

Usage:
    python tools/mock_melcloud_server.py                 # Default: 0.0.0.0:8080
    python tools/mock_melcloud_server.py --port 9090     # Custom port
    python tools/mock_melcloud_server.py --debug         # Enable debug logging
    python tools/mock_melcloud_server.py --host 127.0.0.1 --port 8888  # Custom both

Architecture:
    - Single unified API for both device types
    - Shared authentication (OAuth)
    - Multi-type container (UserContext returns both types)
    - Device-specific control endpoints
    - 3-way valve simulation for ATW devices

Reference:
    - Implementation Plan: docs/development/mock-server-implementation-plan.md
    - Architecture: docs/architecture.md
    - ATA API: docs/api/ata-api-reference.md
    - ATW API: docs/api/atw-api-reference.md
"""

import argparse
import asyncio
import json
import logging
import signal
from typing import Any

import aiohttp_cors
from aiohttp import web

# Configure module logger
logger = logging.getLogger(__name__)


class MockMELCloudServer:
    """Mock MELCloud Home API server supporting ATA and ATW devices."""

    def __init__(self):
        """Initialize mock server with default device states."""
        self.ata_states = self._init_ata_devices()
        self.atw_states = self._init_atw_devices()
        self.buildings = self._init_buildings()

    def _init_ata_devices(self) -> dict[str, dict[str, Any]]:
        """Initialize default ATA (Air-to-Air) device states.

        Returns 2 ATA devices by default:
        - Living Room AC
        - Bedroom AC

        Note: Using UUIDs for cleaner entity names (e.g., "MELCloudHome 0efc 76db")
        """
        return {
            "0efc1234-5678-9abc-def0-123456787db": {
                "name": "Living Room AC",
                "power": True,
                "operation_mode": "Heat",
                "set_temperature": 21.0,
                "room_temperature": 20.5,
                "set_fan_speed": "Auto",
                "vane_vertical_direction": "Auto",
                "vane_horizontal_direction": "Auto",
                "in_standby_mode": False,
                "is_in_error": False,
            },
            "bf8d5678-90ab-cdef-0123-456789ab5119": {
                "name": "Bedroom AC",
                "power": False,
                "operation_mode": "Cool",
                "set_temperature": 22.0,
                "room_temperature": 21.0,
                "set_fan_speed": "Two",
                "vane_vertical_direction": "Three",
                "vane_horizontal_direction": "Centre",
                "in_standby_mode": False,
                "is_in_error": False,
            },
        }

    def _init_atw_devices(self) -> dict[str, dict[str, Any]]:
        """Initialize default ATW (Air-to-Water) device states.

        Returns 1 ATW device by default:
        - House Heat Pump (single zone + DHW)

        Note: Using UUID that matches chrome_override test data
        """
        return {
            "bf2d256c-42ac-4799-a6d8-c6ab433e5666": {
                "name": "House Heat Pump",
                "power": True,
                "operation_mode": "HeatRoomTemperature",  # STATUS: What's heating now
                "operation_mode_zone1": "HeatRoomTemperature",  # CONTROL: How to heat zone
                "set_temperature_zone1": 21.0,
                "room_temperature_zone1": 20.0,
                "set_tank_water_temperature": 50.0,
                "tank_water_temperature": 48.5,
                "forced_hot_water_mode": False,
                "has_zone2": False,
                "in_standby_mode": False,
                "is_in_error": False,
                "ftc_model": 4,  # API internal value, mapping to physical FTC controller unknown
            },
        }

    def _init_buildings(self) -> dict[str, dict[str, Any]]:
        """Initialize building structure with device assignments."""
        return {
            "building-home": {
                "id": "building-home",
                "name": "My Home",
                "timezone": "Europe/London",
                "ata_unit_ids": [
                    "0efc1234-5678-9abc-def0-123456787db",
                    "bf8d5678-90ab-cdef-0123-456789ab5119",
                ],
                "atw_unit_ids": ["bf2d256c-42ac-4799-a6d8-c6ab433e5666"],
            },
        }

    def create_app(self) -> web.Application:
        """Create aiohttp application with routes."""
        app = web.Application()

        # Configure CORS to allow web client access from melcloudhome.com
        cors = aiohttp_cors.setup(
            app,
            defaults={
                "*": aiohttp_cors.ResourceOptions(
                    allow_credentials=True,
                    expose_headers="*",
                    allow_headers="*",
                    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
                )
            },
        )

        # Authentication (both paths for compatibility)
        auth_route = app.router.add_post("/api/auth/login", self.handle_login)
        login_route = app.router.add_post("/api/login", self.handle_login)

        # Device discovery (SHARED endpoint - returns both types)
        context_route = app.router.add_get(
            "/api/user/context", self.handle_user_context
        )

        # Device control (SEPARATE endpoints per type)
        ata_route = app.router.add_put(
            "/api/ataunit/{unit_id}", self.handle_ata_control
        )
        atw_route = app.router.add_put(
            "/api/atwunit/{unit_id}", self.handle_atw_control
        )

        # Schedule endpoints
        schedule_get = app.router.add_get(
            "/api/atwcloudschedule/{unit_id}", self.handle_schedule
        )
        schedule_post = app.router.add_post(
            "/api/atwcloudschedule/{unit_id}", self.handle_schedule
        )
        schedule_enabled_get = app.router.add_get(
            "/api/atwcloudschedule/{unit_id}/enabled", self.handle_schedule_enabled_get
        )
        schedule_enabled_put = app.router.add_put(
            "/api/atwcloudschedule/{unit_id}/enabled", self.handle_schedule_enabled_put
        )

        # Add CORS to all routes
        for route in [
            auth_route,
            login_route,
            context_route,
            ata_route,
            atw_route,
            schedule_get,
            schedule_post,
            schedule_enabled_get,
            schedule_enabled_put,
        ]:
            cors.add(route)

        return app

    async def handle_login(self, request: web.Request) -> web.Response:
        """Mock OAuth login endpoint.

        Architecture: Shared authentication for all device types

        Note: No token validation in subsequent requests (design decision).
        Returns valid-looking tokens for integration compatibility.
        """
        try:
            body = await request.json()
        except json.JSONDecodeError:
            return web.json_response(
                {"error": "invalid_request", "error_description": "Invalid JSON"},
                status=400,
            )

        email = body.get("email")
        password = body.get("password")

        # Accept any credentials for testing (permissive approach)
        if email and password:
            logger.info("🔐 Login: %s (mock - always succeeds)", email)
            return web.json_response(
                {
                    "access_token": "mock-access-token-abc123",
                    "refresh_token": "mock-refresh-token-xyz789",
                    "expires_in": 3600,
                    "token_type": "Bearer",
                }
            )

        return web.json_response(
            {
                "error": "invalid_credentials",
                "error_description": "Missing credentials",
            },
            status=401,
        )

    async def handle_user_context(self, request: web.Request) -> web.Response:
        """GET /api/user/context - Returns all devices (both types).

        Architecture: Multi-type container
        Format: {buildings: [{airToAirUnits: [...], airToWaterUnits: [...]}]}
        """
        logger.info("📋 User Context Request")

        buildings_response = []

        for building_id, building in self.buildings.items():
            # Build ATA units array
            ata_units = []
            for unit_id in building["ata_unit_ids"]:
                state = self.ata_states[unit_id]
                ata_units.append(
                    {
                        "id": unit_id,
                        "givenDisplayName": state.get("name", unit_id),
                        "rssi": -45,
                        "scheduleEnabled": False,
                        "settings": self._build_ata_settings(unit_id),
                        "capabilities": self._get_ata_capabilities(),
                        "schedule": [],
                    }
                )

            # Build ATW units array
            atw_units = []
            for unit_id in building["atw_unit_ids"]:
                state = self.atw_states[unit_id]
                atw_units.append(
                    {
                        "id": unit_id,
                        "givenDisplayName": state.get("name", unit_id),
                        "rssi": -42,
                        "scheduleEnabled": False,
                        "settings": self._build_atw_settings(unit_id),
                        "capabilities": self._get_atw_capabilities(),
                        "schedule": [],
                    }
                )

            buildings_response.append(
                {
                    "id": building_id,
                    "name": building["name"],
                    "timezone": building["timezone"],
                    "airToAirUnits": ata_units,  # ATA devices
                    "airToWaterUnits": atw_units,  # ATW devices
                }
            )

        logger.info(
            "   ✅ Returned %d ATA + %d ATW devices", len(ata_units), len(atw_units)
        )

        return web.json_response({"buildings": buildings_response})

    async def handle_ata_control(self, request: web.Request) -> web.Response:
        """PUT /api/ataunit/{unit_id} - Control ATA device.

        Architecture: Device-specific endpoint
        Reference: docs/api/ata-api-reference.md

        Note: Auto-creates device if not found (permissive for testing)
        """
        unit_id = request.match_info.get("unit_id")

        try:
            body = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        # Auto-create device if not found (permissive for testing)
        if unit_id not in self.ata_states:
            logger.info(f"📝 Auto-creating ATA device: {unit_id}")
            self.ata_states[unit_id] = {
                "name": f"ATA Device {len(self.ata_states) + 1}",
                "power": False,
                "operation_mode": "Heat",
                "set_temperature": 21.0,
                "room_temperature": 20.0,
                "set_fan_speed": "Auto",
                "vane_vertical_direction": "Auto",
                "vane_horizontal_direction": "Auto",
                "in_standby_mode": False,
                "is_in_error": False,
            }

        logger.info("🌡️  ATA Control: %s", unit_id)
        logger.debug("   Request: %s", json.dumps(body, indent=2))

        state = self.ata_states[unit_id]

        # Update state based on non-null values (sparse update pattern)
        # Permissive: Accept all values, warn if suspicious

        if body.get("power") is not None:
            state["power"] = body["power"]
            logger.info("   ✅ Power: %s", body["power"])

        if body.get("operationMode") is not None:
            mode = body["operationMode"]
            valid_modes = ["Heat", "Cool", "Automatic", "Dry", "Fan"]
            if mode not in valid_modes:
                logger.warning("   ⚠️  Unusual operation mode: %s", mode)
            state["operation_mode"] = mode
            logger.info("   ✅ Mode: %s", mode)

        if body.get("setTemperature") is not None:
            temp = body["setTemperature"]
            if temp < 10 or temp > 35:
                logger.warning(
                    "   ⚠️  Temperature %.1f°C outside typical range (10-35°C)", temp
                )
            state["set_temperature"] = temp
            logger.info("   ✅ Temperature: %.1f°C", temp)

        if body.get("setFanSpeed") is not None:
            state["set_fan_speed"] = body["setFanSpeed"]
            logger.info("   ✅ Fan: %s", body["setFanSpeed"])

        if body.get("vaneVerticalDirection") is not None:
            state["vane_vertical_direction"] = body["vaneVerticalDirection"]
            logger.info("   ✅ Vertical Vane: %s", body["vaneVerticalDirection"])

        if body.get("vaneHorizontalDirection") is not None:
            state["vane_horizontal_direction"] = body["vaneHorizontalDirection"]
            logger.info("   ✅ Horizontal Vane: %s", body["vaneHorizontalDirection"])

        if body.get("inStandbyMode") is not None:
            state["in_standby_mode"] = body["inStandbyMode"]
            logger.info("   ✅ Standby: %s", body["inStandbyMode"])

        # Print summary
        logger.info(
            "📊 State: Power=%s, Mode=%s, Target=%.1f°C, Current=%.1f°C",
            state["power"],
            state["operation_mode"],
            state["set_temperature"],
            state["room_temperature"],
        )

        # Real API returns 200 with empty body
        return web.Response(status=200, body=b"")

    async def handle_atw_control(self, request: web.Request) -> web.Response:
        """PUT /api/atwunit/{unit_id} - Control ATW device.

        Architecture: Device-specific endpoint
        Reference: docs/api/atw-api-reference.md
        3-Way Valve: Simulates physical limitation (DHW or Zone, not both)

        Note: Auto-creates device if not found (permissive for testing)
        """
        unit_id = request.match_info.get("unit_id")

        try:
            body = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        # Auto-create device if not found (permissive for testing)
        if unit_id not in self.atw_states:
            logger.info(f"📝 Auto-creating ATW device: {unit_id}")
            self.atw_states[unit_id] = {
                "name": f"ATW Device {len(self.atw_states) + 1}",
                "power": True,
                "operation_mode": "HeatRoomTemperature",
                "operation_mode_zone1": "HeatRoomTemperature",
                "set_temperature_zone1": 21.0,
                "room_temperature_zone1": 20.0,
                "set_tank_water_temperature": 50.0,
                "tank_water_temperature": 48.5,
                "forced_hot_water_mode": False,
                "has_zone2": False,
                "in_standby_mode": False,
                "is_in_error": False,
                "ftc_model": 4,
            }

        logger.info("♨️  ATW Control: %s", unit_id)
        logger.debug("   Request: %s", json.dumps(body, indent=2))

        state = self.atw_states[unit_id]

        # Update state based on non-null values
        if body.get("power") is not None:
            state["power"] = body["power"]
            logger.info("   ✅ Power: %s", body["power"])

        if body.get("setTemperatureZone1") is not None:
            temp = body["setTemperatureZone1"]
            if temp < 10 or temp > 30:
                logger.warning(
                    "   ⚠️  Zone temperature %.1f°C outside typical range (10-30°C)",
                    temp,
                )
            state["set_temperature_zone1"] = temp
            logger.info("   ✅ Zone 1 Target: %.1f°C", temp)

        if body.get("operationModeZone1") is not None:
            mode = body["operationModeZone1"]
            valid_modes = ["HeatRoomTemperature", "HeatFlowTemperature", "HeatCurve"]
            if mode not in valid_modes:
                logger.warning("   ⚠️  Unusual zone operation mode: %s", mode)
            state["operation_mode_zone1"] = mode
            logger.info("   ✅ Zone 1 Mode: %s", mode)

        if body.get("setTankWaterTemperature") is not None:
            temp = body["setTankWaterTemperature"]
            if temp < 40 or temp > 60:
                logger.warning(
                    "   ⚠️  DHW temperature %.1f°C outside typical range (40-60°C)", temp
                )
            state["set_tank_water_temperature"] = temp
            logger.info("   ✅ DHW Target: %.1f°C", temp)

        if body.get("forcedHotWaterMode") is not None:
            state["forced_hot_water_mode"] = body["forcedHotWaterMode"]
            logger.info("   ✅ Forced DHW: %s", body["forcedHotWaterMode"])

        if body.get("inStandbyMode") is not None:
            state["in_standby_mode"] = body["inStandbyMode"]
            logger.info("   ✅ Standby: %s", body["inStandbyMode"])

        # Update operation_mode STATUS based on 3-way valve logic
        self._update_atw_operation_mode(unit_id)

        # Print summary with 3-way valve status
        logger.info(
            "📊 State: Zone1=%.1f°C→%.1f°C, DHW=%.1f°C→%.1f°C",
            state["room_temperature_zone1"],
            state["set_temperature_zone1"],
            state["tank_water_temperature"],
            state["set_tank_water_temperature"],
        )
        self._log_3way_valve_status(unit_id)

        # Real API returns 200 with empty body
        return web.Response(status=200, body=b"")

    def _update_atw_operation_mode(self, unit_id: str):
        """Update ATW operation_mode STATUS field based on 3-way valve logic.

        Architecture: 3-way valve behavior (architecture:line 264-305)

        Logic:
        - If forced_hot_water_mode: "HotWater"
        - Else if DHW < target: "HotWater"
        - Else if Zone < target: operation_mode_zone1 value
        - Else: "Stop"

        Critical: operation_mode is STATUS (read-only), not control parameter
        """
        state = self.atw_states[unit_id]

        if not state["power"]:
            state["operation_mode"] = "Stop"
            return

        # Forced DHW mode takes priority
        if state["forced_hot_water_mode"]:
            state["operation_mode"] = "HotWater"
            return

        # Check if DHW needs heating
        dhw_needs_heat = (
            state["tank_water_temperature"] < state["set_tank_water_temperature"]
        )

        # Check if Zone 1 needs heating
        zone_needs_heat = (
            state["room_temperature_zone1"] < state["set_temperature_zone1"]
        )

        if dhw_needs_heat:
            state["operation_mode"] = "HotWater"
        elif zone_needs_heat:
            state["operation_mode"] = state["operation_mode_zone1"]
        else:
            state["operation_mode"] = "Stop"

    async def handle_schedule(self, request: web.Request) -> web.Response:
        """GET/POST /api/atwcloudschedule/{unit_id} - Get or update schedule."""
        unit_id = request.match_info.get("unit_id")
        method = request.method

        if method == "GET":
            logger.info("📅 Schedule GET: %s", unit_id)
            # Return empty schedule array
            return web.json_response([])

        elif method == "POST":
            try:
                body = await request.json()
            except json.JSONDecodeError:
                return web.json_response({"error": "Invalid JSON"}, status=400)

            logger.info("📅 Schedule POST: %s", unit_id)
            logger.debug("   Schedule data: %s", json.dumps(body, indent=2))

            # Real API returns 200 with empty body
            return web.Response(status=200, body=b"")

        return web.Response(status=405, body=b"Method Not Allowed")

    async def handle_schedule_enabled_get(self, request: web.Request) -> web.Response:
        """GET /api/atwcloudschedule/{unit_id}/enabled - Get schedule enabled status."""
        unit_id = request.match_info.get("unit_id")
        logger.info("📅 Schedule Enabled GET: %s", unit_id)

        # Return schedule enabled status (true/false)
        enabled = True  # Default to enabled
        return web.json_response({"enabled": enabled})

    async def handle_schedule_enabled_put(self, request: web.Request) -> web.Response:
        """PUT /api/atwcloudschedule/{unit_id}/enabled - Set schedule enabled status."""
        unit_id = request.match_info.get("unit_id")

        try:
            body = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        enabled = body.get("enabled", True)
        logger.info("📅 Schedule Enabled PUT: %s -> %s", unit_id, enabled)

        # Real API returns 200 with empty body
        return web.Response(status=200, body=b"")

    def _log_3way_valve_status(self, unit_id: str):
        """Log 3-way valve status for debugging."""
        state = self.atw_states[unit_id]
        mode = state["operation_mode"]

        if mode == "HotWater":
            if state["forced_hot_water_mode"]:
                logger.info("   🔄 3-Way Valve: → DHW TANK (Forced Hot Water Mode)")
            else:
                logger.info("   🔄 3-Way Valve: → DHW TANK (Priority heating)")

            zone_needs_heat = (
                state["room_temperature_zone1"] < state["set_temperature_zone1"]
            )
            if zone_needs_heat:
                logger.warning("   ⚠️  Zone 1 heating suspended")
        elif mode in ["HeatRoomTemperature", "HeatFlowTemperature", "HeatCurve"]:
            logger.info("   🔄 3-Way Valve: → ZONE 1 (%s)", mode)
        else:
            logger.info("   🔄 3-Way Valve: IDLE (%s)", mode)

    def _build_ata_settings(self, unit_id: str) -> list[dict]:
        """Build ATA settings array from state dict.

        Format: Array of {name, value} pairs (ata-api-reference.md)
        Boolean values as strings: "True"/"False"

        Note: Returns minimal field set for MVP. Real API returns 20+ fields.
        """
        state = self.ata_states[unit_id]
        return [
            {"name": "Power", "value": str(state["power"])},
            {"name": "OperationMode", "value": state["operation_mode"]},
            {"name": "SetTemperature", "value": str(state["set_temperature"])},
            {"name": "RoomTemperature", "value": str(state["room_temperature"])},
            {"name": "SetFanSpeed", "value": state["set_fan_speed"]},
            {
                "name": "VaneVerticalDirection",
                "value": state["vane_vertical_direction"],
            },
            {
                "name": "VaneHorizontalDirection",
                "value": state["vane_horizontal_direction"],
            },
            {"name": "InStandbyMode", "value": str(state["in_standby_mode"])},
            {"name": "IsInError", "value": str(state["is_in_error"])},
        ]

    def _build_atw_settings(self, unit_id: str) -> list[dict]:
        """Build ATW settings array from state dict.

        Format: Array of {name, value} pairs (atw-api-reference.md)
        Note: OperationMode is STATUS field (what's heating now)

        Note: Returns minimal field set for MVP. Real API returns 25+ fields.
        """
        state = self.atw_states[unit_id]
        return [
            {"name": "Power", "value": str(state["power"])},
            {"name": "OperationMode", "value": state["operation_mode"]},  # STATUS
            {
                "name": "OperationModeZone1",
                "value": state["operation_mode_zone1"],
            },  # CONTROL
            {
                "name": "SetTemperatureZone1",
                "value": str(state["set_temperature_zone1"]),
            },
            {
                "name": "RoomTemperatureZone1",
                "value": str(state["room_temperature_zone1"]),
            },
            {
                "name": "SetTankWaterTemperature",
                "value": str(state["set_tank_water_temperature"]),
            },
            {
                "name": "TankWaterTemperature",
                "value": str(state["tank_water_temperature"]),
            },
            {
                "name": "ForcedHotWaterMode",
                "value": str(state["forced_hot_water_mode"]),
            },
            {"name": "HasZone2", "value": str(int(state["has_zone2"]))},  # 0 or 1
            {"name": "InStandbyMode", "value": str(state["in_standby_mode"])},
            {"name": "IsInError", "value": str(state["is_in_error"])},
            {"name": "FTCModel", "value": str(state["ftc_model"])},
        ]

    def _get_ata_capabilities(self) -> dict:
        """Get ATA device capabilities.

        Reference: ata-api-reference.md:line 474
        """
        return {
            "numberOfFanSpeeds": 5,
            "minTempHeat": 10.0,
            "maxTempHeat": 31.0,
            "minTempCoolDry": 16.0,
            "maxTempCoolDry": 31.0,
            "minTempAutomatic": 16.0,
            "maxTempAutomatic": 31.0,
            "hasHalfDegreeIncrements": True,
            "hasExtendedTemperatureRange": True,
            "hasAutomaticFanSpeed": True,
            "hasSwing": True,
            "hasAirDirection": True,
            "hasCoolOperationMode": True,
            "hasHeatOperationMode": True,
            "hasAutoOperationMode": True,
            "hasDryOperationMode": True,
            "hasStandby": False,
        }

    def _get_atw_capabilities(self) -> dict:
        """Get ATW device capabilities.

        Reference: atw-api-reference.md
        """
        return {
            "hasHotWater": True,
            "minSetTankTemperature": 40.0,
            "maxSetTankTemperature": 60.0,
            "minSetTemperature": 10.0,
            "maxSetTemperature": 30.0,
            "hasHalfDegrees": True,
            "hasZone2": False,
            "hasThermostatZone1": True,
            "hasHeatZone1": True,
            "hasMeasuredEnergyConsumption": True,
            "hasEstimatedEnergyConsumption": False,
            "ftcModel": 4,  # API internal value
        }

    def print_startup_banner(self, host: str, port: int):
        """Print startup banner with server info and device list."""
        print("\n" + "=" * 70)
        print("🚀 Mock MELCloud Home API Server")
        print("=" * 70)
        print(f"Server running at: http://{host}:{port}")
        print()
        print("📋 Configure Home Assistant with:")
        print("   Email: test@example.com (any credentials work)")
        print("   Password: test123")
        print()

        for building_id, building in self.buildings.items():
            print(f"🏢 Building: {building['name']} ({building_id})")
            print()

            if building["ata_unit_ids"]:
                print(f"🔌 ATA (Air-to-Air) - {len(building['ata_unit_ids'])} devices:")
                for unit_id in building["ata_unit_ids"]:
                    state = self.ata_states[unit_id]
                    print(f"   🌡️  {state['name']} ({unit_id})")
                print()

            if building["atw_unit_ids"]:
                print(
                    f"🔌 ATW (Air-to-Water) - {len(building['atw_unit_ids'])} devices:"
                )
                for unit_id in building["atw_unit_ids"]:
                    state = self.atw_states[unit_id]
                    print(f"   ♨️  {state['name']} ({unit_id})")
                    print(
                        f"       - Zone 1: Space heating "
                        f"({state['room_temperature_zone1']}°C → {state['set_temperature_zone1']}°C)"
                    )
                    print(
                        f"       - DHW Tank: Hot water "
                        f"({state['tank_water_temperature']}°C → {state['set_tank_water_temperature']}°C)"
                    )
                print()

        print("💡 Tip: Use --port and --host to customize server address")
        print()
        print("Press Ctrl+C to stop")
        print("=" * 70)
        print()


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Mock MELCloud Home API Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                              # Default: 0.0.0.0:8080
  %(prog)s --port 9090                  # Custom port
  %(prog)s --debug                      # Enable debug logging
  %(prog)s --host 127.0.0.1             # Localhost only
  %(prog)s --host 127.0.0.1 --port 8888 # Custom both
        """,
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to bind to (default: 8080)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging (shows full request payloads)",
    )

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(message)s",  # Simple format for console output
        handlers=[logging.StreamHandler()],
    )

    # Create server and app
    server = MockMELCloudServer()
    app = server.create_app()

    # Print startup banner
    server.print_startup_banner(args.host, args.port)

    # Run server
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, args.host, args.port)

    try:
        await site.start()
    except OSError as e:
        logger.error("Failed to start server: %s", e)
        logger.error(
            "Port %d may already be in use. Try a different port with --port", args.port
        )
        await runner.cleanup()
        return

    # Setup signal handlers for clean shutdown
    loop = asyncio.get_running_loop()
    shutdown_event = asyncio.Event()

    # Use loop.add_signal_handler for proper asyncio signal handling
    def handle_shutdown():
        """Handle shutdown signals."""
        logger.info("\n\n👋 Shutting down mock server...")
        shutdown_event.set()

    # Register signal handlers (asyncio-compatible)
    loop.add_signal_handler(signal.SIGINT, handle_shutdown)
    loop.add_signal_handler(signal.SIGTERM, handle_shutdown)

    # Keep running until interrupted
    try:
        await shutdown_event.wait()
    finally:
        logger.info("Cleaning up...")
        await runner.cleanup()
        logger.info("Server stopped")


if __name__ == "__main__":
    asyncio.run(main())
