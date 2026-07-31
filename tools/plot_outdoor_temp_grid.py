# /// script
# requires-python = ">=3.13"
# dependencies = ["matplotlib>=3.9"]
# ///
"""Comparison grid for outdoor-temperature recorder data (tools/outdoor_temp_recorder.py).

One column per unit, one row per series: HA's reported state, direct-API Daily,
direct-API Hourly, optionally a real-world reference temperature sensor, and —
when the recording includes ha_last_reading — a staleness sawtooth (minutes
since the reading HA reports; climbs through upload pauses, snaps down when a
fresh reading arrives). Shading marks outdoor-unit active-cooling windows (if
a zone map is given) and the Daily-period BST-midnight anomaly windows.

Usage:
    uv run tools/plot_outdoor_temp_grid.py --start 2026-07-28T20:00:00 --end 2026-07-29T06:00:00
    uv run tools/plot_outdoor_temp_grid.py --start ... --end ... \\
        --units dining_room,master_bedroom \\
        --reference-entity sensor.my_garden_thermometer \\
        --zones "dining_room=climate.melcloudhome_aaaa_1111,climate.melcloudhome_bbbb_2222"

--zones maps a recorded unit to ALL climate entities sharing its physical
outdoor unit (multi-split), so "compressor active" shading reflects any zone
calling for cooling. Without it, cooling shading is skipped.

Environment: HA_URL + HA_TOKEN (or HA_API_KEY), only needed when fetching
reference/zone history that isn't already cached.
"""

import argparse
import csv
import json
import os
import ssl
import tempfile
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt

REPO_ROOT = Path(__file__).parent.parent
DEFAULT_RECORDER_DIR = REPO_ROOT / "diagnostics" / "outdoor-temp-recorder"


