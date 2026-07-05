"""Phase 9 probe script for the real MoMo (墨墨) Open API.

This is a *manual investigation* tool. It is NOT imported by the desktop
mock server, the Anki addon, or any UI path. It only runs when executed
explicitly:

    python3 desktop_mock/momo_api_probe.py            # probe (real network)
    python3 desktop_mock/momo_api_probe.py --dry-run  # no network at all

The endpoints below are taken from the official OpenAPI bundle published
at https://open.maimemo.com/ (墨墨开放 API).  Two product lines are
exposed:

- 墨墨背单词 (Maimemo): study data -- today's progress, today's items,
  study records, vocabulary lookup, add words, advance review.
- 墨墨记忆卡 (Markji): content -- decks, chapters, cards.

Authentication
--------------
The Open API uses a single bearer token (NOT cookies). The token is
obtained from the MoMo app
(My -> 更多设置 -> 实验功能 -> 开放 API) or from
https://open.maimemo.com/open/api/v1/tokens/openapi, and is sent as
``Authorization: Bearer <token>``.  This probe reads it only from the
``MOMO_TOKEN`` environment variable.

Hard rules
----------
- No credentials are stored, hardcoded, or printed in full. Credentials
  are read *only* from environment variables defined in ``CREDENTIAL_ENVS``.
- Importing this module must NEVER trigger a network call. All network
  work happens inside ``main()`` when the script is run directly.
- ``--dry-run`` performs zero network I/O and only prints the plan.
- Only the Python standard library is used. No ``requests`` etc.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any, Iterable

# ---------------------------------------------------------------------------
# Credential configuration
# ---------------------------------------------------------------------------
# Environment variables the probe *may* read. They are listed centrally so
# reviewers / tests can confirm the surface. The script never writes these
# values anywhere and never prints them in full.
CREDENTIAL_ENVS: tuple[str, ...] = (
    "MOMO_TOKEN",   # bearer token from the MoMo app / open API portal
    "MOMO_COOKIE",  # reserved -- the Open API uses a bearer token, not
                    # cookies, but the var is kept so a future auth scheme
                    # can be probed without changing the test surface.
)

# ---------------------------------------------------------------------------
# Real endpoints (confirmed from open.maimemo.com OpenAPI bundle)
# ---------------------------------------------------------------------------
# Base host is https://open.maimemo.com/open ; the OpenAPI ``servers`` entry
# lists https://open.maimemo.com/open as the production server, and paths
# are appended to it.
BASE_URL = "https://open.maimemo.com/open"

# Each entry: (key, method, path, body-or-None, purpose)
# GET paths use query params built separately; POST paths send a JSON body.
CANDIDATE_ENDPOINTS: tuple[dict[str, str], ...] = (
    {
        "key": "study_progress",
        "method": "POST",
        "path": "/api/v1/study/get_study_progress",
        "body": "{}",
        "purpose": "今日学习进度 (finished / total / study_time)",
    },
    {
        "key": "today_items",
        "method": "POST",
        "path": "/api/v1/study/get_today_items",
        "body": "{}",
        "purpose": "今日学习单词列表 (voc_id / voc_spelling / is_new / is_finished)",
    },
    {
        "key": "study_records",
        "method": "POST",
        "path": "/api/v1/study/query_study_records",
        "body": "{}",
        "purpose": "学习记录 (voc_id / study_count / next_study_date / tags)",
    },
    {
        "key": "markji_decks",
        "method": "GET",
        "path": "/api/v1/markji/decks",
        "body": "",
        "purpose": "墨墨记忆卡牌组列表 (id / name / card_count / parent_id)",
    },
    {
        "key": "vocabulary_query",
        "method": "POST",
        "path": "/api/v1/vocabulary/query",
        "body": '{"spellings": ["apple"]}',
        "purpose": "单词查询 (id / spelling)",
    },
)

# Frontend contract that downstream code expects. Used by the mapping
# report to flag direct / derived / missing / defaulted fields.
DECK_ROW_FIELDS: tuple[str, ...] = (
    "id", "name", "newCount", "failedCount", "totalCount", "isGroup",
)
CARD_FIELDS: tuple[str, ...] = (
    "cid", "nid", "term", "fields", "is_new", "is_failed", "review_count",
)


# ---------------------------------------------------------------------------
# Credential helpers (pure -- safe to test)
# ---------------------------------------------------------------------------
def mask_credential(value: str | None) -> str:
    """Return a masked representation of *value*.

    Shows at most the first 4 and last 4 characters, with the middle
    replaced by ``***``. Empty / None values return ``<empty>`` /
    ``<unset>`` so logs and dry-run output never leak a full secret.
    Short values (<=8 chars) are fully masked so length-leak is minimal.
    """
    if value is None:
        return "<unset>"
    if value == "":
        return "<empty>"
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}***{value[-4:]}"


def load_credentials(environ: dict[str, str] | None = None) -> dict[str, str]:
    """Read the credential env vars from *environ* (defaults to ``os.environ``).

    Returns a dict keyed by env var name. Missing values are present as
    the empty string so callers can branch uniformly. This function does
    no I/O and never prints anything.
    """
    env = environ if environ is not None else os.environ
    return {name: env.get(name, "") for name in CREDENTIAL_ENVS}


def has_credentials(creds: dict[str, str]) -> bool:
    """True if at least one configured credential env var is non-empty."""
    return any(v for v in creds.values())


def build_request_headers(creds: dict[str, str]) -> dict[str, str]:
    """Build headers for an outbound request from *creds*.

    The Open API uses ``Authorization: Bearer <token>``. ``Cookie`` is
    attached only when ``MOMO_COOKIE`` is set, so a cookie-based auth
    scheme could still be probed without code changes.
    """
    headers: dict[str, str] = {
        "User-Agent": "dairr-momo-probe/0.1 (manual investigation)",
        "Accept": "application/json",
    }
    token = creds.get("MOMO_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    cookie = creds.get("MOMO_COOKIE", "")
    if cookie:
        headers["Cookie"] = cookie
    return headers


# ---------------------------------------------------------------------------
# Response parsers (pure -- safe to test, no network)
# ---------------------------------------------------------------------------
def _as_dict(value: Any) -> dict[str, Any]:
    """Coerce *value* to a dict; non-dicts become ``{}``."""
    return value if isinstance(value, dict) else {}


def parse_study_progress_response(data: Any) -> dict[str, Any]:
    """Parse ``POST /study/get_study_progress``.

    Real shape: ``{"progress": {"finished": int, "total": int,
    "study_time": int}}``. Unknown shapes return ``{}``.
    """
    body = _as_dict(data)
    progress = _as_dict(body.get("progress"))
    out: dict[str, Any] = {}
    for key in ("finished", "total", "study_time"):
        if key in progress:
            out[key] = progress[key]
    return out


def parse_today_items_response(data: Any) -> list[dict[str, Any]]:
    """Parse ``POST /study/get_today_items``.

    Real shape: ``{"today_items": [StudyTodayItem]}`` where each item has
    ``voc_id``, ``voc_spelling``, ``order``, ``is_new``, ``is_finished``,
    and optional ``first_response``.
    """
    body = _as_dict(data)
    items = body.get("today_items")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def parse_study_records_response(data: Any) -> dict[str, Any]:
    """Parse ``POST /study/query_study_records``.

    Real shape: ``{"records": [StudyRecord], "count": int}``. ``records``
    is empty when ``as_count=true`` was requested.
    """
    body = _as_dict(data)
    records = body.get("records")
    if not isinstance(records, list):
        records = []
    records = [r for r in records if isinstance(r, dict)]
    count = body.get("count")
    if not isinstance(count, int):
        count = len(records)
    return {"records": records, "count": count}


def parse_markji_deck_list_response(data: Any) -> list[dict[str, Any]]:
    """Parse ``GET /markji/decks``.

    Real shape: ``{"decks": [MarkjiDeck], "total": int}``.
    """
    body = _as_dict(data)
    decks = body.get("decks")
    if not isinstance(decks, list):
        return []
    return [d for d in decks if isinstance(d, dict)]


def parse_vocabulary_query_response(data: Any) -> list[dict[str, Any]]:
    """Parse ``POST /vocabulary/query``.

    Real shape: ``{"voc": [Vocabulary]}`` where each entry has ``id`` and
    ``spelling``.
    """
    body = _as_dict(data)
    voc = body.get("voc")
    if not isinstance(voc, list):
        return []
    return [v for v in voc if isinstance(v, dict)]


# ---------------------------------------------------------------------------
# Mapping report (pure -- safe to test)
# ---------------------------------------------------------------------------
def _field_report(
    raw: dict[str, Any], target_fields: Iterable[str],
) -> dict[str, dict[str, str]]:
    """Classify each target field as direct / derived / missing / defaulted.

    direct    -- present under the exact target name (or a known alias).
    defaulted -- not present, but the probe fills it with a fixed default.
    missing   -- not present and no default is defined.
    """
    aliases: dict[str, tuple[str, ...]] = {
        # deck row (frontend)
        "id":          ("id", "deck_id", "bookId", "book_id"),
        "name":        ("name", "title", "deckName", "bookName"),
        "newCount":    ("newCount", "new_count", "newToday", "new_today", "finished"),
        "failedCount": ("failedCount", "failed_count", "reviewCount", "review_count"),
        "totalCount":  ("totalCount", "total_count", "total", "count", "card_count"),
        "isGroup":     ("isGroup", "is_group", "isGrouped"),
        # card payload (frontend)
        "cid":          ("cid", "card_id", "cardId", "id", "voc_id"),
        "nid":          ("nid", "note_id", "noteId"),
        "term":         ("term", "word", "front", "headword", "voc_spelling", "spelling"),
        "fields":       ("fields", "content", "back", "definition"),
        "is_new":       ("is_new", "isNew", "new"),
        "is_failed":    ("is_failed", "isFailed", "failed"),
        "review_count": ("review_count", "reviewCount", "reviews", "study_count"),
    }
    defaults: dict[str, Any] = {
        "isGroup": False,
        "newCount": 0,
        "failedCount": 0,
        "nid": "",
        "fields": {},
        "is_new": False,
        "is_failed": False,
        "review_count": 0,
    }
    report: dict[str, dict[str, str]] = {}
    for field in target_fields:
        names = aliases.get(field, (field,))
        hit = next((name for name in names if name in raw), None)
        if hit is not None:
            report[field] = {"status": "direct", "source": hit}
        elif field in defaults:
            report[field] = {"status": "defaulted", "default": str(defaults[field])}
        else:
            report[field] = {"status": "missing"}
    return report


def deck_row_mapping_report(raw_deck: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Mapping report for a single raw deck dict -> frontend deck row."""
    return _field_report(raw_deck, DECK_ROW_FIELDS)


