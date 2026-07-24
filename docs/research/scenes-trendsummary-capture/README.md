# Scenes & Trend Summary (Legacy Web Host) — Capture Notes

## What's In This Folder

Two captures backing the **Scenes** and legacy-web **Trend Summary** sections
of [docs/api/ata-api-reference.md](../../api/ata-api-reference.md), both
against `melcloudhome.com` (the web host, distinct from the mobile BFF the
integration talks to — see [Hosts](../../api/ata-api-reference.md#hosts)),
2026-07-23, real account, one live ATA unit exercised:

- **`scenes_anonymized.har`** — a genuine Chrome DevTools "Save all as HAR"
  export, manually captured. Covers the Scenes endpoints: List, Create,
  Enable, Get-single, Update, Disable, Delete. This is the primary evidence
  for that section.
- **`captured-requests_anonymized.json`** — **not** a HAR export. An earlier
  same-day pass drove the UI via `claude-in-chrome` browser automation and
  read requests back through an injected `fetch`/`XMLHttpRequest` hook rather
  than a native export. It's the only source for the **Trend Summary
  legacy-variant** findings (that pass wasn't repeated with a real HAR), and
  it also documents *why* the second capture happened: three Scenes calls
  (Get-single, Update, Delete) completed with real `200`s per the browser's
  own network monitor but never appeared in the hook's buffer — an
  unexplained gap in that technique, not a claim about the API. The real HAR
  above fills exactly that gap.

## Method

**`scenes_anonymized.har`:** DevTools open, Network tab recording, "Preserve
log" on. Drove Scenarios → created a test scene targeting three ATA units
(mixed power on/off per unit) → enabled it → opened it for edit (GET) →
changed a setting and saved (PUT) → deleted it (DELETE). Exported via
right-click → "Save all as HAR with content", then anonymized with
`tools/anonymize_har.py` plus a manual pass (see Anonymization below) and
curated to drop Chrome's `_initiator` stack traces and other verbose
per-request metadata not relevant to the API shape.

**`captured-requests_anonymized.json`:** Injected an interceptor patching
`XMLHttpRequest.prototype.open/send` and `window.fetch` to log `{method, url,
status, requestBody, responseBody}` to a page-global array, decoding Blazor's
`Uint8Array`-shaped XHR bodies via `TextDecoder`. Drove the same Scenes round
trip (a separate test scene, one unit, cleaned up the same way) plus the
target unit's Grafici/Reports → Temperature chart, cycling all four period
tabs (Orario/Giorno/Settimana/Mese = Hourly/Daily/Weekly/Monthly).

Both sessions restored the target unit(s) to their pre-capture state and
deleted their test scenes; verified via the dashboard afterward.

## Sampling Note on Trend Summary Datasets (JSON file only)

The Hourly/Weekly/Monthly trend responses carry over a hundred datapoints per
dataset in places. Rather than paste the full arrays, the JSON file keeps
each dataset's **length**, **first point**, and **last point** — enough to
verify the shape and resolution claims in the doc — and says so explicitly
per entry (`"dataSampled": true`). The full arrays were only ever inspected
transiently in-browser and were not saved anywhere.

## Anonymization

Real identifiers seen during these sessions — unit IDs, scene IDs, the
account's user ID, first/last name, the building's real name — are replaced
with placeholder values, consistently so the same placeholder always maps to
the same real value throughout each file.

For the HAR file specifically: `tools/anonymize_har.py` handles most of this
automatically, but needed three manual corrections applied afterward:
1. The script's generic UUID-scrubbing doesn't know that
   `00000000-0000-0000-0000-000000000000` is a meaningful protocol sentinel
   (the client's literal Create-scene placeholder ID) rather than a real
   identifier — it was getting swapped for a fake UUID like anything else,
   which would have misrepresented the very claim this capture exists to
   verify. Reverted that one specific value back to the literal all-zero GUID.
2. The script's `"name"` field handling isn't memoized per real value (unlike
   its UUID handling), so the same real scene name got a different
   placeholder every time it appeared, and it also caught the HAR's own
   `log.creator.name` (Chrome's internal `"WebInspector"` label) as if it were
   account data. Fixed both: consistent placeholders per real value, and
   `log.creator`/`log.browser` left untouched.
3. The scene ID's URL-embedded form (`.../scene/{id}`, `.../scene/{id}/enable`)
   didn't match the same scene's `id` field in the JSON bodies
   (`BBBBBBBB-BBBB-BBBB-BBBB-000000000004` vs.
   `BBBBBBBB-BBBB-BBBB-BBBB-BBBBBBBBBBBB`): the script's UUID pass replaced
   the real ID with a placeholder ending in a run of one repeated letter,
   and its MAC-address pass then re-matched that same run (indistinguishable
   from a 12-hex-digit MAC) and mangled it again. Both placeholders were
   fake, so this wasn't a real secret leak, but it broke cross-checking that
   the GET/PUT/DELETE calls target the scene the Create call made. Fixed at
   the source (`tools/anonymize_har.py` now skips MAC-anonymizing any
   already-placeholder-shaped run of a single repeated character) and
   corrected in this file.

For the JSON file: identifiers were substituted by hand while writing it,
using the same fixed placeholder values throughout
(`11111111-2222-4333-8444-555555555555` for the unit,
`66666666-7777-4888-8999-000000000000` for the scene,
`aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee` for the user). Timestamps and
temperature readings are real but carry no PII.

## Where the Findings Live

The actual documented conclusions from these captures are in
[docs/api/ata-api-reference.md](../../api/ata-api-reference.md), under
**Scenes** and **Trend Summary — Legacy Web Host Variant**. This folder exists
so those claims are checkable against the capture rather than taken on faith.
