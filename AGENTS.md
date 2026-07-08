# AGENTS.md

## Project goal
Build DAIRR (Daily AI Reading Reinforcement) as a polished standalone app for macOS, Windows, and Android, while keeping the Anki add-on path working. The standalone app is now the primary product surface; the Anki add-on is a compatibility/runtime integration layer.

The core learning, article generation, provider, and rendering logic should stay platform-agnostic. Standalone mode should connect to Anki-compatible storage through clean adapters, to desktop Anki through AnkiConnect where available, and to MoMo through the official OpenAPI. Anki-internal `aqt`/`mw` APIs must stay isolated to the add-on wrapper.

## Setup
- Use Python 3.11+ if available.
- New dependencies are allowed when they directly support the standalone app, native shell, mobile shell, packaging, testing, or provider integrations. Keep them deliberate and documented.
- Package structure may change when it improves the standalone/add-on split, enables macOS/Windows/Android targets, or reduces coupling. Keep migrations scoped and update tests.
- Treat Android as a first-class target, but keep platform-specific Android behavior behind adapters so the desktop and add-on paths do not inherit Android-only assumptions.

## Common commands
- Package addon: `python3 package_addon.py`
- Run Python syntax check: `python3 -m compileall .`
- Run desktop mock server: `python3 desktop_mock/main.py`
- Package browser-style desktop app: `python3 package_desktop.py --entry browser --windowed --clean`
- Package native desktop app: `python3 package_desktop.py --entry native --windowed --clean`

## Project layout

Current layout:
- `addon/daily_ai_reading_reinforcement/`: Current packaged Anki add-on. Keep it runnable as an Anki plugin.
- `addon/daily_ai_reading_reinforcement/core/`: Pure learning, article generation, card, provider, and config logic. This should contain no `aqt`, browser-window, or mobile-shell assumptions.
- `addon/daily_ai_reading_reinforcement/web/`: Shared HTML/CSS/JS UI. This is the current cross-platform interface surface and should remain portable while the app shell evolves.
- `addon/daily_ai_reading_reinforcement/__init__.py`: Anki-specific wrapper. This is the only place that should directly touch `aqt`, `mw`, or Anki GUI hooks.
- `desktop_mock/`: Standalone Python HTTP server, desktop adapters, MoMo provider, AnkiConnect provider, probes, and local diagnostics.
- `desktop_app.py`: Browser fallback launcher for the local desktop server.
- `desktop_native.py`: Native-window launcher. This should become the preferred packaged app entry once the native shell is production-ready.
- `package_desktop.py`: PyInstaller packaging command builder for browser/native entries.
- `package_addon.py`: Anki add-on package builder.
- `api_bundle.yaml`: Local official MoMo OpenAPI schema reference.
- `tests/`: Unit and integration-style tests for core, provider, desktop, probe, and packaging behavior.
- `docs/`: Design notes, acceptance notes, and implementation records.
- `assets/`: Shared static/package assets.

Target layout direction:
- `core/` or `src/dairr_core/`: Eventually extract platform-agnostic DAIRR logic out of the Anki add-on package path when the migration is worth the churn.
- `apps/desktop/`: macOS/Windows shell and packaging entry. This may be PyInstaller/pywebview during transition or Tauri if explicitly adopted.
- `apps/android/`: Android shell and platform bridge. Keep Android storage/sync/export integration behind interfaces.
- `apps/addon/`: Anki add-on wrapper and package metadata.
- `apps/web/`: Shared web UI when it is no longer nested under the add-on package.
- `providers/`: MoMo, AnkiConnect, local/mock, and future sync providers if extracting them improves clarity.
- `docs/architecture/`: ADRs for shell choice, provider boundaries, Anki/AnkiDroid integration, and packaging decisions.

Do not perform this target-layout migration casually. Prefer it when a feature would otherwise increase coupling or make macOS/Windows/Android support harder to reason about.

## Rules
- Prefer focused diffs, but do not avoid necessary refactors when they make the desktop app cleaner or more reliable.
- Do not rewrite unrelated code.
- UI text, CSS, and interaction design may be changed when improving the standalone app experience. Keep it consistent with the existing UI and test the result.
- Standalone application mode MUST be cleanly decoupled from Anki-internal `aqt` hooks via the Adapter pattern.
- Do not remove Anki plugin compatibility fallbacks.
- Do not delete tests or runtime files to make checks pass.
- Real API behavior should be verified with the existing probe/diagnostic tools when endpoint semantics matter. Do not guess MoMo OpenAPI request shapes.
- Generated desktop/app artifacts may be rebuilt when packaging is part of the task.
- If adopting a new shell framework such as Tauri, Flutter, or a mobile-native wrapper, first keep the existing user workflow intact and migrate one boundary at a time: app shell, bridge API, provider adapters, packaging.
- Keep platform-specific code at the edges. Shared UI and shared learning/provider logic should not branch directly on macOS/Windows/Android unless the platform detail is truly UI-shell specific.
- Before finishing, report what files changed and what checks were run.

## Current Execution Plan

**Standalone App Shell**
- Make the native app window the primary user-facing entry on macOS and Windows.
- Evaluate Tauri as the preferred long-term shell before committing to a larger rewrite, because the current DAIRR UI is already HTML/CSS/JS.
- Keep `desktop_native.py` / pywebview useful as a transition path until a replacement shell is proven.
- Keep the browser launcher as a debug/fallback path.
- Plan Android as a real target from the start: shared UI first, Android-specific bridges second, and AnkiDroid/export behavior behind adapters.
- Ensure packaged macOS/Windows apps open a DAIRR window directly without requiring the user to manage a browser tab.

**Provider Reliability**
- Keep AnkiConnect and MoMo providers functional in standalone desktop mode.
- For MoMo, use official `api_bundle.yaml` / <https://open.maimemo.com/#/> plus `desktop_mock/momo_api_probe.py` for real-token validation.
- For AnkiConnect, avoid Anki-internal APIs and keep writeback paths safe, duplicate-tolerant, and user-visible.

**Product Polish**
- Improve article generation, history, filtering, and save-to-card workflows as desktop-first features.
- Rebuild `.app` / add-on packages when runtime code changes affect packaged behavior.

## Completion report format
When done, report:
1. Files changed
2. What changed
3. Checks run
4. Any remaining risks
