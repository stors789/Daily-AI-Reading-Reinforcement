"""Article file management with host-configurable storage."""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any

from .rendering import parse_article_response, render_article_html
from .utils import slugify

# Compatibility default for callers that do not supply a host storage path.
# Desktop and Anki adapters provide their own location instead.
ARTICLES_DIR = Path.cwd() / "user_files" / "articles"


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


def _article_title(article: str) -> str:
    """Return the generated title in a frontmatter-safe, single-line form."""
    title = str(parse_article_response(article).get("title") or "").strip()
    return " ".join(title.splitlines())


def _legacy_generated_day(generated_at: str) -> str:
    """Extract a day from historical metadata without browser date parsing.

    Older files only have ``generated_at`` in the local ``YYYY-MM-DD HH:MM:SS``
    format.  Keep accepting that shape while new files persist the explicit
    ``generated_day`` field used by the history heatmap.
    """
    candidate = str(generated_at or "").strip()[:10]
    if len(candidate) == 10 and candidate[4] == "-" and candidate[7] == "-":
        year, month, day = candidate.split("-")
        if year.isdigit() and month.isdigit() and day.isdigit():
            return candidate
    return ""


def _article_metadata(text: str, meta: dict[str, str]) -> tuple[str, str]:
    """Return title and generated day, with compatibility for old Markdown."""
    title = meta.get("title", "").strip()
    if not title and "[ARTICLE_TITLE]" in text:
        title = _article_title(text)
    generated_day = meta.get("generated_day", "").strip()
    if not generated_day:
        generated_day = _legacy_generated_day(meta.get("generated_at", ""))
    return title, generated_day


def save_article(
    deck_name_value: str,
    cards: list[Any],
    article: str,
    *,
    articles_dir: Path | None = None,
) -> dict[str, Path]:
    destination = articles_dir or ARTICLES_DIR
    destination.mkdir(parents=True, exist_ok=True)
    date_part = time.strftime("%Y-%m-%d")
    time_part = time.strftime("%H%M%S")
    unique_part = f"{int((time.time() % 1) * 1000):03d}-{uuid.uuid4().hex[:6]}"
    slug = slugify(deck_name_value)
    basename = f"{date_part}-{slug}-{time_part}-{unique_part}"
    markdown_path = destination / f"{basename}.md"
    html_path = destination / f"{basename}.html"

    metadata = [
        "---",
        f"deck: {deck_name_value}",
        f"generated_at: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"generated_day: {date_part}",
        f"title: {_article_title(article)}",
        f"card_count: {len(cards)}",
        "---",
        "",
    ]
    markdown_path.write_text("\n".join(metadata) + article + "\n", encoding="utf-8")
    html_path.write_text(render_article_html(deck_name_value, cards, article), encoding="utf-8")
    return {"markdown": markdown_path, "html": html_path}


def list_saved_articles(*, articles_dir: Path | None = None) -> list[dict[str, str]]:
    destination = articles_dir or ARTICLES_DIR
    if not destination.is_dir():
        return []
    articles = []
    for md_file in sorted(destination.glob("*.md"), reverse=True):
        try:
            text = md_file.read_text(encoding="utf-8")
        except Exception:
            continue
        meta = parse_article_frontmatter(text)
        title, generated_day = _article_metadata(text, meta)
        articles.append({
            "path": str(md_file),
            "filename": md_file.name,
            "deck": meta.get("deck", ""),
            "generated_at": meta.get("generated_at", ""),
            "generated_day": generated_day,
            "title": title,
            "card_count": meta.get("card_count", ""),
        })
    return articles


def load_saved_article(
    path: str,
    *,
    articles_dir: Path | None = None,
) -> dict[str, Any]:
    destination = articles_dir or ARTICLES_DIR
    article_path = Path(path)
    if not article_path.is_file():
        raise RuntimeError(f"Article file not found: {path}")
    if not str(article_path).startswith(str(destination)):
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
    title, generated_day = _article_metadata(body, meta)
    return {
        "path": str(article_path),
        "deck": meta.get("deck", ""),
        "generated_at": meta.get("generated_at", ""),
        "generated_day": generated_day,
        "title": title,
        "card_count": meta.get("card_count", ""),
        "article": body,
        "htmlPath": str(html_path) if html_path.is_file() else "",
    }
