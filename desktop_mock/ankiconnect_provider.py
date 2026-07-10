"""AnkiConnect deck provider for standalone desktop development.

This provider implements the same high-level interface as the MoMo providers
without importing Anki's ``aqt`` runtime.  It talks to a local AnkiConnect
server using only ``urllib.request`` from the Python standard library.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Callable


DEFAULT_ANKICONNECT_URL = "http://127.0.0.1:8765"
ANKICONNECT_VERSION = 6


class AnkiConnectError(RuntimeError):
    """Raised when AnkiConnect is unavailable or returns an error."""


class AnkiConnectDeckProvider:
    """Deck/card provider backed by a local AnkiConnect server.

    AnkiConnect exposes card state through search and ``cardsInfo`` rather than
    Anki's full revlog rows.  The native addon can tell whether a card was first
    learned or failed today by querying revlog directly; this standalone
    provider uses conservative approximations:
    - today's candidate cards come from ``rated:1``;
    - today's Anki answer buttons are mapped to the MoMo-compatible response
      names FORGET/VAGUE/FAMILIAR/RECOGNIZE via ``rated:1:<ease>``;
    - failed-today cards are identified with ``rated:1:1`` when supported, with
      relearning queue/type as a secondary signal;
    - newly learned cards prefer ``introduced:1`` when supported, and otherwise
      fall back to ``rated:1`` plus ``reps <= 1``.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_ANKICONNECT_URL,
        timeout: float = 10.0,
        opener: Callable[..., Any] | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._opener = opener or urllib.request.urlopen
        self._deck_cache: dict[str, dict[str, Any]] = {}

    def _invoke(self, action: str, params: dict[str, Any] | None = None) -> Any:
        payload = {
            "action": action,
            "version": ANKICONNECT_VERSION,
            "params": params or {},
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self._base_url,
            data=data,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "dairr-ankiconnect-provider/0.1",
            },
            method="POST",
        )
        try:
            with self._opener(req, timeout=self._timeout) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            raise AnkiConnectError(f"AnkiConnect HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise AnkiConnectError("AnkiConnect URL error") from exc

        try:
            body = json.loads(raw.decode("utf-8", errors="replace") if raw else "{}")
        except json.JSONDecodeError as exc:
            raise AnkiConnectError("Invalid JSON from AnkiConnect") from exc

        if not isinstance(body, dict):
            raise AnkiConnectError("Invalid AnkiConnect response")
        if body.get("error"):
            raise AnkiConnectError(str(body.get("error")))
        if "result" not in body:
            raise AnkiConnectError("AnkiConnect response missing result")
        return body.get("result")

    def _find_cards(self, query: str) -> list[int]:
        result = self._invoke("findCards", {"query": query})
        if not isinstance(result, list):
            return []
        ids: list[int] = []
        for value in result:
            card_id = _as_int(value)
            if card_id is not None:
                ids.append(card_id)
        return ids

    def _find_cards_optional(self, query: str) -> set[int]:
        try:
            return set(self._find_cards(query))
        except AnkiConnectError:
            return set()

    def _today_card_sets(self) -> tuple[list[int], dict[int, set[int]], set[int]]:
        """Fetch today's candidates and answer grades with one round trip.

        ``multi`` has been part of AnkiConnect's stable API for years.  The
        individual-query fallback keeps older installations working.
        """
        queries = ["rated:1", *(f"rated:1:{ease}" for ease in range(1, 5)), "introduced:1"]
        try:
            result = self._invoke(
                "multi",
                {"actions": [
                    {"action": "findCards", "params": {"query": query}}
                    for query in queries
                ]},
            )
            if not isinstance(result, list) or len(result) != len(queries):
                raise AnkiConnectError("Invalid AnkiConnect multi response")
            card_sets: list[set[int]] = []
            for item in result:
                values = item.get("result") if isinstance(item, dict) else None
                if not isinstance(values, list):
                    raise AnkiConnectError("Invalid AnkiConnect multi result")
                card_sets.append({cid for value in values if (cid := _as_int(value)) is not None})
        except AnkiConnectError:
            card_sets = [set(self._find_cards(queries[0]))]
            card_sets.extend(self._find_cards_optional(query) for query in queries[1:])

        today_ids = sorted(card_sets[0])
        grade_ids = {ease: card_sets[ease] for ease in range(1, 5)}
        return today_ids, grade_ids, card_sets[5]

    def _cards_info(self, card_ids: list[int]) -> list[dict[str, Any]]:
        if not card_ids:
            return []
        result = self._invoke("cardsInfo", {"cards": card_ids})
        if not isinstance(result, list):
            return []
        return [item for item in result if isinstance(item, dict)]

    def get_today_decks(self) -> list[dict[str, Any]]:
        """Return frontend-compatible deck rows for cards studied today."""
        decks = self._refresh_cache()
        return [
            {
                "id": deck_id,
                "name": deck["name"],
                "newCount": deck["newCount"],
                "failedCount": deck["failedCount"],
                "totalCount": deck["totalCount"],
                "isGroup": bool(deck.get("isGroup")),
            }
            for deck_id, deck in sorted(
                decks.items(), key=lambda item: item[1]["name"].lower()
            )
        ]

    def get_deck_cards(self, deck_id: str) -> dict[str, Any]:
        """Return frontend-compatible card rows for a deck or group id."""
        if not self._deck_cache or deck_id not in self._deck_cache:
            self._refresh_cache()
        deck = self._deck_cache.get(deck_id)
        if not deck:
            return {
                "deckId": deck_id,
                "name": "",
                "cards": [],
                "fields": [],
                "selectedFields": [],
            }
        cards = [dict(card, fields=dict(card.get("fields", {}))) for card in deck["cards"]]
        fields = _field_names(cards)
        return {
            "deckId": deck_id,
            "name": deck["name"],
            "cards": cards,
            "fields": fields,
            "selectedFields": list(fields),
        }

    def _refresh_cache(self) -> dict[str, dict[str, Any]]:
        today_ids, grade_ids, introduced_today_ids = self._today_card_sets()
        failed_today_ids = grade_ids[1]
        infos = self._cards_info(today_ids)

        decks: dict[str, dict[str, Any]] = {}
        for info in infos:
            card = _card_from_info(info, failed_today_ids, introduced_today_ids, grade_ids)
            if card is None:
                continue
            deck_name = str(info.get("deckName") or "Default")
            _append_card(decks, deck_name, deck_name, card, is_group=False)

        _add_parent_groups(decks)
        for deck in decks.values():
            _refresh_counts(deck)
            deck["cards"].sort(
                key=lambda card: (
                    not bool(card.get("is_failed")),
                    not bool(card.get("is_new")),
                    str(card.get("term", "")).lower(),
                    str(card.get("cid", "")),
                )
            )
        self._deck_cache = decks
        return decks


def _card_from_info(
    info: dict[str, Any],
    failed_today_ids: set[int],
    introduced_today_ids: set[int],
    grade_ids: dict[int, set[int]],
) -> dict[str, Any] | None:
    cid = _as_int(info.get("cardId") or info.get("card_id"))
    if cid is None:
        return None
    nid = _as_int(info.get("note") or info.get("noteId") or info.get("nid")) or 0
    fields = _extract_fields(info.get("fields"))
    term = _first_meaningful_field(fields) or str(info.get("question") or f"Card {cid}")
    reps = _as_int(info.get("reps")) or 0
    queue = _as_int(info.get("queue"))
    card_type = _as_int(info.get("type"))

    is_failed = cid in failed_today_ids or queue == 3 or card_type == 3
    is_new = cid in introduced_today_ids or (cid not in failed_today_ids and reps <= 1)
    response_grades = [ease for ease in range(1, 5) if cid in grade_ids.get(ease, set())]
    response_names = {
        1: "FORGET",
        2: "VAGUE",
        3: "FAMILIAR",
        4: "RECOGNIZE",
    }
    # A card can receive more than one answer today.  Keep the complete set for
    # filters, while the single compatibility field uses the lowest grade.
    first_response = response_names.get(min(response_grades)) if response_grades else None

    return {
        "cid": cid,
        "nid": nid,
        "term": _clean_text(term),
        "fields": {name: _clean_text(value) for name, value in fields.items()},
        "is_new": bool(is_new),
        "is_failed": bool(is_failed),
        "first_response": first_response,
        "response_grades": response_grades,
        "review_count": reps,
    }


def _extract_fields(raw_fields: Any) -> dict[str, str]:
    if not isinstance(raw_fields, dict):
        return {}
    fields: dict[str, str] = {}
    for name, value in raw_fields.items():
        if isinstance(value, dict):
            fields[str(name)] = str(value.get("value") or "")
        else:
            fields[str(name)] = str(value or "")
    return fields


def _append_card(
    decks: dict[str, dict[str, Any]],
    deck_id: str,
    name: str,
    card: dict[str, Any],
    is_group: bool,
) -> None:
    if deck_id not in decks:
        decks[deck_id] = {
            "name": name,
            "newCount": 0,
            "failedCount": 0,
            "totalCount": 0,
            "isGroup": is_group,
            "cards": [],
            "_cards_by_note": {},
        }
    cards_by_note = decks[deck_id]["_cards_by_note"]
    note_key = str(card.get("nid") or card.get("cid"))
    existing = cards_by_note.get(note_key)
    if existing is None:
        copied = dict(card, fields=dict(card.get("fields", {})))
        cards_by_note[note_key] = copied
        decks[deck_id]["cards"].append(copied)
        return
    existing["is_new"] = bool(existing.get("is_new")) or bool(card.get("is_new"))
    existing["is_failed"] = bool(existing.get("is_failed")) or bool(card.get("is_failed"))
    existing["response_grades"] = sorted({
        *existing.get("response_grades", []),
        *card.get("response_grades", []),
    })
    response_names = {1: "FORGET", 2: "VAGUE", 3: "FAMILIAR", 4: "RECOGNIZE"}
    grades = existing["response_grades"]
    existing["first_response"] = response_names.get(min(grades)) if grades else None
    existing["review_count"] = int(existing.get("review_count") or 0) + int(card.get("review_count") or 0)


def _add_parent_groups(decks: dict[str, dict[str, Any]]) -> None:
    leaf_items = [
        (deck_id, deck)
        for deck_id, deck in decks.items()
        if not bool(deck.get("isGroup"))
    ]
    for _deck_id, deck in leaf_items:
        parts = str(deck["name"]).split("::")
        for index in range(1, len(parts)):
            parent_name = "::".join(parts[:index])
            group_id = f"group:{parent_name}"
            for card in deck["cards"]:
                _append_card(decks, group_id, parent_name, card, is_group=True)


def _refresh_counts(deck: dict[str, Any]) -> None:
    deck["totalCount"] = len(deck["cards"])
    deck["newCount"] = sum(1 for card in deck["cards"] if card.get("is_new"))
    deck["failedCount"] = sum(1 for card in deck["cards"] if card.get("is_failed"))
    deck.pop("_cards_by_note", None)


def _field_names(cards: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    names: list[str] = []
    for card in cards:
        fields = card.get("fields")
        if not isinstance(fields, dict):
            continue
        for name, value in fields.items():
            if name in seen or not value:
                continue
            seen.add(name)
            names.append(name)
    return names


def _first_meaningful_field(fields: dict[str, str]) -> str:
    for value in fields.values():
        cleaned = _clean_text(value)
        if cleaned:
            return cleaned
    return ""


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
