# Desktop Standalone Mode

This document summarizes the Phase 28/29/30 desktop architecture, provider
modes, diagnostics, and release-time manual acceptance checklist.

## Current Architecture

Standalone desktop mode reuses the same web UI and pure core logic as the Anki
add-on:

```text
desktop_app.py
  -> desktop_mock/main.py
    -> addon/daily_ai_reading_reinforcement/web/
      -> provider/adapters
```

- `desktop_app.py` is the dependency-free launcher. It configures the provider,
  starts the local HTTP server, and opens the system browser unless
  `--no-browser` is passed.
- `desktop_mock/main.py` serves the shared HTML/CSS/JS UI and injects a browser
  bridge that posts UI actions to `/api/bridge`.
- The shared web UI is `addon/daily_ai_reading_reinforcement/web/`, also used
  by the Anki add-on.
- Provider and adapter modules keep desktop mode decoupled from Anki's internal
  `aqt` runtime:
  - deck providers load today's studied cards;
  - `DesktopConfigAdapter` reads and writes desktop config;
  - `DesktopDeckAdapter` writes generated Markdown/HTML and, in AnkiConnect
    mode, writes article cards back to Anki.

Phase 28 added Anki/MoMo newly learned card detection and the UI
`新学` / `New` / `新規` filter. Phase 29 added the dependency-free
`desktop_app.py` launcher. Phase 30 added AnkiConnect read support for today's
cards plus AnkiConnect article-card writeback.

## Provider Modes

Desktop mode selects a deck provider with `--provider` or
`DAIRR_DESKTOP_PROVIDER`.

### `mock`

Uses in-repository mock MoMo-like data. This mode is best for UI smoke testing
and does not require Anki, AnkiConnect, MoMo, or network credentials.

### `real_momo`

Uses the real MoMo API provider. It requires `MOMO_TOKEN` or `Maimemo_key` in
the environment. It is intended for validating external MoMo data shape while
still running the shared desktop UI.

### `ankiconnect`

Uses a local Anki instance through the AnkiConnect add-on. It does not import
Anki's internal Python modules and can run outside the Anki process. This mode
supports:

- reading today's studied cards;
- grouping cards by deck and parent deck groups;
- identifying failed and newly learned cards with conservative AnkiConnect
  queries;
- generating Markdown/HTML through the shared core pipeline;
- writing generated article cards back to Anki when `create_article_cards=true`.

## AnkiConnect Data Flow

The Anki add-on can inspect Anki internals directly, including revlog SQL. The
standalone AnkiConnect provider cannot access those internals, so it uses a
conservative mapping from AnkiConnect search queries and `cardsInfo`.

### Reading Today's Cards

1. Candidate cards come from:

   ```text
   findCards query="rated:1"
   ```

2. Failed-today cards prefer:

   ```text
   findCards query="rated:1:1"
   ```

   If that query is unavailable or incomplete, card queue/type values from
   `cardsInfo` provide a secondary relearning signal.

3. Newly learned cards prefer:

   ```text
   findCards query="introduced:1"
   ```

   If unavailable, the provider falls back to `rated:1` plus low repetition
   count (`reps <= 1`), excluding cards already marked failed today.

4. Card rows are populated from:

   ```text
   cardsInfo cards=[...]
   ```

   The provider uses `cardId`, `note`/`noteId`, `deckName`, `fields`,
   `question`, `reps`, `queue`, and `type` when present. Frontend rows expose
   `cid`, `nid`, `term`, `fields`, `is_new`, `is_failed`, and `review_count`.

### Writing Article Cards

When `create_article_cards=true` and desktop mode is using `ankiconnect`,
`DesktopDeckAdapter.save_article_card()` delegates to
`AnkiConnectArticleCardSaver`.

The write path is:

```text
DesktopDeckAdapter.save_article_card()
  -> AnkiConnectArticleCardSaver.save_article_card()
    -> createDeck
    -> modelNames / createModel
    -> addNote
    -> findCards nid:<noteId>
    -> suspend
```

Article notes use the `Daily AI Reading Reinforcement Article` note type. If the
note type is missing, the saver creates it with the expected fields and card
template. Created article cards are suspended by default.

## Running Desktop Mode

Run from the repository root.

```bash
python3 desktop_app.py --provider mock
python3 desktop_app.py --provider ankiconnect
python3 desktop_app.py --provider ankiconnect --check
python3 desktop_app.py --provider ankiconnect --check-write
```

Useful optional flags:

```bash
python3 desktop_app.py --provider ankiconnect --ankiconnect-url http://127.0.0.1:8765
python3 desktop_app.py --provider mock --no-browser
```

The launcher starts the local server at `http://127.0.0.1:8755` by default.

## Environment Variables

