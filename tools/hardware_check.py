#!/usr/bin/env python3
"""Drive control-write checks against the production Home Assistant and read the log back.

The integration suite proves the control clients send what they should. This proves what
the cloud and the unit do with it, which no mock reproduces: the optimistic state a poll
returns inside a minute of a command, the device's own report that overrides it, and the
loss of a command that follows another too closely. See docs/testing/manual-hardware-checks.md
for the matrix these checks fill and for how to read the lines this prints.

    uv run python tools/hardware_check.py [-k] [--no-debug] [--entity FAN_ENTITY] CHECK ...

Checks:
    state               current fan, climate and actual-fan-speed state, no writes
    reversal            A -> B -> A speeds, three seconds apart: expect three speed writes
    same-value          the current speed sent twice: expect two speed writes
    same-value-sweep    every other ATA setter sent its own current value twice, through the
                        climate entity: temperature, both vanes and fan mode
    combined-write      a mode and a temperature in one service call: expect one PUT, and the
                        unit reporting the temperature it was asked for
    off-behind-on       from off, power on then off --gap seconds later, then wait --settle
                        seconds for the device report and say whether the off held
    restart-after-zero  zero, a one-second pause, then 40: expect off, on, speed
    out-of-band-match   set a speed through the MELCloud API outside HA, wait for HA to
                        show it, send the same speed through HA: expect the write (#135)

Reads HA_URL, HA_TOKEN, HA_SSH_HOST and HA_CONTAINER from the repo .env; out-of-band-match
also needs MELCLOUD_USER_OWNER and MELCLOUD_PASSWORD_OWNER. -k disables TLS verification:
the LAN hostname in HA_URL serves a certificate issued for another name, and the public
hostname sits behind Cloudflare Access and refuses API tokens. Unless --no-debug, the
melcloudhome, homekit and pyhap loggers run at debug for the check and are restored after;
the Setting lines are INFO but the polls, deltas and PUT statuses that make sense of them
are DEBUG. Every check leaves the unit in the power state it found.

This moves real hardware. Do not point it at units that are not yours.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
LOG_PATTERN = re.compile(
    r"Setting |API Response: PUT|WebSocket delta|ATA Poll|client_update_value"
    r"|set_value:|Listener update failed|Request pacing"
)
# Lines worth printing that carry no unit id at all, so the per-unit filter can
# never pass them: the write-through's failure path, and both directions of the
# HomeKit bridge. Filtering these out made a dump look empty rather than
# unmatched, which is how the bridge was wrongly read as having stopped pushing.
UNIT_AGNOSTIC = re.compile(
    r"Listener update failed|client_update_value|set_value:|Request pacing"
)
# api/pacing.py DEFAULT_MIN_REQUEST_INTERVAL. One pacer per client, the lock held
# across each request, so two PUTs cannot leave less than this far apart however
# close together the service calls are made.
PACER_FLOOR = 0.5

# A contradiction arriving this soon after our command is more likely the
# device's own report of the *previous* state, generated before our command
# reached it and delivered afterwards, than proof the command was lost. The
# device reports on its own clock, tens of seconds to minutes, so a report that
# still contradicts us well beyond this had time to know better. Recorded losses
# have contradicted at 33s, 63s and beyond; the one case at 2.7s was ambiguous
# and is why this exists.
LAG_SUSPECT_SECONDS = 15.0
ANSI = re.compile(r"\x1b\[[0-9;]*m")
# Prod's configuration.yaml pins child loggers individually, and a pinned child
# ignores its parent's level, so naming only the parent leaves the coordinator
# and climate at info: the ATA Poll and WebSocket delta lines in LOG_PATTERN
# then never appear and the dump looks like a poll that never ran. Loggers with
# no pin (the control clients, fan, api.client) inherit and need no entry.
# api.models and api.models_atw are pinned too but are parse-level noise.
DEBUG_LOGGERS = {
    "custom_components.melcloudhome": ("debug", "info"),
    "custom_components.melcloudhome.coordinator": ("debug", "info"),
    "custom_components.melcloudhome.climate": ("debug", "info"),
    "homeassistant.components.homekit": ("debug", "warning"),
    "pyhap": ("debug", "warning"),
}


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    env_file = REPO / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip().strip('"').strip("'")
    env.update(
        {
            k: v
            for k, v in os.environ.items()
            if k
            in {
                "HA_URL",
                "HA_TOKEN",
                "HA_SSH_HOST",
                "HA_CONTAINER",
                "MELCLOUD_USER_OWNER",
                "MELCLOUD_PASSWORD_OWNER",
            }
        }
    )
    return env


class HomeAssistant:
    """Minimal REST client for the checks; one place for TLS and auth."""

    def __init__(self, base: str, token: str, insecure: bool) -> None:
        if not base.startswith(("https://", "http://")):
            sys.exit(f"HA_URL must be http(s), got {base!r}")
        self.base = base.rstrip("/")
        self.token = token
        self.ctx = ssl.create_default_context()
        if insecure:
            self.ctx.check_hostname = False
            self.ctx.verify_mode = ssl.CERT_NONE
            print("! TLS verification disabled (-k)", file=sys.stderr)

    def call(self, path: str, payload: dict[str, Any] | None = None) -> Any:
        req = urllib.request.Request(  # noqa: S310  scheme checked in __init__
            self.base + path,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            method="POST" if payload is not None else "GET",
        )
        with urllib.request.urlopen(req, timeout=30, context=self.ctx) as resp:  # noqa: S310
            return json.loads(resp.read() or b"null")

    def state(self, entity: str) -> dict[str, Any]:
        result: dict[str, Any] = self.call(f"/api/states/{entity}")
        return result

    def service(self, domain: str, name: str, **data: Any) -> None:
        self.call(f"/api/services/{domain}/{name}", data)

    def set_levels(self, which: int) -> None:
        self.call(
            "/api/services/logger/set_level",
            {k: v[which] for k, v in DEBUG_LOGGERS.items()},
        )


class Unit:
    """The fan entity under test and its neighbours, found from the fan entity id."""

    def __init__(self, ha: HomeAssistant, fan_entity: str) -> None:
        self.ha = ha
        self.fan = fan_entity
        self.tail4 = fan_entity.split("_a_c_fan")[0][-4:]
        states = ha.call("/api/states")
        self.climate = next(
            (
                s["entity_id"]
                for s in states
                if s["entity_id"].startswith("climate.")
                and self.tail4 in s["entity_id"]
                and "_zone_" not in s["entity_id"]
            ),
            None,
        )
        self.actual = next(
            (
                s["entity_id"]
                for s in states
                if s["entity_id"].startswith("sensor.")
                and self.tail4 in s["entity_id"]
                and "actual_fan" in s["entity_id"]
            ),
            None,
        )

    def display_name(self) -> str:
        """The name the coordinator logs polls under, e.g. "Dining Room".

        `ATA Poll` lines name the unit rather than carrying its id, so the log
        filter needs this as well as the id fragment or it drops every poll.
        """
        friendly: str = self.ha.state(self.fan)["attributes"].get("friendly_name", "")
        return friendly.replace(" A/C fan", "").strip()

    def speed_steps(self) -> list[int]:
        """The percentages this unit's slider can actually take.

        percentage_step is 100 / speed_count, so a three-speed ducted unit has
        detents at 33/67/100 and none at 40 or 60.
        """
        step = self.ha.state(self.fan)["attributes"].get("percentage_step")
        if not step:
            return []
        count = round(100 / step)
        return [round(100 * i / count) for i in range(1, count + 1)]

    def speed_word(self, percentage: int) -> str:
        """The API's name for a percentage, e.g. 40 -> "two" on a five-speed unit."""
        steps = self.speed_steps()
        words = ["one", "two", "three", "four", "five"]
        return words[steps.index(percentage)]

    def preset(self) -> str | None:
        """The fan entity's preset, "auto" when the unit picks its own speed."""
        value = self.ha.state(self.fan)["attributes"].get("preset_mode")
        return None if value is None else str(value)

    def state_changed_at(self) -> datetime:
        """When the fan entity's state last changed, in UTC.

        After a settle in which the device contradicted us, this is when that
        contradiction landed, and the distance from our command is what
        separates a lost command from a late report.
        """
        stamp: str = self.ha.state(self.fan)["last_changed"]
        return datetime.fromisoformat(stamp)

    def actual_stamp(self) -> str | None:
        """When the actual-fan-speed sensor last changed, the device's own signal.

        The only reading in a run that does not come from our own write-through,
        so it is the one thing that can confirm the device acted.
        """
        if not self.actual:
            return None
        stamp: str = self.ha.state(self.actual)["last_changed"]
        return stamp

    def snapshot(self) -> str:
        fan = self.ha.state(self.fan)
        parts = [f"fan {fan['state']} {fan['attributes'].get('percentage')}%"]
        if self.climate:
            climate = self.ha.state(self.climate)
            parts.append(
                f"climate {climate['state']}/{climate['attributes'].get('hvac_action')} fan_mode={climate['attributes'].get('fan_mode')}"
            )
        if self.actual:
            actual = self.ha.state(self.actual)
            parts.append(
                f"actual_fan={actual['state']} (since {actual['last_changed'][11:19]}Z)"
            )
        return " | ".join(parts)

    def percentage(self) -> int | None:
        value = self.ha.state(self.fan)["attributes"].get("percentage")
        return None if value is None else int(value)

    def is_on(self) -> bool:
        return bool(self.ha.state(self.fan)["state"] == "on")

    def set_percentage(self, pct: int) -> None:
        self.ha.service("fan", "set_percentage", entity_id=self.fan, percentage=pct)

    def turn_off(self) -> None:
        self.ha.service("fan", "turn_off", entity_id=self.fan)

    def turn_on(self) -> None:
        self.ha.service("fan", "turn_on", entity_id=self.fan)


