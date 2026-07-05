# AGENTS.md

## Project goal
This is an Anki addon for AI reading reinforcement. Keep the existing Anki addon behavior stable while gradually extracting reusable core logic.

## Setup
- Use Python 3.11+ if available.
- Do not introduce new dependencies unless explicitly requested.
- Do not change package structure unless the task specifically asks for it.

## Common commands
- Package addon: `python3 package_addon.py`
- Run Python syntax check: `python3 -m compileall .`

## Architecture
- `__init__.py` currently contains both Anki-specific code and reusable logic.
- `web/` contains the HTML/CSS/JS UI.
- Anki-specific code depends on `aqt`, `mw`, `gui_hooks`, and Anki WebView `pycmd`.
- Reusable logic should be moved gradually into `core/`.

## Rules
- Prefer minimal diffs.
- Do not rewrite unrelated code.
- Do not change UI text or CSS unless requested.
- Do not modify `web/app.js` unless the task explicitly asks for bridge/UI changes.
- Do not remove Anki compatibility fallbacks.
- Do not delete tests or runtime files to make checks pass.
- Before finishing, report what files changed and what checks were run.

## Current refactor plan
Phase 1:
- Only extract pure functions into `core/`.
- Do not change Anki hooks.
- Do not change `pycmd`.
- Do not introduce desktop/Tauri/Electron code.

Phase 2:
- Add tests for pure core functions.

Phase 3:
- Introduce adapter interfaces for config, deck collection, and card saving.

## Completion report format
When done, report:

1. Files changed
2. What changed
3. Checks run
4. Any remaining risks