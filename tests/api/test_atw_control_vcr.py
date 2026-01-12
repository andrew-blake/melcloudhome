"""VCR tests for ATW control operations using real API.

These tests record actual API interactions with a real ATW device.
Separate from test_atw_control.py which contains validation + mock server tests.

These tests use VCR to record/replay HTTP interactions:
- First run: Records real API calls to cassettes
- Subsequent runs: Replays from cassettes (fast, no API calls)
- To re-record: Delete specific cassette files in tests/api/cassettes/

IMPORTANT: These tests make write operations to a real ATW heat pump.
- Always reads current state before modifying
- Makes small, safe changes (±0.5°C)
- Restores original state after each test
- Uses 1-2 second sleeps for API propagation
"""

import asyncio
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from custom_components.melcloudhome.api.client import MELCloudHomeClient


# ============================================================================
# Priority 1: Power Control
# ============================================================================


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_atw_set_power_on(
    authenticated_client: "MELCloudHomeClient", atw_unit_id: str
) -> None:
    """Test turning ATW system power on."""
    # Turn system on
    await authenticated_client.atw.set_power(atw_unit_id, True)

    # Wait for state to propagate
    await asyncio.sleep(2)

    # Verify state changed
    context = await authenticated_client.get_user_context()
    unit = context.get_air_to_water_unit_by_id(atw_unit_id)
    assert unit is not None
    assert unit.power is True


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_atw_set_power_off(
    authenticated_client: "MELCloudHomeClient", atw_unit_id: str
) -> None:
    """Test turning ATW system power off."""
    # Turn system off
    await authenticated_client.atw.set_power(atw_unit_id, False)

    # Wait for state to propagate
    await asyncio.sleep(2)

    # Verify state changed
    context = await authenticated_client.get_user_context()
    unit = context.get_air_to_water_unit_by_id(atw_unit_id)
    assert unit is not None
    assert unit.power is False


# ============================================================================
# Priority 2: Zone 1 Temperature Control
# ============================================================================


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_atw_set_temperature_zone1(
    authenticated_client: "MELCloudHomeClient", atw_unit_id: str
) -> None:
    """Test setting Zone 1 target temperature with safe restore pattern."""
    # 1. Get current state
    context = await authenticated_client.get_user_context()
    unit = context.get_air_to_water_unit_by_id(atw_unit_id)
    assert unit is not None

    original_temp = unit.set_temperature_zone1
    original_power = unit.power

    # Ensure we have a valid temperature to work with
    assert original_temp is not None, "Zone 1 temperature not available"

    # 2. CRITICAL: Turn system ON first (controls may not work when off)
    if not original_power:
        await authenticated_client.atw.set_power(atw_unit_id, True)
        await asyncio.sleep(2)

    # 3. Make small, safe change (+0.5°C)
    new_temp = original_temp + 0.5
    await authenticated_client.atw.set_temperature_zone1(atw_unit_id, new_temp)

    # 4. Wait for API to propagate
    await asyncio.sleep(2)

    # 5. Verify change applied
    context = await authenticated_client.get_user_context()
    unit = context.get_air_to_water_unit_by_id(atw_unit_id)
    assert unit is not None
    assert unit.set_temperature_zone1 is not None
    assert abs(unit.set_temperature_zone1 - new_temp) < 0.1

    # 6. RESTORE: Temperature first, then power
    await authenticated_client.atw.set_temperature_zone1(atw_unit_id, original_temp)
    await asyncio.sleep(1)

    if not original_power:
        await authenticated_client.atw.set_power(atw_unit_id, False)
        await asyncio.sleep(1)

    # 7. Verify restoration
    context = await authenticated_client.get_user_context()
    unit = context.get_air_to_water_unit_by_id(atw_unit_id)
    assert unit is not None
    assert unit.set_temperature_zone1 is not None
    assert abs(unit.set_temperature_zone1 - original_temp) < 0.1
    assert unit.power == original_power


