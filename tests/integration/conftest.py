"""Fixtures for Home Assistant integration tests.

These fixtures require pytest-homeassistant-custom-component.
"""

from unittest.mock import AsyncMock, patch

import pytest

# Import fixtures from pytest-homeassistant-custom-component
pytest_plugins = ["pytest_homeassistant_custom_component"]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations in all tests."""
    yield


# Mock path for MELCloudHomeClient in config_flow
MOCK_CLIENT_CONFIG_FLOW = (
    "custom_components.melcloudhome.config_flow.MELCloudHomeClient"
)


@pytest.fixture
def mock_melcloud_client():
    """Mock MELCloudHomeClient for config_flow tests."""
    with patch(MOCK_CLIENT_CONFIG_FLOW) as mock_client:
        client = mock_client.return_value
        client.login = AsyncMock()
        client.close = AsyncMock()
        yield client


@pytest.fixture
def mock_setup_entry():
    """Mock async_setup_entry to skip actual setup during config flow tests."""
    from custom_components.melcloudhome.const import DOMAIN

    with patch(
        f"custom_components.{DOMAIN}.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup
