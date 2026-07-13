from __future__ import annotations

from typing import Any, Callable


class AnkiDeckProvider:
    """Thin adapter that delegates to collect_today_decks().

    The add-on deliberately supports only Anki's internal collection. Desktop
    provider selection lives outside the add-on package.
    """

    def __init__(self, collect_today_decks_func: Callable[[], dict[str, dict[str, Any]]]) -> None:
        self._collect_today_decks = collect_today_decks_func

    def get_today_decks(self) -> dict[str, dict[str, Any]]:
        return self._collect_today_decks()