# ============================================================================
# Priority 3: DHW (Domestic Hot Water) Temperature Control
# ============================================================================


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_atw_set_dhw_temperature(
    authenticated_client: "MELCloudHomeClient", atw_unit_id: str
) -> None:
    """Test setting DHW tank target temperature with safe restore pattern."""
    # 1. Get current state
    context = await authenticated_client.get_user_context()
    unit = context.get_air_to_water_unit_by_id(atw_unit_id)
    assert unit is not None

    original_temp = unit.set_tank_water_temperature
    original_power = unit.power

    # Ensure we have a valid temperature to work with
    assert original_temp is not None, "DHW temperature not available"

    # 2. CRITICAL: Turn system ON first (controls may not work when off)
    if not original_power:
        await authenticated_client.atw.set_power(atw_unit_id, True)
        await asyncio.sleep(2)

    # 3. Make small, safe change (+0.5°C)
    new_temp = original_temp + 0.5
    await authenticated_client.atw.set_dhw_temperature(atw_unit_id, new_temp)

    # 4. Wait for API to propagate
    await asyncio.sleep(2)

    # 5. Verify change applied
    context = await authenticated_client.get_user_context()
    unit = context.get_air_to_water_unit_by_id(atw_unit_id)
    assert unit is not None
    assert unit.set_tank_water_temperature is not None
    assert abs(unit.set_tank_water_temperature - new_temp) < 0.1

    # 6. RESTORE: Temperature first, then power
    await authenticated_client.atw.set_dhw_temperature(atw_unit_id, original_temp)
    await asyncio.sleep(1)

    if not original_power:
        await authenticated_client.atw.set_power(atw_unit_id, False)
        await asyncio.sleep(1)

    # 7. Verify restoration
    context = await authenticated_client.get_user_context()
    unit = context.get_air_to_water_unit_by_id(atw_unit_id)
    assert unit is not None
    assert unit.set_tank_water_temperature is not None
    assert abs(unit.set_tank_water_temperature - original_temp) < 0.1
    assert unit.power == original_power


# ============================================================================
# Priority 4: Forced Hot Water Control
# ============================================================================


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_atw_set_forced_hot_water_on(
    authenticated_client: "MELCloudHomeClient", atw_unit_id: str
) -> None:
    """Test enabling forced DHW mode (DHW priority heating)."""
    # 1. Get current state
    context = await authenticated_client.get_user_context()
    unit = context.get_air_to_water_unit_by_id(atw_unit_id)
    assert unit is not None

    original_forced = unit.forced_hot_water_mode
    original_power = unit.power

    # 2. CRITICAL: Turn system ON first (controls may not work when off)
    if not original_power:
        await authenticated_client.atw.set_power(atw_unit_id, True)
        await asyncio.sleep(2)

    # 3. Enable forced DHW mode
    await authenticated_client.atw.set_forced_hot_water(atw_unit_id, True)

    # 4. Wait for API to propagate
    await asyncio.sleep(2)

    # 5. Verify change applied
    context = await authenticated_client.get_user_context()
    unit = context.get_air_to_water_unit_by_id(atw_unit_id)
    assert unit is not None
    assert unit.forced_hot_water_mode is True

    # 6. RESTORE: Forced DHW first, then power
    await authenticated_client.atw.set_forced_hot_water(atw_unit_id, original_forced)
    await asyncio.sleep(1)

    if not original_power:
        await authenticated_client.atw.set_power(atw_unit_id, False)
        await asyncio.sleep(1)

    # 7. Verify restoration
    context = await authenticated_client.get_user_context()
    unit = context.get_air_to_water_unit_by_id(atw_unit_id)
    assert unit is not None
    assert unit.forced_hot_water_mode == original_forced
    assert unit.power == original_power


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_atw_set_forced_hot_water_off(
    authenticated_client: "MELCloudHomeClient", atw_unit_id: str
) -> None:
    """Test disabling forced DHW mode."""
    # 1. Get current state
    context = await authenticated_client.get_user_context()
    unit = context.get_air_to_water_unit_by_id(atw_unit_id)
    assert unit is not None

    original_forced = unit.forced_hot_water_mode
    original_power = unit.power

    # 2. CRITICAL: Turn system ON first (controls may not work when off)
    if not original_power:
        await authenticated_client.atw.set_power(atw_unit_id, True)
        await asyncio.sleep(2)

    # 3. Disable forced DHW mode
    await authenticated_client.atw.set_forced_hot_water(atw_unit_id, False)

    # 4. Wait for API to propagate
    await asyncio.sleep(2)

    # 5. Verify change applied
    context = await authenticated_client.get_user_context()
    unit = context.get_air_to_water_unit_by_id(atw_unit_id)
    assert unit is not None
    assert unit.forced_hot_water_mode is False

    # 6. RESTORE: Forced DHW first, then power
    await authenticated_client.atw.set_forced_hot_water(atw_unit_id, original_forced)
    await asyncio.sleep(1)

    if not original_power:
        await authenticated_client.atw.set_power(atw_unit_id, False)
        await asyncio.sleep(1)

    # 7. Verify restoration
    context = await authenticated_client.get_user_context()
    unit = context.get_air_to_water_unit_by_id(atw_unit_id)
    assert unit is not None
    assert unit.forced_hot_water_mode == original_forced
    assert unit.power == original_power


