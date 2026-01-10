"""Tests for ATW API control methods.

Contains two types of tests:
1. Validation tests - Fast unit tests for input validation (no network)
2. Mock server integration tests - Full HTTP cycle tests against mock server
"""

import asyncio
import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

from custom_components.melcloudhome.api.client import MELCloudHomeClient

# Skip mock server tests in CI (mock server not running)
skip_if_no_mock_server = pytest.mark.skipif(
    os.getenv("CI") == "true", reason="Mock server not available in CI"
)

# =============================================================================
# Validation Tests (No Network - Fast Unit Tests)
# =============================================================================


@pytest.mark.asyncio
async def test_set_temperature_zone1_below_minimum() -> None:
    """Zone 1 temperature below 10°C should raise ValueError."""
    client = MELCloudHomeClient()

    with pytest.raises(ValueError, match="must be between 10"):
        await client.atw.set_temperature_zone1("unit-id", 9.5)


@pytest.mark.asyncio
async def test_set_temperature_zone1_above_maximum() -> None:
    """Zone 1 temperature above 30°C should raise ValueError."""
    client = MELCloudHomeClient()

    with pytest.raises(ValueError, match="must be between"):
        await client.atw.set_temperature_zone1("unit-id", 35.0)


@pytest.mark.asyncio
async def test_set_temperature_zone2_out_of_range() -> None:
    """Zone 2 temperature out of range should raise ValueError."""
    client = MELCloudHomeClient()

    with pytest.raises(ValueError, match="must be between"):
        await client.atw.set_temperature_zone2("unit-id", 5.0)


@pytest.mark.asyncio
async def test_set_dhw_temperature_below_minimum() -> None:
    """DHW temperature below 40°C should raise ValueError."""
    client = MELCloudHomeClient()

    with pytest.raises(ValueError, match="must be between 40"):
        await client.atw.set_dhw_temperature("unit-id", 35.0)


@pytest.mark.asyncio
async def test_set_dhw_temperature_above_maximum() -> None:
    """DHW temperature above 60°C should raise ValueError."""
    client = MELCloudHomeClient()

    with pytest.raises(ValueError, match="must be between"):
        await client.atw.set_dhw_temperature("unit-id", 70.0)


@pytest.mark.asyncio
async def test_set_mode_zone1_invalid() -> None:
    """Invalid Zone 1 mode should raise ValueError."""
    client = MELCloudHomeClient()

    with pytest.raises(ValueError, match="must be one of"):
        await client.atw.set_mode_zone1("unit-id", "InvalidMode")


@pytest.mark.asyncio
async def test_set_mode_zone2_invalid() -> None:
    """Invalid Zone 2 mode should raise ValueError."""
    client = MELCloudHomeClient()

    with pytest.raises(ValueError, match="must be one of"):
        await client.atw.set_mode_zone2("unit-id", "InvalidMode")


# =============================================================================
# Mock Server Integration Tests
# =============================================================================


@pytest_asyncio.fixture
async def mock_client() -> AsyncIterator[MELCloudHomeClient]:
    """Client connected to mock server (debug mode)."""
    client = MELCloudHomeClient(debug_mode=True)
    await client.login("test@example.com", "password")
    yield client
    await client.close()


@skip_if_no_mock_server
@pytest.mark.asyncio
async def test_mock_set_power_atw_on(mock_client: MELCloudHomeClient) -> None:
    """Test turning ATW heat pump on via mock server."""
    # Get initial state
    ctx = await mock_client.get_user_context()
    atw_unit = ctx.buildings[0].air_to_water_units[0]
    unit_id = atw_unit.id

    # Set power on
    await mock_client.atw.set_power(unit_id, True)

    # Wait for state propagation
    await asyncio.sleep(0.5)

    # Fetch fresh state
    ctx = await mock_client.get_user_context()
    unit = ctx.get_air_to_water_unit_by_id(unit_id)

    # Verify
    assert unit is not None
    assert unit.power is True


@skip_if_no_mock_server
@pytest.mark.asyncio
async def test_mock_set_power_atw_off(mock_client: MELCloudHomeClient) -> None:
    """Test turning ATW heat pump off via mock server."""
    ctx = await mock_client.get_user_context()
    atw_unit = ctx.buildings[0].air_to_water_units[0]
    unit_id = atw_unit.id

    await mock_client.atw.set_power(unit_id, False)
    await asyncio.sleep(0.5)

    ctx = await mock_client.get_user_context()
    unit = ctx.get_air_to_water_unit_by_id(unit_id)

    assert unit is not None
    assert unit.power is False


@skip_if_no_mock_server
@pytest.mark.asyncio
async def test_mock_set_temperature_zone1(mock_client: MELCloudHomeClient) -> None:
    """Test setting Zone 1 target temperature via mock server."""
    ctx = await mock_client.get_user_context()
    atw_unit = ctx.buildings[0].air_to_water_units[0]
    unit_id = atw_unit.id
    target_temp = 22.0

    await mock_client.atw.set_temperature_zone1(unit_id, target_temp)
    await asyncio.sleep(0.5)

    ctx = await mock_client.get_user_context()
    unit = ctx.get_air_to_water_unit_by_id(unit_id)

    assert unit is not None
    assert unit.set_temperature_zone1 == target_temp


