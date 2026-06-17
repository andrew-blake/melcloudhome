"""Tests for MELCloud Home ATA sensor entities.

Tests cover sensor entity creation, state updates, and conditional creation.
Follows HA best practices: test observable behavior through hass.states, not internals.

Reference: docs/testing-best-practices.md
Run with: make test-integration
"""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant

from .conftest import (
    create_mock_ata_building,
    create_mock_ata_unit,
    create_mock_ata_user_context,
    setup_ata_integration_custom,
)

MOCK_STORE_PATH = "custom_components.melcloudhome.energy_tracker_base.Store"


def _create_mock_energy_response(wh_value: float) -> dict:
    return {
        "measureData": [
            {
                "measure": "cumulative_energy_consumed_since_last_upload",
                "unit": "Wh",
                "values": [{"time": "2025-01-15T10:00:00Z", "value": wh_value}],
            }
        ]
    }


@pytest.mark.asyncio
async def test_sensor_entity_creation(hass: HomeAssistant) -> None:
    """Test that all sensor entities are created correctly."""
    unit_with_energy = create_mock_ata_unit(has_energy_meter=True)
    mock_context = create_mock_ata_user_context(
        [create_mock_ata_building(units=[unit_with_energy])]
    )
    mock_energy_data = _create_mock_energy_response(5500.0)

    def configure(client: Any) -> None:
        client.get_energy_data = AsyncMock(return_value=mock_energy_data)

    with patch(MOCK_STORE_PATH) as mock_store_class:
        mock_store = mock_store_class.return_value
        mock_store.async_load = AsyncMock(return_value=None)
        mock_store.async_save = AsyncMock()

        await setup_ata_integration_custom(
            hass, mock_context, configure_client=configure
        )

        temp_state = hass.states.get("sensor.melcloudhome_a1b2_9abc_room_temperature")
        assert temp_state is not None
        assert float(temp_state.state) == 20.0
        assert temp_state.attributes["unit_of_measurement"] == "°C"
        assert temp_state.attributes["device_class"] == "temperature"

        wifi_state = hass.states.get("sensor.melcloudhome_a1b2_9abc_wifi_signal")
        assert wifi_state is not None
        assert int(wifi_state.state) == -50
        assert wifi_state.attributes["unit_of_measurement"] == "dBm"
        assert wifi_state.attributes["device_class"] == "signal_strength"

        energy_state = hass.states.get("sensor.melcloudhome_a1b2_9abc_energy")
        assert energy_state is not None
        assert float(energy_state.state) == 0.0  # First init starts at 0
        assert energy_state.attributes["unit_of_measurement"] == "kWh"
        assert energy_state.attributes["device_class"] == "energy"


@pytest.mark.asyncio
async def test_energy_sensor_conditional_creation(hass: HomeAssistant) -> None:
    """Test that energy sensor is only created for units with energy meter capability."""
    unit_with_energy = create_mock_ata_unit(
        unit_id="aaaa1234-5678-9abc-def0-123456789999",
        name="Unit With Energy",
        has_energy_meter=True,
    )
    unit_without_energy = create_mock_ata_unit(
        unit_id="bbbb1234-5678-9abc-def0-123456788888",
        name="Unit Without Energy",
        has_energy_meter=False,
    )
    mock_context = create_mock_ata_user_context(
        [create_mock_ata_building(units=[unit_with_energy, unit_without_energy])]
    )
    mock_energy_data = _create_mock_energy_response(10000.0)

    def configure(client: Any) -> None:
        client.get_energy_data = AsyncMock(return_value=mock_energy_data)

    with patch(MOCK_STORE_PATH) as mock_store_class:
        mock_store = mock_store_class.return_value
        mock_store.async_load = AsyncMock(return_value=None)
        mock_store.async_save = AsyncMock()

        await setup_ata_integration_custom(
            hass, mock_context, configure_client=configure
        )

        energy_state_1 = hass.states.get("sensor.melcloudhome_aaaa_9999_energy")
        assert energy_state_1 is not None
        assert float(energy_state_1.state) == 0.0

        energy_state_2 = hass.states.get("sensor.melcloudhome_bbbb_8888_energy")
        assert energy_state_2 is None

        assert (
            hass.states.get("sensor.melcloudhome_aaaa_9999_room_temperature")
            is not None
        )
        assert (
            hass.states.get("sensor.melcloudhome_bbbb_8888_room_temperature")
            is not None
        )


@pytest.mark.asyncio
async def test_sensor_state_updates_on_refresh(hass: HomeAssistant) -> None:
    """Test that sensor values update when coordinator refreshes."""
    initial_unit = create_mock_ata_unit(room_temperature=20.0, rssi=-50)
    initial_context = create_mock_ata_user_context(
        [create_mock_ata_building(units=[initial_unit])]
    )
    updated_unit = create_mock_ata_unit(room_temperature=22.0, rssi=-45)
    updated_context = create_mock_ata_user_context(
        [create_mock_ata_building(units=[updated_unit])]
    )

    def configure(client: Any) -> None:
        client.get_user_context = AsyncMock(
            side_effect=[initial_context, updated_context]
        )

    await setup_ata_integration_custom(
        hass, initial_context, configure_client=configure
    )

    temp_state = hass.states.get("sensor.melcloudhome_a1b2_9abc_room_temperature")
    assert float(temp_state.state) == 20.0

    from custom_components.melcloudhome.const import DOMAIN

    await hass.services.async_call(DOMAIN, "force_refresh", {}, blocking=True)
    await hass.async_block_till_done()

    assert (
        float(hass.states.get("sensor.melcloudhome_a1b2_9abc_room_temperature").state)
        == 22.0
    )
    assert (
        int(hass.states.get("sensor.melcloudhome_a1b2_9abc_wifi_signal").state) == -45
    )


@pytest.mark.asyncio
async def test_energy_sensor_availability(hass: HomeAssistant) -> None:
    """Test that energy sensor availability depends on data presence."""
    unit_with_energy = create_mock_ata_unit(has_energy_meter=True)
    mock_context = create_mock_ata_user_context(
        [create_mock_ata_building(units=[unit_with_energy])]
    )
    no_energy_data: dict = {"measureData": []}

    def configure(client: Any) -> None:
        client.get_energy_data = AsyncMock(return_value=no_energy_data)

    with patch(MOCK_STORE_PATH) as mock_store_class:
        mock_store = mock_store_class.return_value
        mock_store.async_load = AsyncMock(return_value=None)
        mock_store.async_save = AsyncMock()

        await setup_ata_integration_custom(
            hass, mock_context, configure_client=configure
        )

        energy_state = hass.states.get("sensor.melcloudhome_a1b2_9abc_energy")
        assert energy_state is not None
        assert energy_state.state == "unavailable"

        temp_state = hass.states.get("sensor.melcloudhome_a1b2_9abc_room_temperature")
        assert temp_state is not None
        assert float(temp_state.state) == 20.0
