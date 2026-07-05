from __future__ import annotations

from typing import Any, Callable


class AnkiDeckProvider:
    """Thin adapter that delegates to collect_today_decks().

    This lets the UI bridge call DECK_PROVIDER.get_today_decks()
    instead of reaching for the raw helper directly, which keeps
    the door open for non-Anki deck providers later.
    """

    def __init__(self, collect_today_decks_func: Callable[[], dict[str, dict[str, Any]]]) -> None:
        self._collect_today_decks = collect_today_decks_func

    def get_today_decks(self) -> dict[str, dict[str, Any]]:
        return self._collect_today_decks()
