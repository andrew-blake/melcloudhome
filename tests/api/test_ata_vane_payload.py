"""Unit tests for ATA vane control request payloads (issue #100).

Verifies that the decoupled vane methods send the correct PUT payload — the
untouched axis MUST be sent as null. This matches the official MELCloud app
and prevents server-side cross-axis validation from silently dropping the
request on units without horizontal vanes.

These tests mock the HTTP layer; they do not hit the network or use VCR.
"""

from unittest.mock import AsyncMock

import pytest

from custom_components.melcloudhome.api.client import MELCloudHomeClient


@pytest.mark.asyncio
async def test_set_vane_vertical_sends_null_for_horizontal(mocker):
    """V-only update must send vaneHorizontalDirection=null."""
    client = MELCloudHomeClient()
    mock_request = mocker.patch.object(client, "_api_request", new=AsyncMock())

    await client.ata.set_vane_vertical("unit-xyz", "Swing")

    mock_request.assert_awaited_once()
    _, kwargs = mock_request.call_args
    payload = kwargs["json"]
    # Word form, not numeric — matches the official mobile app's payload shape
    # captured via mitmproxy. Sending numeric "7" was a holdover from the legacy
    # web API and is the likely trigger for issue #100 (server validation matrix
    # rejecting numeric Swing on units without horizontal vanes).
    assert payload["vaneVerticalDirection"] == "Swing"
    assert payload["vaneHorizontalDirection"] is None


@pytest.mark.asyncio
async def test_set_vane_horizontal_sends_null_for_vertical(mocker):
    """H-only update must send vaneVerticalDirection=null."""
    client = MELCloudHomeClient()
    mock_request = mocker.patch.object(client, "_api_request", new=AsyncMock())

    await client.ata.set_vane_horizontal("unit-xyz", "Centre")

    mock_request.assert_awaited_once()
    _, kwargs = mock_request.call_args
    payload = kwargs["json"]
    assert payload["vaneHorizontalDirection"] == "Centre"
    assert payload["vaneVerticalDirection"] is None
