"""Article file management with host-configurable storage."""

from __future__ import annotations

import time
import uuid
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from .atomic_persistence import atomic_write_json, atomic_write_text, path_lock
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
    generation_metadata: Mapping[str, Any] | None = None,
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
    manifest_path = destination / f"{basename}.manifest.json"

    generated_at = time.strftime('%Y-%m-%d %H:%M:%S')
    manifest = _build_article_manifest(
        deck_name_value,
        cards,
        generated_at,
        date_part,
        _article_title(article),
        generation_metadata,
    )

    metadata = [
        "---",
        f"schema_version: 2",
        f"deck: {_frontmatter_value(deck_name_value)}",
        f"generated_at: {generated_at}",
        f"generated_day: {date_part}",
        f"title: {_frontmatter_value(_article_title(article))}",
        f"card_count: {len(cards)}",
        f"manifest: {manifest_path.name}",
        "---",
        "",
    ]
    markdown_text = "\n".join(metadata) + article + "\n"
    html_text = render_article_html(deck_name_value, cards, article)
    # Markdown is the authoritative history record and is replaced last. A
    # crash can leave an ignored auxiliary orphan, never a half-written article.
    atomic_write_json(manifest_path, manifest, private=True)
    atomic_write_text(html_path, html_text, private=True)
    atomic_write_text(markdown_path, markdown_text, private=True)
    return {"markdown": markdown_path, "html": html_path}


def list_saved_articles(*, articles_dir: Path | None = None) -> list[dict[str, Any]]:
    destination = articles_dir or ARTICLES_DIR
    if not destination.is_dir():
        return []
    articles: list[dict[str, Any]] = []
    for md_file in sorted(destination.glob("*.md"), reverse=True):
        try:
            md_file = _contained_article_path(md_file, destination)
            text = md_file.read_text(encoding="utf-8")
        except Exception:
            continue
        meta = parse_article_frontmatter(text)
        title, generated_day = _article_metadata(text, meta)
        manifest = _load_manifest(md_file, meta)
        item: dict[str, Any] = {
            "path": str(md_file),
            "filename": md_file.name,
            "deck": meta.get("deck", ""),
            "generated_at": meta.get("generated_at", ""),
            "generated_day": generated_day,
            "title": title,
            "card_count": meta.get("card_count", ""),
        }
        if manifest:
            item["targetUsage"] = deepcopy(manifest.get("target_usage", []))
            item["unusedTargets"] = deepcopy(manifest.get("unused_targets", []))
            item["targetReuse"] = deepcopy(manifest.get("target_reuse", {}))
            item["manifestVersion"] = manifest.get("schema_version", 1)
        articles.append(item)
    return articles


def load_saved_article(
    path: str,
    *,
    articles_dir: Path | None = None,
) -> dict[str, Any]:
    destination = articles_dir or ARTICLES_DIR
    article_path = _contained_article_path(Path(path), destination)
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
    manifest = _load_manifest(article_path, meta)
    return {
        "path": str(article_path),
        "deck": meta.get("deck", ""),
        "generated_at": meta.get("generated_at", ""),
        "generated_day": generated_day,
        "title": title,
        "card_count": meta.get("card_count", ""),
        "article": body,
        "htmlPath": str(html_path) if html_path.is_file() else "",
        "metadata": deepcopy(manifest),
        "targetUsage": deepcopy(manifest.get("target_usage", [])),
        "unusedTargets": deepcopy(manifest.get("unused_targets", [])),
        "targetReuse": deepcopy(manifest.get("target_reuse", {})),
    }


def delete_saved_article(
    path: str,
    *,
    articles_dir: Path | None = None,
) -> dict[str, Any]:
    """Delete one saved article and its rendered HTML companion."""
    destination = articles_dir or ARTICLES_DIR
    root = Path(destination).resolve(strict=False)
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        candidate.resolve(strict=False).relative_to(root)
    except ValueError as exc:
        raise RuntimeError("Access denied: path outside articles directory.") from exc
    article_path = _contained_article_path(Path(path), destination)

    html_path = article_path.with_suffix(".html")
    article_path.unlink()
    html_deleted = False
    if html_path.is_file():
        html_path.unlink()
        html_deleted = True
    manifest_path = article_path.with_suffix(".manifest.json")
    manifest_deleted = False
    if manifest_path.is_file():
        manifest_path.unlink()
        manifest_deleted = True
    return {"path": str(article_path), "htmlDeleted": html_deleted, "manifestDeleted": manifest_deleted}


