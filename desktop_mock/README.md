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

Then open <http://127.0.0.1:8765> in a browser.

## How it works

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

Tests cover `handle_action()` for `load`, unknown actions, `generate` (no
network), and the mock state shape.
Then open <http://127.0.0.1:8755> in a browser.
- `main.py` is a stdlib `http.server` (port 8755, chosen to avoid clashing with
  AnkiConnect's default 8765).
