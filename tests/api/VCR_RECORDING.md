# VCR Cassette Recording Guide

VCR cassettes record real HTTP interactions with the MELCloud mobile BFF API for replay in tests. This gives us real API response shapes without hitting the network on every test run.

## Key Principles

1. **Always record against the real API** (`mobile.bff.melcloudhome.com`), never the mock server. Cassettes should capture real response shapes and data structures.
2. **Control tests modify real hardware.** The `test_client_control.py` and `test_atw_control_vcr.py` files send PUT commands to real devices. Dump device state before and after to verify restoration.
3. **Deterministic PKCE seeding** is applied automatically via `tests/api/conftest.py`. This ensures the OAuth PKCE flow produces identical query strings during recording and replay, which is required because `match_on` includes `query`.
4. **Secrets are automatically redacted** by the VCR config in `tests/conftest.py` — access tokens, refresh tokens, cookies, passwords, CSRF tokens, emails, building names, and device names.

## Prerequisites

```bash
# Set credentials in .env
echo "MELCLOUD_USER=your@email.com" >> .env
echo "MELCLOUD_PASSWORD=yourpassword" >> .env
source .env
```

## Recording Cassettes

### Read-only tests (safe)

These only GET data — no risk to real devices:

```bash
source .env
uv run pytest tests/api/test_client_read.py -v
uv run pytest tests/api/test_energy.py -v
uv run pytest tests/api/test_energy_atw.py -v
uv run pytest tests/api/test_telemetry.py -v
uv run pytest tests/api/test_outdoor_temperature_vcr.py -v
uv run pytest tests/api/test_multi_building.py -v
uv run pytest tests/api/test_atw_models.py -v
```

### Control tests (careful — modifies real hardware)

These send PUT commands to real devices. Always:
1. Dump state before
2. Record cassettes
3. Dump state after and diff
4. Restore any differences manually

```bash
# 1. Save baseline
source .env
uv run python tools/dump_device_state.py --json > /tmp/state_before.json

# 2. Record (one file at a time)
uv run pytest tests/api/test_client_control.py -v      # ATA devices
uv run pytest tests/api/test_atw_control_vcr.py -v      # ATW devices

# 3. Verify restoration
uv run python tools/dump_device_state.py --json > /tmp/state_after.json
diff <(jq -S . /tmp/state_before.json) <(jq -S . /tmp/state_after.json)

# 4. Fix any differences (tests should restore state, but verify)
```

### Rate limiting

Recording ~44 cassettes means ~44 full OAuth PKCE login flows against `auth.melcloudhome.com` and Cognito. Record **per-file** (not `make test-api`) to avoid rate limiting. If you get 429s, wait a few minutes between files.

## Re-recording

To re-record a specific test's cassette:

```bash
# Delete the old cassette
rm -f tests/api/cassettes/test_name_here.yaml

# Re-record
source .env
uv run pytest tests/api/test_file.py::test_name_here -v
```

VCR's `record_mode: "once"` means it only records when the cassette file doesn't exist. To force re-recording, delete the cassette first.

## Verifying Cassettes

After recording, check for leaked secrets:

```bash
# Should return empty (all tokens redacted)
grep -i "access_token\|refresh_token\|id_token" tests/api/cassettes/*.yaml | grep -v REDACTED

# Verify mobile BFF paths are used
grep -l "/context\|/monitor/" tests/api/cassettes/*.yaml | head -5
```

## How It Works

### Authentication flow in cassettes

Every VCR cassette starts with the full OAuth PKCE auth chain (~6-8 HTTP interactions):
1. POST `auth.melcloudhome.com/connect/par` (Pushed Authorization Request)
2. GET `auth.melcloudhome.com/connect/authorize` → redirects to Cognito
3. GET/POST Cognito login page (credential submission)
4. GET `auth.melcloudhome.com/connect/authorize/callback` → redirect with auth code
5. POST `auth.melcloudhome.com/connect/token` (code → token exchange)
6. Actual API call(s) to `mobile.bff.melcloudhome.com`

### Deterministic PKCE

The OAuth PKCE flow generates random values (`state`, `code_challenge`, `code_verifier`) that appear in query strings. VCR matches on query strings, so these must be identical during recording and replay. The `deterministic_pkce` fixture in `tests/api/conftest.py` patches `secrets.token_bytes` with a seeded function to achieve this.

### Redaction

Configured in `tests/conftest.py`:
- **Headers:** `authorization`, `cookie`, `set-cookie`
- **POST params:** `username`, `password`, `_csrf`, `code_verifier`, `code`, `refresh_token`
- **Response bodies:** `access_token`, `refresh_token`, `id_token`, email addresses, names, building names, device names

## Test Account

The VCR test account is a beta tester with **guest** access. Devices appear under `guestBuildings`, not `buildings`. This is expected — see `memory/project_vcr_test_account.md`.

## Troubleshooting

### "Not authenticated" errors on replay

The deterministic PKCE fixture may not be active. Ensure `tests/api/conftest.py` exists and contains the `deterministic_pkce` fixture.

### Empty `measureData` in energy tests

Some devices don't report all energy measures. The test account's ATW device reports `interval_energy_produced` but not `interval_energy_consumed`. Energy tests use `@freeze_time` to fix the time window — update the frozen date if data has aged out.

### Control test left device in wrong state

Use the dump tool to check and restore:

```bash
source .env
uv run python tools/dump_device_state.py --unit-id <uuid>
```
