# Packaging and release artifacts

DAIRR has three packaging paths: the supported Anki add-on archive, the Tauri desktop product bundle with a Python sidecar, and legacy browser/pywebview PyInstaller fallbacks. Android has its own build/validation instructions under `apps/android/README.md`.

Packaging must run natively on the target OS/architecture. Do not cross-label a dry-run or a different platform’s artifact as verified.

## Anki add-on

```bash
python3 package_addon.py
```

Output: `dist/daily_ai_reading_reinforcement.ankiaddon`.

The builder includes the shared core under `dairr_core/`, sanitizes credential-like configuration values, excludes bytecode/caches, and excludes private contents of `user_files` except its marker README. Inspect the archive before release.

## Tauri desktop product

Requirements include Python 3.11+, PyInstaller, Node/npm, Rust, Tauri platform dependencies, and target-native signing tools where distribution signing is claimed.

1. Build the target-native Python sidecar:

   ```bash
   python3 package_tauri_sidecar.py --clean
   python3 package_tauri_sidecar.py --check-runtime
   ```

2. Build the Tauri bundle:

   ```bash
   cd apps/desktop
   npm install
   npm run build
   ```

Tauri targets DMG on macOS and NSIS on Windows. Its resource contract expects the onedir backend at `apps/desktop/src-tauri/binaries/dairr-backend/`. The runtime must include the portable UI, complete shared core, desktop bridge/server, AnkiConnect provider and normalized adapter, persistence/config/provider modules, and their dynamic standard-library imports.

PyInstaller cannot cross-compile the Python runtime. Build macOS ARM64 on ARM64 macOS, macOS Intel on Intel macOS, and Windows x64 on Windows x64. A real build or runtime check fails if `--target-triple` does not match the native host. `package_tauri_sidecar.py --dry-run` is the explicit command-construction-only exception and produces no artifact.

Before publishing, launch the installed bundle without the repository or a system Python, verify mock and applicable AnkiConnect modes, inspect storage paths, quit/sidecar cleanup, and run the [manual verification guide](manual-verification.md).

The credential-free consolidated gate is:

```bash
python3 scripts/desktop_release.py pre-publish
```

It validates synchronized and secret-free release metadata, compiles/imports production Python, runs the full unit suite, inspects add-on package privacy, checks the portable UI and JavaScript syntax, runs Android static validation plus exactly seven SDK-free JVM tests against production Android sources, checks browser/native/sidecar PyInstaller commands, reports the Tauri environment, and runs locked Rust compilation. The Android JVM harness discovers and validates JDK 17 and accepts the explicitly tested Gradle 8.10.2 and 9.6.1 versions while reporting the version actually used; CI installs the canonical JDK 17/Gradle 8.10.2 combination explicitly. A first clean run resolves pinned Kotlin/JUnit/JSON dependencies from public repositories. It does not manufacture signing credentials or prove another OS.

## Browser and pywebview fallbacks

```bash
python3 package_desktop.py --entry browser --dry-run
python3 package_desktop.py --entry browser --windowed --clean
python3 package_desktop.py --entry native --dry-run
python3 package_desktop.py --entry native --windowed --clean
```

The browser entry packages `desktop_app.py`. The native entry packages `desktop_native.py` and requires pywebview in the build/runtime environment. These are fallback artifacts, not substitutes for validating the Tauri product bundle.

## User-data boundary

Packaged desktop mode stores data outside the application bundle:

- macOS: `~/Library/Application Support/DAIRR/`
- Windows: `%APPDATA%\DAIRR\`
- Linux/development: `~/.local/share/dairr/`

An existing legacy `~/.dairr_config.json` remains preferred for backward compatibility. Packaging/updating application files must not delete config, article Markdown/HTML/manifests, or practice-session JSON.

Never package or publish local config, credentials, articles, practice text, logs, output directories, build caches, virtual environments, or raw diagnostic captures.

## Signing and updater claims

- A local/ad-hoc macOS signature is not Developer ID notarization.
- An unsigned NSIS installer is not Authenticode verified and can trigger SmartScreen.
- A Tauri updater signature does not replace Apple/Windows code signing.
- Release staging rejects missing or zero-byte installers/updater archives and missing, empty, or blank updater signatures. Both architecture-specific DMGs must be present alongside the three signed updater artifacts before `latest.json` is emitted.
- Checked-in updater configuration and CI workflow do not prove that credentials were present or a release was published.

See [desktop automatic updates](desktop_auto_updates.md) for required credentials and [release notes](release-notes-next-major.md) for the current distribution status.
