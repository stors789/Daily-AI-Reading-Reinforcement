"""Legacy article API that preserves the add-on's article storage path."""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from ..dairr_core import article as _article  # type: ignore[import-not-found]
    from ..dairr_core.article import parse_article_frontmatter  # type: ignore[import-not-found]
except ImportError:
    from dairr_core import article as _article
    from dairr_core.article import parse_article_frontmatter

ARTICLES_DIR = Path(__file__).resolve().parents[1] / "user_files" / "articles"
time = _article.time
uuid = _article.uuid


def save_article(deck_name_value: str, cards: list[Any], article: str) -> dict[str, Path]:
    return _article.save_article(
        deck_name_value,
        cards,
        article,
        articles_dir=ARTICLES_DIR,
    )


def list_saved_articles() -> list[dict[str, str]]:
    return _article.list_saved_articles(articles_dir=ARTICLES_DIR)


def load_saved_article(path: str) -> dict[str, Any]:
    return _article.load_saved_article(path, articles_dir=ARTICLES_DIR)


def delete_saved_article(path: str) -> dict[str, Any]:
    return _article.delete_saved_article(path, articles_dir=ARTICLES_DIR)


def delete_all_saved_articles() -> dict[str, int]:
    return _article.delete_all_saved_articles(articles_dir=ARTICLES_DIR)


def delete_saved_articles_by_day(generated_day: str) -> dict[str, Any]:
    return _article.delete_saved_articles_by_day(generated_day, articles_dir=ARTICLES_DIR)
