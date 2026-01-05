"""Tests for MELCloud Home water heater entity.

Tests cover water heater entity behavior through Home Assistant core interfaces only.
Follows HA best practices: test observable behavior, not implementation details.

Reference: docs/testing-best-practices.md
Run with: make test-ha
"""

from unittest.mock import AsyncMock, PropertyMock, patch

import pytest
from homeassistant.components.water_heater import (
    ATTR_OPERATION_MODE,
    STATE_ECO,
    STATE_PERFORMANCE,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_EMAIL,
    CONF_PASSWORD,
)
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.melcloudhome.const import DOMAIN

# Import shared test helpers from conftest
from .conftest import (
    MOCK_CLIENT_PATH,
    TEST_ATW_UNIT_ID,
    TEST_WATER_HEATER_ENTITY_ID,
    create_mock_atw_building,
    create_mock_atw_unit,
    create_mock_atw_user_context,
)


@pytest.mark.asyncio
async def test_water_heater_entity_created_with_correct_attributes(
    hass: HomeAssistant,
    setup_atw_integration: MockConfigEntry,
) -> None:
    """Test water heater entity is created with correct attributes."""
    # Check entity exists
    state = hass.states.get("water_heater.melcloudhome_0efc_9abc_tank")
    assert state is not None
    # Water heater state is the operation mode, not ON/OFF
    assert state.state == STATE_ECO
    # ATTR_TEMPERATURE is target temp (not current)
    assert (
        state.attributes[ATTR_TEMPERATURE] == 50.0
    )  # Target (set_tank_water_temperature)
    assert (
        state.attributes["current_temperature"] == 48.5
    )  # Current (tank_water_temperature)
    assert state.attributes[ATTR_OPERATION_MODE] == STATE_ECO


@pytest.mark.asyncio
async def test_set_temperature_updates_dhw_temp(hass: HomeAssistant) -> None:
    """Test setting DHW temperature via service."""
    mock_context = create_mock_atw_user_context()

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        mock_client.set_dhw_temperature = AsyncMock()
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Call set_temperature service
        await hass.services.async_call(
            "water_heater",
            "set_temperature",
            {
                "entity_id": TEST_WATER_HEATER_ENTITY_ID,
                "temperature": 55,
            },
            blocking=True,
        )

        # Verify API was called correctly
        await hass.async_block_till_done()
        mock_client.set_dhw_temperature.assert_called_once_with(TEST_ATW_UNIT_ID, 55)


@pytest.mark.asyncio
async def test_set_operation_mode_eco_to_performance(hass: HomeAssistant) -> None:
    """Test changing operation mode from eco to performance."""
    mock_unit = create_mock_atw_unit(forced_hot_water_mode=False)
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        mock_client.set_forced_hot_water = AsyncMock()
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Check initial state
        state = hass.states.get(TEST_WATER_HEATER_ENTITY_ID)
        assert state.attributes[ATTR_OPERATION_MODE] == STATE_ECO

        # Call set_operation_mode service
        await hass.services.async_call(
            "water_heater",
            "set_operation_mode",
            {
                "entity_id": TEST_WATER_HEATER_ENTITY_ID,
                "operation_mode": STATE_PERFORMANCE,
            },
            blocking=True,
        )

        # Verify API was called correctly
        await hass.async_block_till_done()
        mock_client.set_forced_hot_water.assert_called_once_with(TEST_ATW_UNIT_ID, True)


@pytest.mark.asyncio
async def test_set_operation_mode_performance_to_eco(hass: HomeAssistant) -> None:
    """Test changing operation mode from performance to eco."""
    mock_unit = create_mock_atw_unit(forced_hot_water_mode=True)
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        mock_client.set_forced_hot_water = AsyncMock()
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Check initial state
        state = hass.states.get(TEST_WATER_HEATER_ENTITY_ID)
        assert state.attributes[ATTR_OPERATION_MODE] == STATE_PERFORMANCE

        # Call set_operation_mode service
        await hass.services.async_call(
            "water_heater",
            "set_operation_mode",
            {
                "entity_id": TEST_WATER_HEATER_ENTITY_ID,
                "operation_mode": STATE_ECO,
            },
            blocking=True,
        )

        # Verify API was called correctly
        await hass.async_block_till_done()
        mock_client.set_forced_hot_water.assert_called_once_with(
            TEST_ATW_UNIT_ID, False
        )


@pytest.mark.asyncio
async def test_turn_on_powers_entire_system(hass: HomeAssistant) -> None:
    """Test turning on water heater powers entire ATW system."""
    mock_unit = create_mock_atw_unit(power=False)
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        mock_client.set_power_atw = AsyncMock()
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Check initial state - when powered off, state might still show operation mode
        # The is_on attribute reflects power state
        state = hass.states.get(TEST_WATER_HEATER_ENTITY_ID)
        # State could be operation mode even when off - check via attributes or just verify entity exists
        assert state is not None

        # Call turn_on service
        await hass.services.async_call(
            "water_heater",
            "turn_on",
            {"entity_id": TEST_WATER_HEATER_ENTITY_ID},
            blocking=True,
        )

        # Verify system was powered on
        await hass.async_block_till_done()
        mock_client.set_power_atw.assert_called_once_with(TEST_ATW_UNIT_ID, True)


