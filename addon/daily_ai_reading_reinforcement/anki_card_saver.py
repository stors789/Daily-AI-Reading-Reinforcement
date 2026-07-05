"""AnkiCardSaver adapter -- wraps create_article_card behind a uniform interface.

This is a thin shell that delegates to the real Anki-specific
create_article_card function.  It exists so that UI/bridge callers
depend on CARD_SAVER.save_article_card(...) instead of calling
create_article_card(...) directly, making it possible to swap in
alternative backends (desktop, momo, etc.) later.
"""

from __future__ import annotations

from typing import Any, Callable, TypeVar


_F = TypeVar("_F", bound=Callable[..., Any])


class AnkiCardSaver:
    """Minimal adapter that delegates every call to an injected function."""

    __slots__ = ("_create_article_card",)

    def __init__(self, create_article_card_func: _F) -> None:
        self._create_article_card: _F = create_article_card_func

    def save_article_card(self, *args: Any, **kwargs: Any) -> Any:
        """Save an article as an Anki card, forwarding all arguments."""
        return self._create_article_card(*args, **kwargs)

