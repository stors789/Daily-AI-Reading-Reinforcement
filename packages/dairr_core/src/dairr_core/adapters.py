"""Platform adapter interfaces for DAIRR hosts.

These Protocol classes define the contracts that concrete adapters
(Anki and Desktop) must fulfill.  They let the article generation
pipeline run in either environment without importing aqt / mw.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Protocol, TypeVar

_T = TypeVar("_T")


class ConfigAdapter(Protocol):
    """Read and persist add-on configuration.

    Anki bridges to mw.addonManager; Desktop bridges to env vars or a
    local JSON file.
    """

    def load(self) -> dict[str, Any] | None:
        """Return the raw config dict or None."""
        ...

    def save(self, config: dict[str, Any]) -> None:
        """Persist *config*."""
        ...


class DeckAdapter(Protocol):
    """Save generated articles and article cards.

    Anki writes into the Anki collection; Desktop writes Markdown + HTML
    files onto the local filesystem.
    """

    def save_article(
        self,
        deck_name_value: str,
        cards: list[Any],
        article: str,
    ) -> dict[str, Path]:
        """Persist the generated article and return {markdown, html} paths."""
        ...

    def save_article_card(
        self,
        source_deck_name: str,
        cards: list[Any],
        article: str,
        markdown_path: Path,
        html_path: Path,
    ) -> dict[str, Any]:
        """Create an article card in the destination deck/collection."""
        ...


class EnvironmentAdapter(Protocol):
    """Schedule async work in a background thread.

    Anki uses mw.taskman; Desktop uses threading.Thread.
    """

    def run_in_background(
        self,
        task: Callable[[], _T],
        on_done: Callable[[Any], None],
    ) -> None:
        """Run *task* on a background thread and call *on_done* with a Future-ish wrapper."""
        ...
