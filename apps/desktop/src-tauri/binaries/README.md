# DAIRR Backend Sidecar Binaries

This directory holds the platform-specific sidecar binaries for the DAIRR
Tauri desktop application.

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

The target-triple files below are legacy compatibility fallbacks:

| Platform                  | Filename in this directory                             |
|---------------------------|--------------------------------------------------------|
| macOS ARM64 (Apple Silicon) | `dairr-backend-aarch64-apple-darwin`                 |
| macOS Intel               | `dairr-backend-x86_64-apple-darwin`                   |
| Windows MSVC              | `dairr-backend-x86_64-pc-windows-msvc.exe`            |

The checked-in target-triple files are **placeholders** (small shell scripts
that exit 70). They exist so `cargo check` and Tauri config validation can
run before a real backend is packaged. Before publishing a distributable
build, replace each placeholder with a real PyInstaller sidecar binary.

## Building the Sidecar

From the repository root:

```bash
# Build for the current platform (auto-detected)
python3 package_tauri_sidecar.py

# macOS Intel (cross-compile from ARM not supported — build on Intel machine)
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

The build script uses PyInstaller (`pip install pyinstaller`) to produce an
onedir runtime. It bundles:

- `desktop_app.py` as the entry point
- `desktop_mock/` (all provider and server logic)
- `addon/daily_ai_reading_reinforcement/core/` (shared learning logic)
- `addon/daily_ai_reading_reinforcement/web/` (shared HTML/CSS/JS UI)

## Verifying the Sidecar

After building, verify the sidecar is not a placeholder:

```bash
python3 package_tauri_sidecar.py --check-placeholder
```

Start the sidecar and smoke-test the endpoints:

```bash
./apps/desktop/src-tauri/binaries/dairr-backend/dairr-backend \
  --provider mock --host 127.0.0.1 --port 8755 --no-browser

# In another terminal:
curl http://127.0.0.1:8755/api/health
# {"app":"DAIRR","name":"Daily AI Reading Reinforcement",...,"bridge":{"available":true,...}}

curl -X POST http://127.0.0.1:8755/api/bridge \
  -H 'Content-Type: application/json' \
  -d '{"action":"load","payload":{}}'
# {"event":"state","payload":{...}}
```

## Running Tauri with Sidecar Mode

The sidecar path is active in release builds by default. To force it in
development:

```bash
cd apps/desktop
DAIRR_BACKEND_MODE=sidecar npm run dev

# Or point at a specific sidecar build:
DAIRR_BACKEND_SIDECAR=$(pwd)/src-tauri/binaries/dairr-backend-aarch64-apple-darwin \
  DAIRR_BACKEND_MODE=sidecar npm run dev
```

## Build Artifacts

`.build/` under this directory is excluded from version control. It contains
PyInstaller work files and `.spec` files that are not needed after the binary
is produced.

## Current Status

- **macOS ARM64**: real sidecar built and smoke-tested (2026-07-08)
- **macOS Intel**: placeholder — build on Intel hardware
- **Windows MSVC**: placeholder — build on Windows
