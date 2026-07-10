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

The Tauri config now enables bundling and declares the onedir runtime as a
resource:

```json
"resources": ["binaries/dairr-backend"]
```

The packaged runtime entry is `binaries/dairr-backend/dairr-backend` (or
`dairr-backend.exe` on Windows). Legacy target-triple files remain available
as compatibility fallbacks, for example:

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

## Sidecar Build Pipeline (Phase 3)

### Build Script

`package_tauri_sidecar.py` (repository root) generates platform-specific
sidecar binaries from the existing Python backend using PyInstaller.

The script:

1. Auto-detects the current platform's target triple
2. Builds a PyInstaller onedir runtime containing `desktop_app.py`,
   `desktop_mock/`, shared core, and shared web UI
3. Writes it to `apps/desktop/src-tauri/binaries/dairr-backend/`
4. Lets Tauri copy that directory into the application resources

Onedir is deliberate: the previous onefile build took about 15 seconds to
unpack on every cold launch, while the same backend starts from onedir in about
0.13 seconds on the ARM64 development machine.

### Supported Target Triples

| Triple                      | Build environment     | Status (2026-07-08)            |
|-----------------------------|-----------------------|--------------------------------|
| `aarch64-apple-darwin`      | macOS ARM64           | Real binary, smoke-tested      |
| `x86_64-apple-darwin`       | macOS Intel           | Placeholder — build on Intel   |
| `x86_64-pc-windows-msvc`    | Windows               | Placeholder — build on Windows |

### Build Commands

```bash
# macOS ARM64 (auto-detected)
python3 package_tauri_sidecar.py

# macOS Intel
python3 package_tauri_sidecar.py --target-triple x86_64-apple-darwin

# Windows
python3 package_tauri_sidecar.py --target-triple x86_64-pc-windows-msvc

# Dry-run, check placeholder, clean rebuild
python3 package_tauri_sidecar.py --dry-run
python3 package_tauri_sidecar.py --check-placeholder
python3 package_tauri_sidecar.py --clean
```

### Sidecar Verification

The sidecar exposes the same three endpoints as `desktop_mock/main.py`:

- `GET /api/health` — returns `{"app":"DAIRR","bridge":{"available":true}}`
- `POST /api/bridge` — handles all `load`, `generate`, `saveArticleCard`, etc.
- `GET /` — serves the full DAIRR web UI with injected `__DAIRR_BRIDGE__`

Smoke test procedure:

```bash
python3 package_tauri_sidecar.py --check-placeholder
./apps/desktop/src-tauri/binaries/dairr-backend/dairr-backend \
  --provider mock --host 127.0.0.1 --port 8755 --no-browser
curl http://127.0.0.1:8755/api/health
curl -X POST http://127.0.0.1:8755/api/bridge \
  -H 'Content-Type: application/json' -d '{"action":"load","payload":{}}'
```

### Running Tauri with Sidecar Mode

```bash
cd apps/desktop
DAIRR_BACKEND_MODE=sidecar npm run dev
DAIRR_BACKEND_SIDECAR=/path/to/dairr-backend-aarch64-apple-darwin \
  DAIRR_BACKEND_MODE=sidecar npm run dev
```

### Sandbox Note

The PyInstaller bootloader calls `nice(5)` and `semctl` during startup.
These calls are blocked by macOS application sandboxing, which means the
sidecar binary cannot run inside a strict sandbox. This affects the
`npm run dev` and `cargo test` development flows when using `direnv` or
sandboxed environments.

In production, the Tauri bundle includes the runtime under
`Resources/binaries/dairr-backend/` and starts it while the startup window is
visible. The Tauri process itself will have the necessary entitlements.

The Desktop dev flow (`python3 desktop_app.py` and `npm run dev` with the
default Python launcher) is unaffected since it runs `python3` directly
without a PyInstaller wrapper.

### Testing

Sidecar-specific tests live in `tests/test_tauri_app_shell.py` class
`TauriSidecarTests`:

- Placeholder detection for all three target triples
- `package_tauri_sidecar.py` build script exists and is runnable
- Target triple naming rules produce correct filenames
- Dry-run mode outputs expected PyInstaller command
- Known target triples are in the valid set
- `is_placeholder()` correctly detects known placeholder files

Run with:

```bash
python3 -m pytest tests/test_tauri_app_shell.py -v -k Sidecar
```

### Next Steps

- Build macOS Intel sidecar on Intel hardware
- Build Windows sidecar on Windows
- Sign and notarize macOS sidecar for distribution
- Verify the full `npm run build` pipeline with real sidecar binaries
- Consider caching the PyInstaller build output in CI to avoid repeated
  Python bundling