# ============================================================================
# Priority 5: Zone 1 Mode Control
# ============================================================================


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_atw_set_mode_zone1_heat_room_temperature(
    authenticated_client: "MELCloudHomeClient", atw_unit_id: str
) -> None:
    """Test setting Zone 1 to HeatRoomTemperature mode (thermostat control)."""
    # 1. Get current state
    context = await authenticated_client.get_user_context()
    unit = context.get_air_to_water_unit_by_id(atw_unit_id)
    assert unit is not None

    original_mode = unit.operation_mode_zone1
    original_power = unit.power

    # 2. CRITICAL: Turn system ON first (controls may not work when off)
    if not original_power:
        await authenticated_client.atw.set_power(atw_unit_id, True)
        await asyncio.sleep(2)

    # 3. Set mode to HeatRoomTemperature
    await authenticated_client.atw.set_mode_zone1(atw_unit_id, "HeatRoomTemperature")

    # 4. Wait for API to propagate
    await asyncio.sleep(2)

    # 5. Verify change applied
    context = await authenticated_client.get_user_context()
    unit = context.get_air_to_water_unit_by_id(atw_unit_id)
    assert unit is not None
    assert unit.operation_mode_zone1 == "HeatRoomTemperature"

    # 6. RESTORE: Mode first, then power
    await authenticated_client.atw.set_mode_zone1(atw_unit_id, original_mode)
    await asyncio.sleep(1)

    if not original_power:
        await authenticated_client.atw.set_power(atw_unit_id, False)
        await asyncio.sleep(1)

    # 7. Verify restoration
    context = await authenticated_client.get_user_context()
    unit = context.get_air_to_water_unit_by_id(atw_unit_id)
    assert unit is not None
    assert unit.operation_mode_zone1 == original_mode
    assert unit.power == original_power


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_atw_set_mode_zone1_heat_flow_temperature(
    authenticated_client: "MELCloudHomeClient", atw_unit_id: str
) -> None:
    """Test setting Zone 1 to HeatFlowTemperature mode (direct flow control)."""
    # 1. Get current state
    context = await authenticated_client.get_user_context()
    unit = context.get_air_to_water_unit_by_id(atw_unit_id)
    assert unit is not None

    original_mode = unit.operation_mode_zone1
    original_power = unit.power

    # 2. CRITICAL: Turn system ON first (controls may not work when off)
    if not original_power:
        await authenticated_client.atw.set_power(atw_unit_id, True)
        await asyncio.sleep(2)

    # 3. Set mode to HeatFlowTemperature
    await authenticated_client.atw.set_mode_zone1(atw_unit_id, "HeatFlowTemperature")

    # 4. Wait for API to propagate
    await asyncio.sleep(2)

    # 5. Verify change applied
    context = await authenticated_client.get_user_context()
    unit = context.get_air_to_water_unit_by_id(atw_unit_id)
    assert unit is not None
    assert unit.operation_mode_zone1 == "HeatFlowTemperature"

    # 6. RESTORE: Mode first, then power
    await authenticated_client.atw.set_mode_zone1(atw_unit_id, original_mode)
    await asyncio.sleep(1)

    if not original_power:
        await authenticated_client.atw.set_power(atw_unit_id, False)
        await asyncio.sleep(1)

    # 7. Verify restoration
    context = await authenticated_client.get_user_context()
    unit = context.get_air_to_water_unit_by_id(atw_unit_id)
    assert unit is not None
    assert unit.operation_mode_zone1 == original_mode
    assert unit.power == original_power


