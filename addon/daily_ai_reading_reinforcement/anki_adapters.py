"""Anki-specific adapter implementations.

These concrete adapters bridge the Protocol interfaces defined in
core/adapters.py to Anki's aqt/mw runtime.  They are imported only
by __init__.py, never by desktop_mock or core modules.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, TypeVar

from aqt import mw

from .anki_config_store import AnkiConfigStore
from .core.article import save_article as core_save_article

_T = TypeVar("_T")


class _FutureWrapper:
    """Thin wrapper around a python concurrent.futures.Future or Anki future."""

    __slots__ = ("_future",)

    def __init__(self, future: Any) -> None:
        self._future = future

    def result(self) -> Any:
        return self._future.result()


class AnkiConfigAdapter:
    """ConfigAdapter backed by mw.addonManager."""

    __slots__ = ("_store",)

    def __init__(self, addon_package: str) -> None:
        self._store = AnkiConfigStore(addon_package)

    def load(self) -> dict[str, Any] | None:
        return self._store.load()

    def save(self, config: dict[str, Any]) -> None:
        self._store.save(config)


class AnkiDeckAdapter:
    """DeckAdapter that writes articles as local files and cards into Anki."""

    __slots__ = ("_card_saver",)

    def __init__(self, card_saver: Any) -> None:
        """*card_saver* is an AnkiCardSaver instance (from anki_card_saver.py)."""
        self._card_saver = card_saver

    def save_article(
        self,
        deck_name_value: str,
        cards: list[Any],
        article: str,
    ) -> dict[str, Path]:
        """Persist article as Markdown + HTML on disk (same as Anki path)."""
        return core_save_article(deck_name_value, cards, article)

    def save_article_card(
        self,
        source_deck_name: str,
        cards: list[Any],
        article: str,
        markdown_path: Path,
        html_path: Path,
    ) -> dict[str, Any]:
        """Create an Anki card through the injected card-saver function."""
        return self._card_saver.save_article_card(
            source_deck_name, cards, article, markdown_path, html_path
        )


class AnkiEnvironmentAdapter:
    """EnvironmentAdapter backed by mw.taskman.run_in_background."""

    __slots__ = ()

    def run_in_background(
        self,
        task: Callable[[], _T],
        on_done: Callable[[Any], None],
    ) -> None:
        mw.taskman.run_in_background(task, on_done)