@skip_if_no_mock_server
@pytest.mark.asyncio
async def test_mock_set_temperature_zone1_half_degree(
    mock_client: MELCloudHomeClient,
) -> None:
    """Test setting Zone 1 temperature with 0.5° increment via mock server."""
    ctx = await mock_client.get_user_context()
    atw_unit = ctx.buildings[0].air_to_water_units[0]
    unit_id = atw_unit.id
    target_temp = 21.5

    await mock_client.atw.set_temperature_zone1(unit_id, target_temp)
    await asyncio.sleep(0.5)

    ctx = await mock_client.get_user_context()
    unit = ctx.get_air_to_water_unit_by_id(unit_id)

    assert unit is not None
    assert unit.set_temperature_zone1 == target_temp


@skip_if_no_mock_server
@pytest.mark.asyncio
async def test_mock_set_mode_zone1_room_temperature(
    mock_client: MELCloudHomeClient,
) -> None:
    """Test setting Zone 1 to thermostat control mode via mock server."""
    ctx = await mock_client.get_user_context()
    atw_unit = ctx.buildings[0].air_to_water_units[0]
    unit_id = atw_unit.id
    mode = "HeatRoomTemperature"

    await mock_client.atw.set_mode_zone1(unit_id, mode)
    await asyncio.sleep(0.5)

    ctx = await mock_client.get_user_context()
    unit = ctx.get_air_to_water_unit_by_id(unit_id)

    assert unit is not None
    assert unit.operation_mode_zone1 == mode


@skip_if_no_mock_server
@pytest.mark.asyncio
async def test_mock_set_mode_zone1_heat_curve(
    mock_client: MELCloudHomeClient,
) -> None:
    """Test setting Zone 1 to weather compensation mode via mock server."""
    ctx = await mock_client.get_user_context()
    atw_unit = ctx.buildings[0].air_to_water_units[0]
    unit_id = atw_unit.id
    mode = "HeatCurve"

    await mock_client.atw.set_mode_zone1(unit_id, mode)
    await asyncio.sleep(0.5)

    ctx = await mock_client.get_user_context()
    unit = ctx.get_air_to_water_unit_by_id(unit_id)

    assert unit is not None
    assert unit.operation_mode_zone1 == mode


@skip_if_no_mock_server
@pytest.mark.asyncio
async def test_mock_set_dhw_temperature(mock_client: MELCloudHomeClient) -> None:
    """Test setting DHW tank target temperature via mock server."""
    ctx = await mock_client.get_user_context()
    atw_unit = ctx.buildings[0].air_to_water_units[0]
    unit_id = atw_unit.id
    target_temp = 50.0

    await mock_client.atw.set_dhw_temperature(unit_id, target_temp)
    await asyncio.sleep(0.5)

    ctx = await mock_client.get_user_context()
    unit = ctx.get_air_to_water_unit_by_id(unit_id)

    assert unit is not None
    assert unit.set_tank_water_temperature == target_temp


@skip_if_no_mock_server
@pytest.mark.asyncio
async def test_mock_set_forced_hot_water_enable(
    mock_client: MELCloudHomeClient,
) -> None:
    """Test enabling forced DHW priority mode via mock server."""
    ctx = await mock_client.get_user_context()
    atw_unit = ctx.buildings[0].air_to_water_units[0]
    unit_id = atw_unit.id

    await mock_client.atw.set_forced_hot_water(unit_id, True)
    await asyncio.sleep(0.5)

    ctx = await mock_client.get_user_context()
    unit = ctx.get_air_to_water_unit_by_id(unit_id)

    assert unit is not None
    assert unit.forced_hot_water_mode is True


@skip_if_no_mock_server
@pytest.mark.asyncio
async def test_mock_set_forced_hot_water_disable(
    mock_client: MELCloudHomeClient,
) -> None:
    """Test disabling forced DHW mode via mock server."""
    ctx = await mock_client.get_user_context()
    atw_unit = ctx.buildings[0].air_to_water_units[0]
    unit_id = atw_unit.id

    await mock_client.atw.set_forced_hot_water(unit_id, False)
    await asyncio.sleep(0.5)

    ctx = await mock_client.get_user_context()
    unit = ctx.get_air_to_water_unit_by_id(unit_id)

    assert unit is not None
    assert unit.forced_hot_water_mode is False


@skip_if_no_mock_server
@pytest.mark.asyncio
async def test_mock_set_standby_mode(mock_client: MELCloudHomeClient) -> None:
    """Test enabling standby mode via mock server."""
    ctx = await mock_client.get_user_context()
    atw_unit = ctx.buildings[0].air_to_water_units[0]
    unit_id = atw_unit.id

    await mock_client.atw.set_standby_mode(unit_id, True)
    await asyncio.sleep(0.5)

    ctx = await mock_client.get_user_context()
    unit = ctx.get_air_to_water_unit_by_id(unit_id)

    assert unit is not None
    assert unit.in_standby_mode is True
