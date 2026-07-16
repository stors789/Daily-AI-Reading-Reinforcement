# DAIRR Android offline-practice shell

The Android app packages DAIRR's portable HTML/CSS/JavaScript UI in a local
WebView and now provides a production edge for **offline pasted-text
translation practice**. It is not a Python runtime and does not duplicate the
shared scoring, prompt, provider, or Anki business logic.

## Available on Android

- Create a pasted-text practice session without Anki or a network connection.
- Split text at blank lines, edit/split/merge/reorder segments in the portable
  workspace, and translate a segment or the complete text.
- Autosave drafts in memory/browser app-private storage and explicitly persist
  them to an app-private JSON repository.
- List, reopen, and delete saved practice sessions.
- Reject stale edits through persisted optimistic revisions.
- Preserve unknown JSON envelope/session/segment fields when an older Android
  writer updates a record.
- Use bridge protocol v2 request/response envelopes with `requestId` and
  privacy-safe structured failures.

The repository stores one schema-v2 file per session under the application's
private `filesDir/practice_sessions` directory. Writes use a same-directory
temporary file, flush and file-descriptor sync, then atomic replacement when
the filesystem supports it. Android backup is disabled for the application.
No source text, translation, prompt, token, or exception detail is logged.

Explicit limits are returned by `getCapabilities` and enforced without silent
truncation:

- 50,000 source characters per session;
- 20,000 characters per segment;
- 500 segments per session;
- 100,000 characters per translation draft.

## Deliberately unavailable

This release has no supported Android adapter for saved desktop/add-on article
history, Anki/AnkiDroid review data, FSRS, target scoring, AI generation or
review, prompt customization, or provider reasoning controls. These actions
return an `operationFailed` envelope with an actionable `data_absent`,
`provider_unsupported`, or `unavailable_in_mode` capability reason. They never
return fake success. Paste article prose into the offline practice workspace
when article history is unavailable.

`CredentialStore` remains fail closed. Do not accept provider secrets until a
Keystore-backed implementation and a supported Android provider adapter are
added; plaintext `SharedPreferences` is not acceptable.

## Security and lifecycle boundary

- Shared assets are served from the AndroidX WebView asset-loader HTTPS origin.
- File/content access, mixed content, and external-origin navigation are
  blocked; only `/assets/dairr/` on `appassets.androidplatform.net` is allowed.
- The JavaScript interface accepts only an explicit action allow-list and
  bounded JSON envelopes.
- Repository work runs on a dedicated background executor.
- Activity destruction closes the dispatcher, cancels queued work, removes the
  JavaScript interface, and destroys the WebView before late events can arrive.
- App-private DOM storage remains enabled solely for the portable UI's
  unsaved-draft recovery and preferences.

## Build and tests

Use Android Studio with JDK 17 and Android SDK 35. The repository intentionally
does not commit a Gradle wrapper or generated APKs. A compatible local Gradle
installation can run:

```bash
cd apps/android
gradle :app:testDebugUnitTest
gradle :app:assembleDebug
```

First use may need network access for Android Gradle and Kotlin plugin
resolution. The SDK-free production-edge tests use a standalone Kotlin/JVM
project that compiles the actual production bridge, dispatcher, and repository
files. They require JDK 17 and one of the tested Gradle versions (8.10.2 or
9.6.1), but no Android SDK:

```bash
python3 apps/android/tests/run_jvm_tests.py
python3 apps/android/tests/validate_scaffold.py
```

The runner discovers JDK 17 from `JAVA_HOME`, `--java-home`, and common
Homebrew/OpenJDK locations; it fails with an actionable message when no valid
JDK is found. It probes and reports the actual Gradle and Java versions before
building and fails for an untested Gradle version. CI installs the
canonical Gradle 8.10.2 version explicitly; on a clean local machine, Gradle's first run resolves the
pinned Kotlin 2.0.21, JUnit 4.13.2, and JSON dependencies from public Maven
repositories. JVM tests cover bridge identity/allow-listing, explicit capabilities,
privacy-safe unsupported operations, persistence round trips, unknown-field
preservation, atomic-write cleanup, revision conflicts, manual segmentation,
and input limits.