def parse(t):
    dt = datetime.fromisoformat(t)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def fetch_ha_history(entity_id, start, end, insecure, cache_path, no_attributes):
    """Fetch an entity's history from HA, caching to disk."""
    if os.path.exists(cache_path):
        with open(cache_path) as f:
            return json.load(f)
    ha_url = os.environ.get("HA_URL", "https://homeassistant.local:8123")
    token = os.environ.get("HA_API_KEY") or os.environ.get("HA_TOKEN")
    if not token:
        raise SystemExit(
            f"{cache_path} doesn't exist and HA_API_KEY/HA_TOKEN not set to fetch it"
        )
    if not ha_url.startswith(("http://", "https://")):
        raise SystemExit(f"HA_URL must be http(s), got: {ha_url}")
    ctx = ssl.create_default_context()
    if insecure:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    start_s = urllib.parse.quote(start.strftime("%Y-%m-%dT%H:%M:%S+00:00"))
    end_s = urllib.parse.quote(end.strftime("%Y-%m-%dT%H:%M:%S+00:00"))
    url = (
        f"{ha_url}/api/history/period/{start_s}?filter_entity_id={entity_id}"
        f"&end_time={end_s}{'&no_attributes=true' if no_attributes else ''}"
    )
    req = urllib.request.Request(  # noqa: S310 - scheme validated above
        url, headers={"Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req, context=ctx, timeout=30) as r:  # noqa: S310
        data = json.loads(r.read())
    with open(cache_path, "w") as f:
        json.dump(data, f)
    return data


def load_reference(start, end, entity_id, cache_path, insecure):
    data = fetch_ha_history(
        entity_id, start, end, insecure, cache_path, no_attributes=True
    )
    pts = []
    for series in data:
        for s in series:
            try:
                pts.append((parse(s["last_updated"]), float(s["state"])))
            except (ValueError, KeyError):
                continue
    return sorted(pts)


def cooling_intervals(entity_id, start, end, insecure, cache_dir):
    """Intervals where this zone's hvac_action == 'cooling', clipped to [start, end]."""
    safe = entity_id.replace(".", "_")
    cache_path = f"{cache_dir}/hvac_{safe}.json"
    data = fetch_ha_history(
        entity_id, start, end, insecure, cache_path, no_attributes=False
    )
    rows = data[0] if data else []
    intervals = []
    cur_start = None
    for row in rows:
        t = parse(row["last_changed"])
        is_cooling = row.get("attributes", {}).get("hvac_action") == "cooling"
        if is_cooling and cur_start is None:
            cur_start = t
        elif not is_cooling and cur_start is not None:
            intervals.append((cur_start, t))
            cur_start = None
    if cur_start is not None:
        intervals.append((cur_start, end))
    return [(max(s, start), min(e, end)) for s, e in intervals if e > start and s < end]


def merge_intervals(intervals):
    if not intervals:
        return []
    intervals = sorted(intervals)
    merged = [list(intervals[0])]
    for s, e in intervals[1:]:
        if s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return [(s, e) for s, e in merged]


def load_ha(recorder_dir, unit):
    pts = []
    with open(recorder_dir / "ha_state.csv") as f:
        for r in csv.DictReader(f):
            if r["unit"] != unit:
                continue
            try:
                pts.append((parse(r["poll_time"]), float(r["ha_outdoor_temp"])))
            except (ValueError, TypeError):
                continue
    return sorted(pts)


def load_ha_ages(recorder_dir, unit):
    """Reported staleness per poll: poll_time - last_reading, in minutes.

    Climbs 1:1 through upload pauses and snaps down when a fresh reading
    arrives (a sawtooth). Resets bottom out around the integration's outdoor
    poll interval, not zero, because last_reading only refreshes on that poll.
    Empty for recordings made before the recorder captured ha_last_reading.
    """
    pts = []
    with open(recorder_dir / "ha_state.csv") as f:
        for r in csv.DictReader(f):
            if r["unit"] != unit:
                continue
            try:
                poll = parse(r["poll_time"])
                reading = parse(r["ha_last_reading"])
            except (ValueError, TypeError, KeyError):
                continue
            pts.append((poll, (poll - reading).total_seconds() / 60))
    return sorted(pts)


def load_live(recorder_dir, unit, period):
    pts = []
    with open(recorder_dir / f"{unit}_{period}.csv") as f:
        for r in csv.DictReader(f):
            try:
                pts.append((parse(r["point_x"]), float(r["point_y"])))
            except (ValueError, KeyError):
                continue
    # dedupe identical (x,y) pairs written across multiple polls
    return sorted(set(pts))


def parse_arg_dt(s):
    return datetime.fromisoformat(s).replace(tzinfo=UTC)


parser = argparse.ArgumentParser(
    description="HA/Hourly/Daily/reference comparison grid"
)
parser.add_argument(
    "--start", required=True, help="UTC start, e.g. 2026-06-24T20:30:00"
)
parser.add_argument("--end", required=True, help="UTC end, e.g. 2026-06-25T05:45:00")
parser.add_argument(
    "--recorder-dir",
    type=Path,
    default=DEFAULT_RECORDER_DIR,
    help="Directory of recorder CSVs (default: diagnostics/outdoor-temp-recorder/)",
)
parser.add_argument(
    "--units",
    default=None,
    help="Comma-separated recorded unit labels (default: every *_hourly.csv in --recorder-dir)",
)
parser.add_argument(
    "--reference-entity",
    default=None,
    help="HA entity ID of a real-world reference temperature sensor (row skipped if omitted)",
)
parser.add_argument(
    "--zones",
    action="append",
    default=[],
    metavar="UNIT=ENTITY[,ENTITY...]",
    help="Climate entities sharing a unit's outdoor unit, for cooling shading (repeatable)",
)
parser.add_argument("--out", default=None, help="PNG output path (default: auto-named)")
parser.add_argument(
    "--insecure",
    action="store_true",
    help="Disable TLS certificate verification for HA history fetches (self-signed certs; "
    "prefer pointing HA_URL at a properly-certificated hostname)",
)
args = parser.parse_args()

START = parse_arg_dt(args.start)
END = parse_arg_dt(args.end)
if END <= START:
    raise SystemExit(f"--end ({END}) must be after --start ({START})")

date_tag = f"{START.strftime('%Y%m%dT%H%M')}_{END.strftime('%Y%m%dT%H%M')}"
tmp_dir = Path(tempfile.gettempdir())
out_path = args.out or str(tmp_dir / f"outdoor_temp_grid_{date_tag}.png")
cache_dir = str(tmp_dir / f"outdoor_temp_grid_cache_{date_tag}")
os.makedirs(cache_dir, exist_ok=True)

if args.units:
    UNITS = [u.strip() for u in args.units.split(",")]
else:
    UNITS = sorted(
        p.name.removesuffix("_hourly.csv")
        for p in args.recorder_dir.glob("*_hourly.csv")
    )
if not UNITS:
    raise SystemExit(f"No recorded units found in {args.recorder_dir}")

zone_map = {}
for spec in args.zones:
    unit, _, entities = spec.partition("=")
    zone_map[unit.strip()] = [e.strip() for e in entities.split(",") if e.strip()]

ROWS = [
    ("HA state", "step", "black"),
    ("Direct Daily", "marker_dashed", "tab:red"),
    ("Direct Hourly", "marker", "tab:blue"),
]
reference = []
if args.reference_entity:
    ROWS.append(("Reference sensor", "line", "tab:green"))
    reference = [
        (t, v)
        for t, v in load_reference(
            START,
            END,
            args.reference_entity,
            f"{cache_dir}/reference.json",
            args.insecure,
        )
        if START <= t <= END
    ]

per_unit_series = {}
all_values = []
all_ages = []
for unit in UNITS:
    ha = [(t, v) for t, v in load_ha(args.recorder_dir, unit) if START <= t <= END]
    ages = [
        (t, v) for t, v in load_ha_ages(args.recorder_dir, unit) if START <= t <= END
    ]
    hourly = [
        (t, v)
        for t, v in load_live(args.recorder_dir, unit, "hourly")
        if START <= t <= END
    ]
    daily = [
        (t, v)
        for t, v in load_live(args.recorder_dir, unit, "daily")
        if START <= t <= END
    ]
    per_unit_series[unit] = {
        "HA state": ha,
        "Direct Hourly": hourly,
        "Direct Daily": daily,
        "Reference sensor": reference,
        "last_reading age": ages,
    }
    all_values += [v for _, v in ha] + [v for _, v in hourly] + [v for _, v in daily]
    all_ages += [v for _, v in ages]
all_values += [v for _, v in reference]
if not all_values:
    raise SystemExit("No datapoints in the requested window")

# Staleness sawtooth (minutes, own y-scale) — only when the recording has it
if all_ages:
    ROWS.append(("last_reading age", "age", "tab:purple"))

margin = 0.5
ymin, ymax = min(all_values) - margin, max(all_values) + margin
age_ymax = max(all_ages) * 1.05 if all_ages else 1

# Daily-period BST-midnight anomaly window: 00:00-01:00 local == 23:00-00:00 UTC.
# Mark every occurrence that overlaps the plotted range.
anomaly_windows = []
day_cursor = datetime(
    START.year, START.month, START.day, 23, 0, tzinfo=UTC
) - timedelta(days=1)
while day_cursor < END:
    w_start, w_end = day_cursor, day_cursor + timedelta(hours=1)
    if w_end > START and w_start < END:
        anomaly_windows.append((max(w_start, START), min(w_end, END)))
    day_cursor += timedelta(days=1)

# OU-level active-cooling windows: union of "any zone on this outdoor unit is
# calling for cooling" across all zones sharing that compressor (--zones).
cooling_windows = {}
for unit in UNITS:
    zone_intervals = []
    for entity_id in zone_map.get(unit, []):
        zone_intervals += cooling_intervals(
            entity_id, START, END, args.insecure, cache_dir
        )
    cooling_windows[unit] = merge_intervals(zone_intervals)

fig, axes = plt.subplots(
    len(ROWS),
    len(UNITS),
    figsize=(8 * len(UNITS), 4 * len(ROWS)),
    sharex=True,
    squeeze=False,
)

for col, unit in enumerate(UNITS):
    series_by_label = per_unit_series[unit]

    for row, (label, style, color) in enumerate(ROWS):
        ax = axes[row][col]
        data = series_by_label[label]
        if data:
            xs = [t for t, v in data]
            ys = [v for t, v in data]
            if style == "step":
                ax.step(xs, ys, where="post", color=color, linewidth=2)
            elif style == "marker":
                ax.plot(xs, ys, "o-", color=color, markersize=3)
            elif style == "marker_dashed":
                ax.plot(xs, ys, "x--", color=color, markersize=4)
            elif style == "age":
                ax.plot(xs, ys, "o-", color=color, markersize=3)
            else:
                ax.plot(xs, ys, "-", color=color, linewidth=1.5)
        if style == "age":
            ax.set_ylim(0, age_ymax)
        else:
            ax.set_ylim(ymin, ymax)
        for w_start, w_end in cooling_windows[unit]:
            ax.axvspan(w_start, w_end, color="tab:blue", alpha=0.15, zorder=0)
        for w_start, w_end in anomaly_windows:
            ax.axvspan(w_start, w_end, color="orange", alpha=0.25, zorder=0)
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        if col == 0:
            unit_label = "min" if style == "age" else "°C"
            ax.set_ylabel(f"{label}\n({unit_label})")
        if row == 0:
            ax.set_title(unit)

for col in range(len(UNITS)):
    axes[-1][col].set_xlabel("Time (UTC)")

legend_handles = [
    plt.Rectangle(
        (0, 0), 1, 1, color="tab:blue", alpha=0.15, label="OU active (any zone cooling)"
    ),
    plt.Rectangle(
        (0, 0),
        1,
        1,
        color="orange",
        alpha=0.25,
        label="Daily-period BST-midnight anomaly window",
    ),
]
fig.legend(
    handles=legend_handles, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 1.02)
)
fig.suptitle(f"{START.isoformat()} -> {END.isoformat()}", y=1.05)
fig.tight_layout()
fig.savefig(out_path, dpi=130, bbox_inches="tight")
print(f"saved -> {out_path}")
