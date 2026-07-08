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
- `desktop_app.py` still owns provider selection, environment setup, and
  loading `desktop_mock/main.py`.
- `desktop_mock/main.py` still serves
  `addon/daily_ai_reading_reinforcement/web/`, injects
  `window.__DAIRR_BRIDGE__`, and handles `/api/bridge`.
- `real_momo_provider.py`, AnkiConnect, config persistence, article
  generation, and card saving remain in Python.

At startup, the Rust shell checks `127.0.0.1:8755`. If an existing DAIRR
backend is already listening, it connects to it. Otherwise it starts:

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

## Next Steps

- Package the Python backend as a signed Tauri sidecar instead of assuming a
  developer checkout and `python3`.
- Decide whether desktop production should keep the HTTP bridge or expose a
  narrower Rust command bridge.
- Add app icons and enable Tauri bundling for macOS `.app` and Windows
  installer artifacts. The current `src-tauri/icons/icon.png` is a development
  placeholder copied from existing project assets so the Tauri configuration
  can compile.
- Add a startup health endpoint to the Python backend so Tauri can distinguish
  DAIRR from another process bound to the same port.
