# Tauri App Shell Technical Verification

## Decision

DAIRR's first standalone desktop verification shell lives in `apps/desktop/`.
That matches the target layout in `AGENTS.md` without moving the existing
Anki add-on, shared web UI, or Python desktop backend.

Tauri is the preferred proof-of-concept shell because DAIRR's current product
surface is already HTML/CSS/JS, and Tauri can provide a macOS/Windows native
window while the existing Python provider stack stays intact. The current
Tauri configuration follows the Tauri v2 model where `devUrl` is the
development URL and `frontendDist` can point at a URL during this brownfield
phase.

## Current Boundary

The shell is deliberately thin:

- Tauri owns the native desktop process and the main app window.
- In development mode, `desktop_app.py` still owns provider selection,
  environment setup, and loading `desktop_mock/main.py`.
- In production mode, Tauri expects to start a bundled backend sidecar with
  the same CLI shape as `desktop_app.py`.
- `desktop_mock/main.py` still serves
  `addon/daily_ai_reading_reinforcement/web/`, injects
  `window.__DAIRR_BRIDGE__`, and handles `/api/bridge` plus `/api/health`.
- `real_momo_provider.py`, AnkiConnect, config persistence, article
  generation, and card saving remain in Python.

At startup, the Rust shell checks `127.0.0.1:8755`. A listening port is never
trusted by TCP alone. Tauri first requests `GET /api/health` and only reuses
the process if the response identifies itself as DAIRR and reports the bridge
as available. If another local service owns the port, startup fails with a
clear port ownership error instead of loading an unrelated page.

## Backend Modes

### Development Backend

Debug builds default to the Python development launcher:

```bash
python3 desktop_app.py --provider mock --host 127.0.0.1 --port 8755 --no-browser
```

Environment overrides are preserved:

- `DAIRR_REPO_ROOT`: explicit repository root for development or unusual
  launch locations.
- `DAIRR_PYTHON`: Python executable to use instead of `python3`.
- `DAIRR_DESKTOP_PROVIDER`: `mock`, `ankiconnect`, or `real_momo`.
- `DAIRR_ANKICONNECT_URL`: AnkiConnect endpoint when using that provider.
- `MOMO_TOKEN` / `Maimemo_key`: MoMo token consumed by the existing provider.
- `DAIRR_BACKEND_MODE=dev` or `DAIRR_BACKEND_MODE=python`: force the Python
  development launcher.

This path keeps the current developer workflow intact and preserves the
browser launcher and pywebview fallback.

### Production Sidecar

Release builds default to the production sidecar path. Tauri looks for a
bundled backend executable named `dairr-backend` and starts it with the same
arguments as the development launcher:

```bash
dairr-backend --provider ankiconnect --host 127.0.0.1 --port 8755 --no-browser
```

The sidecar boundary is intentionally at the process and HTTP bridge level.
MoMo, AnkiConnect, article generation, config storage, and card saving remain
inside the Python backend. This phase does not migrate provider logic to Rust.

The Tauri config now enables bundling and declares:

```json
"externalBin": ["binaries/dairr-backend"]
```

At bundle time, platform-specific sidecar files must be created using Tauri's
target-triple convention, for example:

- `dairr-backend-aarch64-apple-darwin`
- `dairr-backend-x86_64-apple-darwin`
- `dairr-backend-x86_64-pc-windows-msvc.exe`

The checked-in files with those names are placeholders for Tauri config
validation and `cargo check`. They are not production backends and must be
replaced by packaged Python sidecar executables before distributable builds are
created.

Useful overrides:

- `DAIRR_BACKEND_MODE=sidecar` or `DAIRR_BACKEND_MODE=production`: force the
  sidecar path, even in a debug build.
- `DAIRR_BACKEND_SIDECAR=/absolute/path/to/dairr-backend`: test a specific
  sidecar executable before it is bundled.

## Health Check Protocol

`GET /api/health` returns JSON and must be cheap, local, and safe. It must not
initialize network-backed providers.

Current response shape:

```json
{
  "app": "DAIRR",
  "name": "Daily AI Reading Reinforcement",
  "version": "0.1.0",
  "mode": "desktop",
  "provider": "mock",
  "bridge": {
    "available": true,
    "type": "http",
    "endpoint": "/api/bridge",
    "windowObject": "__DAIRR_BRIDGE__"
  }
}
```

Tauri requires:

- HTTP 200
- valid JSON
- `app == "DAIRR"`
- `bridge.available == true`

`provider` and `mode` are logged for diagnosis but are not provider
connectivity guarantees. Provider diagnostics stay in the existing Python
diagnostic tools.

## Why Not Rewrite the Backend Yet

The existing Python backend already isolates the standalone runtime from Anki
internals. Rewriting provider calls as Rust commands in this phase would
increase risk without proving the app-shell question. Keeping the HTTP bridge
lets the first Tauri build validate window startup, resource loading, and
provider connectivity while preserving add-on compatibility.

## Android Path

Android is not packaged in this phase. The useful boundary for Android is the
same bridge contract:

- Shared UI remains portable.
- Provider/storage behavior sits behind adapters.
- A future Android shell can replace the local Python HTTP backend with a
  mobile-native bridge while keeping `window.__DAIRR_BRIDGE__.send(action,
  payload)` as the UI contract.

Before Android packaging, avoid adding desktop-only assumptions to
`addon/daily_ai_reading_reinforcement/web/`. Platform details should remain in
the shell or provider adapters.

## Run

```bash
cd apps/desktop
npm install
npm run dev
```

For AnkiConnect:

```bash
cd apps/desktop
DAIRR_DESKTOP_PROVIDER=ankiconnect npm run dev
```

For MoMo:

```bash
cd apps/desktop
DAIRR_DESKTOP_PROVIDER=real_momo MOMO_TOKEN=... npm run dev
```

To test the production path before bundling:

```bash
cd apps/desktop
DAIRR_BACKEND_MODE=sidecar DAIRR_BACKEND_SIDECAR=/path/to/dairr-backend npm run dev
```

## Next Steps

- Package the Python backend as a Tauri sidecar instead of assuming a developer
  checkout and `python3`.
- Decide whether desktop production should keep the HTTP bridge or expose a
  narrower Rust command bridge.
- Generate and verify platform sidecar binaries for macOS ARM64, macOS Intel,
  and Windows MSVC.
- Decide whether production should keep loading web assets through the backend
  or bundle static assets as Tauri resources and let the backend only serve API
  routes.
- Add production icons and app metadata. The current
  `src-tauri/icons/icon.png` is still a development placeholder copied from
  existing project assets.
- Add signing, notarization, and installer publishing only after unsigned local
  bundles are verified.

## macOS and Windows Packaging Risks

- Sidecar generation is not complete in this phase. The configured
  `externalBin` path documents the bundle contract, and the current
  target-triple files are placeholders. CI still needs to replace them with
  real packaged Python sidecar binaries.
- macOS packaging will need code signing and notarization for distribution.
  Those are deliberately not enabled yet.
- Windows packaging will need a stable WebView2 and installer strategy. The
  current config keeps the existing WebView2 bootstrapper behavior but does not
  sign installers.
- Port `8755` remains a local singleton. Health checks prevent accidental reuse
  of unrelated services, but the product may later need dynamic port selection
  for multiple running instances.
- The sidecar must include or locate the shared web UI and Python modules in a
  way that does not rely on the source checkout.
