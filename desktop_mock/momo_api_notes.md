# MoMo API Probe Notes

## Status
- Not integrated into UI / desktop mock / Anki addon.
- No credentials are stored. The probe reads `MOMO_TOKEN` / `MOMO_COOKIE`
  from the environment only when run manually.
- Probe script must be run manually:
  `python3 desktop_mock/momo_api_probe.py` (real network) or
  `python3 desktop_mock/momo_api_probe.py --dry-run` (no network).
- Importing the module does NOT trigger any network call.

## Source of truth
Official OpenAPI bundle, fetched 2026-07-05 from
`https://open.maimemo.com/api_bundle.yaml` (墨墨开放 API v1, OpenAPI 3.1.0).
Hosted at <https://open.maimemo.com/#/>.

## Authentication
- **Bearer token** (NOT cookies / sessions).
- Header: `Authorization: Bearer <token>`.
- How to get a token:
  1. In the MoMo app: 我的 -> 更多设置 -> 实验功能 -> 开放 API
  2. Or open <https://open.maimemo.com/open/api/v1/tokens/openapi>
- The probe reads it from `MOMO_TOKEN`. `Maimemo_key` is also supported as a backward-compatible alias, but `MOMO_TOKEN` is the primary and recommended name. `MOMO_COOKIE` is reserved for a future cookie-based scheme and currently unused by the Open API.
- Rate limits: 10s/20, 60s/40, 5h/2000.
- Security scheme in the spec: `user` (oauth2 type, but in practice a
  static bearer token placed in the `Authorization` header).

## Base URL
`https://open.maimemo.com/open` (production; `https://open-dev.maimemo.com/open`
for testing). Paths are appended to this base.

## Confirmed endpoints
Two product lines share one token:

### 墨墨背单词 (study data, 公测 / public beta)
| key              | method | path                                  | body / params                         | response                                                  |
|------------------|--------|---------------------------------------|---------------------------------------|-----------------------------------------------------------|
| study_progress   | POST   | /api/v1/study/get_study_progress      | `{}`                                  | `{progress: {finished, total, study_time}}`               |
| today_items      | POST   | /api/v1/study/get_today_items         | `{is_finished?, is_new?, limit?}`     | `{today_items: [StudyTodayItem]}`                         |
| study_records    | POST   | /api/v1/study/query_study_records     | `{next_study_date?, as_count?, limit?}`| `{records: [StudyRecord], count}`                         |
| add_words        | POST   | /api/v1/study/add_words               | `{words: [{id}], advance}`            | `{added_count}`                                           |
| advance_study    | POST   | /api/v1/study/advance_study           | `{voc_ids: [...]}`                    | `{advanced_count}`                                        |
| vocabulary       | GET    | /api/v1/vocabulary?spelling=apple     | `spelling` (required)                 | `{voc: {id, spelling}}`                                   |
| vocabulary_query | POST   | /api/v1/vocabulary/query              | `{spellings? | ids?}` (mutex)         | `{voc: [{id, spelling}]}`                                 |

### 墨墨记忆卡 (markji content)
| key                       | method | path                                         | response                                  |
|---------------------------|--------|----------------------------------------------|-------------------------------------------|
| markji_decks              | GET    | /api/v1/markji/decks                         | `{decks: [MarkjiDeck], total}`            |
| markji_deck               | GET    | /api/v1/markji/decks/{deck}                  | `{deck: MarkjiDeck}`                      |
| markji_chapters           | GET    | /api/v1/markji/decks/{deck}/chapters         | chapters list                             |
| markji_chapter            | GET    | /api/v1/markji/decks/{deck}/chapters/{chapter}| chapter detail                           |
| markji_card               | GET    | /api/v1/markji/decks/{deck}/cards/{card}     | `{card: MarkjiCard}`                      |
| markji_folders            | GET    | /api/v1/markji/decks/folders                 | folders list                              |

### Key schemas
- `StudyProgress`: `finished` (int), `total` (int), `study_time` (int, ms).
- `StudyTodayItem`: `voc_id`, `voc_spelling`, `order`, `is_new`, `is_finished`,
  optional `first_response` (StudyResponse: FAMILIAR/VAGUE/FORGET/WELL_FAMILIAR/CANCEL_WELL_FAMILIAR).
- `StudyRecord`: `voc_id`, `voc_spelling`, `add_date`, `first_study_date`,
  `last_study_date`, `next_study_date`, `last_response`, `study_count`, `tags`.
- `MarkjiDeck`: `id`, `parent_id`, `name`, `description`, `card_count`,
  `chapter_count`, `is_private`, `source`, `status`, `revision`,
  `created_time`, `updated_time`, `root_deck`.
