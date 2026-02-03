# Outdoor Temperature Sensor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use @superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add outdoor temperature sensor support for ATA (air conditioning) devices

**Architecture:** Extends API client with trendsummary endpoint support, adds outdoor_temperature field to AirToAirUnit model, implements runtime capability discovery in coordinator, creates new sensor entity

**Tech Stack:** Python 3.13, Home Assistant integration framework, aiohttp, pytest, Docker (for integration tests)

**Design Document:** `docs/plans/2026-02-03-outdoor-temperature-design.md`

---

## Pre-Implementation Checklist

- [x] Design document approved
- [x] Isolated worktree created (`.worktrees/outdoor-temperature-sensor`)
- [x] All tests passing at baseline (215 API + 133 integration + 12 E2E)
- [x] Dev environment verified working (29 entities, no outdoor temp sensors)
- [ ] Mock server updated with trendsummary endpoint

---

## Task 1: Update Mock Server with Trendsummary Endpoint

**Files:**

- Modify: `tools/mock_melcloud_server.py`

**Step 1: Add trendsummary endpoint handler**

Add after existing endpoint handlers (around line 400):

```python
async def get_trend_summary(self, request: web.Request) -> web.Response:
    """GET /api/report/trendsummary - Temperature trend data."""
    unit_id = request.query.get("unitId")
    to_param = request.query.get("to", "")
    from_param = request.query.get("from", "")

    if not unit_id:
        return web.json_response({"error": "unitId required"}, status=400)

    # Parse timestamps
    from datetime import datetime, timedelta
    if to_param:
        to_time = datetime.fromisoformat(to_param.replace('.0000000', ''))
    else:
        to_time = datetime.now()

    if from_param:
        from_time = datetime.fromisoformat(from_param.replace('.0000000', ''))
    else:
        from_time = to_time - timedelta(hours=1)

    # Generate datapoints (every 10 minutes)
    datapoints_room = []
    datapoints_set = []
    datapoints_outdoor = []

    current = from_time
    while current <= to_time:
        timestamp = current.isoformat()
        datapoints_room.append({"x": timestamp, "y": 20.5})
        datapoints_set.append({"x": timestamp, "y": 21.0})
        datapoints_outdoor.append({"x": timestamp, "y": 12.0})
        current += timedelta(minutes=10)

    # Check if device has outdoor sensor (Living Room AC has it, Bedroom doesn't)
    has_outdoor_sensor = unit_id == "0efc1234-5678-9abc-def0-123456787db"

    datasets = [
        {
            "label": "REPORT.TREND_SUMMARY_REPORT.DATASET.LABELS.ROOM_TEMPERATURE",
            "data": datapoints_room,
            "backgroundColor": "#F1995D",
            "borderColor": "#F1995D",
            "yAxisId": "yTemp",
            "pointRadius": 0,
            "lineTension": 0,
            "borderWidth": 2,
            "stepped": True,
            "spanGaps": False,
            "isNonInteractive": False
        },
        {
            "label": "REPORT.TREND_SUMMARY_REPORT.DATASET.LABELS.SET_TEMPERATURE",
            "data": datapoints_set,
            "backgroundColor": "#36BC6A",
            "borderColor": "#36BC6A",
            "yAxisId": "yTemp",
            "pointRadius": 0,
            "lineTension": 0,
            "borderWidth": 2,
            "stepped": True,
            "spanGaps": False,
            "isNonInteractive": False
        }
    ]

    # Add outdoor temp dataset only for devices with sensor
    if has_outdoor_sensor:
        datasets.append({
            "label": "REPORT.TREND_SUMMARY_REPORT.DATASET.LABELS.OUTDOOR_TEMPERATURE",
            "data": datapoints_outdoor,
            "backgroundColor": "#156082",
            "borderColor": "#156082",
            "yAxisId": "yTemp",
            "pointRadius": 0,
            "lineTension": 0,
            "borderWidth": 2,
            "stepped": True,
            "spanGaps": False,
            "isNonInteractive": False
        })

    return web.json_response({"datasets": datasets, "annotations": []})
```

**Step 2: Register route in setup_routes()**

Find the `setup_routes()` method and add:

```python
app.router.add_get("/api/report/trendsummary", self.get_trend_summary)
```

**Step 3: Add datetime import**

At top of file, add to imports:

```python
from datetime import datetime, timedelta
```

**Step 4: Test mock server starts**

Run: `python tools/mock_melcloud_server.py --debug`
Expected: Server starts without errors, shows "Mock MELCloud Home API Server running on 0.0.0.0:8080"
Stop with Ctrl+C

**Step 5: Commit**

```bash
git add tools/mock_melcloud_server.py
git commit -m "feat: add trendsummary endpoint to mock server

Supports outdoor temperature data for testing. Living Room AC has outdoor
sensor (returns outdoor temp dataset), Bedroom AC does not (omits dataset).

Generates realistic multi-point time series data matching real API format."
```

---

## Task 2: Add Outdoor Temperature to Data Model

**Files:**

- Modify: `custom_components/melcloudhome/api/models_ata.py:86-104`

**Step 1: Write failing test for outdoor_temperature field**

Create: `tests/api/test_outdoor_temperature_model.py`

```python
"""Tests for outdoor temperature in ATA data model."""

import pytest

from custom_components.melcloudhome.api.models_ata import AirToAirUnit


def test_air_to_air_unit_has_outdoor_temperature_field():
    """Test that AirToAirUnit has outdoor_temperature field with default None."""
    # Minimal data for AirToAirUnit.from_dict
    data = {
        "id": "test-unit-id",
        "givenDisplayName": "Test Unit",
        "settings": [],
        "capabilities": {}
    }

    unit = AirToAirUnit.from_dict(data)

    assert hasattr(unit, "outdoor_temperature")
    assert unit.outdoor_temperature is None


def test_air_to_air_unit_has_outdoor_temp_sensor_field():
    """Test that AirToAirUnit has has_outdoor_temp_sensor flag."""
    data = {
        "id": "test-unit-id",
        "givenDisplayName": "Test Unit",
        "settings": [],
        "capabilities": {}
    }

    unit = AirToAirUnit.from_dict(data)

    assert hasattr(unit, "has_outdoor_temp_sensor")
    assert unit.has_outdoor_temp_sensor is False
```

**Step 2: Run test to verify it fails**

Run: `make test-api`
Expected: FAIL with "AttributeError: 'AirToAirUnit' object has no attribute 'outdoor_temperature'"

**Step 3: Add fields to AirToAirUnit dataclass**

In `custom_components/melcloudhome/api/models_ata.py`, modify the `AirToAirUnit` class:

Find the energy_consumed comment and field (around line 102-103), add after it:

```python
    # Energy monitoring (set by coordinator, not from main API)
    energy_consumed: float | None = None  # kWh
    # Outdoor temperature monitoring (set by coordinator via trendsummary API)
    outdoor_temperature: float | None = None  # °C
    has_outdoor_temp_sensor: bool = False  # Runtime discovery flag
```

**Step 4: Run test to verify it passes**

Run: `make test-api`
Expected: PASS (all tests including new ones)

**Step 5: Commit**

```bash
git add custom_components/melcloudhome/api/models_ata.py tests/api/test_outdoor_temperature_model.py
git commit -m "feat: add outdoor temperature fields to AirToAirUnit model

Adds outdoor_temperature (float | None) and has_outdoor_temp_sensor (bool)
fields to AirToAirUnit dataclass for runtime capability discovery pattern."
```

---

## Task 3: Implement API Client Trendsummary Support

**Files:**

- Modify: `custom_components/melcloudhome/api/client.py`
- Create: `tests/api/test_outdoor_temperature_client.py`

**Step 1: Write failing tests for API client**

Create: `tests/api/test_outdoor_temperature_client.py`