def card_mapping_report(raw_card: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Mapping report for a single raw card dict -> frontend card payload."""
    return _field_report(raw_card, CARD_FIELDS)


def today_item_mapping_report(raw_item: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Mapping report for a single StudyTodayItem -> frontend card payload.

    StudyTodayItem carries ``voc_id`` / ``voc_spelling`` / ``is_new`` /
    ``is_finished``; several card fields have no source and must be
    defaulted.
    """
    return _field_report(raw_item, CARD_FIELDS)


# ---------------------------------------------------------------------------
# Network helpers (only called from main())
# ---------------------------------------------------------------------------
def _request(
    url: str, headers: dict[str, str], method: str, body: str, timeout: float = 10.0,
) -> Any:
    """Perform one HTTP request and return parsed JSON. Raises on error."""
    data = body.encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 -- manual probe
        raw = resp.read()
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return {"_raw_text": raw.decode("utf-8", errors="replace")}


def _probe_endpoint(
    spec: dict[str, str], headers: dict[str, str],
) -> dict[str, Any]:
    """Probe one endpoint and return a structured result dict.

    On any failure, ``error`` is filled and ``data`` is ``None`` so the
    caller can keep probing other endpoints.
    """
    url = BASE_URL + spec["path"]
    method = spec["method"]
    body = spec.get("body", "")
    print(f"[probe] {method} {url}")
    result: dict[str, Any] = {
        "key": spec["key"], "method": method, "url": url,
        "ok": False, "data": None, "error": "",
    }
    try:
        result["data"] = _request(url, headers, method, body)
        result["ok"] = True
    except urllib.error.HTTPError as exc:
        result["error"] = f"HTTP {exc.code}: {exc.reason}"
    except urllib.error.URLError as exc:
        result["error"] = f"URL error: {exc.reason}"
    except Exception as exc:  # noqa: BLE001 -- probe must not crash the run
        result["error"] = f"{type(exc).__name__}: {exc}"
    print(f"[probe]   -> ok={result['ok']} error={result['error'] or '-'}")
    return result


# ---------------------------------------------------------------------------
# Dry-run (no network)
# ---------------------------------------------------------------------------
def run_dry_run() -> int:
    """Print the probe plan without making any network call."""
    creds = load_credentials()
    print("== dry-run: no network will be performed ==")
    print()
    print("Credentials that would be read from the environment:")
    for name in CREDENTIAL_ENVS:
        present = bool(creds.get(name))
        if present:
            print(f"  - {name}: present {mask_credential(creds[name])}")
        else:
            print(f"  - {name}: <unset>")
    if not has_credentials(creds):
        print("  (no credentials set -- real run would abort with a hint)")
    print()
    print(f"Base URL: {BASE_URL}")
    print("Endpoints that would be requested:")
    for spec in CANDIDATE_ENDPOINTS:
        print(f"  - {spec['key']:18} {spec['method']:4} {spec['path']}")
        print(f"      purpose: {spec['purpose']}")
        if spec.get("body"):
            print(f"      body: {spec['body']}")
    print()
    print("Fields the mapping report would classify:")
    print("  deck row:", ", ".join(DECK_ROW_FIELDS))
    print("  card    :", ", ".join(CARD_FIELDS))
    print()
    print("Headers that would be sent (sensitive values masked):")
    headers = build_request_headers(creds)
    for hk, hv in headers.items():
        if hk in ("Cookie", "Authorization"):
            print(f"  {hk}: {mask_credential(hv)}")
        else:
            print(f"  {hk}: {hv}")
    return 0


# ---------------------------------------------------------------------------
# Real run (network -- only inside main())
# ---------------------------------------------------------------------------
def _report_mapping(raw: dict[str, Any], fn) -> None:
    """Print a mapping report for one raw dict."""
    print(f"  raw keys: {sorted(raw.keys())}")
    report = fn(raw)
    for field, info in report.items():
        tail = info.get("source", info.get("default", ""))
        print(f"    {field}: {info['status']} {tail}".rstrip())


def run_real_probe() -> int:
    """Run the real probe against confirmed endpoints."""
    creds = load_credentials()
    if not has_credentials(creds):
        print("No credentials found in the environment.")
        print("Set at least one of: " + ", ".join(CREDENTIAL_ENVS))
        print("Example:")
        print('  MOMO_TOKEN="..." python3 desktop_mock/momo_api_probe.py')
        print()
        print("Run with --dry-run to see the plan without network access.")
        return 2

    print("== MoMo Open API probe ==")
    print(f"Base URL: {BASE_URL}")
    print("Credentials (masked):")
    for name in CREDENTIAL_ENVS:
        print(f"  {name}: {mask_credential(creds[name])}")
    print()

    headers = build_request_headers(creds)

    for spec in CANDIDATE_ENDPOINTS:
        result = _probe_endpoint(spec, headers)
        if not (result["ok"] and result["data"] is not None):
            continue
        data = result["data"]
        if spec["key"] == "study_progress":
            parsed = parse_study_progress_response(data)
            print(f"[probe] study progress: {parsed}")
        elif spec["key"] == "today_items":
            items = parse_today_items_response(data)
            print(f"[probe] parsed {len(items)} today item(s)")
            for it in items[:3]:
                _report_mapping(it, today_item_mapping_report)
        elif spec["key"] == "study_records":
            parsed = parse_study_records_response(data)
            print(f"[probe] study records count={parsed['count']}")
            for r in parsed["records"][:3]:
                _report_mapping(r, today_item_mapping_report)
        elif spec["key"] == "markji_decks":
            decks = parse_markji_deck_list_response(data)
            print(f"[probe] parsed {len(decks)} markji deck(s)")
            for d in decks[:3]:
                _report_mapping(d, deck_row_mapping_report)
        elif spec["key"] == "vocabulary_query":
            voc = parse_vocabulary_query_response(data)
            print(f"[probe] parsed {len(voc)} vocabulary item(s)")
            for v in voc[:3]:
                print(f"  voc: {v}")

    print()
    print("== probe complete ==")
    print("Record confirmed endpoints and field mappings in momo_api_notes.md.")
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="momo_api_probe",
        description="Manual probe for the real MoMo (墨墨) Open API. Never runs at import time.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the probe plan without making any network request",
    )
    args = parser.parse_args(argv)
    if args.dry_run:
        return run_dry_run()
    return run_real_probe()


if __name__ == "__main__":
    sys.exit(main())
