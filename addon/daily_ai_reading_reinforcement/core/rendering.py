# Article parsing and HTML rendering, extracted from __init__.py.
# Parse functions live here (not in article.py) to avoid a circular import:
#   article.py → rendering.py (save_article calls render_article_html)
#   If parse functions were in article.py, rendering.py → article.py → rendering.py.
# These do not depend on Anki/aqt/mw/gui_hooks.

from __future__ import annotations

import html
import re
import time
from typing import Any


def extract_article_block(raw: str, start_marker: str, end_marker: str = "") -> str:
    start = raw.find(start_marker)
    if start == -1:
        return ""
    content_start = start + len(start_marker)
    end = raw.find(end_marker, content_start) if end_marker else -1
    return raw[content_start : len(raw) if end == -1 else end].strip()


def parse_review_notes(review_raw: str) -> list[dict[str, str]]:
    notes = []
    for raw_line in str(review_raw or "").splitlines():
        line = re.sub(r"^[-*]\s*", "", raw_line.strip())
        if not line:
            continue
        if "::" in line:
            term, note = line.split("::", 1)
        elif "：" in line:
            term, note = line.split("：", 1)
        elif ":" in line:
            term, note = line.split(":", 1)
        else:
            term, note = "", line
        notes.append({"term": term.strip(), "note": note.strip()})
    return notes


def parse_article_response(article: str) -> dict[str, Any]:
    raw = str(article or "").strip()
    title = extract_article_block(raw, "[ARTICLE_TITLE]", "[MAIN_ARTICLE]")
    main_article = extract_article_block(raw, "[MAIN_ARTICLE]", "[REVIEW_NOTES]")
    review_raw = extract_article_block(raw, "[REVIEW_NOTES]")
    if not title and not main_article and not review_raw:
        return {
            "title": "Reading Article",
            "main_article": raw,
            "review_notes": [],
        }
    return {
        "title": title or "Reading Article",
        "main_article": main_article or raw,
        "review_notes": parse_review_notes(review_raw),
    }


def render_paragraph_html(text: str) -> str:
    return "".join(
        f"<p>{html.escape(block.strip()).replace(chr(10), '<br>')}</p>"
        for block in str(text or "").split("\n\n")
        if block.strip()
    )


def render_review_notes_html(notes: list[dict[str, str]]) -> str:
    if not notes:
        return ""
    rows = []
    for note in notes:
        term = html.escape(note.get("term", ""))
        body = html.escape(note.get("note", ""))
        rows.append(
            f"{f'<dt>{term}</dt>' if term else ''}<dd>{body}</dd>"
        )
    return f"""
    <section class="review-notes">
      <h2>Review Notes</h2>
      <dl>{''.join(rows)}</dl>
    </section>
"""


def render_article_fragment_html(article: str) -> str:
    parsed = parse_article_response(article)
    return f"""
<section class="reading-body">
  {render_paragraph_html(parsed["main_article"])}
</section>
{render_review_notes_html(parsed["review_notes"])}
"""


def render_article_html(deck_name_value: str, cards: list[Any], article: str) -> str:
    parsed = parse_article_response(article)
    article_title = html.escape(parsed["title"])
    article_body = render_paragraph_html(parsed["main_article"])
    review_notes = render_review_notes_html(parsed["review_notes"])
    terms = "\n".join(
        f"<li>{html.escape(card.term)}</li>" for card in cards[:40] if card.term
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(deck_name_value)} Reading Reinforcement</title>
  <style>
    body {{
      margin: 0;
      background: #f6f2ea;
      color: #24211d;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.7;
    }}
    main {{
      max-width: 820px;
      margin: 0 auto;
      padding: 48px 24px 64px;
    }}
    h1 {{
      margin: 0 0 12px;
      font-size: 34px;
      letter-spacing: 0;
      line-height: 1.25;
    }}
    .meta {{
      color: #6c6256;
      margin-bottom: 32px;
    }}
    article {{
      background: #fffdf8;
      border: 1px solid #ded4c6;
      border-radius: 8px;
      padding: 32px;
      box-shadow: 0 18px 50px rgba(43, 34, 24, 0.08);
    }}
    .reading-body {{
      font-size: 18px;
      line-height: 1.9;
    }}
    .reading-body p {{
      margin: 0 0 1.05em;
    }}
    .review-notes {{
      background: #f8f4ed;
      border: 1px solid #ded4c6;
      border-radius: 8px;
      margin-top: 28px;
      padding: 18px;
    }}
    .review-notes h2 {{
      font-size: 18px;
      margin: 0 0 14px;
    }}
    .review-notes dl {{
      display: grid;
      gap: 10px 14px;
      grid-template-columns: minmax(80px, 35%) minmax(0, 1fr);
      margin: 0;
    }}
    .review-notes dt {{
      color: #1f5558;
      font-weight: 800;
    }}
    .review-notes dd {{
      margin: 0;
    }}
    .terms {{
      margin-top: 24px;
      color: #4e453d;
    }}
  </style>
</head>
<body>
  <main>
    <h1>{article_title}</h1>
    <div class="meta">{html.escape(deck_name_value)} · Generated {time.strftime('%Y-%m-%d %H:%M:%S')} from {len(cards)} studied cards.</div>
    <article>
      <section class="reading-body">{article_body}</section>
      {review_notes}
    </article>
    <section class="terms">
      <h2>Source Terms</h2>
      <ul>{terms}</ul>
    </section>
  </main>
</body>
</html>
"""