# ============================================================================
# Priority 6: Standby Mode Control
# ============================================================================


@pytest.mark.skip(reason="This specific device doesn't support entering standby mode")
@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_atw_set_standby_mode_on(
    authenticated_client: "MELCloudHomeClient", atw_unit_id: str
) -> None:
    """Test enabling standby mode (frost protection only)."""
    # 1. Get current state
    context = await authenticated_client.get_user_context()
    unit = context.get_air_to_water_unit_by_id(atw_unit_id)
    assert unit is not None

    original_standby = unit.in_standby_mode
    original_power = unit.power

    # 2. CRITICAL: Turn system ON first (controls may not work when off)
    if not original_power:
        await authenticated_client.atw.set_power(atw_unit_id, True)
        await asyncio.sleep(2)

    # 3. Enable standby mode
    await authenticated_client.atw.set_standby_mode(atw_unit_id, True)

    # 4. Wait for API to propagate
    await asyncio.sleep(2)

    # 5. Verify change applied
    context = await authenticated_client.get_user_context()
    unit = context.get_air_to_water_unit_by_id(atw_unit_id)
    assert unit is not None
    assert unit.in_standby_mode is True

    # 6. RESTORE: Standby mode first, then power
    await authenticated_client.atw.set_standby_mode(atw_unit_id, original_standby)
    await asyncio.sleep(1)

    if not original_power:
        await authenticated_client.atw.set_power(atw_unit_id, False)
        await asyncio.sleep(1)

    # 7. Verify restoration
    context = await authenticated_client.get_user_context()
    unit = context.get_air_to_water_unit_by_id(atw_unit_id)
    assert unit is not None
    assert unit.in_standby_mode == original_standby
    assert unit.power == original_power


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_atw_set_standby_mode_off(
    authenticated_client: "MELCloudHomeClient", atw_unit_id: str
) -> None:
    """Test disabling standby mode."""
    # 1. Get current state
    context = await authenticated_client.get_user_context()
    unit = context.get_air_to_water_unit_by_id(atw_unit_id)
    assert unit is not None

    original_standby = unit.in_standby_mode
    original_power = unit.power

    # 2. CRITICAL: Turn system ON first (controls may not work when off)
    if not original_power:
        await authenticated_client.atw.set_power(atw_unit_id, True)
        await asyncio.sleep(2)

    # 3. Disable standby mode
    await authenticated_client.atw.set_standby_mode(atw_unit_id, False)

    # 4. Wait for API to propagate
    await asyncio.sleep(2)

    # 5. Verify change applied
    context = await authenticated_client.get_user_context()
    unit = context.get_air_to_water_unit_by_id(atw_unit_id)
    assert unit is not None
    assert unit.in_standby_mode is False

    # 6. RESTORE: Standby mode first, then power
    await authenticated_client.atw.set_standby_mode(atw_unit_id, original_standby)
    await asyncio.sleep(1)

    if not original_power:
        await authenticated_client.atw.set_power(atw_unit_id, False)
        await asyncio.sleep(1)

    # 7. Verify restoration
    context = await authenticated_client.get_user_context()
    unit = context.get_air_to_water_unit_by_id(atw_unit_id)
    assert unit is not None
    assert unit.in_standby_mode == original_standby
    assert unit.power == original_power
