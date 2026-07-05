# Article file management, extracted from __init__.py.
# These do not depend on Anki/aqt/mw/gui_hooks.

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .rendering import render_article_html
from .utils import slugify

# Article storage directory, computed from the core module location.
_ADDON_DIR = Path(__file__).resolve().parent.parent
ARTICLES_DIR = _ADDON_DIR / "user_files" / "articles"


def parse_article_frontmatter(text: str) -> dict[str, str]:
    meta: dict[str, str] = {}
    if not text.startswith("---"):
        return meta
    end = text.find("---", 3)
    if end == -1:
        return meta
    for line in text[3:end].strip().splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    return meta


def save_article(
    deck_name_value: str, cards: list[Any], article: str
) -> dict[str, Path]:
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    date_part = time.strftime("%Y-%m-%d")
    time_part = time.strftime("%H%M%S")
    slug = slugify(deck_name_value)
    basename = f"{date_part}-{slug}-{time_part}"
    markdown_path = ARTICLES_DIR / f"{basename}.md"
    html_path = ARTICLES_DIR / f"{basename}.html"

    metadata = [
        "---",
        f"deck: {deck_name_value}",
        f"generated_at: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"card_count: {len(cards)}",
        "---",
        "",
    ]
    markdown_path.write_text("\n".join(metadata) + article + "\n", encoding="utf-8")
    html_path.write_text(render_article_html(deck_name_value, cards, article), encoding="utf-8")
    return {"markdown": markdown_path, "html": html_path}


def list_saved_articles() -> list[dict[str, str]]:
    if not ARTICLES_DIR.is_dir():
        return []
    articles = []
    for md_file in sorted(ARTICLES_DIR.glob("*.md"), reverse=True):
        try:
            text = md_file.read_text(encoding="utf-8")
        except Exception:
            continue
        meta = parse_article_frontmatter(text)
        articles.append({
            "path": str(md_file),
            "filename": md_file.name,
            "deck": meta.get("deck", ""),
            "generated_at": meta.get("generated_at", ""),
            "card_count": meta.get("card_count", ""),
        })
    return articles


def load_saved_article(path: str) -> dict[str, Any]:
    article_path = Path(path)
    if not article_path.is_file():
        raise RuntimeError(f"Article file not found: {path}")
    if not str(article_path).startswith(str(ARTICLES_DIR)):
        raise RuntimeError("Access denied: path outside articles directory.")
    text = article_path.read_text(encoding="utf-8")
    meta = parse_article_frontmatter(text)
    # Strip frontmatter to get article body
    body = text
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            body = text[end + 3:].strip()
    html_path = article_path.with_suffix(".html")
    return {
        "path": str(article_path),
        "deck": meta.get("deck", ""),
        "generated_at": meta.get("generated_at", ""),
        "card_count": meta.get("card_count", ""),
        "article": body,
        "htmlPath": str(html_path) if html_path.is_file() else "",
    }
