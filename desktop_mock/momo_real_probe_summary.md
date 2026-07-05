# MoMo Open API Real Probe Summary

## Authentication
- token 是否可用: Yes (Returns 200 for study endpoints)
- 是否确认为 Bearer token: Yes
- 401 / 403 / rate limit 行为: Invalid token returns 401. Markji endpoints returned 403 Forbidden (may lack permissions).

## study_progress
```text
endpoint: /api/v1/study/get_study_progress
status: OK (200)
top-level keys: errors, data, success
progress keys: finished (int), total (int), study_time (int)
value types: nested under "data.progress"
can map to frontend: Yes (finished, total)
open questions: The response is wrapped in `{"data": {"progress": ...}, "success": true}`, so parsers need to unwrap `data` first.
```

## today_items
```text
endpoint: /api/v1/study/get_today_items
status: OK (200)
top-level keys: errors, data, success
item count observed: 50
item keys: voc_id, voc_spelling, order, first_response, is_new, is_finished
value types: str, int, bool (nested under "data.today_items")
is_new 是否存在: Yes (bool)
is_finished 是否存在: Yes (bool)
first_response 是否存在: Yes (str)
voc_id / voc_spelling 是否存在: Yes (str)
can map to frontend card fields: Yes
missing fields: nid, fields, is_failed, review_count.
```

## study_records
```text
endpoint: /api/v1/study/query_study_records
status: OK (200)
top-level keys: errors, data, success
record count observed: 50 (nested under "data.records")
record keys: voc_id, voc_spelling, add_date, first_study_date, last_study_date, next_study_date, last_response, study_count, tags
study_count 是否存在: Yes (int)
last_response 是否存在: Yes (str)
tags 是否存在: Yes (list)
是否能补充 review_count / is_failed: review_count can map from study_count. is_failed could map from last_response.
```

## markji_decks
```text
endpoint: /api/v1/markji/decks
status: Failed (403 Forbidden)
top-level keys: N/A
deck count observed: N/A
deck keys: N/A
id/name/card_count/parent_id/root_deck 是否存在: N/A
isGroup 应如何推导: N/A
totalCount 能否从 card_count 得到: N/A
```

## vocabulary_query
```text
endpoint: /api/v1/vocabulary/query
status: OK (200)
request sample: apple
top-level keys: errors, data, success
voc item keys: id (str), spelling (str)
是否只有 id/spelling: Yes
是否有释义字段: No
能否补充 fields: Cannot map 'fields' directly from vocabulary_query since interpretations are not included.
```
