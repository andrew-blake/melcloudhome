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


@pytest.mark.asyncio
async def test_set_power_and_mode_carries_the_speed_and_nulls_the_rest(mocker):
    """Power, mode and speed in one request; every other field still null.

    Two requests to one unit are spaced by the pacer's minimum, and a command
    arriving that close behind another can be accepted by the cloud and ignored
    by the device (ADR-026), so a power-on that also sets a speed is one PUT.
    The untouched fields stay null for the same reason the vane axes do above.
    """
    client = MELCloudHomeClient()
    mock_request = mocker.patch.object(client, "_api_request", new=AsyncMock())

    await client.ata.set_power_and_mode("unit-xyz", True, "Cool", "Five")

    _, kwargs = mock_request.call_args
    payload = kwargs["json"]
    assert payload["power"] is True
    assert payload["operationMode"] == "Cool"
    assert payload["setFanSpeed"] == "Five"
    assert payload["vaneVerticalDirection"] is None
    assert payload["vaneHorizontalDirection"] is None
    assert payload["setTemperature"] is None


@pytest.mark.asyncio
async def test_set_power_and_mode_omits_the_speed_when_none_is_given(mocker):
    """The climate entity's power-on carries no speed, and must not invent one."""
    client = MELCloudHomeClient()
    mock_request = mocker.patch.object(client, "_api_request", new=AsyncMock())

    await client.ata.set_power_and_mode("unit-xyz", True, "Cool")

    _, kwargs = mock_request.call_args
    assert kwargs["json"]["setFanSpeed"] is None


@pytest.mark.asyncio
async def test_set_power_and_mode_rejects_an_invalid_speed(mocker):
    """A bad speed must be refused here rather than sent.

    The server has been seen to accept a field combination it cannot honour,
    answering 200 and silently dropping the part it did not like (issue #100).
    A speed riding along with a power-on would fail that way rather than being
    refused, so it is validated before the request is built.
    """
    client = MELCloudHomeClient()
    mock_request = mocker.patch.object(client, "_api_request", new=AsyncMock())

    with pytest.raises(ValueError, match="Invalid fan speed"):
        await client.ata.set_power_and_mode("unit-xyz", True, "Cool", "Eleven")

    mock_request.assert_not_awaited()