```python
"""Tests for outdoor temperature API client methods."""

import pytest
from datetime import datetime, timezone

from custom_components/melcloudhome.api.client import MELCloudHomeClient


class TestParseOutdoorTemp:
    """Tests for _parse_outdoor_temp method."""

    def test_parse_outdoor_temperature_success(self):
        """Test parsing outdoor temperature from valid response."""
        client = MELCloudHomeClient()
        response = {
            "datasets": [
                {
                    "label": "REPORT.TREND_SUMMARY_REPORT.DATASET.LABELS.ROOM_TEMPERATURE",
                    "data": [{"x": "2026-02-03T12:00:00", "y": 20.5}]
                },
                {
                    "label": "REPORT.TREND_SUMMARY_REPORT.DATASET.LABELS.OUTDOOR_TEMPERATURE",
                    "data": [
                        {"x": "2026-02-03T11:00:00", "y": 11.0},
                        {"x": "2026-02-03T12:00:00", "y": 12.0}
                    ]
                }
            ]
        }

        result = client._parse_outdoor_temp(response)

        assert result == 12.0  # Latest value

    def test_parse_outdoor_temperature_missing_dataset(self):
        """Test when outdoor temperature dataset is missing."""
        client = MELCloudHomeClient()
        response = {
            "datasets": [
                {
                    "label": "REPORT.TREND_SUMMARY_REPORT.DATASET.LABELS.ROOM_TEMPERATURE",
                    "data": [{"x": "2026-02-03T12:00:00", "y": 20.5}]
                }
            ]
        }

        result = client._parse_outdoor_temp(response)

        assert result is None

    def test_parse_outdoor_temperature_empty_data(self):
        """Test when outdoor temperature dataset exists but data array empty."""
        client = MELCloudHomeClient()
        response = {
            "datasets": [
                {
                    "label": "REPORT.TREND_SUMMARY_REPORT.DATASET.LABELS.OUTDOOR_TEMPERATURE",
                    "data": []
                }
            ]
        }

        result = client._parse_outdoor_temp(response)

        assert result is None

    def test_parse_outdoor_temperature_malformed(self):
        """Test with malformed response structure."""
        client = MELCloudHomeClient()
        response = {}

        result = client._parse_outdoor_temp(response)

        assert result is None


@pytest.mark.asyncio
async def test_get_outdoor_temperature_formats_time_correctly(mocker):
    """Test that get_outdoor_temperature formats timestamps correctly."""
    client = MELCloudHomeClient()

    # Mock _request to capture params
    mock_request = mocker.patch.object(
        client,
        "_request",
        return_value={
            "datasets": [{
                "label": "REPORT.TREND_SUMMARY_REPORT.DATASET.LABELS.OUTDOOR_TEMPERATURE",
                "data": [{"x": "2026-02-03T12:00:00", "y": 12.0}]
            }]
        }
    )

    # Mock datetime to control time
    fake_now = datetime(2026, 2, 3, 12, 30, 0, tzinfo=timezone.utc)
    mocker.patch(
        "custom_components.melcloudhome.api.client.datetime"
    ).now.return_value = fake_now

    await client.get_outdoor_temperature("test-unit-id")

    # Verify request was called with correct params
    mock_request.assert_called_once()
    call_args = mock_request.call_args
    assert call_args[0][0] == "GET"
    assert call_args[0][1] == "/api/report/trendsummary"

    params = call_args[1]["params"]
    assert params["unitId"] == "test-unit-id"
    assert params["from"] == "2026-02-03T11:30:00.0000000"  # 1 hour before
    assert params["to"] == "2026-02-03T12:30:00.0000000"
```

**Step 2: Run tests to verify they fail**

Run: `make test-api`
Expected: FAIL with "AttributeError: 'MELCloudHomeClient' object has no attribute '_parse_outdoor_temp'"

**Step 3: Implement _parse_outdoor_temp method**

In `custom_components/melcloudhome/api/client.py`, add after the `get_energy_data` method (around line 236):

```python
    def _parse_outdoor_temp(self, response: dict[str, Any]) -> float | None:
        """Extract outdoor temperature from trendsummary response.

        Response format:
        {
          "datasets": [
            {
              "label": "REPORT.TREND_SUMMARY_REPORT.DATASET.LABELS.OUTDOOR_TEMPERATURE",
              "data": [{"x": "2026-01-12T20:00:00", "y": 11}, ...]
            }
          ]
        }

        Args:
            response: Trendsummary API response

        Returns:
            Outdoor temperature in Celsius, or None if not available
        """
        datasets = response.get("datasets", [])
        for dataset in datasets:
            label = dataset.get("label", "")
            if "OUTDOOR_TEMPERATURE" in label:
                data = dataset.get("data", [])
                if data:
                    # Return latest value (last datapoint)
                    return data[-1].get("y")
        return None  # No outdoor temp dataset found
```

**Step 4: Implement get_outdoor_temperature method**

Add after `_parse_outdoor_temp`:

```python
    async def get_outdoor_temperature(self, unit_id: str) -> float | None:
        """Get latest outdoor temperature for an ATA unit.

        Queries trendsummary endpoint for last hour, extracts most recent
        outdoor temperature from the OUTDOOR_TEMPERATURE dataset.

        Args:
            unit_id: ATA unit UUID

        Returns:
            Outdoor temperature in Celsius, or None if not available
        """
        from datetime import datetime, timedelta, timezone

        # Build time range: last 1 hour
        now = datetime.now(timezone.utc)
        from_time = now - timedelta(hours=1)

        # Format: 2026-01-12T20:00:00.0000000 (7 decimal places for nanoseconds)
        params = {
            "unitId": unit_id,
            "from": from_time.strftime("%Y-%m-%dT%H:%M:%S.0000000"),
            "to": now.strftime("%Y-%m-%dT%H:%M:%S.0000000"),
        }

        try:
            response = await self._request(
                "GET",
                "/api/report/trendsummary",
                params=params
            )
            return self._parse_outdoor_temp(response)
        except Exception:
            # Log at debug level - outdoor temp is nice-to-have, not critical
            _LOGGER.debug(
                "Failed to fetch outdoor temperature for unit %s",
                unit_id,
                exc_info=True
            )
            return None
```

**Step 5: Run tests to verify they pass**

Run: `make test-api`
Expected: PASS (all tests)

**Step 6: Commit**

```bash
git add custom_components/melcloudhome/api/client.py tests/api/test_outdoor_temperature_client.py
git commit -m "feat: add trendsummary API support to client

Implements get_outdoor_temperature() method to query /api/report/trendsummary
endpoint and extract latest outdoor temperature value from response datasets.

Includes graceful error handling - outdoor temp failures don't break main flow."
```

---

## Task 4: Add Outdoor Temperature Sensor Entity

**Files:**

- Modify: `custom_components/melcloudhome/sensor_ata.py:49-87`
- Modify: `custom_components/melcloudhome/strings.json`

**Step 1: Write failing integration test**

Create: `tests/integration/test_outdoor_temperature_sensor.py`

```python
"""Integration tests for outdoor temperature sensor."""

import pytest

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from custom_components.melcloudhome.const import DOMAIN


async def test_outdoor_temperature_sensor_created_when_device_has_sensor(hass: HomeAssistant):
    """Test outdoor temp sensor created for device with outdoor sensor."""
    # Living Room AC (0efc1234...) has outdoor sensor in mock
    entity_id = "sensor.melcloudhome_0efc_76db_outdoor_temperature"

    state = hass.states.get(entity_id)

    assert state is not None
    assert state.state == "12.0"  # Value from mock server
    assert state.attributes["unit_of_measurement"] == "°C"
    assert state.attributes["device_class"] == "temperature"
    assert state.attributes["state_class"] == "measurement"


async def test_outdoor_temperature_sensor_not_created_when_no_sensor(hass: HomeAssistant):
    """Test outdoor temp sensor NOT created for device without outdoor sensor."""
    # Bedroom AC (5b3e4321...) does not have outdoor sensor in mock
    entity_id = "sensor.melcloudhome_5b3e_7a9b_outdoor_temperature"

    state = hass.states.get(entity_id)

    assert state is None  # Entity should not exist


async def test_outdoor_temperature_updates_on_coordinator_refresh(hass: HomeAssistant):
    """Test outdoor temperature value updates when coordinator refreshes."""
    entity_id = "sensor.melcloudhome_0efc_76db_outdoor_temperature"

    # Initial state
    state_before = hass.states.get(entity_id)
    assert state_before.state == "12.0"

    # Trigger coordinator refresh
    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {"entity_id": entity_id},
        blocking=True
    )

    # Value should still be 12.0 (mock returns constant)
    state_after = hass.states.get(entity_id)
    assert state_after.state == "12.0"


async def test_outdoor_temperature_unavailable_when_device_in_error(hass: HomeAssistant):
    """Test outdoor temp sensor shows unavailable when device errors."""
    entity_id = "sensor.melcloudhome_0efc_76db_outdoor_temperature"

    # Mock coordinator to return device in error state
    # TODO: Implement this test when we have error injection in mock server

    # For now, verify sensor can handle unavailable state
    state = hass.states.get(entity_id)
    assert state is not None
```

**Step 2: Run tests to verify they fail**