- `MarkjiChapter`: `id`, `deck_id`, `name`, `card_ids` (list), `revision`.
- `MarkjiCard`: `id`, `deck_id`, `parent_id`, `root_id`, `content`,
  `content_type`, `files`, `revision`.
- `Vocabulary`: `id`, `spelling`.

## Response mapping

### Deck row (frontend contract: id, name, newCount, failedCount, totalCount, isGroup)
Source: `MarkjiDeck` from `GET /api/v1/markji/decks`.

| frontend field | status    | source / note                                              |
|----------------|-----------|------------------------------------------------------------|
| id             | direct    | `MarkjiDeck.id`                                            |
| name           | direct    | `MarkjiDeck.name`                                          |
| newCount       | defaulted | No per-deck "new today" count in markji. Default 0, or     |
|                |           | derive from `study_progress.finished` (global, not per     |
|                |           | deck) -- needs investigation.                              |
| failedCount    | defaulted | No "failed today" concept in markji. Default 0.            |
| totalCount     | direct    | `MarkjiDeck.card_count`                                    |
| isGroup        | defaulted | markji has `parent_id` (deck nesting). Map `isGroup =      |
|                |           | parent_id is None`? Unconfirmed -- need a real response to |
|                |           | verify whether root decks behave as groups. Default False. |

### Card payload (frontend contract: cid, nid, term, fields, is_new, is_failed, review_count)
Two candidate sources:

**A. StudyTodayItem** (from `POST /api/v1/study/get_today_items`) -- best
for "today's review" semantics:

| frontend field | status    | source / note                                              |
|----------------|-----------|------------------------------------------------------------|
| cid            | direct    | `StudyTodayItem.voc_id`                                    |
| nid            | defaulted | MoMo has no note id. Default `""`.                         |
| term           | direct    | `StudyTodayItem.voc_spelling`                              |
| fields         | defaulted | MoMo does not expose a definition in the study endpoint.   |
|                |           | Default `{}`; can be enriched via `vocabulary/query` later |
|                |           | (returns only id+spelling, no definition).                 |
| is_new         | direct    | `StudyTodayItem.is_new`                                    |
| is_failed      | derived   | `is_finished == false` is a loose proxy; `first_response`  |
|                |           | == `FORGET` is a stronger one. Needs a real response to    |
|                |           | confirm which mapping the UI should use. Default False.    |
| review_count   | defaulted | Not in StudyTodayItem. Derive from `study_records`         |
|                |           | (`study_count`) per voc_id, or default 0.                  |

**B. MarkjiCard** (from `GET /api/v1/markji/decks/{deck}/cards/{card}`) --
best for "all cards in a deck", but only content is exposed, no study
state:

| frontend field | status    | source / note                                              |
|----------------|-----------|------------------------------------------------------------|
| cid            | direct    | `MarkjiCard.id`                                            |
| nid            | defaulted | Default `""`.                                              |
| term           | missing   | `MarkjiCard.content` is free text, not a headword. Needs   |
|                |           | parsing or a vocabulary cross-reference.                   |
| fields         | direct    | `MarkjiCard.content`                                       |
| is_new         | defaulted | No study state on markji cards. Default False.             |
| is_failed      | defaulted | No study state. Default False.                             |
| review_count   | defaulted | No study state. Default 0.                                 |

## Recommended RealMoMoDeckProvider strategy (for Phase 10)
The frontend's deck concept maps most naturally to **markji decks** for
the deck list, and the frontend's "today's review cards" concept maps to
**StudyTodayItem**. A hybrid provider would:

1. `get_today_decks()`:
   - Call `GET /api/v1/markji/decks` for the deck list (id, name, card_count).
   - Call `POST /api/v1/study/get_study_progress` for a global
     finished/total (NOT per-deck -- open question below).
   - `newCount` / `failedCount` default to 0 unless per-deck study state
     can be obtained (open question).
2. `get_deck_cards(deck_id)`:
   - If deck is a markji deck: `GET /api/v1/markji/decks/{deck}/chapters`
     then `GET .../chapters/{chapter}` to collect `card_ids`, then
     `GET .../cards/{card}` per card. NOTE: there is no bulk card list
     endpoint in the spec -- this is N+1 and may be expensive.
   - Alternatively, for "today's items" semantics regardless of deck,
     use `POST /api/v1/study/get_today_items` and filter/group by
     vocabulary. This avoids N+1 but loses deck grouping.
   - Open question: does markji expose a bulk card list endpoint not in
     the spec? Need to confirm with a real token.

