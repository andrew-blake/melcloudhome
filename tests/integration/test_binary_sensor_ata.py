"""Tests for MELCloud Home ATA binary sensor entities.

Tests cover binary sensor entity creation, connection/error state reporting.
Follows HA best practices: test observable behavior through hass.states, not internals.

Reference: docs/testing-best-practices.md
Run with: make test-integration
"""

from unittest.mock import AsyncMock

import pytest
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from custom_components.melcloudhome.api.models_ata import ProtectionModeState

from .conftest import (
    create_mock_ata_building,
    create_mock_ata_unit,
    create_mock_ata_user_context,
    setup_ata_integration_custom,
)


@pytest.mark.asyncio
async def test_binary_sensor_entity_creation(hass: HomeAssistant) -> None:
    """Test that binary sensor entities are created for each unit."""
    mock_context = create_mock_ata_user_context()
    await setup_ata_integration_custom(hass, mock_context)

    error_state = hass.states.get("binary_sensor.melcloudhome_a1b2_9abc_error_state")
    connection_state = hass.states.get(
        "binary_sensor.melcloudhome_a1b2_9abc_connection_state"
    )

    assert error_state is not None
    assert error_state.attributes["device_class"] == "problem"

    assert connection_state is not None
    assert connection_state.attributes["device_class"] == "connectivity"


@pytest.mark.asyncio
async def test_error_state_sensor_reflects_unit_status(hass: HomeAssistant) -> None:
    """Test that error state sensor reflects unit error status."""
    unit_with_error = create_mock_ata_unit(is_in_error=True)
    mock_context = create_mock_ata_user_context(
        [create_mock_ata_building(units=[unit_with_error])]
    )
    _, mock_client = await setup_ata_integration_custom(hass, mock_context)

    error_sensor_id = "binary_sensor.melcloudhome_a1b2_9abc_error_state"
    assert hass.states.get(error_sensor_id).state == STATE_ON  # ON = problem exists

    # Update to no-error state and refresh
    unit_no_error = create_mock_ata_unit(is_in_error=False)
    mock_context_updated = create_mock_ata_user_context(
        [create_mock_ata_building(units=[unit_no_error])]
    )
    mock_client.get_user_context = AsyncMock(return_value=mock_context_updated)

    from custom_components.melcloudhome.const import DOMAIN

    await hass.services.async_call(DOMAIN, "force_refresh", {}, blocking=True)
    await hass.async_block_till_done()

    assert hass.states.get(error_sensor_id).state == STATE_OFF


@pytest.mark.asyncio
async def test_error_state_sensor_exposes_error_code(hass: HomeAssistant) -> None:
    """Test that error state sensor exposes the device error code as attribute."""
    unit_with_error = create_mock_ata_unit(is_in_error=True, error_code="E6")
    mock_context = create_mock_ata_user_context(
        [create_mock_ata_building(units=[unit_with_error])]
    )
    await setup_ata_integration_custom(hass, mock_context)

    error_state = hass.states.get("binary_sensor.melcloudhome_a1b2_9abc_error_state")
    assert error_state.state == STATE_ON
    assert error_state.attributes["error_code"] == "E6"


@pytest.mark.asyncio
async def test_error_state_sensor_error_code_none_when_no_error(
    hass: HomeAssistant,
) -> None:
    """Test that error code attribute is None when device has no error."""
    mock_context = create_mock_ata_user_context()
    await setup_ata_integration_custom(hass, mock_context)

    error_state = hass.states.get("binary_sensor.melcloudhome_a1b2_9abc_error_state")
    assert error_state.state == STATE_OFF
    assert error_state.attributes["error_code"] is None


@pytest.mark.asyncio
async def test_connection_state_sensor_reflects_coordinator_status(
    hass: HomeAssistant,
) -> None:
    """Test that connection state sensor reflects coordinator update success."""
    mock_context = create_mock_ata_user_context()
    _, mock_client = await setup_ata_integration_custom(hass, mock_context)

    connection_sensor_id = "binary_sensor.melcloudhome_a1b2_9abc_connection_state"
    assert hass.states.get(connection_sensor_id).state == STATE_ON  # Connected

    from custom_components.melcloudhome.api.exceptions import ApiError
    from custom_components.melcloudhome.const import DOMAIN

    mock_client.get_user_context = AsyncMock(side_effect=ApiError("Connection failed"))
    await hass.services.async_call(DOMAIN, "force_refresh", {}, blocking=True)
    await hass.async_block_till_done()

    assert hass.states.get(connection_sensor_id).state == STATE_OFF


@pytest.mark.asyncio
async def test_error_sensor_unavailable_when_coordinator_fails(
    hass: HomeAssistant,
) -> None:
    """Test that error state sensor becomes unavailable when coordinator fails."""
    mock_context = create_mock_ata_user_context()
    _, mock_client = await setup_ata_integration_custom(hass, mock_context)

    error_sensor_id = "binary_sensor.melcloudhome_a1b2_9abc_error_state"
    assert hass.states.get(error_sensor_id).state != "unavailable"

    from custom_components.melcloudhome.api.exceptions import ApiError
    from custom_components.melcloudhome.const import DOMAIN

    mock_client.get_user_context = AsyncMock(side_effect=ApiError("Connection failed"))
    await hass.services.async_call(DOMAIN, "force_refresh", {}, blocking=True)
    await hass.async_block_till_done()

    assert hass.states.get(error_sensor_id).state == "unavailable"


