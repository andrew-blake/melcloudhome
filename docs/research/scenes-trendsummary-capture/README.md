# Scenes & Trend Summary (Legacy Web Host) — Capture Notes

## What This Is (and Isn't)

A capture of the **Scenes** and legacy-web **Trend Summary** endpoints
(`melcloudhome.com`, distinct from the mobile BFF the integration talks to —
see [Hosts](../../api/ata-api-reference.md#hosts)), gathered 2026-07-23 by
driving the real web UI with `claude-in-chrome` browser automation against a
real account, targeting one live ATA unit.

**This is not a browser DevTools HAR export.** Earlier captures in this repo
(e.g. [web-bff-websocket-capture](../web-bff-websocket-capture/README.md)) used
Chrome's native "Save as HAR" feature. This session instead injected a
`fetch`/`XMLHttpRequest.prototype.send` hook into the page via JavaScript and
read the intercepted request/response pairs back out — a different technique
with a different (and, it turned out, incomplete) capture surface. The result
is committed as `captured-requests_anonymized.json`, a plain JSON log of what
the hook actually saw, not a `.har` file, so it isn't mistaken for a native
export.

## Method

1. Logged into `melcloudhome.com` in a real Chrome profile (manual login —
   browser automation does not handle credentials).
2. Injected an interceptor patching `XMLHttpRequest.prototype.open/send` and
   `window.fetch` to log `{method, url, status, requestBody, responseBody}` to
   a page-global array, decoding Blazor's `Uint8Array`-shaped XHR bodies via
   `TextDecoder`.
3. Drove the UI: Scenarios → create a scene named "TEST API CAPTURE DELETE ME"
   targeting one ATA unit (Cucina, 25°C/Cool/Auto fan) → enabled it → disabled
   it → edited it (no-op save) → deleted it. Separately, opened the unit's
   Grafici/Reports → Temperature chart and cycled through all four period tabs
   (Orario/Giorno/Settimana/Mese = Hourly/Daily/Weekly/Monthly).
4. Read the interceptor's buffer back via JavaScript after each step.
5. Cross-checked against the browser's own network monitor
   (`read_network_requests`), which surfaces method/URL/status for every real
   request regardless of whether the JS-level hook caught it — this is how the
   Get-single/Update/Delete gap below was noticed at all.
6. Restored the unit to its pre-capture state (off) and confirmed via the
   dashboard; deleted the test scene so no residue was left on the account.

## Known Gap: Three Calls the Hook Never Caught

`GET /api/scene/{id}`, `PUT /api/scene/{id}` (Update), and
`DELETE /api/scene/{id}` all completed with real `200` responses per the
browser's own network monitor, but **never appeared in the interceptor's
buffer** — despite `PUT /api/scene/{id}/enable` and `/disable` (equally
ID-scoped URLs) being captured without issue. Not root-caused this session.
The JSON file below has entries for these three with `"capturedVia":
"network-monitor-only"` and no body, rather than a guessed one.

## Sampling Note on Trend Summary Datasets

The Hourly/Weekly/Monthly trend responses carry over a hundred datapoints per
dataset in places. Rather than paste the full arrays, the JSON file below
keeps each dataset's **length**, **first point**, and **last point** — enough
to verify the shape and resolution claims in the doc — and says so explicitly
per entry (`"dataSampled": true`). The full arrays were only ever inspected
transiently in-browser and were not saved anywhere.

## Anonymization

Real identifiers seen during this session — the test scene's server-assigned
ID, the target unit's ID, and the account's user ID — are replaced with fixed
placeholder UUIDs (`11111111-...`, `66666666-...`, `aaaaaaaa-...`) throughout
the JSON file, consistently so the same placeholder always maps to the same
real value. Timestamps are real (this was a live capture) but carry no PII.

## Where the Findings Live

The actual documented conclusions from this capture are in
[docs/api/ata-api-reference.md](../../api/ata-api-reference.md), under
**Scenes** and **Trend Summary — Legacy Web Host Variant**. This folder exists
so those claims are checkable against the raw(ish) capture rather than taken
on faith.
