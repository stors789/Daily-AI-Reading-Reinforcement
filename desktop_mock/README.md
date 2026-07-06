# Desktop Mock (Phase 7)

A minimal, dependency-free desktop mock that loads the **same shared web UI**
the Anki addon uses, so you can verify the bridge / receive contract outside
Anki.

It does NOT touch:

- the real Anki collection / aqt
- the momo (墨墨) API
- any real LLM endpoint

## Run

```bash
python3 desktop_mock/main.py
```

Then open <http://127.0.0.1:8755> in a browser.

## How it works

- `momo_provider.py` contains `MockMoMoDeckProvider`, a mock-first deck/card
  provider shell. It returns static mock data (2 decks, 3 cards each) through
  `get_today_decks()` and `get_deck_cards()`. This is NOT live MoMo (墨墨)
  data — no account, cookie, token, or network access is needed. The real
  MoMo API will be wired in during a later phase; the provider interface
  (`get_today_decks` / `get_deck_cards`) is designed to stay the same.

- `main.py` is a stdlib `http.server`.
- `GET /` returns the shared `web/index.html` with `web/style.css` inlined as a
  `<style>` tag and `web/app.js` inlined as a `<script>` -- exactly the shape the
  addon's `_load_page()` produces.
- Before `app.js` runs, a mock `window.__DAIRR_BRIDGE__` is injected. Its
  `send(action, payload)` POSTs to `/api/bridge` and feeds the JSON response
  straight into `window.DAIRR.receive({event, payload})`, which is the same
  envelope shape the Anki `pycmd` path produces via `_emit`.
- `POST /api/bridge` dispatches to `handle_action()` in `main.py`, which returns
  mock `{event, payload}` envelopes built from `mock_data.py`.

## Provider mode

Default:

```bash
python3 desktop_mock/main.py
```


Real MoMo provider, manual opt-in:

```bash
DAIRR_DESKTOP_PROVIDER=real_momo MOMO_TOKEN="..." python3 desktop_mock/main.py
```

Token is read only from the environment and is never saved.
`Maimemo_key` is supported only as a legacy alias; prefer `MOMO_TOKEN`.

## Supported mock actions

| action        | event returned  | notes                                   |
|---------------|-----------------|-----------------------------------------|
| `load`        | `state`         | initial decks / config / provider list  |
| `selectDeck`  | `deckCards`     | cards + fields for the chosen deck id   |
| `generate`    | `article`       | mock article body, no LLM call          |
| `listArticles`| `articleList`   | mock saved-articles list                |
| `loadArticle` | `articleLoaded` | mock article body for a path            |

Any other action returns an `error` event so the UI's error path is exercised
without crashing the server.

## Mock data

`mock_data.py` provides 2 decks (`deck-japanese`, `deck-english`) with 3 cards
each. Card payloads match `CandidateCard.to_payload()` (`cid`, `nid`, `term`,
`fields`, `is_new`, `is_failed`, `review_count`). Provider profiles and the
default config are loaded from the pure `core/config.py` (no aqt) so the mock
state stays aligned with the real addon.

## Tests

```bash
python3 -m unittest tests.test_desktop_mock -v
```

```bash
python3 -m unittest tests.test_momo_provider -v
```

`test_desktop_mock` covers `handle_action()` for `load`, unknown actions,
`generate` (no network), and the mock state shape. `test_momo_provider` covers
the provider contract (deck rows, card fields, unknown-deck handling, no
network) and the integration with `mock_data.py` payload builders.
## Phase 9 -- MoMo API probe script

`momo_api_probe.py` is a *standalone manual investigation* tool for the real
MoMo (墨墨) Open API at <https://open.maimemo.com/>. It is NOT imported by
`main.py`, the mock provider, the Anki addon, or any UI path, and it never
runs at import time.

- `--dry-run` prints the endpoint plan and masked-credential preview without
  any network call.
- A real run reads `MOMO_TOKEN` (bearer token) from the environment, hits the
  confirmed study / markji / vocabulary endpoints, and prints a per-field
  mapping report (direct / defaulted / missing) against the frontend contract.
- No credentials are stored, hardcoded, or printed in full; only the first 4
  and last 4 characters are shown.
- Findings are recorded in `momo_api_notes.md`.

```bash
python3 desktop_mock/momo_api_probe.py --dry-run
MOMO_TOKEN="..." python3 desktop_mock/momo_api_probe.py
```

Tests: `python3 -m unittest tests.test_momo_api_probe -v` (pure functions only,
no network).