def delete_all_saved_articles(*, articles_dir: Path | None = None) -> dict[str, int]:
    """Delete all saved article pairs inside the configured storage directory."""
    destination = articles_dir or ARTICLES_DIR
    if not destination.is_dir():
        return {"deleted": 0}
    deleted = 0
    for article in list_saved_articles(articles_dir=destination):
        delete_saved_article(article["path"], articles_dir=destination)
        deleted += 1
    return {"deleted": deleted}


def delete_saved_articles_by_day(
    generated_day: str,
    *,
    articles_dir: Path | None = None,
) -> dict[str, Any]:
    """Delete saved article pairs belonging to one explicit calendar day."""
    day = str(generated_day or "").strip()
    if len(day) != 10 or day[4] != "-" or day[7] != "-" or not day.replace("-", "").isdigit():
        raise RuntimeError("Choose a valid article date before deleting.")
    destination = articles_dir or ARTICLES_DIR
    deleted = 0
    for article in list_saved_articles(articles_dir=destination):
        if article.get("generated_day") != day:
            continue
        delete_saved_article(article["path"], articles_dir=destination)
        deleted += 1
    return {"deleted": deleted, "generatedDay": day}


def update_article_manifest(
    path: str,
    updates: Mapping[str, Any],
    *,
    articles_dir: Path | None = None,
) -> dict[str, Any]:
    """Merge article metadata atomically, retaining unknown extension fields."""
    destination = articles_dir or ARTICLES_DIR
    article_path = _contained_article_path(Path(path), destination)
    text = article_path.read_text(encoding="utf-8")
    meta = parse_article_frontmatter(text)
    manifest_path = article_path.with_suffix(".manifest.json")
    with path_lock(manifest_path):
        manifest = _load_manifest(article_path, meta)
        for key, value in updates.items():
            if _sensitive_metadata_key(str(key)):
                continue
            manifest[str(key)] = deepcopy(value)
        manifest.setdefault("schema_version", 2)
        atomic_write_json(manifest_path, manifest, private=True)
    return deepcopy(manifest)


def _contained_article_path(path: Path, destination: Path) -> Path:
    lexical_root = Path(destination).absolute()
    root = lexical_root.resolve(strict=False)
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = lexical_root / candidate
    if not candidate.is_file():
        raise RuntimeError("Article file not found.")
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise RuntimeError("Access denied: path outside articles directory.") from exc
    if resolved.suffix.lower() != ".md":
        raise RuntimeError("Only saved Markdown articles can be accessed.")
    return candidate.absolute()


def _frontmatter_value(value: Any) -> str:
    return " ".join(str(value or "").replace("\x00", "").splitlines()).strip()


def _build_article_manifest(
    deck_name: str,
    cards: list[Any],
    generated_at: str,
    generated_day: str,
    title: str,
    supplied: Mapping[str, Any] | None,
) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "schema_version": 2,
        "deck": deck_name,
        "generated_at": generated_at,
        "generated_day": generated_day,
        "title": title,
        "card_count": len(cards),
        "targets": [
            {
                "card_id": str(getattr(card, "cid", getattr(card, "card_id", "")) or ""),
                "term": str(getattr(card, "term", "") or ""),
            }
            for card in cards
        ],
        "target_usage": [],
        "unused_targets": [],
        "target_reuse": {},
    }
    for key, value in (supplied or {}).items():
        if not _sensitive_metadata_key(str(key)):
            manifest[str(key)] = deepcopy(value)
    return manifest


def _load_manifest(article_path: Path, frontmatter: Mapping[str, str]) -> dict[str, Any]:
    name = str(frontmatter.get("manifest") or article_path.with_suffix(".manifest.json").name)
    candidate = article_path.parent / name
    try:
        resolved = candidate.resolve(strict=False)
        resolved.relative_to(article_path.parent.resolve(strict=False))
        if not resolved.is_file():
            return {}
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        return dict(payload) if isinstance(payload, dict) else {}
    except (ValueError, OSError, UnicodeError, json.JSONDecodeError):
        return {}


def _sensitive_metadata_key(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in ("api_key", "authorization", "password", "secret", "access_token"))
