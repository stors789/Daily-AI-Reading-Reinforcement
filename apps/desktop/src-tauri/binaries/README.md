# DAIRR Backend Sidecar Binaries

This directory is the build destination for the target-native DAIRR Python
sidecar used by the Tauri desktop application. Generated runtimes are ignored
and must never be committed.

## Sidecar Purpose

Tauri starts the sidecar as a subprocess before opening the app window. The
sidecar exposes the same CLI and HTTP API as `desktop_app.py`:

```bash
dairr-backend --provider ankiconnect --host 127.0.0.1 --port 8755 --no-browser
```

Tauri verifies the backend is healthy by calling `GET /api/health` before
loading the window.

## Runtime Layout

The production build is an onedir PyInstaller runtime at
`binaries/dairr-backend/dairr-backend` (`.exe` on Windows). Tauri bundles this
directory as an application resource, avoiding onefile extraction on every
launch.

There are no checked-in executable placeholders. Every release job builds the
onedir runtime natively for its target and then fails the build if the runtime
entry is absent or still looks like a placeholder. The `--target-triple`
argument selects the target's runtime-entry convention (not an alternate
output name); PyInstaller itself does not cross-compile.

## Building the Sidecar

From the repository root:

```bash
# Build for the current platform (auto-detected)
python3 package_tauri_sidecar.py

# macOS Intel (run on Intel macOS; cross-compilation is not supported)
python3 package_tauri_sidecar.py --target-triple x86_64-apple-darwin

# Windows (from a Windows machine)
python3 package_tauri_sidecar.py --target-triple x86_64-pc-windows-msvc

# Dry-run: print the PyInstaller command without building
python3 package_tauri_sidecar.py --dry-run

# Clean rebuild
python3 package_tauri_sidecar.py --clean

# Check if the sidecar is a placeholder
python3 package_tauri_sidecar.py --check-placeholder
```

The build script uses PyInstaller (`pip install pyinstaller`) to produce a
target-native onedir runtime at the resource path above. It bundles:

- `desktop_app.py` as the entry point
- `desktop_mock/` (all provider and server logic)
- `packages/dairr_core/src/dairr_core/` (shared learning logic)
- `addon/daily_ai_reading_reinforcement/web/` (shared HTML/CSS/JS UI)

## Verifying the Sidecar

After building, verify the sidecar is not a placeholder:

```bash
python3 package_tauri_sidecar.py --check-placeholder
```

Start the sidecar and smoke-test the endpoints. Bridge POSTs require both the
per-process token injected into the served page and an allowed loopback
`Origin`; an unauthenticated curl example is expected to receive HTTP 403.

```bash
./apps/desktop/src-tauri/binaries/dairr-backend/dairr-backend \
  --provider mock --host 127.0.0.1 --port 8755 --no-browser

# In another terminal:
curl http://127.0.0.1:8755/api/health
# {"app":"DAIRR","name":"Daily AI Reading Reinforcement",...,"bridge":{"available":true,...}}

BRIDGE_TOKEN="$(curl -fsS http://127.0.0.1:8755/ | python3 -c 'import re,sys; page=sys.stdin.read(); match=re.search(r"window\.__DAIRR_BRIDGE_TOKEN__ = \"([0-9A-Za-z_-]+)\"", page); print(match.group(1) if match else "")')"
test -n "$BRIDGE_TOKEN"
curl -X POST http://127.0.0.1:8755/api/bridge \
  -H 'Origin: http://127.0.0.1:8755' \
  -H 'Content-Type: application/json' \
  -H "X-DAIRR-Bridge-Token: $BRIDGE_TOKEN" \
  -d '{"version":2,"requestId":"manual-smoke-1","action":"load","payload":{}}'
# {"version":2,"requestId":"manual-smoke-1","event":"state","payload":{...}}
```

## Running Tauri with Sidecar Mode

The sidecar path is active in release builds by default. To force it in
development:

```bash
cd apps/desktop
DAIRR_BACKEND_MODE=sidecar npm run dev

# Or point at the current target-native onedir entry:
DAIRR_BACKEND_SIDECAR=$(pwd)/src-tauri/binaries/dairr-backend/dairr-backend \
  DAIRR_BACKEND_MODE=sidecar npm run dev
```

## Build Artifacts

`.build/` under this directory is excluded from version control. It contains
PyInstaller work files and `.spec` files that are not needed after the binary
is produced.

## Release Status

No executable is represented by repository state alone. The release workflow
builds and checks a fresh sidecar on macOS ARM64, macOS Intel, and Windows x64.
Signed/notarized installability and installed-app behavior remain properties of
the corresponding release job and its smoke/manual verification evidence; the
checked-in `.gitkeep` makes no such claim.
