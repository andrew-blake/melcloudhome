"""Tests for MELCloud Home API client - Read operations only.

These tests use VCR to record/replay HTTP interactions:
- First run: Records real API calls to cassettes
- Subsequent runs: Replays from cassettes (fast, no API calls)
- To re-record: Delete tests/cassettes/ directory
"""

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from custom_components.melcloudhome.api.client import MELCloudHomeClient


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_get_devices(authenticated_client: "MELCloudHomeClient") -> None:
    """Test fetching all devices from the API."""
    devices = await authenticated_client.get_devices()

    # Should have at least one device
    assert len(devices) >= 1

    # Check that devices have expected attributes
    for device in devices:
        assert device.id is not None
        assert device.name is not None
        assert isinstance(device.power, bool)

    # Check that all devices have names (will be redacted in cassettes)
    device_names = [d.name for d in devices]
    assert len(device_names) >= 1
    assert all(isinstance(name, str) and len(name) > 0 for name in device_names)


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_get_device_by_id(
    authenticated_client: "MELCloudHomeClient", dining_room_unit_id: str
) -> None:
    """Test fetching a specific device by ID."""
    device = await authenticated_client.get_device(dining_room_unit_id)

    assert device is not None
    assert device.id == dining_room_unit_id
    # Device name exists and is non-empty (will be redacted in cassettes)
    assert isinstance(device.name, str)
    assert len(device.name) > 0

    # Check state attributes exist
    assert device.power is not None
    assert device.operation_mode is not None
    assert device.set_temperature is not None
    assert device.room_temperature is not None


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_device_state_attributes(
    authenticated_client: "MELCloudHomeClient", dining_room_unit_id: str
) -> None:
    """Test that device state includes all expected attributes."""
    device = await authenticated_client.get_device(dining_room_unit_id)

    # Core attributes
    assert hasattr(device, "id")
    assert hasattr(device, "name")
    assert hasattr(device, "power")
    assert hasattr(device, "operation_mode")

    # Temperature attributes
    assert hasattr(device, "set_temperature")
    assert hasattr(device, "room_temperature")

    # Control attributes
    assert hasattr(device, "set_fan_speed")
    assert hasattr(device, "vane_vertical_direction")
    assert hasattr(device, "vane_horizontal_direction")

    # Validate types where applicable
    assert device is not None  # For mypy
    if device.set_temperature is not None:
        assert isinstance(device.set_temperature, int | float)
        assert 10.0 <= device.set_temperature <= 31.0

    if device.room_temperature is not None:
        assert isinstance(device.room_temperature, int | float)


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_multiple_devices_consistency(
    authenticated_client: "MELCloudHomeClient",
) -> None:
    """Test that calling get_devices multiple times returns consistent data."""
    devices1 = await authenticated_client.get_devices()
    devices2 = await authenticated_client.get_devices()

    # Should return same number of devices
    assert len(devices1) == len(devices2)

    # Device IDs should be the same
    ids1 = sorted([d.id for d in devices1])
    ids2 = sorted([d.id for d in devices2])
    assert ids1 == ids2
