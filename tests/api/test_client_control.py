"""Tests for MELCloud Home API client - Control operations.

These tests use VCR to record/replay HTTP interactions:
- First run: Records real API calls to cassettes
- Subsequent runs: Replays from cassettes (fast, no API calls)
- To re-record: Delete tests/cassettes/ directory

IMPORTANT: These tests make write operations to real devices.
Only run against test devices where temporary state changes are acceptable.
"""

import asyncio
from typing import TYPE_CHECKING

import pytest

from tests.conftest import VCR_OPERATION_DELAY, VCR_RESTORE_DELAY

if TYPE_CHECKING:
    from custom_components.melcloudhome.api.client import MELCloudHomeClient


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_set_power_on(
    authenticated_client: "MELCloudHomeClient", dining_room_unit_id: str
) -> None:
    """Test turning device on."""
    # Turn device on
    await authenticated_client.ata.set_power(dining_room_unit_id, True)

    # Wait for state to propagate
    await asyncio.sleep(VCR_OPERATION_DELAY)

    # Verify state changed
    context = await authenticated_client.get_user_context()
    device = context.get_unit_by_id(dining_room_unit_id)
    assert device is not None
    assert device.power is True


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_set_power_off(
    authenticated_client: "MELCloudHomeClient", dining_room_unit_id: str
) -> None:
    """Test turning device off."""
    # Turn device off
    await authenticated_client.ata.set_power(dining_room_unit_id, False)

    # Wait for state to propagate
    await asyncio.sleep(VCR_OPERATION_DELAY)

    # Verify state changed
    context = await authenticated_client.get_user_context()
    device = context.get_unit_by_id(dining_room_unit_id)
    assert device is not None
    assert device.power is False


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_set_temperature(
    authenticated_client: "MELCloudHomeClient", dining_room_unit_id: str
) -> None:
    """Test setting target temperature."""
    # Set temperature to 22.0°C
    target_temp = 22.0
    await authenticated_client.ata.set_temperature(dining_room_unit_id, target_temp)

    # Wait for state to propagate
    await asyncio.sleep(VCR_OPERATION_DELAY)

    # Verify state changed
    context = await authenticated_client.get_user_context()
    device = context.get_unit_by_id(dining_room_unit_id)
    assert device is not None
    assert device.set_temperature == target_temp


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_set_temperature_half_degree(
    authenticated_client: "MELCloudHomeClient", dining_room_unit_id: str
) -> None:
    """Test setting temperature with 0.5° increment."""
    # Set temperature to 21.5°C
    target_temp = 21.5
    await authenticated_client.ata.set_temperature(dining_room_unit_id, target_temp)

    # Wait for state to propagate
    await asyncio.sleep(VCR_OPERATION_DELAY)

    # Verify state changed
    context = await authenticated_client.get_user_context()
    device = context.get_unit_by_id(dining_room_unit_id)
    assert device is not None
    assert device.set_temperature == target_temp


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_set_mode_heat(
    authenticated_client: "MELCloudHomeClient", dining_room_unit_id: str
) -> None:
    """Test changing operation mode to Heat."""
    await authenticated_client.ata.set_mode(dining_room_unit_id, "Heat")

    # Wait for state to propagate
    await asyncio.sleep(VCR_OPERATION_DELAY)

    # Verify state changed
    context = await authenticated_client.get_user_context()
    device = context.get_unit_by_id(dining_room_unit_id)
    assert device is not None
    assert device.operation_mode == "Heat"


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_set_mode_cool(
    authenticated_client: "MELCloudHomeClient", dining_room_unit_id: str
) -> None:
    """Test changing operation mode to Cool."""
    await authenticated_client.ata.set_mode(dining_room_unit_id, "Cool")

    # Wait for state to propagate
    await asyncio.sleep(VCR_OPERATION_DELAY)

    # Verify state changed
    context = await authenticated_client.get_user_context()
    device = context.get_unit_by_id(dining_room_unit_id)
    assert device is not None
    assert device.operation_mode == "Cool"


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_set_mode_automatic(
    authenticated_client: "MELCloudHomeClient", dining_room_unit_id: str
) -> None:
    """Test changing operation mode to Automatic."""
    await authenticated_client.ata.set_mode(dining_room_unit_id, "Automatic")

    # Wait for state to propagate
    await asyncio.sleep(VCR_OPERATION_DELAY)

    # Verify state changed
    context = await authenticated_client.get_user_context()
    device = context.get_unit_by_id(dining_room_unit_id)
    assert device is not None
    assert device.operation_mode == "Automatic"


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_set_fan_speed_auto(
    authenticated_client: "MELCloudHomeClient", dining_room_unit_id: str
) -> None:
    """Test setting fan speed to Auto."""
    await authenticated_client.ata.set_fan_speed(dining_room_unit_id, "Auto")

    # Wait for state to propagate
    await asyncio.sleep(VCR_OPERATION_DELAY)

    # Verify state changed
    context = await authenticated_client.get_user_context()
    device = context.get_unit_by_id(dining_room_unit_id)
    assert device is not None
    assert device.set_fan_speed == "Auto"


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_set_fan_speed_three(
    authenticated_client: "MELCloudHomeClient", dining_room_unit_id: str
) -> None:
    """Test setting fan speed to level Three."""
    await authenticated_client.ata.set_fan_speed(dining_room_unit_id, "Three")

    # Wait for state to propagate
    await asyncio.sleep(VCR_OPERATION_DELAY)

    # Verify state changed
    context = await authenticated_client.get_user_context()
    device = context.get_unit_by_id(dining_room_unit_id)
    assert device is not None
    assert device.set_fan_speed == "Three"


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_set_vanes_auto(
    authenticated_client: "MELCloudHomeClient", dining_room_unit_id: str
) -> None:
    """Test setting vanes to Auto."""
    await authenticated_client.ata.set_vanes(dining_room_unit_id, "Auto", "Auto")

    # Wait for state to propagate
    await asyncio.sleep(VCR_OPERATION_DELAY)

    # Verify state changed
    context = await authenticated_client.get_user_context()
    device = context.get_unit_by_id(dining_room_unit_id)
    assert device is not None
    assert device.vane_vertical_direction == "Auto"
    assert device.vane_horizontal_direction == "Auto"


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_set_vanes_swing(
    authenticated_client: "MELCloudHomeClient", dining_room_unit_id: str
) -> None:
    """Test setting vanes to Swing."""
    await authenticated_client.ata.set_vanes(dining_room_unit_id, "Swing", "Swing")

    # Wait for state to propagate
    await asyncio.sleep(VCR_OPERATION_DELAY)

    # Verify state changed
    context = await authenticated_client.get_user_context()
    device = context.get_unit_by_id(dining_room_unit_id)
    assert device is not None
    assert device.vane_vertical_direction == "Swing"
    assert device.vane_horizontal_direction == "Swing"


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_multiple_controls_together(
    authenticated_client: "MELCloudHomeClient", dining_room_unit_id: str
) -> None:
    """Test setting multiple controls in sequence.

    This test verifies that multiple control operations can be
    executed one after another without conflicts.
    """
    # Set power on, mode to Heat, temp to 20°C, fan to Auto
    await authenticated_client.ata.set_power(dining_room_unit_id, True)
    await asyncio.sleep(VCR_RESTORE_DELAY)

    await authenticated_client.ata.set_mode(dining_room_unit_id, "Heat")
    await asyncio.sleep(VCR_RESTORE_DELAY)

    await authenticated_client.ata.set_temperature(dining_room_unit_id, 20.0)
    await asyncio.sleep(VCR_RESTORE_DELAY)

    await authenticated_client.ata.set_fan_speed(dining_room_unit_id, "Auto")
    await asyncio.sleep(VCR_OPERATION_DELAY)

    # Verify all state changes
    context = await authenticated_client.get_user_context()
    device = context.get_unit_by_id(dining_room_unit_id)
    assert device is not None
    assert device.power is True
    assert device.operation_mode == "Heat"
    assert device.set_temperature == 20.0
    assert device.set_fan_speed == "Auto"
