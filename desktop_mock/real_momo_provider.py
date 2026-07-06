"""Phase 10: Real MoMo DeckProvider skeleton.

This module provides the RealMoMoDeckProvider class, which interacts with
the real MoMo (墨墨) Open API. It implements the same high-level interface
(get_today_decks, get_deck_cards) as MockMoMoDeckProvider, but sources its
data from the network.

Currently, this is a skeleton:
- get_today_decks() fetches Markji decks but fills newCount/failedCount
  with default values (0).
- get_deck_cards(deck_id) uses a conservative skeleton strategy (Strategy A)
  and does not yet fetch real cards, returning an empty list.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Callable


class MoMoAPIError(RuntimeError):
    """Raised when the MoMo Open API returns an error or invalid response."""
    pass


class MoMoProviderDataError(MoMoAPIError):
    """Raised when data fetching or mapping fails at a specific stage."""
    def __init__(self, stage: str):
        super().__init__(f"provider_stage_failed:{stage}")
        self.stage = stage


def unwrap_api_response(data: Any) -> Any:
    """Unwrap MoMo API response envelope.
    
    If the data is an envelope containing 'success' and 'errors':
    - Returns data["data"] (or {}) if success is True.
    - Raises MoMoAPIError if success is False.
    - If it's not an envelope, returns data unchanged.
    """
    if isinstance(data, dict) and "success" in data and "errors" in data:
        if data.get("success") is True:
            return data.get("data", {})
        else:
            errors = data.get("errors")
            err_msg = "MoMo API returned errors"
            if isinstance(errors, list) and len(errors) > 0 and isinstance(errors[0], dict):
                code = errors[0].get("code", "UNKNOWN")
                msg = errors[0].get("message", "No message")
                err_msg = f"MoMo API error: {code} - {msg}"
            elif isinstance(errors, dict):
                code = errors.get("code", "UNKNOWN")
                msg = errors.get("message", "No message")
                err_msg = f"MoMo API error: {code} - {msg}"
            raise MoMoAPIError(err_msg)
    return data


def _as_dict(value: Any) -> dict[str, Any]:
    """Coerce value to a dict; non-dicts become empty dicts."""
    return value if isinstance(value, dict) else {}


def parse_study_progress_response(data: Any) -> dict[str, Any]:
    """Parse POST /study/get_study_progress response."""
    body = _as_dict(unwrap_api_response(data))
    progress = _as_dict(body.get("progress"))
    out: dict[str, Any] = {}
    for key in ("finished", "total", "study_time"):
        if key in progress:
            out[key] = progress[key]
    return out


def parse_today_items_response(data: Any) -> list[dict[str, Any]]:
    """Parse POST /study/get_today_items response."""
    body = _as_dict(unwrap_api_response(data))
    items = body.get("today_items")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def parse_study_records_response(data: Any) -> dict[str, Any]:
    """Parse POST /study/query_study_records response."""
    body = _as_dict(unwrap_api_response(data))
    records = body.get("records")
    if not isinstance(records, list):
        records = []
    records = [r for r in records if isinstance(r, dict)]
    count = body.get("count")
    if not isinstance(count, int):
        count = len(records)
    return {"records": records, "count": count}


def parse_markji_deck_list_response(data: Any) -> list[dict[str, Any]]:
    """Parse GET /markji/decks response."""
    body = _as_dict(unwrap_api_response(data))
    decks = body.get("decks")
    if not isinstance(decks, list):
        return []
    return [d for d in decks if isinstance(d, dict)]


def parse_vocabulary_query_response(data: Any) -> list[dict[str, Any]]:
    """Parse POST /vocabulary/query response."""
    body = _as_dict(unwrap_api_response(data))
    voc = body.get("voc")
    if not isinstance(voc, list):
        return []
    return [v for v in voc if isinstance(v, dict)]


class RealMoMoDeckProvider:
    """Real provider interacting with the MoMo Open API.
    
    This requires a valid bearer token to be provided during initialization.
    Network requests are only made when calling the respective methods.
    """

    def __init__(
        self,
        token: str,
        base_url: str = "https://open.maimemo.com/open",
        timeout: float = 10.0,
        opener: Callable[..., Any] | None = None,
    ) -> None:
        if not token:
            raise ValueError("MoMo token is required.")
        self._token = token
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._opener = opener or urllib.request.urlopen

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        url = self._base_url + path
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
            "User-Agent": "dairr-momo-provider/0.1",
        }
        
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
            
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with self._opener(req, timeout=self._timeout) as resp:
                raw = resp.read()
            if not raw:
                return {}
            return json.loads(raw.decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as exc:
            raise MoMoAPIError(f"HTTP {exc.code}: {exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise MoMoAPIError(f"URL error: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise MoMoAPIError("Invalid JSON in response") from exc

    def get_study_progress_raw(self) -> dict[str, Any]:
        """Fetch raw study progress."""
        return self._request("POST", "/api/v1/study/get_study_progress", body={})

    def get_today_items_raw(
        self, is_finished: bool | None = None, is_new: bool | None = None, limit: int | None = None
    ) -> dict[str, Any]:
        """Fetch raw today items. Only set parameters are included in the request body."""
        body: dict[str, Any] = {}
        if is_finished is not None:
            body["is_finished"] = is_finished
        if is_new is not None:
            body["is_new"] = is_new
        if limit is not None:
            body["limit"] = limit
        return self._request("POST", "/api/v1/study/get_today_items", body=body)

    def query_study_records_raw(
        self, next_study_date: str | None = None, as_count: bool | None = None, limit: int | None = None
    ) -> dict[str, Any]:
        """Query raw study records."""
        body: dict[str, Any] = {}
        if next_study_date is not None:
            body["next_study_date"] = next_study_date
        if as_count is not None:
            body["as_count"] = as_count
        if limit is not None:
            body["limit"] = limit
        return self._request("POST", "/api/v1/study/query_study_records", body=body)

    def get_markji_decks_raw(self) -> dict[str, Any]:
        """Fetch raw Markji decks."""
        return self._request("GET", "/api/v1/markji/decks")

    def query_vocabulary_raw(self, spellings: list[str] | None = None, ids: list[int] | None = None) -> dict[str, Any]:
        """Query raw vocabulary. spellings and ids are mutually exclusive."""
        if spellings is not None and ids is not None:
            raise ValueError("spellings and ids are mutually exclusive")
        body: dict[str, Any] = {}
        if spellings is not None:
            body["spellings"] = spellings
        if ids is not None:
            body["ids"] = ids
        return self._request("POST", "/api/v1/vocabulary/query", body=body)

    # --- High-level mappings ---

    def get_today_decks(self) -> list[dict[str, Any]]:
        """Return deck rows mapped from Markji decks."""
        try:
            raw_data = self.get_markji_decks_raw()
            decks = parse_markji_deck_list_response(raw_data)
        except MoMoAPIError:
            # Fallback for markji 403
            decks = None
        
        if decks is None:
            # Try to get study progress for totalCount fallback
            total_count = 0
            try:
                prog_raw = self.get_study_progress_raw()
                prog = parse_study_progress_response(prog_raw)
                total_count = prog.get("total", 0)
            except MoMoAPIError:
                pass
            
            return [{
                "id": "momo_today",
                "name": "MoMo Today",
                "newCount": 0,
                "failedCount": 0,
                "totalCount": total_count,
                "isGroup": False,
            }]

        result = []
        for deck in decks:
            result.append({
                "id": deck.get("id", ""),
                "name": deck.get("name", "Unknown Deck"),
                "totalCount": deck.get("card_count", 0),
                "newCount": 0,      # TODO: per-deck new count not exposed in confirmed spec
                "failedCount": 0,   # TODO: per-deck failed count not exposed in confirmed spec
                "isGroup": False,   # TODO: verify parent_id / root_deck semantics with real data
            })
        return result

    def get_deck_cards(self, deck_id: str) -> dict[str, Any]:
        """Return skeleton deck cards or study-based cards.
        
        Strategy A: Conservative skeleton.
        If deck_id is 'momo_today' (fallback deck), uses today_items
        and query_study_records_raw to populate cards.
        """
        if deck_id == "momo_today":
            try:
                raw_items = self.get_today_items_raw()
            except MoMoAPIError as exc:
                raise MoMoProviderDataError("today_items_request") from exc
                
            try:
                items = parse_today_items_response(raw_items)
            except MoMoAPIError as exc:
                raise MoMoProviderDataError("today_items_parse") from exc

            if not items:
                return {
                    "deckId": deck_id,
                    "cards": [],
                    "fields": ["term", "status", "source", "review_count_status"],
                    "selectedFields": ["term"],
                }
            
            records_available = False
            try:
                raw_records = self.query_study_records_raw()
                records_data = parse_study_records_response(raw_records)
                records = {r.get("voc_id"): r for r in records_data.get("records", []) if "voc_id" in r}
                records_available = True
            except MoMoAPIError:
                records = {}
            
            try:
                cards = []
                for item in items:
                    voc_id = item.get("voc_id")
                    if voc_id is None:
                        continue
                    voc_spelling = item.get("voc_spelling", str(voc_id))
                    is_new = bool(item.get("is_new"))
                    first_response = item.get("first_response")
                    is_finished = item.get("is_finished")

                    # Phase 16: is_failed reserved for FORGET only;
                    # is_finished=False maps to status="unfinished" instead.
                    is_failed = first_response == "FORGET"

                    # Derive status from study item state.
                    if is_new:
                        status = "new"
                    elif is_finished is True:
                        status = "finished"
                    elif is_finished is False:
                        status = "unfinished"
                    else:
                        status = "unknown"

                    review_count = 0
                    review_count_status = "unavailable"
                    if records_available:
                        review_count_status = "provider_value_unverified"
                        if voc_id in records:
                            review_count = records[voc_id].get("study_count", 0)

                    cards.append({
                        "cid": str(voc_id),
                        "nid": "",
                        "term": voc_spelling,
                        "fields": {
                            "term": voc_spelling,
                            "status": status,
                            "source": "MoMo Today",
                            "review_count_status": review_count_status,
                        },
                        "is_new": is_new,
                        "is_failed": is_failed,
                        "review_count": review_count,
                    })
            except Exception as exc:
                raise MoMoProviderDataError("card_mapping") from exc

            return {
                "deckId": deck_id,
                "cards": cards,
                "fields": ["term", "status", "source", "review_count_status"],
                "selectedFields": ["term"],
            }

        return {
            "deckId": deck_id,
            "cards": [],
            "fields": ["term", "status", "source", "review_count_status"],
            "selectedFields": ["term"],
        }