class Log:
    """Reads the integration's log lines for one unit back over SSH."""

    def __init__(
        self, ssh_host: str, container: str, tail4: str, name: str = ""
    ) -> None:
        self.ssh_host, self.container, self.tail4 = ssh_host, container, tail4
        self.tokens = [t for t in (tail4, name) if t]
        self.started = time.time()

    def lines(self) -> list[str]:
        since = int(time.time() - self.started) + 5
        result = subprocess.run(
            [
                "ssh",
                self.ssh_host,
                f"sudo docker logs --since {since}s {self.container} 2>&1",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        # A failed ssh, a renamed container or a sudo prompt all return nothing,
        # and every count then reads zero while the verdicts print as normal. An
        # unreadable log has to stop the run, not quietly become an empty one.
        if result.returncode != 0:
            sys.exit(
                f"cannot read the log (ssh exit {result.returncode}): "
                f"{result.stderr.strip()[:200]}"
            )
        raw = result.stdout
        out = []
        for line in raw.splitlines():
            line = ANSI.sub("", line)
            keep = any(t in line for t in self.tokens) or UNIT_AGNOSTIC.search(line)
            if keep and LOG_PATTERN.search(line):
                line = re.sub(r" \(MainThread\) \[[a-z_.]+\]", "", line)
                line = re.sub(r"Temp: [^|]*\| ", "", line)
                line = re.sub(r" from client: .*", "", line)
                line = re.sub(r"PUT /monitor/ataunit/[0-9a-f-]+", "PUT", line)
                out.append(line[11:])
        return out

    def count(self, needle: str) -> int:
        return sum(1 for line in self.lines() if needle in line)

    def dump(self) -> None:
        for line in self.lines():
            print("   ", line)


def wait(seconds: float, why: str) -> None:
    print(f"    ... {seconds:g}s ({why})")
    time.sleep(seconds)


def verdict(ok: bool, text: str) -> None:
    print(f"==> {'PASS' if ok else 'FAIL'}: {text}")


def report_delivery(log: Log, issued: int) -> None:
    """Compare writes issued against PUTs the API answered.

    A `Setting …` line is logged in the control client before the pacer is even
    acquired, so counting it proves a write was *issued*. The delivery record is
    `API Response: PUT … [200]`. They come apart when a write runs inside a timer
    callback rather than a service call, because then no REST response carries
    the failure back to us: the service call has already returned 200 and only
    the log knows. Any shortfall here means a verdict above counted an intent
    that no API answer matches.
    """
    answered = log.count("API Response: PUT")
    if answered < issued:
        print(
            f"!   {issued} write(s) issued but only {answered} PUT answer(s) in the "
            "window: at least one never reached the API, or its response is missing"
        )
    else:
        print(f"    {issued} issued, {answered} PUT answer(s) in the window")


# --- checks -----------------------------------------------------------------------------


def check_state(unit: Unit, log: Log, args: argparse.Namespace) -> None:
    """The header line already printed the snapshot; nothing is written."""


def ensure_on(unit: Unit, log: Log) -> None:
    if not unit.is_on():
        print("    unit is off; powering on at 60 first")
        unit.set_percentage(60)
        wait(4, "power-on to land")


def check_reversal(unit: Unit, log: Log, args: argparse.Namespace) -> None:
    ensure_on(unit, log)
    base = log.count("Setting fan speed")
    for pct in (60, 40, 60):
        unit.set_percentage(pct)
        wait(3, f"after {pct}%")
        print(f"    {pct}% -> {unit.snapshot()}")
    n = log.count("Setting fan speed") - base
    log.dump()
    verdict(
        n >= 3,
        f"{n} speed writes for 60/40/60; the return to 60 is the one deduplication dropped",
    )


def check_same_value(unit: Unit, log: Log, args: argparse.Namespace) -> None:
    ensure_on(unit, log)
    # In the auto preset `percentage` reports the last numbered speed, not what
    # the unit holds, so sending it back would be an ordinary different-value
    # write and would prove nothing about the property.
    if unit.preset() == "auto":
        sys.exit(
            "unit is in the auto preset: percentage reports the last numbered "
            "speed rather than the value the unit holds, so this check would "
            "send a value it does not have. Set a numbered speed first."
        )
    pct = unit.percentage() or 40
    base = log.count("Setting fan speed")
    for _ in range(2):
        unit.set_percentage(pct)
        wait(3, f"after {pct}% again")
    n = log.count("Setting fan speed") - base
    log.dump()
    verdict(n >= 2, f"{n} speed writes for the value the unit already had")


def off_behind_on(
    unit: Unit, log: Log, gap: float, settle: float
) -> tuple[bool, int, bool, float | None]:
    """From off: on, then off after `gap` seconds.

    `gap` is the pause between the two service calls. It is not the interval the
    cloud sees and cannot be below PACER_FLOOR however small it is set, because
    every request is serialised through one pacer. Read the delivered interval
    off the two `API Response: PUT` lines, which are logged after dispatch; the
    `Setting` lines are logged before the pacer is even acquired and record
    intent only.

    The power-on is `turn_on`, not a slider position: `set_percentage` also
    queues a debounced speed write, which lands between the on and the off and
    makes this a three-command sequence whose middle command is invisible to the
    power-write count. A drag's real shape belongs to the Home app column.

    Returns whether the off held, the power-write count as it stood once the
    unit was off, whether the device itself reported anything during the settle,
    and how long after the off the contradiction arrived when there was one.
    Without the third a caller cannot tell a held off from a window in which
    nothing was observed; without the fourth it cannot tell a lost command from
    a report that was merely late.
    """
    if unit.is_on():
        unit.turn_off()
        wait(5, "precondition: unit off")
    base = log.count("Setting power")
    before = unit.actual_stamp()
    unit.turn_on()
    time.sleep(gap)
    off_at = datetime.now(UTC)
    unit.turn_off()
    wait(4, "both PUTs and the first poll")
    print(f"    after the pair: {unit.snapshot()}")
    wait(settle, "the device's own status report")
    held = not unit.is_on()
    reported = unit.actual_stamp() != before
    contradicted_after = (
        None if held else (unit.state_changed_at() - off_at).total_seconds()
    )
    print(f"    after settle:   {unit.snapshot()}")
    if contradicted_after is not None:
        print(f"    contradicted {contradicted_after:.0f}s after the off was sent")
    return held, base, reported, contradicted_after


def check_off_behind_on(unit: Unit, log: Log, args: argparse.Namespace) -> None:
    if args.gap < PACER_FLOOR:
        print(
            f"!   --gap {args.gap:g} is below the pacer's {PACER_FLOOR:g}s floor and "
            "cannot be delivered; the two PUTs will be at least that far apart"
        )
    held, base, reported, contradicted_after = off_behind_on(
        unit, log, args.gap, args.settle
    )
    log.dump()
    # A power-on sends power+mode when the unit reports a mode to preserve and a
    # plain power write when it does not (fan.py _async_power_on), so counting
    # the common prefix is what holds for either branch; requiring both strings
    # would fail a run in which the on and the off were both sent correctly.
    sent = log.count("Setting power") - base
    verdict(
        sent >= 2,
        f"{sent} power writes for the pair: power-on and power-off both left HA (the half that is ours)",
    )
    if contradicted_after is not None and contradicted_after < LAG_SUSPECT_SECONDS:
        print(
            f"==> INCONCLUSIVE: the unit read on again only {contradicted_after:.0f}s "
            "after the off. That is soon enough to be the device reporting the "
            "state it was in before the off reached it, rather than the off being "
            "lost. Re-run and look for a contradiction tens of seconds out."
        )
    elif not reported:
        print(
            "==> INCONCLUSIVE: the device reported nothing during the settle, so "
            "'off' here is only our own write-through read back. Re-run, or wait "
            "for an actual-fan-speed change before believing either answer."
        )
    else:
        verdict(
            held,
            f"the off held at the device, the device having reported during the "
            f"settle (service calls {args.gap:g}s apart, delivered no closer "
            f"than {PACER_FLOOR:g}s)",
        )


def check_restart_after_zero(unit: Unit, log: Log, args: argparse.Namespace) -> None:
    """Zero, a pause, then a numbered speed: the off, the power-on and the speed.

    The off and the power-on here are consecutive writes to one unit, which the
    pacer spaces at its floor, so this is one of the shapes the device has been
    seen to accept at the cloud and ignore. It therefore waits for the device's
    own report like off-behind-on, rather than reading back its own write-through.
    """
    ensure_on(unit, log)
    base_power = log.count("Setting power")
    base_speed = log.count("Setting fan speed")
    before = unit.actual_stamp()
    unit.set_percentage(0)
    wait(1, "the zero")
    unit.set_percentage(40)
    wait(4, "the restart")
    print(f"    after the restart: {unit.snapshot()}")
    wait(args.settle, "the device's own status report")
    print(f"    after settle:      {unit.snapshot()}")
    log.dump()
    powers = log.count("Setting power") - base_power
    speeds = log.count("Setting fan speed") - base_speed
    report_delivery(log, powers + speeds)
    verdict(
        powers >= 2 and speeds >= 1,
        f"{powers} power writes and {speeds} speed write(s): the zero powered the "
        f"unit off, the way back up re-powered it, and a speed followed",
    )
    if unit.actual_stamp() == before:
        print(
            "==> INCONCLUSIVE: the device reported nothing during the settle, so "
            "whether it acted on the restart is unobserved. HA reading on here is "
            "our own write-through."
        )
    else:
        verdict(unit.is_on(), "the unit is running, on its own report")


async def _out_of_band_set(env: dict[str, str], tail4: str, speed: str) -> None:
    sys.path.insert(0, str(REPO))
    from custom_components.melcloudhome.api.client import MELCloudHomeClient

    client = MELCloudHomeClient()
    try:
        await client.login(env["MELCLOUD_USER_OWNER"], env["MELCLOUD_PASSWORD_OWNER"])
        ctx = await client.get_user_context()
        unit = next(
            u for b in ctx.buildings for u in b.air_to_air_units if u.id.endswith(tail4)
        )
        await client.ata.set_fan_speed(unit.id, speed)
    finally:
        await client.close()


def check_out_of_band_match(
    unit: Unit, log: Log, args: argparse.Namespace, env: dict[str, str]
) -> None:
    if not env.get("MELCLOUD_USER_OWNER"):
        sys.exit(
            "out-of-band-match needs MELCLOUD_USER_OWNER / MELCLOUD_PASSWORD_OWNER in .env"
        )
    ensure_on(unit, log)
    if unit.preset() == "auto":
        sys.exit(
            "unit is in the auto preset, so percentage does not report what the "
            "unit holds and the pickup cannot be detected. Set a numbered speed "
            "first."
        )
    # Pick the target off the entity's own speed list rather than assuming five
    # speeds: on a three-speed ducted unit the old 40/60 pair is unreachable, the
    # wait always timed out, and the check then sent a value HA did not hold.
    steps = unit.speed_steps()
    current = unit.percentage()
    target_pct = next((p for p in steps if p != current), None)
    if target_pct is None:
        sys.exit(f"cannot pick a different speed from {steps} (current {current})")
    target_word = unit.speed_word(target_pct)
    print(f"    setting {target_word} through the MELCloud API, outside HA")
    asyncio.run(_out_of_band_set(env, unit.tail4, target_word.capitalize()))
    # The poll interval is 60s, so a pickup inside 30s needs a websocket delta.
    # Allow longer than one poll, and make the timeout fatal: without the pickup
    # HA still holds the old value, the "matching" command would differ from it,
    # and the run would quietly become an ordinary different-value write.
    picked_up = False
    for _ in range(40):
        time.sleep(2)
        if unit.percentage() == target_pct:
            picked_up = True
            break
    print(f"    HA now shows: {unit.snapshot()}")
    if not picked_up:
        sys.exit(
            f"precondition failed: HA never showed the out-of-band {target_word} "
            f"({target_pct}%) within 80s, so there is no matching value to send. "
            "Nothing was written through HA."
        )
    before = log.count("Setting fan speed")
    unit.set_percentage(target_pct)
    wait(3, "the matching command")
    log.dump()
    issued = log.count("Setting fan speed") - before
    report_delivery(log, issued)
    verdict(
        issued >= 1,
        f"a command matching the {target_word} HA already held reached the API "
        "(discussion #135)",
    )


def check_same_value_sweep(unit: Unit, log: Log, args: argparse.Namespace) -> None:
    """Send each remaining ATA setter the value it already holds, twice.

    `same-value` proves property 4 for fan speed, which is one of the six setters
    ADR-026 removed the comparison from. Temperature and the two vanes are only
    reachable through the climate entity, so nothing else here touches them and
    they had no hardware coverage at all. Fan mode is included because it reaches
    the same setter as the fan entity by a different caller.

    Writes no power, so it leaves an off unit off.
    """
    if not unit.climate:
        sys.exit("no climate entity found for this unit")
    fields = [
        ("Setting temperature", "set_temperature", "temperature"),
        ("Setting vertical vane", "set_swing_mode", "swing_mode"),
        (
            "Setting horizontal vane",
            "set_swing_horizontal_mode",
            "swing_horizontal_mode",
        ),
        ("Setting fan speed", "set_fan_mode", "fan_mode"),
    ]
    attributes = unit.ha.state(unit.climate)["attributes"]
    for needle, service, key in fields:
        value = attributes.get(key)
        if value is None:
            print(f"    {key}: not offered by this unit, skipped")
            continue
        base = log.count(needle)
        for _ in range(2):
            unit.ha.service("climate", service, entity_id=unit.climate, **{key: value})
            wait(2, f"{key}={value} again")
        n = log.count(needle) - base
        verdict(n >= 2, f"{n} writes for {key} at its current value {value}")
    log.dump()


def check_combined_write(unit: Unit, log: Log, args: argparse.Namespace) -> None:
    """Set an operation mode and a temperature in one service call.

    `climate.set_temperature` accepts an hvac_mode, and the entity now issues the
    mode write and the temperature write together so the coalescer merges them.
    The server has answered 200 to a combination it could not honour and dropped
    the half it disliked (issue #100), so a structural test proving one request
    left Home Assistant cannot prove the unit acted on all of it. The device's
    own reading is the witness.

    Leaves the unit's mode and temperature where it found them.
    """
    if not unit.climate:
        sys.exit("no climate entity found for this unit")
    attributes = unit.ha.state(unit.climate)["attributes"]
    was_mode = unit.ha.state(unit.climate)["state"]
    was_temp = attributes.get("temperature")
    if was_temp is None:
        sys.exit("this unit reports no target temperature")
    target = was_temp + 1 if was_temp < 24 else was_temp - 1
    print(f"    before: mode={was_mode} temperature={was_temp}")

    base = log.count("API Response: PUT")
    unit.ha.service(
        "climate",
        "set_temperature",
        entity_id=unit.climate,
        temperature=target,
        hvac_mode=was_mode,
    )
    wait(4, "the merged request and the first poll")
    puts = log.count("API Response: PUT") - base
    verdict(puts == 1, f"{puts} PUT(s) left Home Assistant for mode+temperature")

    wait(args.settle, "the device's own status report")
    now = unit.ha.state(unit.climate)
    applied = now["attributes"].get("temperature")
    print(f"    after settle: mode={now['state']} temperature={applied}")
    verdict(applied == target, f"the unit reports {applied}, asked for {target}")

    unit.ha.service(
        "climate", "set_temperature", entity_id=unit.climate, temperature=was_temp
    )
    wait(3, "restore")
    log.dump()


# --- main -------------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "-k", "--insecure", action="store_true", help="disable TLS verification"
    )
    parser.add_argument(
        "--no-debug", action="store_true", help="leave logger levels alone"
    )
    parser.add_argument(
        "--keep-debug",
        action="store_true",
        help="raise the levels but do not restore them, for a session of manual "
        "gestures afterwards: restoring them silently hides the set_value and "
        "poll lines a human observer is relying on",
    )
    parser.add_argument(
        "--entity", help="fan entity id; omitted lists the fan entities and exits"
    )
    parser.add_argument(
        "--gap",
        type=float,
        default=0.3,
        help="off-behind-on: seconds between on and off",
    )
    parser.add_argument(
        "--settle", type=float, default=90, help="seconds to wait for the device report"
    )
    parser.add_argument(
        "check",
        nargs="?",
        choices=[
            "state",
            "reversal",
            "same-value",
            "same-value-sweep",
            "combined-write",
            "off-behind-on",
            "restart-after-zero",
            "out-of-band-match",
        ],
    )
    args = parser.parse_args()

    env = load_env()
    for key in ("HA_URL", "HA_TOKEN", "HA_SSH_HOST", "HA_CONTAINER"):
        if not env.get(key):
            sys.exit(f"{key} missing from .env")
    ha = HomeAssistant(env["HA_URL"], env["HA_TOKEN"], args.insecure)

    if not args.entity or not args.check:
        for s in ha.call("/api/states"):
            if s["entity_id"].startswith("fan.") and "melcloudhome" in s["entity_id"]:
                print(
                    f"  {s['entity_id']:<55} {s['state']:>3} {s['attributes'].get('percentage')}%"
                )
        return

    unit = Unit(ha, args.entity)
    log = Log(env["HA_SSH_HOST"], env["HA_CONTAINER"], unit.tail4, unit.display_name())
    was_on, was_pct = unit.is_on(), unit.percentage()
    print(f"{datetime.now(UTC):%H:%M:%S}Z  {args.check}  {unit.snapshot()}")

    if not args.no_debug:
        ha.set_levels(0)
    try:
        if args.check == "state":
            check_state(unit, log, args)
        elif args.check == "reversal":
            check_reversal(unit, log, args)
        elif args.check == "same-value":
            check_same_value(unit, log, args)
        elif args.check == "same-value-sweep":
            check_same_value_sweep(unit, log, args)
        elif args.check == "combined-write":
            check_combined_write(unit, log, args)
        elif args.check == "off-behind-on":
            check_off_behind_on(unit, log, args)
        elif args.check == "restart-after-zero":
            check_restart_after_zero(unit, log, args)
        elif args.check == "out-of-band-match":
            check_out_of_band_match(unit, log, args, env)
    finally:
        if args.check != "state":
            if was_on and not unit.is_on():
                unit.turn_on()
                if was_pct:
                    time.sleep(1)
                    unit.set_percentage(was_pct)
            elif not was_on and unit.is_on():
                unit.turn_off()
            # snapshot() would read back the pending value this restore just
            # queued, so it can never disagree. Say what was asked for instead.
            print(
                f"    restore requested: power={'on' if was_on else 'off'} "
                f"pct={was_pct}. Its writes are a close pair, so confirm against "
                "the unit's own report rather than this line."
            )
        if args.no_debug:
            pass
        elif args.keep_debug:
            print("    logger levels left at debug (--keep-debug)")
        else:
            ha.set_levels(1)
            print("    logger levels restored")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as err:
        sys.exit(f"HTTP {err.code} from Home Assistant: {err.reason}")
