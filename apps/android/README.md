# DAIRR Android shell foundation

This is a deliberately small Android shell for DAIRR's existing portable
HTML/CSS/JS interface. It is not a Python-backend port and it does not yet
connect to AnkiDroid, MoMo, an LLM provider, or a local desktop process.

## What is already wired

- Gradle packages the current shared `web/index.html`, `web/style.css`, and
  `web/app.js` into the APK at build time. The source UI remains outside this
  Android project and is not copied into a second editable implementation.
- The bootstrap provides the existing UI contract:
  `window.__DAIRR_BRIDGE__.send(action, payload)`.
- `DairrJavascriptBridge` validates the command envelope and returns events to
  `window.DAIRR.receive({ event, payload })`.
- `BridgeDispatcher` is the only integration point for Android provider,
  article, export, and history adapters. The scaffold's dispatcher fails
  closed: it makes no provider requests and stores no data.
- `CredentialStore` defines the credential boundary. The supplied
  `DisabledCredentialStore` intentionally refuses writes; do not replace it
  with plaintext `SharedPreferences`.

## Build

Use Android Studio (JDK 17) or a local Gradle installation with Android SDK 35:

```bash
cd apps/android
gradle :app:assembleDebug
```

The build needs network access on first run to resolve the Android Gradle and
Kotlin plugins. This repository intentionally does not commit a Gradle wrapper
or generated APKs.

## Next adapter milestone

1. Implement a Keystore-backed `CredentialStore` before accepting any token.
2. Implement a `BridgeDispatcher` that calls the platform-agnostic DAIRR core
   contract (not `desktop_mock/main.py`), then map only capabilities supported
   by Android.
3. Add an AnkiDroid/export adapter behind that dispatcher; do not add Anki
   `aqt` APIs or desktop HTTP assumptions to this shell.
4. Add device tests after a real provider has deterministic offline fixtures.

## Validation

```bash
python3 tests/validate_scaffold.py
```

This static test checks the asset-generation task, the exact JavaScript bridge
contract, local-only WebView navigation, and the fail-closed credential stub.
