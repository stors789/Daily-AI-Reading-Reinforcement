# Desktop standalone reference

Standalone DAIRR runs the shared workbench in a native Tauri window, with the browser and pywebview launchers retained as development/fallback paths. It uses the same platform-neutral practice, scoring, prompt, provider, parsing, generation, and persistence core as the Anki add-on, but it accesses Anki **only through standard AnkiConnect**.

For task-level instructions, start with the [user guide](user-guide.md). This document focuses on the desktop host, providers, diagnostics, paths, bridge, and fallbacks.

## Runtime boundary

```text
Tauri / desktop_app.py / desktop_native.py
  -> local Python backend (desktop_mock/main.py)
    -> authenticated loopback bridge v2
      -> shared application services (dairr_core)
      -> standard AnkiConnect, MoMo, or explicit mock provider
      -> local config, article history, and practice repository
```

- The backend binds only to loopback and serves the portable UI plus `/api/bridge` and `/api/health`.
- Bridge requests carry protocol version and request ID. Long operations return an operation ID, run in a bounded executor, and are polled/cancelled without freezing the UI.
- Every bridge POST requires a per-process token injected into the same-origin page. Host/Origin, JSON content type, request size, and security headers are enforced.
- The standalone process does not import `aqt`, `mw`, Anki collection objects, scheduler internals, Qt objects, internal database handles, or add-on hooks.

## Provider modes

Select with `--provider` or `DAIRR_DESKTOP_PROVIDER`.

### `ankiconnect`

The normal standalone learning-source mode. It supports deck/card reads, normalized partial study signals, local article generation/history, and suspended article-card writeback when configured. Anki must be running for Anki-backed actions, but local pasted-text practice remains available when it is not.

Standard action coverage and limitations:

- `findCards` and `cardsInfo` provide candidates, identity, fields, lifetime repetitions, lapses, and state-like values where present.
- The richer standard `getReviewsOfCards` action is optional. Ordered current-day events are used only when valid rows and authoritative Anki-day bounds are supplied; a guessed midnight is never treated as evidence.
- `cardsInfo.reps` is lifetime metadata, not same-day attempts.
- Standard `cardsInfo` exposes no normalized FSRS retrievability, difficulty, or stability. Those score contributions remain unavailable/zero.
- Connection, timeout, malformed response, unsupported action, incompatible version, partial response, stale connection, and cancellation failures are classified and redacted.

Article-card writeback uses `createDeck`, `modelNames`/`createModel`, `addNote`, `findCards`, and `suspend`. The note type is `Daily AI Reading Reinforcement Article`. An existing incompatible note type is reported rather than rewritten silently.

### `real_momo`

Uses the official MoMo API provider and requires `MOMO_TOKEN` or `Maimemo_key`. MoMo is a learning source, not a substitute for AnkiConnect writeback or Anki review/FSRS evidence. Validate endpoint semantics with the repository’s MoMo probes and `api_bundle.yaml`; do not infer them from mock data.

### `mock`

Explicit demo/test data. It requires no Anki or external credential. A real-provider failure never falls back to mock success; mock generation occurs only when mock/demo was selected.

## Run and diagnose

From the repository root:

```bash
python3 desktop_app.py --provider mock
python3 desktop_app.py --provider ankiconnect
python3 desktop_app.py --provider ankiconnect --check
python3 desktop_app.py --provider ankiconnect --check-write
python3 desktop_app.py --provider ankiconnect --ankiconnect-url http://127.0.0.1:8765
python3 desktop_app.py --provider mock --no-browser
```

`--check` is read-only. It validates the AnkiConnect version envelope, current-day search, sample `cardsInfo`, and DAIRR article note-type fields. `--check-write` is intentionally mutating: it creates and suspends one smoke-test reading card. Remove the test note afterward if it is unwanted.

Native development shell:

```bash
cd apps/desktop
npm install
npm run dev
```

See [native shell](native_shell.md) and [packaging](packaging.md) for Tauri, sidecar, browser, and pywebview paths.

## Configuration and storage

Configuration priority is:

1. Supported `DAIRR_*` environment variables.
2. `DESKTOP_CONFIG_PATH` when set.
3. Legacy `~/.dairr_config.json` when that file already exists.
4. The platform app-data config.
5. Core defaults.

Platform defaults:

| Platform | Root | Config | Articles | Practice |
| --- | --- | --- | --- | --- |
| macOS | `~/Library/Application Support/DAIRR/` | `config.json` | `articles/` | `practice_sessions/` |
| Windows | `%APPDATA%\DAIRR\` | `config.json` | `articles\` | `practice_sessions\` |
| Linux/dev | `~/.local/share/dairr/` | `config.json` | `articles/` | `practice_sessions/` |

`DESKTOP_OUTPUT_DIR` overrides the data root used for articles/practice. Supported generation/config overrides include `DAIRR_API_KEY`, `DAIRR_BASE_URL`, `DAIRR_MODEL`, `DAIRR_TEMPERATURE`, `DAIRR_MAX_TOKENS`, `DAIRR_PROVIDER`, and `DAIRR_UI_LANGUAGE`.

Config schema v2 preserves unknown/local fields while adding prompt scopes, reasoning intent, and scoring presets. Invalid optional additions fall back individually. Writes use private same-directory temporary files, `fsync`, and atomic replace where supported.

## Troubleshooting

### Anki-backed controls are unavailable

1. Start Anki and open the intended profile.
2. Verify AnkiConnect is enabled and restart Anki after installing/updating it.
3. Run `python3 desktop_app.py --provider ankiconnect --check`.
4. Confirm the endpoint (default `http://127.0.0.1:8765`) and local security software.
5. Retry the specific operation. Pasted practice/history/config remain usable during the outage.

### A scoring signal says unavailable

Open the candidate’s Evidence details. Unavailability is expected when the host cannot prove ordered review history, FSRS values, or another optional field. Do not substitute a neutral number. The remaining available signals still contribute.

### Provider generation/review fails

Open **API / Reasoning** and preview effective non-secret settings. Verify provider ID, base URL, model, response mode, and reasoning capability. Unknown compatible providers expose no guessed explicit reasoning fields. Public errors deliberately omit raw response bodies and prompts.

### Prompt language/content is unexpected

Use **Prompts → Render exact preview** for the relevant task. The rendered system/user messages are the messages transported; no substantive hidden suffix is appended. Treat the preview as private because it can contain card or pasted text.

The developer `tools/debug_prompt.py` client must authenticate to the current bridge. It is for local diagnosis and does not include API keys in its summary; avoid sharing its full JSON when it contains private prompt content.

## Known desktop limits

- Standard AnkiConnect cannot provide the same evidence as the in-process add-on.
- Cooperative cancellation cannot forcibly interrupt an already-blocked standard-library HTTP call; the finite timeout is the upper bound.
- The per-process bridge token mitigates browser drive-by requests, not another local process running as the same OS user.
- A successful local/dry-run build does not prove signed macOS notarization, Windows Authenticode/SmartScreen reputation, updater publication, or another platform’s package.
