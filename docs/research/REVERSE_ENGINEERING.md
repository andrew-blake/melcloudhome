# API Reverse Engineering Guide

## Overview

Adding device support without owning every hardware variant relies on two phases:

1. **Phase 1 (Device Owner):** Capture real traffic between the official mobile app and the MELCloud mobile API via [mitmproxy](https://mitmproxy.org), anonymise, share.
2. **Phase 2 (Developer):** Feed captured data into the local mock server and simulate the device through the Home Assistant integration.

> **Why mitmproxy now?** The integration migrated from the legacy web API to the mobile API in v2.3.0 (see [ADR-017](../decisions/017-migrate-to-mobile-bff.md)). The mobile API (`mobile.bff.melcloudhome.com`) is the only surface the integration calls, so the only relevant capture source is traffic between the official MELCloud Home mobile app and that host. HAR captures from the `melcloudhome.com` web UI no longer reflect what the integration sees.

---

## Phase 1: Capturing Mobile App Traffic (Device Owners)

### When to do this

Developers will ask for a capture when:

- Your unit model isn't yet fully supported (new controller firmware, uncommon capability mix).
- A field is decoded incorrectly for your device.
- A control command is being silently dropped by MELCloud (200 OK, no effect).

### What you'll need

- An iPhone with the official **MELCloud Home** app installed and signed in.
- A computer on the same Wi-Fi as the iPhone.
- A working Python environment (`uv` recommended — see repo README).
- 15–30 minutes to install a certificate profile on the iPhone and capture traffic.

### Setup

Follow [`tools/mitmproxy/README.md`](../../tools/mitmproxy/README.md) for the full iOS + mitmproxy setup — it covers installing the mitmproxy CA on your iPhone, configuring the Wi-Fi proxy, and running the capture script. The rest of this guide assumes mitmproxy is working.

### Recording the capture

Start the capture script (this filters to MELCloud-only traffic and saves flows to a `.flow` file):

```bash
uv run mitmdump -s tools/mitmproxy/capture.py
```

Open the MELCloud Home app on the iPhone and exercise the device:

1. **Open the app** — this triggers the OAuth flow and the initial `/context` fetch.
2. **Navigate to the unit** — the app fetches `/telemetry/...` and `/report/v1/trendsummary`.
3. **Exercise every control** that matters for your report:
   - Change temperature (up and down)
   - Toggle power
   - Switch HVAC modes (Heat, Cool, Dry, Fan, Auto)
   - Change fan speed across all positions
   - Change vane positions (vertical AND horizontal, including "Swing")
   - For ATW: toggle zones, change DHW target, toggle forced DHW
4. **Let it idle for 1–2 minutes** — captures periodic polling and telemetry updates.

Stop mitmdump with `Ctrl-C` when done. Your capture lives at `tools/mitmproxy/captures/<timestamp>.flow`.

### Anonymising for sharing

Flow files contain your access tokens, refresh tokens, device IDs, and email address — **never share the raw `.flow`**. Export to HAR and anonymise:

```bash
# 1. Export .flow to HAR
uv run mitmdump -r tools/mitmproxy/captures/<timestamp>.flow --set hardump=capture.har

# 2. Strip credentials and PII
python tools/anonymize_har.py capture.har capture_anonymized.har
```

`tools/anonymize_har.py` redacts Bearer tokens, cookies, emails, names, IP addresses, MAC addresses, and UUIDs (users, buildings, devices, systems) — replacing each with a stable placeholder so cross-request references still line up. Open the anonymised HAR in a text editor and sanity-check it before sharing; if anything sensitive remains (unusual custom headers, free-text fields), delete those requests or redact manually.

### Sharing

Open a GitHub Discussion or attach to an existing issue:

```markdown
**Title:** Capture for [Device Model / Controller]

**Context:**
- Device: [model number, e.g. MSZ-HR25VFK2]
- Visible features: [zones, DHW, cooling, vane axes, etc.]
- Problem being investigated: [optional]

**Attached:** capture_anonymized.har
```

---

## Phase 2: Simulating Captured Devices (Developers)

Once a capture lands, you can drive the integration against a local mock server preloaded with the captured device. No real hardware needed.

### Mock server

**Location:** [`tools/mock_melcloud_server.py`](../../tools/mock_melcloud_server.py)

**Start it with the full dev environment:**

```bash
make dev-up
# Home Assistant: http://localhost:8123  (login: dev / dev)
# Mock MELCloud API: http://localhost:8080
```

The mock server stands in for the MELCloud API on localhost. The integration calls it instead of the real API when `MELCLOUD_MOCK_URL` is set (see [`DEV-SETUP.md`](../../DEV-SETUP.md) for the Advanced Mode checkbox flow that enables the "Connect to Mock Server" option during setup).

### Loading a captured device

Edit `tools/mock_melcloud_server.py` so its responses reflect the captured device:

- Update the `/context` response to include the captured unit(s).
- Update the per-unit state response served by `/monitor/ataunit/{id}` or `/monitor/atwunit/{id}` to match.
- If telemetry matters for the scenario, update the `/telemetry/telemetry/actual/{id}` and `/telemetry/telemetry/energy/{id}` responses too.

The mock mutates the in-memory device when PUTs arrive, so you can exercise control flows end-to-end through the HA UI.

### Inspecting live integration traffic

If you want to see exactly what the integration sends (e.g. to verify a fix), run it against the mock server with debug logging enabled, or point the dev HA instance through mitmproxy while talking to the real MELCloud API. `tools/mitmproxy/capture.py` works the same way in either direction — mobile app ↔ real MELCloud API or HA ↔ mock/real API — because it filters by domain.

### Related tooling

- [`tools/test_mobile_api.py`](../../tools/test_mobile_api.py) — standalone OAuth + mobile API smoke test (useful to isolate "is it my credentials or my code?" questions).
- [`tools/dump_device_state.py`](../../tools/dump_device_state.py) — dump current state of all devices via the mobile API; supports `--json` for before/after diffing.

---

## Best Practices

### For device owners capturing

**Do:**

- Install the mitmproxy CA on the iPhone exactly as described in [`tools/mitmproxy/README.md`](../../tools/mitmproxy/README.md) — skipping trust settings leaves traffic unviewable.
- Exercise every control that matters to your report, not just the broken one — cross-referencing neighbouring commands often reveals the pattern.
- Let the app run for a minute after the last interaction to capture the periodic polling.
- Run the anonymiser and eyeball the output before attaching.

**Don't:**

- Share raw `.flow` files — they contain live tokens.
- Share HAR output without running `anonymize_har.py` on it.
- Edit device state from the integration and the app simultaneously during capture — it muddies the request/response pairing.

### For developers simulating

**Do:**

- Use the mock server as the primary test surface. Real-hardware tests are expensive and slow.
- Reproduce reports in the mock environment before changing code. If you can't reproduce, the report may be incomplete.
- When a capture reveals a silently-dropped payload (200 OK, no state change), see [`docs/api/ata-api-reference.md`](../api/ata-api-reference.md) or [`docs/api/atw-api-reference.md`](../api/atw-api-reference.md) for the schemas that MELCloud actually validates — the server-side rules aren't documented but are inferable from working captures.

**Don't:**

- Fabricate capture data — always start from a real capture. MELCloud's validation is not publicly documented and guessing produces payloads the server silently drops.
- Run experimental payloads against real hardware — use the mock server first (see Safety below).

---

## Safety

The MELCloud mobile API controls real HVAC equipment. Before any real-hardware test:

1. Reproduce the behaviour against the mock server first.
2. Use conservative values (safe temperature ranges, well-understood modes).
3. Start with a single control change; avoid batch mutations while developing.
4. Coordinate with the device owner — they should monitor the unit during live testing.
5. If MELCloud returns `200 OK` but the device ignores the change, **do not retry with variations**. Investigate the schema (see [`docs/api/*.md`](../api/)) — silent drops usually indicate a schema violation, and retrying wastes the user's time.

---

## Related

- [`tools/mitmproxy/README.md`](../../tools/mitmproxy/README.md) — mitmproxy + iOS setup mechanics
- [`docs/research/mobile-bff-captures/README.md`](mobile-bff-captures/README.md) — endpoint mapping, OAuth PKCE flow, prior captures
- [ADR-017](../decisions/017-migrate-to-mobile-bff.md) — decision to migrate from the legacy web API to the mobile API
- [`docs/api/ata-api-reference.md`](../api/ata-api-reference.md) / [`docs/api/atw-api-reference.md`](../api/atw-api-reference.md) — schemas derived from prior captures