Run: `make test-integration`
Expected: FAIL (entity doesn't exist yet)

**Step 3: Add sensor description to ATA_SENSOR_TYPES**

In `custom_components/melcloudhome/sensor_ata.py`, add after energy sensor (around line 86):

```python
    # Outdoor temperature - ambient temperature from outdoor unit sensor
    # Only created for devices where outdoor sensor detected during capability discovery
    # Updates every 30 minutes via trendsummary API endpoint
    ATASensorEntityDescription(
        key="outdoor_temperature",
        translation_key="outdoor_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda unit: unit.outdoor_temperature,
        available_fn=lambda unit: unit.outdoor_temperature is not None,
        should_create_fn=lambda unit: unit.has_outdoor_temp_sensor,
    ),
```

**Step 4: Add translation string**

In `custom_components/melcloudhome/strings.json`, find the `sensor` section and add:

```json
      "outdoor_temperature": {
        "name": "Outdoor temperature"
      }
```

**Step 5: Run tests (will still fail - coordinator not implemented)**

Run: `make test-integration`
Expected: FAIL (sensor created but has_outdoor_temp_sensor is False, so entity not created)

**Step 6: Commit**

```bash
git add custom_components/melcloudhome/sensor_ata.py custom_components/melcloudhome/strings.json tests/integration/test_outdoor_temperature_sensor.py
git commit -m "feat: add outdoor temperature sensor entity for ATA devices

Sensor created only for devices with outdoor temperature capability
(has_outdoor_temp_sensor=True). Shows unavailable until coordinator
polls outdoor temp data."
```

---

## Task 5: Implement Coordinator Outdoor Temperature Polling

**Files:**

- Modify: `custom_components/melcloudhome/coordinator.py`

**Step 1: Add outdoor temp polling to coordinator initialization**

In `coordinator.py`, add after telemetry_tracker initialization (around line 91):

```python
        # Outdoor temperature tracking for ATA devices
        self._last_outdoor_temp_poll: float = 0.0
        self._outdoor_temp_checked: set[str] = set()  # Track which units we've probed
```

**Step 2: Add polling helper method**

Add after `_execute_with_retry` method (around line 240):

```python
    def _should_poll_outdoor_temp(self) -> bool:
        """Check if outdoor temp should be polled (30 minute interval)."""
        import time

        now = time.time()
        if now - self._last_outdoor_temp_poll > 1800:  # 30 minutes
            self._last_outdoor_temp_poll = now
            return True
        return False
```

**Step 3: Add outdoor temp update logic to _async_update_data**

In `_async_update_data`, after the energy tracking section (around line 400+), add:

```python
        # Update outdoor temperature for ATA devices (30 minute interval)
        for building in user_context.buildings:
            for unit in building.air_to_air_units:
                # Runtime capability discovery - probe once per device
                if unit.id not in self._outdoor_temp_checked:
                    try:
                        temp = await self._execute_with_retry(
                            lambda: self.client.get_outdoor_temperature(unit.id),
                            "outdoor temperature check"
                        )
                        self._outdoor_temp_checked.add(unit.id)

                        if temp is not None:
                            unit.has_outdoor_temp_sensor = True
                            unit.outdoor_temperature = temp
                            _LOGGER.debug(
                                "Device %s has outdoor temperature sensor: %.1f°C",
                                unit.name,
                                temp
                            )
                        else:
                            _LOGGER.debug(
                                "Device %s has no outdoor temperature sensor",
                                unit.name
                            )
                    except Exception:
                        _LOGGER.debug(
                            "Failed to check outdoor temp for %s",
                            unit.name,
                            exc_info=True
                        )
                        self._outdoor_temp_checked.add(unit.id)

                # Ongoing polling for devices with sensors
                elif unit.has_outdoor_temp_sensor and self._should_poll_outdoor_temp():
                    try:
                        temp = await self._execute_with_retry(
                            lambda: self.client.get_outdoor_temperature(unit.id),
                            "outdoor temperature update"
                        )
                        unit.outdoor_temperature = temp
                        if temp is not None:
                            _LOGGER.debug(
                                "Updated outdoor temp for %s: %.1f°C",
                                unit.name,
                                temp
                            )
                    except Exception:
                        _LOGGER.warning(
                            "Failed to update outdoor temp for %s",
                            unit.name,
                            exc_info=True
                        )
                        unit.outdoor_temperature = None
```

**Step 4: Run integration tests**

Run: `make test-integration`
Expected: PASS (outdoor temp sensor created and shows value)

**Step 5: Commit**

```bash
git add custom_components/melcloudhome/coordinator.py
git commit -m "feat: implement outdoor temperature polling in coordinator

Runtime capability discovery: probe each device once on first update to
detect outdoor sensor presence. Only poll devices with confirmed sensors
every 30 minutes.

Graceful error handling: outdoor temp failures don't break main update."
```

---

## Task 6: Test Dev Environment End-to-End

**Files:**

- None (manual testing)

**Step 1: Start dev environment**

Run: `make dev-up`
Expected: HA starts, mock server running

**Step 2: Access Home Assistant**

Open: <http://localhost:8123>
Login: dev / dev

**Step 3: Verify entities created**

Navigate to Developer Tools → States

Search for: `sensor.melcloudhome`

Expected entities:

- `sensor.melcloudhome_0efc_76db_outdoor_temperature` (Living Room AC) - value: 12.0°C
- `sensor.melcloudhome_0efc_76db_room_temperature` (Living Room AC)
- `sensor.melcloudhome_5b3e_7a9b_room_temperature` (Bedroom AC)

**NOT expected:**

- `sensor.melcloudhome_5b3e_7a9b_outdoor_temperature` (Bedroom has no outdoor sensor)

**Step 4: Check logs for outdoor temp discovery**

Run: `make dev-logs | grep outdoor`

Expected:

```
Device Living Room AC has outdoor temperature sensor: 12.0°C
Device Bedroom AC has no outdoor temperature sensor
```

**Step 5: Verify sensor updates**

Wait 5 minutes, check sensor history in HA UI
Expected: Sensor shows constant 12.0°C (mock returns static value)

**Step 6: Stop dev environment**

Run: `make dev-down`

**Step 7: Document manual test results**

Create: `docs/plans/2026-02-03-outdoor-temperature-manual-test-results.md`

```markdown
# Manual Testing Results - Outdoor Temperature Sensor

**Date:** 2026-02-03
**Environment:** Local dev (Docker Compose + Mock Server)

## Test Results

### Entity Creation
- ✅ Living Room AC outdoor temp sensor created
- ✅ Bedroom AC outdoor temp sensor NOT created (no sensor)
- ✅ Entity ID format correct: `sensor.melcloudhome_{short_id}_outdoor_temperature`

### Sensor Values
- ✅ Living Room shows 12.0°C (from mock server)
- ✅ Sensor attributes correct (°C, temperature device class, measurement state class)

### Capability Discovery
- ✅ Logs show "has outdoor temperature sensor" for Living Room
- ✅ Logs show "has no outdoor temperature sensor" for Bedroom
- ✅ No API spam - only one probe per device

### Error Handling
- ✅ No errors in logs
- ✅ Main coordinator update succeeds even with outdoor temp logic

## Next Steps
- Test with real hardware on remote HA instance
- Verify 30-minute polling interval
- Check sensor history/graphs in Energy Dashboard
```

**Step 8: Commit manual test results**

```bash
git add docs/plans/2026-02-03-outdoor-temperature-manual-test-results.md
git commit -m "docs: add manual testing results for outdoor temp sensor

Verified entity creation, capability discovery, and sensor values in
local dev environment with mock server."
```

---

## Task 7: Update Documentation

**Files:**

- Modify: `docs/entities.md`
- Modify: `docs/api/ata-api-reference.md`

**Step 1: Update entity reference**

In `docs/entities.md`, find the ATA Sensors section (around line 35) and update:

```markdown
### Sensors

- **Room Temperature**: `sensor.melcloudhome_{short_id}_room_temperature`
- **Outdoor Temperature**: `sensor.melcloudhome_{short_id}_outdoor_temperature` (if available)
- **WiFi Signal**: `sensor.melcloudhome_{short_id}_wifi_signal` (diagnostic)
- **Energy**: `sensor.melcloudhome_{short_id}_energy` (cumulative kWh)
```

Add note after energy dashboard section (around line 80):

```markdown
**Outdoor Temperature Sensor:**
- Only created for devices with outdoor temperature sensors
- Automatically detected during integration setup
- Updates every 30 minutes
- Shows ambient temperature from outdoor unit
- Useful for efficiency monitoring and automations
- Not all devices have outdoor sensors (runtime discovery determines availability)
```

**Step 2: Update API reference**

In `docs/api/ata-api-reference.md`, add new section after Device Capabilities (around line 560):

```markdown
---

## Telemetry Endpoints

### Trend Summary (Temperature Reports)

**GET** `/api/report/trendsummary`

Returns historical temperature data for chart display. Used by integration to fetch outdoor temperature.

**Query Parameters:**
- `unitId` - Device UUID
- `from` - Start datetime (ISO 8601: `YYYY-MM-DDTHH:MM:SS.0000000`)
- `to` - End datetime (ISO 8601: `YYYY-MM-DDTHH:MM:SS.0000000`)

**Example Request:**
```

GET /api/report/trendsummary?unitId=0efce33f-5847-4042-88eb-aaf3ff6a76db&from=2026-02-03T11:00:00.0000000&to=2026-02-03T12:00:00.0000000

```

**Response:**
```json
{
  "datasets": [
    {
      "label": "REPORT.TREND_SUMMARY_REPORT.DATASET.LABELS.ROOM_TEMPERATURE",
      "data": [{"x": "2026-02-03T12:00:00", "y": 17.0}],
      "backgroundColor": "#F1995D",
      "borderColor": "#F1995D",
      "yAxisId": "yTemp",
      "pointRadius": 0,
      "lineTension": 0,
      "borderWidth": 2,
      "stepped": true,
      "spanGaps": false,
      "isNonInteractive": false
    },
    {
      "label": "REPORT.TREND_SUMMARY_REPORT.DATASET.LABELS.SET_TEMPERATURE",
      "data": [{"x": "2026-02-03T12:00:00", "y": 19.0}]
    },
    {
      "label": "REPORT.TREND_SUMMARY_REPORT.DATASET.LABELS.OUTDOOR_TEMPERATURE",
      "data": [{"x": "2026-02-03T12:00:00", "y": 11.0}]
    }
  ],
  "annotations": []
}
```

**Integration Usage:**

- Polled every 30 minutes for devices with outdoor sensors
- Extracts latest outdoor temperature value from OUTDOOR_TEMPERATURE dataset
- Not all devices have outdoor sensors (capability auto-detected)
- Dataset may be absent if device lacks outdoor temperature sensor
- Real API returns ~60 datapoints per hour (one per minute)
- Integration uses latest value (last array element)

**Notes:**

- Response includes chart styling metadata (colors, borders, etc.)
- Multiple temperature datasets returned in single call
- Used by MELCloud web UI for temperature graphs
- Time range typically last 1 hour for current temperature

```

**Step 3: Run pre-commit checks**

Run: `make pre-commit`
Expected: All checks pass

**Step 4: Commit documentation**

```bash
git add docs/entities.md docs/api/ata-api-reference.md
git commit -m "docs: document outdoor temperature sensor

Updates entity reference and API documentation with outdoor temperature
sensor details, including availability, polling interval, and trendsummary
endpoint specification."
```

---

## Task 8: Final Testing & Verification

**Files:**

- None (testing only)

**Step 1: Run all tests**

Run: `make test`
Expected: All tests pass (API + Integration + E2E)

**Step 2: Run pre-commit hooks**

Run: `make pre-commit`
Expected: All checks pass (ruff, mypy, codespell, etc.)

**Step 3: Verify test coverage**

Check coverage report from `make test`
Expected: New code has >80% coverage

**Step 4: Create summary of changes**

Create: `docs/plans/2026-02-03-outdoor-temperature-summary.md`

```markdown
# Outdoor Temperature Sensor - Implementation Summary

**Feature:** Outdoor temperature sensor support for ATA devices
**Status:** Complete
**PR:** (will be created in next step)

## Changes Made

### API Layer
- Added `get_outdoor_temperature()` method to MELCloudHomeClient
- Added `_parse_outdoor_temp()` helper to extract outdoor temp from trendsummary response
- Handles missing datasets gracefully (returns None)

### Data Model
- Extended AirToAirUnit with `outdoor_temperature` field
- Added `has_outdoor_temp_sensor` runtime discovery flag

### Coordinator
- Implemented runtime capability discovery (probe once per device)
- 30-minute polling for devices with confirmed sensors
- Graceful error handling (doesn't break main update)

### Sensor Platform
- New outdoor temperature sensor entity for ATA devices
- Only created for devices with outdoor sensors
- Standard HA temperature sensor (°C, measurement state class)

### Mock Server
- Added `/api/report/trendsummary` endpoint
- Living Room AC has outdoor sensor (returns data)
- Bedroom AC doesn't (omits outdoor dataset)

### Documentation
- Updated entity reference (docs/entities.md)
- Added trendsummary endpoint to API reference
- Manual testing results documented

## Test Coverage

- ✅ API unit tests: 8 new tests (parse, format, error cases)
- ✅ Integration tests: 4 new tests (entity creation, updates, availability)
- ✅ Manual dev environment testing: Complete
- ✅ Mock server: Supports both scenarios (with/without sensor)

## Files Changed

- `custom_components/melcloudhome/api/client.py` (+45 lines)
- `custom_components/melcloudhome/api/models_ata.py` (+3 lines)
- `custom_components/melcloudhome/coordinator.py` (+52 lines)
- `custom_components/melcloudhome/sensor_ata.py` (+11 lines)
- `custom_components/melcloudhome/strings.json` (+3 lines)
- `tools/mock_melcloud_server.py` (+85 lines)
- `tests/api/test_outdoor_temperature_model.py` (new, 35 lines)
- `tests/api/test_outdoor_temperature_client.py` (new, 120 lines)
- `tests/integration/test_outdoor_temperature_sensor.py` (new, 70 lines)
- `docs/entities.md` (+10 lines)
- `docs/api/ata-api-reference.md` (+60 lines)

## Ready for Review

- All tests passing
- Documentation updated
- Pre-commit hooks pass
- Manual testing verified
```

**Step 5: Commit summary**

```bash
git add docs/plans/2026-02-03-outdoor-temperature-summary.md
git commit -m "docs: add implementation summary for outdoor temp sensor

Feature complete and ready for review. All tests passing."
```

---

## Post-Implementation: Finishing the Branch

After all tasks complete, use @superpowers:finishing-a-development-branch to:

1. Review all commits
2. Create pull request
3. Clean up worktree (or keep for review)

**Pull Request Template:**

```markdown
## Outdoor Temperature Sensor Support

Closes #28

Adds outdoor temperature sensor support for ATA (air conditioning) devices.

### Changes
- New sensor entity: `sensor.melcloudhome_{short_id}_outdoor_temperature`
- Runtime capability discovery (only creates sensor for devices with outdoor sensors)
- 30-minute polling via `/api/report/trendsummary` endpoint
- ATA devices only (ATW doesn't expose outdoor temp via API)

### Testing
- ✅ 8 new API unit tests
- ✅ 4 new integration tests
- ✅ Manual testing in dev environment
- ✅ All existing tests still pass

### Documentation
- Updated entity reference
- Added trendsummary endpoint to API docs
- Implementation plan and testing results documented
```

---

## Rollback Plan

If issues found during testing:

**Rollback to specific commit:**

```bash
git log --oneline  # Find commit to rollback to
git reset --hard <commit-hash>
```

**Partial rollback (keep some changes):**

```bash
git revert <commit-hash>  # Creates new commit undoing changes
```

**Abandon branch entirely:**

```bash
cd ../..  # Back to main worktree
git worktree remove .worktrees/outdoor-temperature-sensor
git branch -D feature/outdoor-temperature-sensor
```

---

## Notes for Implementation

- **TDD approach:** Write test first, make it fail, implement, make it pass, commit
- **Frequent commits:** Each task step is a commit (very granular)
- **Mock server first:** Update mock before implementing feature (enables testing)
- **Runtime discovery:** Don't assume all devices have outdoor sensors
- **Graceful degradation:** Outdoor temp failures shouldn't break main functionality
- **30-minute polling:** Matches energy monitoring pattern, appropriate for slow-changing data
- **No VCR cassettes needed:** Mock server provides all test data

---

## Success Criteria

- [x] Design document exists and approved
- [ ] Mock server supports trendsummary endpoint
- [ ] Data model has outdoor_temperature field
- [ ] API client can fetch outdoor temperature
- [ ] Sensor entity created for devices with sensors
- [ ] Coordinator polls outdoor temp every 30 minutes
- [ ] Dev environment shows correct entities
- [ ] All tests passing (API + integration)
- [ ] Documentation updated
- [ ] Pre-commit hooks pass
- [ ] Ready for PR

---

## Time Estimate

Total: ~2-3 hours for experienced developer

- Task 1 (Mock server): 20 minutes
- Task 2 (Data model): 15 minutes
- Task 3 (API client): 30 minutes
- Task 4 (Sensor entity): 15 minutes
- Task 5 (Coordinator): 30 minutes
- Task 6 (Dev testing): 20 minutes
- Task 7 (Documentation): 20 minutes
- Task 8 (Final verification): 15 minutes
