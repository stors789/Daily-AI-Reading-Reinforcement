# Desktop Standalone + AnkiConnect Acceptance - 2026-07-08

## Environment

- OS: macOS 27.0 (Build 26A5368g)
- Python: `python3 -V` reported Python 3.13.13 during final report checks
- Anki: 25.09 (`net.ankiweb.launcher`)
- AnkiConnect: enabled and reachable at `http://127.0.0.1:8765`, API version 6
- Desktop URL: `http://127.0.0.1:8755`

## Commands

- `python3 -m unittest discover -s tests`
  - Passed: 346 tests OK after the desktop bridge fixes.
- `python3 -m compileall .`
  - Passed.
- `python3 package_addon.py`
  - Passed; wrote `dist/daily_ai_reading_reinforcement.ankiaddon`.
- `python3 desktop_app.py --provider mock`
  - Server started at `http://127.0.0.1:8755`.
  - macOS system-browser auto-open produced `osascript` application lookup errors, but the server and in-app browser validation worked.
- `python3 desktop_app.py --provider ankiconnect --check`
  - 2026-07-07 run: OK; `rated:1` found 70 cards; article note type existed; all DAIRR article fields were compatible.
  - 2026-07-08 recheck: OK; `rated:1` found 0 cards because the Anki day had rolled over; article note type and fields remained compatible.
- `python3 desktop_app.py --provider ankiconnect --check-write`
  - Passed.
  - Created noteId `1783429696254`.
  - Suspend was attempted and accepted.
  - The smoke-test note was deleted after verification; `findNotes nid:1783429696254` returned `[]`.

## UI Observations

- Mock desktop:
  - Mock decks/cards rendered.
  - Clearing selection and clicking `新学` selected only the new mock card (`1/3`).
  - Generating an article entered reading mode and displayed mock Markdown/HTML paths.
- AnkiConnect desktop:
  - Real Anki decks/cards rendered on 2026-07-07.
  - Observed deck: `中医学考点`, 70 candidate cards, 54 new, 15 failed.
  - Clearing selection then clicking `新学`, `遗忘`, `模糊` produced reasonable counts: `54/70`, `15/70`, `0/70`.
  - Manual testing found the following issues:
    - `Unknown command: saveCollapsedDeckGroups`
    - `Unknown command: saveFieldConfig`
    - Requested Japanese generation produced English output.
    - After generating an article and clicking `退出阅读模式`, the generate button stayed disabled.
    - Clicking create/save card did create a card, but the UI did not show success.

## Fixes Applied During Acceptance

- Added desktop bridge handling for `saveCollapsedDeckGroups`.
- Added desktop bridge handling for `saveFieldConfig`.
- Merged saved desktop config into the standalone state payload, including prompt presets, selected preset, collapsed deck groups, UI language, API settings, and last selected deck.
- Reused saved deck field selections when returning deck cards in standalone mode.
- Updated the web UI to recalculate the generate button after leaving reading mode.
- Updated the web UI article-card success handler to accept either `deckName` or legacy `deck`.
- Added regression tests for the two new desktop bridge commands.

## Remaining Risks

- User retest after the partial fixes still did not confirm the issues as fully resolved. Treat the current fixes as a bridge-contract patch, not final acceptance of the standalone flow.
- Japanese generation likely needs deeper tracing of the selected preset, saved preset config, and exact prompt sent to the LLM.
- Save-to-card UI success should be rechecked in the browser after the next standalone UI iteration.
- Native shell/packaging should wait until the above UI contract and prompt-language issues are fully resolved.

## Recommendation

Do not move to the next native shell/packaging phase yet. Continue with a fuller standalone desktop pass focused on persistent UI state, prompt preset language fidelity, and AnkiConnect save feedback.
