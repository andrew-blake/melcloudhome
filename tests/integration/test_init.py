"""Tests for MELCloud Home integration setup.

These tests require pytest-homeassistant-custom-component which provides
mock Home Assistant fixtures. They run in Docker or CI.

Run with: make test-ha
"""

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.melcloudhome.const import DOMAIN

# Mock where the name is looked up, not where it's defined
# __init__.py IS the melcloudhome module (not __init__ submodule)
MOCK_CLIENT_PATH = "custom_components.melcloudhome.MELCloudHomeClient"


def _create_mock_user_context() -> MagicMock:
    """Create a mock UserContext with empty buildings."""
    context = MagicMock()
    context.buildings = []
    return context


@pytest.mark.asyncio
async def test_force_refresh_service_registered(
    hass: HomeAssistant,
) -> None:
    """Test force refresh service is registered on setup."""
    with patch(MOCK_CLIENT_PATH) as mock_client:
        client = mock_client.return_value
        client.login = AsyncMock()
        client.close = AsyncMock()
        client.get_user_context = AsyncMock(return_value=_create_mock_user_context())
        # is_authenticated is a @property - use PropertyMock
        type(client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Verify service registered
        assert hass.services.has_service(DOMAIN, "force_refresh")


@pytest.mark.asyncio
async def test_force_refresh_service_unregistered_on_last_unload(
    hass: HomeAssistant,
) -> None:
    """Test force refresh service is unregistered when last entry unloaded."""
    with patch(MOCK_CLIENT_PATH) as mock_client:
        client = mock_client.return_value
        client.login = AsyncMock()
        client.close = AsyncMock()
        client.get_user_context = AsyncMock(return_value=_create_mock_user_context())
        # is_authenticated is a @property - use PropertyMock
        type(client).is_authenticated = PropertyMock(return_value=True)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password"},
            unique_id="test@example.com",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert hass.services.has_service(DOMAIN, "force_refresh")

        # Unload entry
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

        # Verify service unregistered
        assert not hass.services.has_service(DOMAIN, "force_refresh")
