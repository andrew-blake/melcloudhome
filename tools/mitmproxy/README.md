# mitmproxy Setup for MELCloud API Capture

Capture and inspect traffic between the MELCloud Home mobile app and the mobile BFF API using [mitmproxy](https://mitmproxy.org/) — a free, open-source, cross-platform HTTPS proxy.

## Prerequisites

Install the reverse-engineering dependencies:

```bash
uv sync --group reverse-engineering
```

This installs `mitmdump` into the project venv. All commands below use `uv run` to invoke it.

## iOS Device Setup

Your iPhone and dev machine must be on the same Wi-Fi network.

### 1. Find your dev machine's IP

```bash
ipconfig getifaddr en0
```

### 2. Configure Wi-Fi proxy on iPhone

1. Settings > Wi-Fi > tap (i) on your network
2. Scroll to HTTP Proxy > Configure Proxy > Manual
3. Server: your dev machine IP from step 1
4. Port: `8080`

### 3. Install the mitmproxy CA certificate

1. Start mitmproxy: `uv run mitmdump`
2. On iPhone Safari, go to **http://mitm.it** (must be HTTP, not HTTPS)
3. Tap "Apple" to download the profile
4. Settings > General > VPN & Device Management > install the mitmproxy profile
5. Settings > General > About > Certificate Trust Settings > enable trust for the mitmproxy CA
6. Stop mitmdump (Ctrl-C)

### 4. Verify

```bash
uv run mitmdump -s tools/mitmproxy/capture.py
```

Open the MELCloud Home app. You should see MELCloud requests logged to the console.

## Usage

### Interactive exploration

```bash
uv run mitmdump --set view_filter='~d melcloudhome.com | ~d amazoncognito.com'
```

Shows only MELCloud traffic. All other traffic passes through transparently.

### Scripted capture (for reproducible recording)

```bash
uv run mitmdump -s tools/mitmproxy/capture.py
```

Filters to MELCloud domains, logs request/response summaries, and saves flows to `tools/mitmproxy/captures/<timestamp>.flow`. The captures directory is gitignored.

### Exporting captures for contribution

Flow files are binary and contain credentials. To share captures, export to HAR and anonymize:

```bash
# 1. Export .flow to HAR
uv run mitmdump -r tools/mitmproxy/captures/<file>.flow --set hardump=capture.har

# 2. Anonymize (strips tokens, device IDs, emails, etc.)
python tools/anonymize_har.py capture.har capture_anonymized.har
```

The anonymized HAR can be committed or shared. See `tools/anonymize_har.py` for what gets redacted.

### Replaying captures

```bash
uv run mitmdump -r tools/mitmproxy/captures/<file>.flow
```

### Ad-hoc domain filtering

```bash
uv run mitmdump --set view_filter='~d auth.melcloudhome.com'
```

## Domains

| Domain | Purpose |
|--------|---------|
| `mobile.bff.melcloudhome.com` | Data API (device state, telemetry, control) |
| `auth.melcloudhome.com` | OAuth 2.0 / IdentityServer (PKCE flow) |
| `*.amazoncognito.com` | AWS Cognito (login UI) |

## iPhone Cleanup

When you're done capturing, undo the proxy setup:

1. Settings > Wi-Fi > tap (i) on your network > HTTP Proxy > **Off**
2. Settings > General > VPN & Device Management > mitmproxy > **Remove Profile**

If you skip step 1, the iPhone won't have internet when mitmproxy isn't running.

## Gotchas

- **Do NOT use `--set confdir=tools/mitmproxy`** — this overrides mitmproxy's certificate directory, causing TLS failures on devices that trust the default `~/.mitmproxy` CA. Pass options on the command line instead.
- **`allow_hosts` blocks non-matching traffic** — it doesn't just filter the display, it prevents other domains from connecting. Use `view_filter` instead.
- **Certificate install must use HTTP** — visit `http://mitm.it` (not HTTPS) on the device to download the CA cert.

## Tips

- **JWT inspection:** Access tokens are JWTs — copy from the `Authorization` header and paste into jwt.io to inspect claims.
- **OAuth flow:** Filter by `auth.melcloudhome.com` to trace the full PKCE flow: PAR > authorize > Cognito > callback > token exchange.
- **Certificate pinning:** The MELCloud Home iOS app does not appear to use certificate pinning as of April 2026. If a future update adds pinning, mitmproxy will show TLS handshake errors.
