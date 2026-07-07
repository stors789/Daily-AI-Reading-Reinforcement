"""Article generation pipeline -- pure, adapter-driven.

This module stitches together config loading, LLM generation, and
article persistence using the adapter interfaces defined in
core/adapters.py.  It does NOT import aqt / mw / gui_hooks.
"""

from __future__ import annotations

from typing import Any

from .adapters import ConfigAdapter, DeckAdapter
from .config import DEFAULT_CONFIG
from .llm import generate_article
from .prompt import build_prompt
from .utils import clean_provider_id, clean_text


def run_article_generation(
    config_adapter: ConfigAdapter,
    deck_adapter: DeckAdapter,
    deck_name_value: str,
    cards: list[Any],
    selected_fields: list[str],
    preset: dict[str, str],
) -> dict[str, Any]:
    """Execute the full generation pipeline and return a result envelope.

    The caller is responsible for input validation, preset resolution,
    and event emission.  This function focuses only on the core work:
    load config, call the LLM, save the article files.

    Returns a dict with keys:
        deckName, article, markdownPath, htmlPath, articleCard (None)
    """
    config = (config_adapter.load() or {}).copy()
    for key, value in DEFAULT_CONFIG.items():
        config.setdefault(key, value)

    api_key = str(config.get("api_key", "")).strip()
    if not api_key:
        raise RuntimeError("Missing API key. Set api_key in configuration.")

    article = generate_article(
        config,
        deck_name_value,
        cards,
        selected_fields,
        preset,
    )
    if not article.strip():
        raise RuntimeError("The AI response was empty.")

    saved = deck_adapter.save_article(deck_name_value, cards, article)
    article_card: dict[str, Any] | None = None
    article_card_error = ""
    if bool(config.get("create_article_cards")):
        try:
            saved_card = deck_adapter.save_article_card(
                deck_name_value,
                cards,
                article,
                saved["markdown"],
                saved["html"],
            )
            if not (isinstance(saved_card, dict) and saved_card.get("_desktop_stub")):
                article_card = saved_card
        except Exception as exc:
            article_card_error = _safe_article_card_error(exc)

    return {
        "deckName": deck_name_value,
        "article": article,
        "markdownPath": str(saved["markdown"]),
        "htmlPath": str(saved["html"]),
        "articleCard": article_card,
        "articleCardError": article_card_error,
    }


def _safe_article_card_error(exc: BaseException) -> str:
    public_message = getattr(exc, "public_message", None)
    if isinstance(public_message, str) and public_message.strip():
        return public_message.strip()
    return "Failed to create article card."
