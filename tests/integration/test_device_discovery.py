"""Tests for MELCloud Home device discovery.

Run with: make test-ha
"""

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.melcloudhome.const import DOMAIN

# Mock where the name is looked up, not where it's defined
MOCK_CLIENT_PATH = "custom_components.melcloudhome.MELCloudHomeClient"


def _create_mock_unit(device_id: str, name: str) -> MagicMock:
    """Create a mock AirToAirUnit."""
    unit = MagicMock()
    unit.id = device_id
    unit.name = name
    return unit


def _create_mock_user_context(device_ids: list[str]) -> MagicMock:
    """Create a mock UserContext with specified devices."""
    context = MagicMock()
    building = MagicMock()
    building.air_to_air_units = [
        _create_mock_unit(device_id, f"Device {device_id}") for device_id in device_ids
    ]
    context.buildings = [building]
    return context


@pytest.mark.asyncio
async def test_initial_device_discovery_logs_count(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that initial setup logs the number of devices found."""
    with patch(MOCK_CLIENT_PATH) as mock_client:
        client = mock_client.return_value
        client.login = AsyncMock()
        client.close = AsyncMock()
        client.get_user_context = AsyncMock(
            return_value=_create_mock_user_context(["device_1", "device_2"])
        )
        type(client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Verify initial discovery logged
        assert "Initial device discovery: 2 device(s) found" in caplog.text


@pytest.mark.asyncio
async def test_known_device_ids_stored(
    hass: HomeAssistant,
) -> None:
    """Test that known device IDs are stored in hass.data."""
    with patch(MOCK_CLIENT_PATH) as mock_client:
        client = mock_client.return_value
        client.login = AsyncMock()
        client.close = AsyncMock()
        client.get_user_context = AsyncMock(
            return_value=_create_mock_user_context(["device_1", "device_2"])
        )
        type(client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Verify known_device_ids stored
        assert "known_device_ids" in hass.data[DOMAIN][entry.entry_id]
        assert hass.data[DOMAIN][entry.entry_id]["known_device_ids"] == {
            "device_1",
            "device_2",
        }


@pytest.mark.asyncio
async def test_device_discovery_detects_new_device(
    hass: HomeAssistant,
) -> None:
    """Test that new devices trigger notification and reload."""
    with patch(MOCK_CLIENT_PATH) as mock_client:
        client = mock_client.return_value
        client.login = AsyncMock()
        client.close = AsyncMock()
        client.get_user_context = AsyncMock(
            return_value=_create_mock_user_context(["device_1"])
        )
        type(client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Import the discovery listener function
        from custom_components.melcloudhome import _create_discovery_listener

        listener = _create_discovery_listener(hass, entry)

        # Simulate coordinator update with new device
        coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        coordinator.data = _create_mock_user_context(["device_1", "device_2"])

        # Entry is already LOADED after async_setup
        with patch.object(hass, "async_create_task") as mock_create_task:
            listener()

            # Verify notification+reload task was scheduled
            mock_create_task.assert_called_once()

            # Verify the task is a coroutine (notification + reload logic)
            task_arg = mock_create_task.call_args[0][0]
            assert task_arg is not None

            # Verify known_device_ids was updated (prevents infinite loop)
            assert "device_2" in hass.data[DOMAIN][entry.entry_id]["known_device_ids"]


@pytest.mark.asyncio
async def test_no_reload_when_no_new_devices(
    hass: HomeAssistant,
) -> None:
    """Test that no reload occurs when device list unchanged."""
    with patch(MOCK_CLIENT_PATH) as mock_client:
        client = mock_client.return_value
        client.login = AsyncMock()
        client.close = AsyncMock()
        client.get_user_context = AsyncMock(
            return_value=_create_mock_user_context(["device_1"])
        )
        type(client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        from custom_components.melcloudhome import _create_discovery_listener

        listener = _create_discovery_listener(hass, entry)

        with patch.object(hass, "async_create_task") as mock_create_task:
            listener()
            mock_create_task.assert_not_called()


@pytest.mark.asyncio
async def test_removed_device_logged_not_reloaded(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that removed devices are logged but don't trigger reload."""
    import logging

    caplog.set_level(logging.WARNING)

    with patch(MOCK_CLIENT_PATH) as mock_client:
        client = mock_client.return_value
        client.login = AsyncMock()
        client.close = AsyncMock()
        client.get_user_context = AsyncMock(
            return_value=_create_mock_user_context(["device_1", "device_2"])
        )
        type(client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        from custom_components.melcloudhome import _create_discovery_listener

        listener = _create_discovery_listener(hass, entry)

        # Simulate coordinator update with one device removed
        coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        coordinator.data = _create_mock_user_context(["device_1"])

        with patch.object(hass, "async_create_task") as mock_create_task:
            listener()
            # No reload should be triggered for removed devices
            mock_create_task.assert_not_called()

        # Verify warning logged
        assert "no longer found" in caplog.text.lower()

        # Verify removed device ID was cleaned up
        assert "device_2" not in hass.data[DOMAIN][entry.entry_id]["known_device_ids"]
        assert "device_1" in hass.data[DOMAIN][entry.entry_id]["known_device_ids"]
