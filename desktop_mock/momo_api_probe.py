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
    "Maimemo_key",  # Alternative token variable
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
    {
        "key": "interpretations",
        "method": "GET",
        "path": "/api/v1/interpretations",
        "body": "",
        "purpose": "单词释义 (content / status)",
    },
    {
        "key": "phrases",
        "method": "GET",
        "path": "/api/v1/phrases",
        "body": "",
        "purpose": "单词例句 (text / translation / highlight)",
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
    token = creds.get("MOMO_TOKEN", "") or creds.get("Maimemo_key", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    cookie = creds.get("MOMO_COOKIE", "")
    if cookie:
        headers["Cookie"] = cookie
    return headers


# ---------------------------------------------------------------------------
# Response parsers (pure -- safe to test, no network)
# ---------------------------------------------------------------------------
def summarize_shape(data: Any, max_items: int = 3) -> Any:
    """Summarize the shape of a JSON response, redacting all actual values."""
    if isinstance(data, dict):
        return {k: summarize_shape(v, max_items) for k, v in data.items()}
    elif isinstance(data, list):
        summary: dict[str, Any] = {"_count": len(data)}
        if data:
            summary["_items"] = [summarize_shape(item, max_items) for item in data[:max_items]]
        return summary
    elif isinstance(data, str):
        return "<redacted str>"
    elif isinstance(data, bool):
        return "bool"
    elif isinstance(data, int):
        return "int"
    elif isinstance(data, float):
        return "float"
    elif data is None:
        return "null"
    else:
        return type(data).__name__


def _as_dict(value: Any) -> dict[str, Any]:
    """Coerce *value* to a dict; non-dicts become ``{}``."""
    return value if isinstance(value, dict) else {}


def _unwrap(data: Any) -> dict[str, Any]:
    """Unwrap the {"success": true, "data": {...}} envelope if present."""
    body = _as_dict(data)
    if "success" in body and "data" in body:
        return _as_dict(body["data"])
    return body


def parse_study_progress_response(data: Any) -> dict[str, Any]:
    """Parse ``POST /study/get_study_progress``.

    Real shape: ``{"progress": {"finished": int, "total": int,
    "study_time": int}}``. Unknown shapes return ``{}``.
    """
    body = _unwrap(data)
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
    body = _unwrap(data)
    items = body.get("today_items")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def parse_study_records_response(data: Any) -> dict[str, Any]:
    """Parse ``POST /study/query_study_records``.

    Real shape: ``{"records": [StudyRecord], "count": int}``. ``records``
    is empty when ``as_count=true`` was requested.
    """
    body = _unwrap(data)
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
    body = _unwrap(data)
    decks = body.get("decks")
    if not isinstance(decks, list):
        return []
    return [d for d in decks if isinstance(d, dict)]


def parse_vocabulary_query_response(data: Any) -> list[dict[str, Any]]:
    """Parse ``POST /vocabulary/query``.

    Real shape: ``{"voc": [Vocabulary]}`` where each entry has ``id`` and
    ``spelling``.
    """
    body = _unwrap(data)
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
) -> tuple[int, Any]:
    """Perform one HTTP request and return ``(status, parsed_json)``.

    Raises on transport / HTTP errors. Response bodies are still parsed with
    strings redacted later by ``summarize_shape``.
    """
    data = body.encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 -- manual probe
        status = getattr(resp, "status", getattr(resp, "code", 0)) or 0
        raw = resp.read()
    if not raw:
        return status, None
    try:
        return status, json.loads(raw.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return status, {"_raw_text": raw.decode("utf-8", errors="replace")}


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
        "ok": False, "status": None, "data": None, "error": "",
    }
    try:
        result["status"], result["data"] = _request(url, headers, method, body)
        result["ok"] = True
    except urllib.error.HTTPError as exc:
        result["status"] = exc.code
        result["error"] = f"HTTP {exc.code}: {exc.reason}"
    except urllib.error.URLError as exc:
        result["error"] = f"URL error: {exc.reason}"
    except Exception as exc:  # noqa: BLE001 -- probe must not crash the run
        result["error"] = f"{type(exc).__name__}: {exc}"
    print(f"[probe]   -> status={result['status'] or '-'} ok={result['ok']} error={result['error'] or '-'}")
    return result


# ---------------------------------------------------------------------------
# Dry-run (no network)
# ---------------------------------------------------------------------------
def _get_endpoints(args: argparse.Namespace) -> list[dict[str, Any]]:
    endpoints = []
    for spec in CANDIDATE_ENDPOINTS:
        spec_copy = dict(spec)
        if spec_copy["key"] == "today_items":
            today_limit = getattr(args, "today_items_limit", None)
            if today_limit is not None:
                spec_copy["body"] = json.dumps({"limit": today_limit})

        if spec_copy["key"] == "study_records" and getattr(args, "probe_study_records", False):
            body: dict[str, Any] = {}
            if getattr(args, "study_records_limit", None) is not None:
                body["limit"] = args.study_records_limit
            as_count = getattr(args, "study_records_as_count", None)
            if as_count == "true":
                body["as_count"] = True
            elif as_count == "false":
                body["as_count"] = False
            next_date = getattr(args, "study_records_next_date", None)
            if next_date is not None:
                body["next_study_date"] = {"end": next_date}
            voc_ids = _split_csv(getattr(args, "study_records_voc_ids", None))
            spellings = _split_csv(getattr(args, "study_records_spellings", None))
            if voc_ids and spellings:
                body["error"] = "voc_ids and spellings are mutually exclusive"
            elif voc_ids:
                body["voc_ids"] = voc_ids
            elif spellings:
                body["spellings"] = spellings
            elif getattr(args, "study_records_from_today", False):
                match_by = getattr(args, "study_records_match", "voc_ids")
                body[match_by] = [f"<from_today_items_{match_by}>"]
            spec_copy["body"] = json.dumps(body)
            
        if getattr(args, "probe_enrichment", False):
            source = getattr(args, "enrichment_source", "today_items")
            is_needed = False
            
            if spec_copy["key"] == source:
                is_needed = True
                
            if spec_copy["key"] == "vocabulary_query" and getattr(args, "probe_vocabulary", False):
                spec_ids = dict(spec_copy)
                spec_ids["key"] = "vocabulary_query_ids"
                spec_ids["body"] = json.dumps({"ids": []})
                endpoints.append(spec_ids)
                
                spec_spellings = dict(spec_copy)
                spec_spellings["key"] = "vocabulary_query_spellings"
                spec_spellings["body"] = json.dumps({"spellings": []})
                endpoints.append(spec_spellings)
                continue
                
            if spec_copy["key"] == "interpretations" and getattr(args, "probe_interpretations", False):
                spec_copy["path"] = "/api/v1/interpretations?voc_id=<voc_id>"
                is_needed = True
                
            if spec_copy["key"] == "phrases" and getattr(args, "probe_phrases", False):
                spec_copy["path"] = "/api/v1/phrases?voc_id=<voc_id>"
                is_needed = True
                
            if not is_needed:
                continue

        endpoints.append(spec_copy)
    return endpoints


def _split_csv(value: str | None) -> list[str]:
    """Split a comma-separated CLI value, dropping empty parts."""
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def run_dry_run(args: argparse.Namespace) -> int:
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
    for spec in _get_endpoints(args):
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


def run_real_probe(args: argparse.Namespace) -> int:
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

    voc_ids: list[str] = []
    voc_spellings: list[str] = []

    for spec in _get_endpoints(args):
        if spec["key"] == "study_records" and getattr(args, "study_records_from_today", False):
            match_by = getattr(args, "study_records_match", "voc_ids")
            values = voc_ids if match_by == "voc_ids" else voc_spellings
            if not values:
                print(f"[probe] skip {spec['key']}: no {match_by} extracted from today_items")
                continue
            body = json.loads(spec.get("body") or "{}")
            body[match_by] = values[: getattr(args, "enrichment_limit", 3)]
            spec["body"] = json.dumps(body)

        if getattr(args, "probe_enrichment", False):
            if spec["key"] == "vocabulary_query_ids":
                if not voc_ids:
                    print(f"[probe] skip {spec['key']}: no voc_ids extracted")
                    continue
                spec["body"] = json.dumps({"ids": voc_ids})
            elif spec["key"] == "vocabulary_query_spellings":
                if not voc_spellings:
                    print(f"[probe] skip {spec['key']}: no voc_spellings extracted")
                    continue
                spec["body"] = json.dumps({"spellings": voc_spellings})
            elif spec["key"] == "interpretations":
                if not voc_ids:
                    print(f"[probe] skip {spec['key']}: no voc_ids extracted")
                    continue
                spec["path"] = f"/api/v1/interpretations?voc_id={voc_ids[0]}"
                spec["body"] = ""
            elif spec["key"] == "phrases":
                if not voc_ids:
                    print(f"[probe] skip {spec['key']}: no voc_ids extracted")
                    continue
                spec["path"] = f"/api/v1/phrases?voc_id={voc_ids[0]}"
                spec["body"] = ""

        result = _probe_endpoint(spec, headers)
        if not (result["ok"] and result["data"] is not None):
            continue
        data = result["data"]
        
        if getattr(args, "probe_enrichment", False) and spec["key"] == getattr(args, "enrichment_source", "today_items"):
            items = parse_today_items_response(data)
            limit = getattr(args, "enrichment_limit", 3)
            for it in items[:limit]:
                if it.get("voc_id"):
                    voc_ids.append(it["voc_id"])
                if it.get("voc_spelling"):
                    voc_spellings.append(it["voc_spelling"])
            print(f"[probe] enrichment extracted {len(voc_ids)} ids, {len(voc_spellings)} spellings")

        if spec["key"] == "today_items" and getattr(args, "study_records_from_today", False):
            items = parse_today_items_response(data)
            limit = getattr(args, "enrichment_limit", 3)
            for it in items[:limit]:
                if it.get("voc_id"):
                    voc_ids.append(it["voc_id"])
                if it.get("voc_spelling"):
                    voc_spellings.append(it["voc_spelling"])
            print(f"[probe] study_records source extracted {len(voc_ids)} ids, {len(voc_spellings)} spellings")

        if args.shape_only:
            shape = summarize_shape(data, max_items=args.limit)
            print(f"[probe] raw shape: {json.dumps(shape, indent=2, ensure_ascii=False)}")
            continue

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
    parser.add_argument(
        "--shape-only",
        action="store_true",
        help="only print the sanitized shape of the response",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=3,
        help="max number of list items to summarize in shape-only mode",
    )
    parser.add_argument(
        "--today-items-limit",
        type=int,
        default=None,
        help="optional limit for get_today_items (OpenAPI max 1000)",
    )
    parser.add_argument(
        "--probe-study-records",
        action="store_true",
        help="enable custom parameters for query_study_records",
    )
    parser.add_argument(
        "--study-records-limit",
        type=int,
        default=None,
        help="limit for query_study_records",
    )
    parser.add_argument(
        "--study-records-as-count",
        choices=["true", "false"],
        default=None,
        help="as_count for query_study_records",
    )
    parser.add_argument(
        "--study-records-next-date",
        type=str,
        default=None,
        help="next_study_date.end for query_study_records (ISO datetime; next-study planning only)",
    )
    parser.add_argument(
        "--study-records-voc-ids",
        type=str,
        default=None,
        help="comma-separated voc_ids for precise query_study_records lookup",
    )
    parser.add_argument(
        "--study-records-spellings",
        type=str,
        default=None,
        help="comma-separated spellings for precise query_study_records lookup",
    )
    parser.add_argument(
        "--study-records-from-today",
        action="store_true",
        help="extract a few values from today_items and use them for precise query_study_records lookup",
    )
    parser.add_argument(
        "--study-records-match",
        choices=["voc_ids", "spellings"],
        default="voc_ids",
        help="field to use with --study-records-from-today",
    )
    parser.add_argument(
        "--probe-enrichment",
        action="store_true",
        help="enable enrichment probing (vocabulary, interpretations, phrases)",
    )
    parser.add_argument(
        "--enrichment-source",
        type=str,
        default="today_items",
        help="source endpoint for extracting enrichment IDs (default: today_items)",
    )
    parser.add_argument(
        "--enrichment-limit",
        type=int,
        default=3,
        help="max items to extract from the source endpoint for enrichment queries",
    )
    parser.add_argument(
        "--probe-vocabulary",
        action="store_true",
        help="probe /api/v1/vocabulary/query during enrichment",
    )
    parser.add_argument(
        "--probe-interpretations",
        action="store_true",
        help="probe /api/v1/interpretations during enrichment",
    )
    parser.add_argument(
        "--probe-phrases",
        action="store_true",
        help="probe /api/v1/phrases during enrichment",
    )
    args = parser.parse_args(argv)
    if args.dry_run:
        return run_dry_run(args)
    return run_real_probe(args)


if __name__ == "__main__":
    sys.exit(main())
