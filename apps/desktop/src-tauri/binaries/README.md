This directory is reserved for the packaged DAIRR backend sidecar.

Tauri's `bundle.externalBin` entry points at `binaries/dairr-backend`.
At bundle time, provide platform-specific executables using Tauri's target
triple naming convention, for example:

- `dairr-backend-aarch64-apple-darwin`
- `dairr-backend-x86_64-pc-windows-msvc.exe`

The sidecar should expose the same CLI as `desktop_app.py`:

```bash
dairr-backend --provider ankiconnect --host 127.0.0.1 --port 8755 --no-browser
```

The checked-in target-triple files are placeholders so `cargo check` and
Tauri config validation can run before the real packaged Python backend exists.
Replace them in the packaging pipeline before producing distributable builds.

The Rust launcher checks both `dairr-backend` and the current platform's
target-triple filename, matching Tauri's `externalBin` naming convention.