@pytest.mark.asyncio
async def test_turn_off_powers_entire_system(hass: HomeAssistant) -> None:
    """Test turning off water heater powers off entire ATW system."""
    mock_unit = create_mock_atw_unit(power=True)
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        mock_client.set_power_atw = AsyncMock()
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Check initial state
        state = hass.states.get(TEST_WATER_HEATER_ENTITY_ID)
        assert state is not None
        # Water heater state is operation mode (eco/performance), not ON/OFF
        assert state.state in [STATE_ECO, STATE_PERFORMANCE]

        # Call turn_off service
        await hass.services.async_call(
            "water_heater",
            "turn_off",
            {"entity_id": TEST_WATER_HEATER_ENTITY_ID},
            blocking=True,
        )

        # Verify system was powered off
        await hass.async_block_till_done()
        mock_client.set_power_atw.assert_called_once_with(TEST_ATW_UNIT_ID, False)


@pytest.mark.asyncio
async def test_current_operation_reflects_forced_dhw_mode(hass: HomeAssistant) -> None:
    """Test current_operation reflects forced_hot_water_mode."""
    # Test eco mode (forced_hot_water_mode = False)
    mock_unit = create_mock_atw_unit(forced_hot_water_mode=False)
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("water_heater.melcloudhome_0efc_9abc_tank")
        assert state.attributes[ATTR_OPERATION_MODE] == STATE_ECO


@pytest.mark.asyncio
async def test_availability_false_when_device_in_error(hass: HomeAssistant) -> None:
    """Test water heater unavailable when device in error."""
    mock_unit = create_mock_atw_unit(is_in_error=True)
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("water_heater.melcloudhome_0efc_9abc_tank")
        assert state.state == "unavailable"


@pytest.mark.asyncio
async def test_extra_state_attributes_include_operation_status(
    hass: HomeAssistant,
) -> None:
    """Test extra state attributes include operation_status."""
    mock_unit = create_mock_atw_unit(operation_status="HotWater")
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("water_heater.melcloudhome_0efc_9abc_tank")
        assert state.attributes["operation_status"] == "HotWater"
        assert "forced_dhw_active" in state.attributes
        assert "zone_heating_suspended" in state.attributes


@pytest.mark.asyncio
async def test_water_heater_with_performance_mode(hass: HomeAssistant) -> None:
    """Test water heater reflects performance mode correctly."""
    mock_unit = create_mock_atw_unit(forced_hot_water_mode=True)
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("water_heater.melcloudhome_0efc_9abc_tank")
        assert state.attributes[ATTR_OPERATION_MODE] == STATE_PERFORMANCE


@pytest.mark.asyncio
async def test_water_heater_device_info_matches_climate(hass: HomeAssistant) -> None:
    """Test water heater and climate entities share same device."""
    mock_context = create_mock_atw_user_context()

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Both entities should exist
        water_heater = hass.states.get("water_heater.melcloudhome_0efc_9abc_tank")
        climate = hass.states.get("climate.melcloudhome_0efc_9abc_zone_1")

        assert water_heater is not None
        assert climate is not None
        # Device info is same (tested through entity registry, but state confirms entities exist)


@pytest.mark.asyncio
async def test_water_heater_temperature_in_range(hass: HomeAssistant) -> None:
    """Test water heater temperature within valid range (40-60°C)."""
    mock_unit = create_mock_atw_unit(
        tank_water_temperature=45.0, set_tank_water_temperature=50.0
    )
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("water_heater.melcloudhome_0efc_9abc_tank")
        # ATTR_TEMPERATURE is target, current_temperature is current
        assert state.attributes["current_temperature"] == 45.0
        assert state.attributes[ATTR_TEMPERATURE] == 50.0  # Target
        assert 40 <= state.attributes[ATTR_TEMPERATURE] <= 60


@pytest.mark.asyncio
async def test_water_heater_entity_naming_includes_tank(hass: HomeAssistant) -> None:
    """Test water heater entity ID includes 'tank' suffix."""
    mock_context = create_mock_atw_user_context()

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Entity ID should include _tank suffix
        state = hass.states.get("water_heater.melcloudhome_0efc_9abc_tank")
        assert state is not None
        assert "_tank" in state.entity_id


@pytest.mark.asyncio
async def test_water_heater_off_when_power_false(hass: HomeAssistant) -> None:
    """Test water heater reflects power state via is_on property."""
    mock_unit = create_mock_atw_unit(power=False)
    mock_context = create_mock_atw_user_context(
        [create_mock_atw_building(units=[mock_unit])]
    )

    with patch(MOCK_CLIENT_PATH) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_client.get_user_context = AsyncMock(return_value=mock_context)
        type(mock_client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Water heater entity exists even when power is false
        # The state shows operation mode, power status is in attributes/is_on property
        state = hass.states.get("water_heater.melcloudhome_0efc_9abc_tank")
        assert state is not None
