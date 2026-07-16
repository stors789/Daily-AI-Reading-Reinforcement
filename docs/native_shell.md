# Desktop shells

DAIRR’s preferred standalone product shell is Tauri. The dependency-free browser launcher and optional pywebview launcher remain useful for development, diagnosis, and fallback.

## Tauri (preferred)

Tauri owns the native window and starts the Python backend/sidecar. The backend continues to own providers, the authenticated loopback bridge, persistence, and the portable UI.

```bash
cd apps/desktop
npm install
npm run dev
```

Provider examples:

```bash
DAIRR_DESKTOP_PROVIDER=ankiconnect npm run dev
DAIRR_DESKTOP_PROVIDER=real_momo MOMO_TOKEN=your-test-token npm run dev
```

Debug builds normally start the Python development launcher. Release jobs build a target-native PyInstaller onedir runtime at `apps/desktop/src-tauri/binaries/dairr-backend/`, and Tauri bundles that directory as a resource. Generated runtime contents are ignored; the repository contains no sidecar executable or target-triple placeholder. PyInstaller does not cross-compile, so each macOS architecture and Windows x64 must build on its corresponding native runner. Run the sidecar build and runtime-entry check before building an artifact.

The shell probes `/api/health` before loading the UI, rejects an already-owned port, and waits for the child-specific `instanceId` before opening the workbench. Browser-originated bridge POSTs require an exact loopback `Origin` such as `http://127.0.0.1:8755` and the page-injected per-process token in `X-DAIRR-Bridge-Token`; `/api/health` does not reveal that token. The shared UI uses the injected bridge automatically.

## Browser fallback

```bash
python3 desktop_app.py --provider mock
python3 desktop_app.py --provider ankiconnect
python3 desktop_app.py --provider ankiconnect --no-browser
```

This is the simplest way to isolate backend/UI issues. It uses the same server, UI, actions, local data, and provider adapters as the native shell.

## pywebview transition shell

```bash
python3 desktop_native.py --provider mock
python3 desktop_native.py --provider ankiconnect
python3 desktop_native.py --provider ankiconnect --fallback-browser
```

pywebview is optional and is not auto-installed by the launcher. When installed, the launcher opens the same loopback UI in a native window with persistent app storage so local draft recovery continues to work. Older pywebview versions are retried without the newer `private_mode` keyword only when that exact signature is unsupported.

Supported options include `--provider mock|real_momo|ankiconnect`, `--host`, `--port`, `--ankiconnect-url`, and `--fallback-browser`. The host remains constrained to loopback by the server.

## Distribution boundary

Tauri, pywebview, and browser launchers are not equivalent release evidence:

- browser/pywebview package checks prove only those fallback entries;
- a Tauri release requires a real target-native sidecar and installed-app smoke test;
- macOS distribution additionally requires signature/notarization verification;
- Windows distribution additionally requires target-native build, installer, Authenticode/timestamp, and SmartScreen validation;
- updater signing is independent from OS signing.

See [packaging](packaging.md), [automatic updates](desktop_auto_updates.md), and the [manual verification guide](manual-verification.md).
