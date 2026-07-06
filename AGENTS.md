# AGENTS.md

## Project goal
Evolve the DAIRR (Daily AI Reading Reinforcement) project from a pure Anki addon into a standalone cross-platform Desktop Application (Win/Mac), while maintaining backward compatibility to run as an Anki plugin. The core logic must remain pure and platform-agnostic, capable of connecting to both Anki (via AnkiConnect) and MoMo API.

## Setup
- Use Python 3.11+ if available.
- Do not introduce new dependencies unless explicitly requested.
- Do not change package structure unless the task specifically asks for it.
- **Android Support**: Postponed for now pending further architectural research on how to best integrate with AnkiDroid.

## Common commands
- Package addon: `python3 package_addon.py`
- Run Python syntax check: `python3 -m compileall .`
- Run desktop mock server: `python3 desktop_mock/main.py`

## Architecture
- `core/`: Contains pure, reusable business logic and Adapter interfaces.
- `web/`: Contains the cross-platform HTML/CSS/JS UI.
- `addon/`: Contains the Anki-specific plugin wrapper (`__init__.py`) using `aqt`, `mw`, `gui_hooks`.
- `desktop_mock/`: Contains the standalone HTTP server and external API providers (e.g., MoMo, AnkiConnect).

## Rules
- Prefer minimal diffs.
- Do not rewrite unrelated code.
- Do not change UI text or CSS unless requested.
- Desktop application mode MUST be cleanly decoupled from Anki-internal `aqt` hooks via the Adapter pattern.
- Do not remove Anki plugin compatibility fallbacks.
- Do not delete tests or runtime files to make checks pass.
- Before finishing, report what files changed and what checks were run.

## Current Execution Plan

**Phase 28: UI & Data Enhancements**
- Detect Anki/MoMo's "newly learned" (新学) status cards.
- Add a "新学" (New) filter button to the UI card selection row.

**Phase 29: Standalone Desktop App Scaffolding**
- Create a standalone desktop entry point (e.g., using PyQt6 WebEngine or pywebview) for Win/Mac.
- Wrap the existing Python core logic and Web UI into a native executable format without modifying the core behavior.

**Phase 30: AnkiConnect Integration**
- Develop an `AnkiConnectDeckProvider` to allow the standalone desktop app to connect to local Anki instances.
- Ensure the app can accurately identify Anki decks and write generated article cards back to Anki via AnkiConnect API.
- Maintain logic consistency with the original Anki plugin version.

## Completion report format
When done, report:
1. Files changed
2. What changed
3. Checks run
4. Any remaining risks