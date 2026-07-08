# Desktop Packaging Scaffold

This is the first packaging scaffold for DAIRR desktop mode. It standardizes
the future PyInstaller command shape, but it is not a formal release pipeline
yet.

The repository does not commit PyInstaller, pywebview, or a packaging
requirements file. Install those optional tools only in the environment you use
for packaging.

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
