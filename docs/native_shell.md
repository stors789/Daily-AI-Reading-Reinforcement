# Native Shell Scaffold

DAIRR currently includes an optional pywebview native shell scaffold:

```bash
python3 desktop_native.py --provider mock
python3 desktop_native.py --provider ankiconnect
python3 desktop_native.py --provider ankiconnect --fallback-browser
```

This is a first native-shell entry point, not a final packaged macOS/Windows
application. It starts the existing `desktop_mock/main.py` local server and, if
pywebview is available in the current Python environment, opens the shared web
UI at `http://127.0.0.1:8755` in a native window.

pywebview and the desktop credential backend are declared in
`requirements-desktop.txt`; the launcher does not auto-install them. Install
that file only in the native development or packaging environment:

```bash
python3 -m pip install -r requirements-desktop.txt
```
If pywebview is missing, `desktop_native.py` prints:

```text
pywebview is not installed. Use python3 desktop_app.py --provider mock instead.
```

The dependency-free launcher remains the stable standalone entry point:

```bash
python3 desktop_app.py --provider mock
python3 desktop_app.py --provider ankiconnect
```

Use `--fallback-browser` when you want the native shell command to fall back to
the stable browser launcher if pywebview is unavailable:

```bash
python3 desktop_native.py --provider ankiconnect --fallback-browser
```

Supported native-shell options:

```text
--provider mock|real_momo|ankiconnect
--host 127.0.0.1
--port 8755
--ankiconnect-url http://127.0.0.1:8765
--fallback-browser
```

Future formal packaging can evaluate pywebview, PyQt6, Tauri, or another native
shell option. This scaffold keeps that decision open while preserving the
current shared server, web UI, and provider flow.

Desktop credentials use macOS Keychain or Windows Credential Manager through
`keyring`. Legacy plaintext values are removed from JSON only after migration
succeeds. If the operating-system backend is unavailable, credential access
fails closed; there is no plaintext fallback.