@pytest.mark.asyncio
async def test_connection_sensor_always_available(hass: HomeAssistant) -> None:
    """Test that connection state sensor is always available, even when coordinator fails."""
    mock_context = create_mock_ata_user_context()
    _, mock_client = await setup_ata_integration_custom(hass, mock_context)

    from custom_components.melcloudhome.api.exceptions import ApiError
    from custom_components.melcloudhome.const import DOMAIN

    mock_client.get_user_context = AsyncMock(side_effect=ApiError("Connection failed"))
    await hass.services.async_call(DOMAIN, "force_refresh", {}, blocking=True)
    await hass.async_block_till_done()

    connection_sensor_id = "binary_sensor.melcloudhome_a1b2_9abc_connection_state"
    connection_state = hass.states.get(connection_sensor_id)
    assert connection_state is not None
    assert connection_state.state == STATE_OFF  # Shows disconnection, not unavailable


@pytest.mark.asyncio
async def test_frost_protection_only_created_when_configured(
    hass: HomeAssistant,
) -> None:
    """Test frost protection sensor is only created for units with the mode ever set."""
    unit_with_frost = create_mock_ata_unit(
        unit_id="aaaa1234-5678-9abc-def0-123456789999",
        name="Unit With Frost",
        frost_protection=ProtectionModeState(
            enabled=True, active=False, min=10, max=12
        ),
    )
    unit_without_frost = create_mock_ata_unit(
        unit_id="bbbb1234-5678-9abc-def0-123456788888",
        name="Unit Without Frost",
    )
    mock_context = create_mock_ata_user_context(
        [create_mock_ata_building(units=[unit_with_frost, unit_without_frost])]
    )
    await setup_ata_integration_custom(hass, mock_context)

    with_frost_state = hass.states.get(
        "binary_sensor.melcloudhome_aaaa_9999_frost_protection"
    )
    without_frost_state = hass.states.get(
        "binary_sensor.melcloudhome_bbbb_8888_frost_protection"
    )

    assert with_frost_state is not None
    assert without_frost_state is None


@pytest.mark.asyncio
async def test_protection_mode_state_reflects_enabled_flag(hass: HomeAssistant) -> None:
    """Test protection mode sensors report on/off based on 'enabled', not 'active'.

    'enabled' (armed/configured) is what a user checks after toggling the mode
    in the MELCloud app - 'active' (currently engaging, e.g. room actually
    crossed the threshold) is a rarer condition, exposed as an attribute instead.
    """
    unit = create_mock_ata_unit(
        overheat_protection=ProtectionModeState(
            enabled=True, active=False, min=35, max=37
        ),
    )
    mock_context = create_mock_ata_user_context(
        [create_mock_ata_building(units=[unit])]
    )
    await setup_ata_integration_custom(hass, mock_context)

    state = hass.states.get("binary_sensor.melcloudhome_a1b2_9abc_overheat_protection")
    assert state is not None
    assert state.state == STATE_ON


@pytest.mark.asyncio
async def test_protection_mode_active_attribute_exposed(hass: HomeAssistant) -> None:
    """Test the 'active' attribute is exposed on the protection mode sensor.

    min/max are separate sensor entities (see test_sensor_ata.py), not
    attributes here, so this only covers 'active'.
    """
    unit = create_mock_ata_unit(
        frost_protection=ProtectionModeState(
            enabled=True, active=False, min=10, max=12
        ),
    )
    mock_context = create_mock_ata_user_context(
        [create_mock_ata_building(units=[unit])]
    )
    await setup_ata_integration_custom(hass, mock_context)

    state = hass.states.get("binary_sensor.melcloudhome_a1b2_9abc_frost_protection")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes["active"] is False
    assert "min" not in state.attributes
    assert "max" not in state.attributes


@pytest.mark.asyncio
async def test_holiday_mode_active_attribute_exposed(hass: HomeAssistant) -> None:
    """Test the 'active' attribute is exposed on the holiday mode sensor.

    start_date/end_date are separate sensor entities (see test_sensor_ata.py).
    """
    unit = create_mock_ata_unit(
        holiday_mode=ProtectionModeState(
            enabled=True,
            active=True,
            start_date="2026-07-20T18:30:53.79",
            end_date="2026-07-22T12:00:00",
        ),
    )
    mock_context = create_mock_ata_user_context(
        [create_mock_ata_building(units=[unit])]
    )
    await setup_ata_integration_custom(hass, mock_context)

    state = hass.states.get("binary_sensor.melcloudhome_a1b2_9abc_holiday_mode")
    assert state is not None
    assert state.attributes["active"] is True
    assert "start_date" not in state.attributes
    assert "end_date" not in state.attributes
