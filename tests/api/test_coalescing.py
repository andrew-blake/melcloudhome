"""Unit tests for control-write coalescing."""

import asyncio
from typing import Any

import pytest

from custom_components.melcloudhome.api.coalescing import WriteCoalescer


def _recorder() -> tuple[list[tuple[str, dict[str, Any]]], Any]:
    """A send function that records what it was asked to send."""
    sent: list[tuple[str, dict[str, Any]]] = []

    async def send(unit_id: str, fields: dict[str, Any]) -> None:
        sent.append((unit_id, fields))

    return sent, send


@pytest.mark.asyncio
async def test_same_turn_writes_share_one_request():
    sent, send = _recorder()
    c = WriteCoalescer(send)

    await asyncio.gather(
        c.submit("unit-1", {"power": True}),
        c.submit("unit-1", {"setTemperature": 21.0}),
    )

    assert len(sent) == 1
    assert sent[0][1] == {"power": True, "setTemperature": 21.0}


@pytest.mark.asyncio
async def test_neither_field_is_lost_to_the_other():
    """The sparse merge must not carry a null that erases the other write."""
    sent, send = _recorder()
    c = WriteCoalescer(send)

    await asyncio.gather(
        c.submit("unit-1", {"power": True, "operationMode": "Heat"}),
        c.submit("unit-1", {"setTemperature": 21.0}),
    )

    assert sent[0][1]["power"] is True
    assert sent[0][1]["operationMode"] == "Heat"
    assert sent[0][1]["setTemperature"] == 21.0


@pytest.mark.asyncio
async def test_different_units_do_not_merge():
    sent, send = _recorder()
    c = WriteCoalescer(send)

    await asyncio.gather(
        c.submit("unit-1", {"power": True}),
        c.submit("unit-2", {"power": True}),
    )

    assert len(sent) == 2


@pytest.mark.asyncio
async def test_a_write_arriving_mid_request_is_not_lost():
    """The pending entry must leave the map before the request is awaited.

    A sequential pair does not test this: the first completes before the second
    begins, so it passes even with the removal deleted. The send has to be held
    open so a write genuinely arrives while the request is in flight.
    """
    gate = asyncio.Event()
    sent: list[dict[str, Any]] = []

    async def send(unit_id: str, fields: dict[str, Any]) -> None:
        sent.append(fields)
        await gate.wait()

    c = WriteCoalescer(send, window=0.001)
    first = asyncio.create_task(c.submit("unit-1", {"power": True}))
    await asyncio.sleep(0.02)  # first is now blocked inside send()
    late = asyncio.create_task(c.submit("unit-1", {"setTemperature": 21.0}))
    await asyncio.sleep(0.02)
    gate.set()
    await asyncio.gather(first, late)

    assert len(sent) == 2
    assert sent[0] == {"power": True}
    assert sent[1] == {"setTemperature": 21.0}


@pytest.mark.asyncio
async def test_a_cancelled_caller_still_sends_its_fields():
    """Documents a real consequence rather than asserting it is desirable.

    A caller cancelled after joining a pending write has already contributed
    its fields, and the request carries them. A cancelled service call
    therefore still reaches the device.
    """
    sent, send = _recorder()
    c = WriteCoalescer(send, window=0.05)

    doomed = asyncio.create_task(c.submit("unit-1", {"power": True}))
    survivor = asyncio.create_task(c.submit("unit-1", {"setTemperature": 21.0}))
    await asyncio.sleep(0)
    doomed.cancel()

    await survivor
    assert sent[0][1]["power"] is True


@pytest.mark.asyncio
async def test_the_later_value_wins_for_one_field():
    sent, send = _recorder()
    c = WriteCoalescer(send)

    await asyncio.gather(
        c.submit("unit-1", {"setFanSpeed": "Two"}),
        c.submit("unit-1", {"setFanSpeed": "Five"}),
    )

    assert len(sent) == 1
    assert sent[0][1]["setFanSpeed"] == "Five"


@pytest.mark.asyncio
async def test_the_vane_axes_never_share_a_request():
    """Issue #100: the server drops a cross-axis combination silently."""
    sent, send = _recorder()
    c = WriteCoalescer(send)

    await asyncio.gather(
        c.submit("unit-1", {"vaneVerticalDirection": "Swing"}),
        c.submit("unit-1", {"vaneHorizontalDirection": "Centre"}),
    )

    assert len(sent) == 2
    for _, fields in sent:
        assert not {"vaneVerticalDirection", "vaneHorizontalDirection"} <= fields.keys()


@pytest.mark.asyncio
async def test_a_failure_reaches_every_caller():
    async def send(unit_id: str, fields: dict[str, Any]) -> None:
        raise RuntimeError("boom")

    c = WriteCoalescer(send)

    results = await asyncio.gather(
        c.submit("unit-1", {"power": True}),
        c.submit("unit-1", {"setTemperature": 21.0}),
        return_exceptions=True,
    )

    assert all(isinstance(r, RuntimeError) for r in results)


@pytest.mark.asyncio
async def test_cancelling_one_caller_leaves_the_others_alone():
    sent, send = _recorder()
    c = WriteCoalescer(send, window=0.05)

    doomed = asyncio.create_task(c.submit("unit-1", {"power": True}))
    survivor = asyncio.create_task(c.submit("unit-1", {"setTemperature": 21.0}))
    await asyncio.sleep(0)
    doomed.cancel()

    await survivor
    assert len(sent) == 1
    assert sent[0][1]["setTemperature"] == 21.0
