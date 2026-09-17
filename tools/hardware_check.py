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
    off-behind-on       from off, power on then off --gap seconds later, then wait --settle
                        seconds for the device report and say whether the off held
    restart-after-zero  zero, a one-second pause, then 40: expect off, on, speed
    out-of-band-match   set a speed through the MELCloud API outside HA, wait for HA to
                        show it, send the same speed through HA: expect the write (#135)
    drop-boundary       off-behind-on across --gaps, reporting which gaps held

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
    r"Setting |API Response: PUT|WebSocket delta|ATA Poll|client_update_value|Listener update failed"
)
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
                and s["entity_id"].endswith(self.tail4)
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

    def __init__(self, ssh_host: str, container: str, tail4: str) -> None:
        self.ssh_host, self.container, self.tail4 = ssh_host, container, tail4
        self.started = time.time()

    def lines(self) -> list[str]:
        since = int(time.time() - self.started) + 5
        raw = subprocess.run(
            [
                "ssh",
                self.ssh_host,
                f"sudo docker logs --since {since}s {self.container} 2>&1",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        ).stdout
        out = []
        for line in raw.splitlines():
            line = ANSI.sub("", line)
            if self.tail4 in line and LOG_PATTERN.search(line):
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
    pct = unit.percentage() or 40
    base = log.count("Setting fan speed")
    for _ in range(2):
        unit.set_percentage(pct)
        wait(3, f"after {pct}% again")
    n = log.count("Setting fan speed") - base
    log.dump()
    verdict(n >= 2, f"{n} speed writes for the value the unit already had")


def off_behind_on(unit: Unit, log: Log, gap: float, settle: float) -> tuple[bool, int]:
    """From off: on, then off after `gap` seconds.

    Returns whether the off held at the device, and the power-write count as it
    stood once the unit was off, so a caller counts only the pair's own writes
    and not the power-off this may have sent to reach the precondition.
    """
    if unit.is_on():
        unit.turn_off()
        wait(5, "precondition: unit off")
    base = log.count("Setting power")
    unit.set_percentage(60)
    time.sleep(gap)
    unit.turn_off()
    wait(4, "both PUTs and the first poll")
    print(f"    after the pair: {unit.snapshot()}")
    wait(settle, "the device's own status report")
    held = not unit.is_on()
    print(f"    after settle:   {unit.snapshot()}")
    return held, base


def check_off_behind_on(unit: Unit, log: Log, args: argparse.Namespace) -> None:
    held, base = off_behind_on(unit, log, args.gap, args.settle)
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
    verdict(
        held,
        f"the off held at the device with a {args.gap:g}s gap (the half that is the cloud's and the unit's)",
    )


def check_restart_after_zero(unit: Unit, log: Log, args: argparse.Namespace) -> None:
    ensure_on(unit, log)
    base = log.count("Setting power")
    unit.set_percentage(0)
    wait(1, "the zero")
    unit.set_percentage(40)
    wait(4, "the restart")
    print(f"    {unit.snapshot()}")
    log.dump()
    n = log.count("Setting power") - base
    # Only the sequence is claimed. Whether the zero *cleared the power-on guard*
    # cannot be read off a run like this: the guard is three seconds on the real
    # clock, so by the time the zero lands it has usually expired on its own and
    # the restart proves nothing about the clearing. The integration suite owns
    # that assertion, in test_power_off_disarms_the_power_on_guard, which widens
    # the window to an hour so expiry cannot be what makes it pass.
    verdict(
        unit.is_on() and n >= 2,
        f"{n} power writes: the zero powered the unit off and the way back up re-powered it and set the speed",
    )


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
    current = unit.percentage() or 0
    target_word, target_pct = ("two", 40) if current != 40 else ("three", 60)
    print(f"    setting {target_word} through the MELCloud API, outside HA")
    asyncio.run(_out_of_band_set(env, unit.tail4, target_word.capitalize()))
    for _ in range(15):
        time.sleep(2)
        if unit.percentage() == target_pct:
            break
    print(f"    HA now shows: {unit.snapshot()}")
    before = log.count("Setting fan speed")
    unit.set_percentage(target_pct)
    wait(3, "the matching command")
    log.dump()
    verdict(
        log.count("Setting fan speed") > before,
        "a command matching what HA already held reached the API (discussion #135)",
    )


def check_drop_boundary(unit: Unit, log: Log, args: argparse.Namespace) -> None:
    results = []
    for gap in [float(g) for g in args.gaps.split(",")]:
        print(f"--- gap {gap:g}s ---")
        results.append((gap, off_behind_on(unit, log, gap, args.settle)[0]))
        if unit.is_on():
            unit.turn_off()
            wait(5, "reset to off")
    print("gap(s)  off held at the device?")
    after_loss = False
    for gap, held in results:
        if not held:
            print(f"  {gap:>4g}  LOST: unit kept the power-on")
        else:
            suspect = "   <- follows a LOST, see below" if after_loss else ""
            print(f"  {gap:>4g}  held{suspect}")
        after_loss = not held
    print(
        "\nOne sample per gap, so this is not a threshold, and the loss has been seen to be\n"
        "non-monotonic: read it as evidence that a gap is unsafe, never that one is safe.\n"
        "A held that follows a LOST is weaker still. The losing iteration ends with a power-off\n"
        "and the next gap begins seconds later, so the device's report of that reset can arrive\n"
        "inside the next settle window and read as the new iteration's off holding."
    )


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
        "--gaps", default="0.2,0.4,0.7,1.0,1.5", help="drop-boundary: gaps to walk"
    )
    parser.add_argument(
        "check",
        nargs="?",
        choices=[
            "state",
            "reversal",
            "same-value",
            "off-behind-on",
            "restart-after-zero",
            "out-of-band-match",
            "drop-boundary",
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
    log = Log(env["HA_SSH_HOST"], env["HA_CONTAINER"], unit.tail4)
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
        elif args.check == "off-behind-on":
            check_off_behind_on(unit, log, args)
        elif args.check == "restart-after-zero":
            check_restart_after_zero(unit, log, args)
        elif args.check == "out-of-band-match":
            check_out_of_band_match(unit, log, args, env)
        elif args.check == "drop-boundary":
            check_drop_boundary(unit, log, args)
    finally:
        if args.check != "state":
            if was_on and not unit.is_on():
                unit.turn_on()
                if was_pct:
                    time.sleep(1)
                    unit.set_percentage(was_pct)
            elif not was_on and unit.is_on():
                unit.turn_off()
            print(f"    restored: {unit.snapshot()}")
        if not args.no_debug:
            ha.set_levels(1)
            print("    logger levels restored")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as err:
        sys.exit(f"HTTP {err.code} from Home Assistant: {err.reason}")