## Open questions
1. **Per-deck new/failed counts.** `study_progress` returns global
   finished/total, not per deck. Is there an undocumented per-deck
   endpoint, or must we compute it from `today_items` + `vocabulary`?
   - Still unconfirmed after real-token probe.
2. **Bulk card listing.** The spec only exposes
   `GET /decks/{deck}/cards/{card}` (single card) and chapter
   `card_ids` lists. Is there a `GET /decks/{deck}/cards` bulk endpoint?
   - Still unconfirmed after real-token probe.
3. **isGroup semantics.** Should `isGroup` follow `parent_id is None`
   (root deck = group) or `chapter_count > 0`?
   - Still unconfirmed after real-token probe. (The markji endpoints returned 403 Forbidden).
4. **is_failed derivation.** Best source is `first_response == FORGET`
   vs `is_finished == false`. Needs real response samples.
   - We observed `first_response: str` and `is_finished: bool` in `today_items`. The exact logic is still unconfirmed after real-token probe.
5. **Token refresh / expiry.** The spec lists no refresh flow. Are
   tokens long-lived static strings? Assumed yes.
   - Still unconfirmed after real-token probe.
6. **Public beta stability.** Study endpoints are tagged 公测 (public
   beta) and "may change at any time". The provider should degrade
   gracefully when they return errors.
   - Acknowledged risk. Study endpoints currently return 200 OK.

## Probe usage
```bash
# No network, just the plan:
python3 desktop_mock/momo_api_probe.py --dry-run

# Real probe (requires a token from the MoMo app):
MOMO_TOKEN="your-openapi-token" python3 desktop_mock/momo_api_probe.py
```

The probe prints masked credentials (first 4 / last 4 chars), the
endpoint URLs it hits, parsed counts, and a per-field mapping report
(direct / defaulted / missing) for up to 3 sample decks and today items.
No credentials are written to disk or logged in full.

## Phase 10 Updates
- Added `RealMoMoDeckProvider` as a pure skeleton.
- Uses `get_markji_decks_raw` mapping for `get_today_decks`, returning 0 for `newCount` and `failedCount` and false for `isGroup` (conservative strategy without arbitrary aliases).
- `get_deck_cards` implemented using Strategy A (returns empty skeleton), deferring actual card fetching pending real token network verification.
- Not integrated into UI flows; callers must explicitly construct with a real token.

### Real Token Probe Status
Probe successfully ran against the real API.
- Study endpoints (`get_study_progress`, `get_today_items`, `query_study_records`, `vocabulary/query`) returned 200 OK.
- Responses are wrapped in `{"data": {...}, "success": true, "errors": []}`.
- Markji endpoint (`/markji/decks`) returned 403 Forbidden.

### Phase 14/15 Updates
Real-token smoke found that POST /api/v1/study/get_today_items with limit=5000 returns HTTP 400. Calling without limit succeeds. RealMoMoDeckProvider therefore does not send a default limit for today_items.

### Phase 15.5 real UI smoke:
- Markji decks still returned 403, so MoMo Today fallback was used.
- get_today_items without default limit succeeded.
- UI rendered 50 today cards.
- study_records remained non-blocking; when it failed, review_count fell back to 0.
- No token, full response, or private vocabulary values were recorded.

### Phase 16: Card field mapping & display quality

**Mapping decisions:**
- `is_finished=false` is treated as `status=unfinished`, **not** as `is_failed=true`.
  Previously `is_failed` was `first_response == "FORGET" or is_finished is False`, which was overly aggressive — "not yet finished" does not equal "failed".
- `is_failed=true` is now reserved exclusively for `first_response == "FORGET"`.
- `status` field is derived as: `new` (if `is_new`), `finished` (if `is_finished is True`), `unfinished` (if `is_finished is False`), `unknown` (otherwise).
- `review_count=0` may mean "data unavailable" when `study_records` request fails; the new `review_count_status` field disambiguates:
  - `"available"` — `study_records` succeeded; `review_count` reflects the real `study_count` (which may legitimately be 0).
  - `"unavailable"` — `study_records` request failed; `review_count` is a fallback 0.
- Default selected field remains `["term"]`. New fields (`status`, `source`, `review_count_status`) are in the `fields` dict for future UI use but not in `selectedFields`.
- `source` is always `"MoMo Today"` (constant).
- No real words, tags, dates, or full responses are stored or logged.

## Phase 17 study_records parameter probe

### Goal
Find a safe request shape for `query_study_records`.

### Results
Not yet verified with real token.

### Mapping decision
- `review_count` can/cannot be derived from `study_count`.
- Join key is `voc_id` if available.
- If study_records is unavailable, keep `review_count_status=unavailable`.

### Open questions
- Needs real probe to confirm exact payload requirements and behavior for `limit` and `as_count`.
