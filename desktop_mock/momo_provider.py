"""Mock MoMo DeckProvider for Phase 8.

Provides a provider interface (get_today_decks / get_deck_cards) that wraps
the existing mock data in mock_data.py.  This is a mock-first shell: it
returns locally-defined fake deck & card data and does NOT contact the real
MoMo (墨墨) API, read browser cookies, or touch any network.

The returned structures match the shared web UI's frontend contract so the
payloads built by mock_data.py remain identical to Phase 7.
"""

from __future__ import annotations

from typing import Any

from mock_data import MOCK_DECKS


class MockMoMoDeckProvider:
    """Mock deck / card provider that wraps desktop_mock's static data.

    Public API
    ----------
    get_today_decks() -> list[dict]
        Deck rows sorted by name, each with ``id``, ``name``, ``newCount``,
        ``failedCount``, ``totalCount``, ``isGroup``.

    get_deck_cards(deck_id) -> dict
        ``{"deckId": str, "cards": list[dict]}`` where each card dict has
        ``cid``, ``nid``, ``term``, ``fields``, ``is_new``, ``is_failed``,
        ``review_count``.  Unknown *deck_id* returns an empty cards list.

    No real API, network, or Anki interaction.
    """

    def get_today_decks(self) -> list[dict[str, Any]]:
        """Return deck rows sorted by display name."""
        return [
            {
                "id": deck["id"],
                "name": deck["name"],
                "newCount": deck["new_count"],
                "failedCount": deck["failed_count"],
                "totalCount": deck["total_count"],
                "isGroup": bool(deck["is_group"]),
            }
            for deck in sorted(
                MOCK_DECKS.values(), key=lambda d: d["name"].lower()
            )
        ]

    def get_deck_cards(self, deck_id: str) -> dict[str, Any]:
        """Return cards for *deck_id* in frontend-compatible format."""
        deck = MOCK_DECKS.get(deck_id)
        if not deck:
            return {"deckId": deck_id, "cards": []}
        cards: list[dict[str, Any]] = []
        for card in deck["cards"]:
            cards.append(
                {
                    "cid": card["cid"],
                    "nid": card["nid"],
                    "term": card["term"],
                    "fields": dict(card["fields"]),
                    "is_new": card["is_new"],
                    "is_failed": card["is_failed"],
                    "review_count": card["review_count"],
                }
            )
        return {"deckId": deck_id, "cards": cards}
