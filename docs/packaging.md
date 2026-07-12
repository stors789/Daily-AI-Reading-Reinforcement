# Desktop Packaging Scaffold

This is the first packaging scaffold for DAIRR desktop mode. It standardizes
the future PyInstaller command shape, but it is not a formal release pipeline
yet.

Install the pinned-major desktop runtime and packaging dependencies in a clean
environment on the target operating system:

```bash
python3 -m pip install -r requirements-desktop.txt
```

PyInstaller does not cross-compile. Build macOS artifacts on macOS and Windows
artifacts on Windows so the packaged keyring backend matches the target.

## Entry Points

Start with the browser entry:

```bash
python3 package_desktop.py --entry browser --dry-run
python3 package_desktop.py --entry browser --windowed --clean
```

The browser entry packages `desktop_app.py`, which launches the existing local
server and opens the shared web UI in the system browser.

The native entry packages `desktop_native.py`:

```bash
python3 package_desktop.py --entry native --windowed --clean
```

Use the native entry only in a packaging environment where pywebview is
installed. pywebview remains optional and is not a repository dependency.

## Included Data

`package_desktop.py` includes the shared web UI and desktop runtime files with
PyInstaller `--add-data` arguments:

```text
addon/daily_ai_reading_reinforcement/web
desktop_mock
```

The script uses the correct PyInstaller add-data separator for the current
platform: `;` on Windows and `:` on macOS/Linux.

## Packaged App Data

Packaged desktop mode uses the same default user-data paths defined in
`desktop_mock/desktop_paths.py`:

- macOS: `~/Library/Application Support/DAIRR/`
- Windows: `%APPDATA%/DAIRR/`
- Linux: `~/.local/share/dairr/`

These defaults cover the desktop config and generated article output paths
unless the user overrides them with environment variables.

## Credential storage

Packaged desktop builds include `keyring` and its macOS and Windows backends.
Credentials are stored in macOS Keychain or Windows Credential Manager; the
JSON configuration keeps non-secret settings and credential references only.

On first use after upgrading, DAIRR migrates legacy plaintext credentials to
the system credential store. It removes each plaintext value only after the
secure write succeeds. A missing, locked, or unusable system backend makes the
operation fail closed: DAIRR does not silently write the credential back to
JSON. Release acceptance must exercise the packaged app on its target OS,
including restart, update, delete, migration-failure, and non-ASCII-user tests.
