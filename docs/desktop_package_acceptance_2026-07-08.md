# Desktop Package Acceptance - 2026-07-08

## Environment

- OS: macOS 27.0 (Build 26A5368g), arm64
- Python: 3.13.13 (`/opt/miniconda3`)
- PyInstaller: 6.21.0
- PyInstaller install note: initially missing, then installed into the user packaging environment with `python3 -m pip install --user PyInstaller`. No project dependency files were changed.

## Packaging Commands

- `python3 package_desktop.py --entry browser --dry-run`
- `python3 package_desktop.py --entry browser --windowed --clean`

## Package Artifact

- Browser executable: `/Users/eros/Documents/Daily AI Reading Reinforcement/dist/DAIRR/DAIRR`
- macOS app bundle: `/Users/eros/Documents/Daily AI Reading Reinforcement/dist/DAIRR.app`

## Browser Entry Result

- Result: runnable.
- `./dist/DAIRR/DAIRR --provider mock --check`: OK.
  - Found 2 mock decks.
  - Found 3 mock cards.
- `./dist/DAIRR/DAIRR --provider mock --host 127.0.0.1 --port 8877 --no-browser`: started the local server.
  - `GET /` returned the inlined shared UI HTML/CSS/JS.
  - `POST /api/bridge` with `load` returned mock deck state.
  - `POST /api/bridge` with `selectDeck` for `deck-english` returned 3 cards with `is_new` / `is_failed` values.
- Playwright smoke against frozen server on port 8878: OK.
  - `AI Reading Reinforcement`, `English Vocab`, and `Japanese Vocab` were visible.

## Native Entry Result

- Native package was not attempted.
- Reason: `pywebview` is not available in the current packaging environment.
- Browser package is not blocked by this.

## Mock Provider Result

- Mock provider works in the packaged browser entry.
- Decks returned: `English Vocab`, `Japanese Vocab`.
- Cards returned for `deck-english`: 3 cards.

## AnkiConnect Provider Result

- `./dist/DAIRR/DAIRR --provider ankiconnect --check`: OK.
- AnkiConnect endpoint: `http://127.0.0.1:8765`.
- AnkiConnect version: 6.
- Note types found: 33.
- `rated:1` cards today: 0.
- Article note type exists and contains all DAIRR article fields.

## Config / Output Paths

- Packaged app default config path: `/Users/eros/Library/Application Support/DAIRR/config.json`.
- Packaged app default output path: `/Users/eros/Library/Application Support/DAIRR/articles`.
- Actual config path on this machine: `/Users/eros/.dairr_config.json`, because the legacy config file already exists and is intentionally preferred for backward compatibility.
- No config/output path used the repo directory during the packaged smoke test.

## Issues

- P0: None found.
- P1: None open.
- P2: Native packaging was skipped because `pywebview` is not installed in the packaging environment.
- P2: Existing legacy config at `/Users/eros/.dairr_config.json` is still preferred over the packaged app-data config path. This preserves compatibility and is outside the repo, but it is not the macOS app-data path.
- P2: The macOS app bundle is PyInstaller/ad-hoc signed only; notarization and installer distribution were not validated.

## Fixed During This Pass

- Added PyInstaller hidden imports for dynamically loaded desktop server modules that need `http.server`, `urllib.error`, and `urllib.request`.
- Included the core module directory in packaged data so desktop adapters can load pure core logic from the frozen app.
- Narrowed packaged `desktop_mock` data to required runtime `.py` files so old `desktop_mock/output` artifacts and `__pycache__` are not bundled.
- Added `--noconfirm` when `--clean` is requested so repeated clean builds can replace existing `dist/DAIRR` and `dist/DAIRR.app`.
- Changed frozen app no-argument startup to default to AnkiConnect instead of mock data.
- Dropped stale saved mock deck ids from the standalone state payload when the active provider does not return that deck.
- Added the missing `uuid` hidden import so packaged preset save/new flows can generate preset ids.