- `DAIRR_DESKTOP_PROVIDER`: provider mode used by `desktop_mock/main.py`.
  Supported values are `mock`, `real_momo`, and `ankiconnect`.
- `DAIRR_ANKICONNECT_URL`: AnkiConnect endpoint. Defaults to
  `http://127.0.0.1:8765`.
- `MOMO_TOKEN` / `Maimemo_key`: token used by the `real_momo` provider.
- `DESKTOP_OUTPUT_DIR`: base output directory for generated desktop
  Markdown/HTML. Defaults to the packaged-app user data directory:
  macOS `~/Library/Application Support/DAIRR/articles/`, Windows
  `%APPDATA%/DAIRR/articles/`, and Linux `~/.local/share/dairr/articles/`.
- `DESKTOP_CONFIG_PATH`: config JSON path used by `DesktopConfigAdapter`.
  When unset, desktop mode reads an existing legacy `~/.dairr_config.json`
  for compatibility. If that legacy file does not exist, it uses the
  packaged-app user data directory: macOS
  `~/Library/Application Support/DAIRR/config.json`, Windows
  `%APPDATA%/DAIRR/config.json`, and Linux
  `~/.local/share/dairr/config.json`.

Related generation/config environment variables are handled by
`DesktopConfigAdapter`, including `DAIRR_API_KEY`, `DAIRR_BASE_URL`,
`DAIRR_MODEL`, `DAIRR_TEMPERATURE`, `DAIRR_MAX_TOKENS`, `DAIRR_PROVIDER`, and
`DAIRR_UI_LANGUAGE`.

## Diagnostics

Use diagnostics before investigating UI behavior.

```bash
python3 desktop_app.py --provider ankiconnect --check
```

This verifies the AnkiConnect endpoint, response envelope, note types,
`rated:1` search, sample `cardsInfo`, and DAIRR article note type compatibility.

```bash
python3 desktop_app.py --provider ankiconnect --check-write
```

This performs an explicit write smoke test. It creates one suspended
DAIRR smoke-test article card in Anki under the `DAIRR Smoke Test` source deck
path and verifies that `suspend` was attempted and accepted.

### Troubleshooting Generation Language

If a request for Japanese generation produces English output, use the
development-only `debugPrompt` bridge action to inspect the preset and prompt
that standalone desktop mode would send to the LLM. Start the standalone server
without opening a browser:

```bash
python3 desktop_app.py --provider ankiconnect --no-browser
```

Then call the diagnostic CLI:

```bash
python3 tools/debug_prompt.py --deck-id "deck-japanese" --preset-id "japanese"
```

Pass repeated card ids when you want to inspect the same selected-card path as
the UI:

```bash
python3 tools/debug_prompt.py --deck-id "deck-japanese" --preset-id "japanese" --card-id 1001 --card-id 1002
```

The tool POSTs this bridge envelope to `/api/bridge`:

```json
{
  "action": "debugPrompt",
  "payload": {
    "deckId": "deck-japanese",
    "presetId": "japanese",
    "cardIds": [1001, 1002]
  }
}
```

By default, the CLI prints a short summary containing the requested preset id,
saved selected preset id, selected fields, selected card count, a prompt preview,
whether that preview contains the resolved article language, and the resolved
article/reader languages. If `articleLanguage` is `Japanese` and
`promptContainsArticleLanguage` is true, the prompt language instruction reached
the LLM path and the remaining issue is likely downstream model behavior. If
they are missing or incorrect, inspect preset selection, `presetId` propagation,
desktop config persistence, or preset field-name mismatches. Use `--json` to
print the complete debug response. The debug payload does not include API keys.

## Known Limitations

- AnkiConnect mode is less precise than the Anki add-on's internal revlog SQL.
- `review_count` comes from `cardsInfo.reps`, so it is closer to a cumulative
  repetition count than a strict today-only review count.
- If the DAIRR article note type already exists but is missing required fields,
  diagnostics report the mismatch, but the saver does not automatically migrate
  the note type.
- `--check-write` creates one suspended smoke-test card in Anki. Delete it
  manually after confirming the write path if you do not want to keep it.

## Manual Acceptance Checklist

- [ ] `python3 desktop_app.py --provider mock` opens the shared UI.
- [ ] `python3 desktop_app.py --provider ankiconnect --check` passes with Anki
  running and AnkiConnect enabled.
- [ ] `python3 desktop_app.py --provider ankiconnect --check-write` creates a
  suspended smoke-test card.
- [ ] `python3 desktop_app.py --provider ankiconnect` shows today's decks.
- [ ] Generating an article creates Markdown and HTML output.
- [ ] With `create_article_cards=true`, generating/saving writes an article card
  through AnkiConnect.
- [ ] `python3 package_addon.py` still packages the Anki add-on.
