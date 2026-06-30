from __future__ import annotations

import html
import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aqt import mw
from aqt.qt import QAction, QDialog, QUrl, QVBoxLayout
from aqt.utils import showWarning
from aqt.webview import AnkiWebView


ADDON_PACKAGE = __name__
ADDON_DIR = Path(__file__).resolve().parent
WEB_DIR = ADDON_DIR / "web"
ARTICLES_DIR = ADDON_DIR / "user_files" / "articles"


DEFAULT_CONFIG = {
    "api_key": "",
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4.1-mini",
    "temperature": 0.7,
    "max_tokens": 1400,
    "language": "English",
    "prompt_template": "",
}


@dataclass
class CandidateCard:
    cid: int
    nid: int
    deck_id: int
    term: str
    fields: dict[str, str]
    is_new: bool
    is_failed: bool
    review_count: int

    def to_payload(self) -> dict[str, Any]:
        return {
            "cid": self.cid,
            "nid": self.nid,
            "term": self.term,
            "fields": self.fields,
            "is_new": self.is_new,
            "is_failed": self.is_failed,
            "review_count": self.review_count,
        }


class ReadingReinforcementDialog(QDialog):
    def __init__(self) -> None:
        super().__init__(mw)
        self.setWindowTitle("AI Reading Reinforcement")
        self.resize(1180, 760)

        self.web = AnkiWebView()
        self.web.set_bridge_command(self._on_bridge_command, self)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.web)
        self.setLayout(layout)

        self.deck_payloads: dict[str, dict[str, Any]] = {}
        self._load_page()

    def _load_page(self) -> None:
        body = (WEB_DIR / "index.html").read_text(encoding="utf-8")
        css = [str(WEB_DIR / "style.css")]
        js = [str(WEB_DIR / "app.js")]
        base_url = QUrl.fromLocalFile(str(WEB_DIR) + "/")
        self.web.stdHtml(body, css=css, js=js, context=self, baseUrl=base_url)

    def _on_bridge_command(self, message: str) -> None:
        try:
            command = json.loads(message)
            action = command.get("action")
            payload = command.get("payload") or {}
            if action == "load":
                self._send_state()
            elif action == "selectDeck":
                self._send_deck_cards(str(payload.get("deckId", "")))
            elif action == "generate":
                self._generate_article(str(payload.get("deckId", "")))
            else:
                self._emit("error", {"message": f"Unknown command: {action}"})
        except Exception as exc:
            self._emit("error", {"message": str(exc)})

    def _send_state(self) -> None:
        if mw.col is None:
            self._emit("error", {"message": "No Anki collection is open."})
            return

        self.deck_payloads = collect_today_decks()
        decks = [
            {
                "id": deck_id,
                "name": payload["name"],
                "newCount": payload["new_count"],
                "failedCount": payload["failed_count"],
                "totalCount": payload["total_count"],
            }
            for deck_id, payload in sorted(
                self.deck_payloads.items(), key=lambda item: item[1]["name"].lower()
            )
        ]
        cutoff = get_day_cutoff(mw.col)
        self._emit(
            "state",
            {
                "decks": decks,
                "dayStart": cutoff - 86400,
                "dayEnd": cutoff,
            },
        )

    def _send_deck_cards(self, deck_id: str) -> None:
        payload = self.deck_payloads.get(deck_id)
        if not payload:
            self._emit("deckCards", {"deckId": deck_id, "cards": []})
            return
        self._emit(
            "deckCards",
            {
                "deckId": deck_id,
                "cards": [card.to_payload() for card in payload["cards"]],
            },
        )

    def _generate_article(self, deck_id: str) -> None:
        payload = self.deck_payloads.get(deck_id)
        if not payload:
            self._emit("error", {"message": "Select a deck with study activity first."})
            return

        cards = payload["cards"]
        if not cards:
            self._emit("error", {"message": "This deck has no candidate cards today."})
            return

        config = load_config()
        api_key = str(config.get("api_key", "")).strip()
        if not api_key:
            self._emit(
                "error",
                {
                    "message": "Missing API key. Set api_key in the add-on configuration, then reopen this page."
                },
            )
            return

        self._emit("generating", {"message": "Generating article..."})
        try:
            article = generate_article(config, payload["name"], cards)
            if not article.strip():
                raise RuntimeError("The AI response was empty.")
            saved = save_article(payload["name"], cards, article)
            self._emit(
                "article",
                {
                    "deckId": deck_id,
                    "deckName": payload["name"],
                    "article": article,
                    "markdownPath": str(saved["markdown"]),
                    "htmlPath": str(saved["html"]),
                },
            )
        except Exception as exc:
            self._emit("error", {"message": str(exc)})

    def _emit(self, event: str, payload: dict[str, Any]) -> None:
        data = json.dumps({"event": event, "payload": payload}, ensure_ascii=False)
        self.web.eval(f"window.DAIRR.receive({data});")


def get_day_cutoff(col: Any) -> int:
    sched = col.sched
    for name in ("dayCutoff", "day_cutoff"):
        value = getattr(sched, name, None)
        if value is None:
            continue
        return int(value() if callable(value) else value)

    backend = getattr(col, "_backend", None)
    if backend is not None:
        getter = getattr(backend, "sched_timing_today", None)
        if getter is not None:
            timing = getter()
            cutoff = getattr(timing, "next_day_at", None)
            if cutoff is not None:
                return int(cutoff)

    return int(time.time())


def collect_today_decks() -> dict[str, dict[str, Any]]:
    col = mw.col
    cutoff = get_day_cutoff(col)
    start_ms = (cutoff - 86400) * 1000
    end_ms = cutoff * 1000

    rows = col.db.all(
        """
        select
            case when c.odid != 0 then c.odid else c.did end as deck_id,
            r.cid,
            max(case when r.ease = 1 then 1 else 0 end) as failed_today,
            max(
                case
                    when r.type = 0
                    and not exists (
                        select 1 from revlog old
                        where old.cid = r.cid and old.id < ?
                    )
                    then 1
                    else 0
                end
            ) as new_today,
            count(*) as review_count
        from revlog r
        join cards c on c.id = r.cid
        where r.id >= ? and r.id < ?
        group by deck_id, r.cid
        order by deck_id, failed_today desc, new_today desc, r.cid
        """,
        start_ms,
        start_ms,
        end_ms,
    )

    decks: dict[str, dict[str, Any]] = {}
    for deck_id, cid, failed_today, new_today, review_count in rows:
        card = col.get_card(cid)
        note = card.note()
        fields = note_fields(note)
        term = first_meaningful_field(fields) or f"Card {cid}"
        candidate = CandidateCard(
            cid=int(cid),
            nid=int(note.id),
            deck_id=int(deck_id),
            term=clean_text(term),
            fields={key: clean_text(value) for key, value in fields.items()},
            is_new=bool(new_today),
            is_failed=bool(failed_today),
            review_count=int(review_count),
        )

        deck_key = str(deck_id)
        if deck_key not in decks:
            decks[deck_key] = {
                "name": deck_name(deck_id),
                "new_count": 0,
                "failed_count": 0,
                "total_count": 0,
                "cards": [],
            }
        decks[deck_key]["cards"].append(candidate)
        decks[deck_key]["total_count"] += 1
        if candidate.is_new:
            decks[deck_key]["new_count"] += 1
        if candidate.is_failed:
            decks[deck_key]["failed_count"] += 1

    return decks


def deck_name(deck_id: int) -> str:
    try:
        return mw.col.decks.name(deck_id)
    except Exception:
        return f"Deck {deck_id}"


def note_fields(note: Any) -> dict[str, str]:
    try:
        return {name: value for name, value in note.items()}
    except Exception:
        model = mw.col.models.get(note.mid)
        names = [field["name"] for field in model.get("flds", [])]
        return dict(zip(names, note.fields))


def first_meaningful_field(fields: dict[str, str]) -> str:
    for value in fields.values():
        cleaned = clean_text(value)
        if cleaned:
            return cleaned
    return ""


def clean_text(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def load_config() -> dict[str, Any]:
    config = DEFAULT_CONFIG.copy()
    loaded = mw.addonManager.getConfig(ADDON_PACKAGE) or {}
    config.update(loaded)
    return config


def build_prompt(config: dict[str, Any], deck_name_value: str, cards: list[CandidateCard]) -> str:
    language = str(config.get("language") or "English")
    card_lines = []
    for index, card in enumerate(cards[:80], start=1):
        labels = []
        if card.is_new:
            labels.append("new")
        if card.is_failed:
            labels.append("failed")
        label = ", ".join(labels) if labels else "studied"
        field_context = "; ".join(
            f"{name}: {value}"
            for name, value in list(card.fields.items())[:4]
            if value and value != card.term
        )
        if field_context:
            card_lines.append(f"{index}. {card.term} ({label}) - {field_context}")
        else:
            card_lines.append(f"{index}. {card.term} ({label})")

    default_prompt = (
        "You are helping an Anki learner reinforce vocabulary through reading.\n"
        "Write one coherent, enjoyable short article in {language} using the studied cards below.\n"
        "Prioritize failed cards naturally, then new cards. Keep the article readable and not list-like.\n"
        "After the article, include a short vocabulary review section with the most important terms.\n\n"
        "Deck: {deck_name}\n"
        "Cards:\n{cards}\n"
    )
    template = str(config.get("prompt_template") or default_prompt)
    return template.format(
        language=language,
        deck_name=deck_name_value,
        cards="\n".join(card_lines),
    )


def generate_article(config: dict[str, Any], deck_name_value: str, cards: list[CandidateCard]) -> str:
    base_url = str(config.get("base_url") or DEFAULT_CONFIG["base_url"]).rstrip("/")
    url = f"{base_url}/chat/completions"
    prompt = build_prompt(config, deck_name_value, cards)
    request_payload = {
        "model": config.get("model") or DEFAULT_CONFIG["model"],
        "messages": [
            {
                "role": "system",
                "content": "You write concise, learner-friendly reading passages from vocabulary lists.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": float(config.get("temperature") or DEFAULT_CONFIG["temperature"]),
        "max_tokens": int(config.get("max_tokens") or DEFAULT_CONFIG["max_tokens"]),
    }
    data = json.dumps(request_payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"AI request failed with HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"AI request failed: {exc.reason}") from exc

    try:
        return response_payload["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("AI response did not contain a chat completion message.") from exc


def save_article(
    deck_name_value: str, cards: list[CandidateCard], article: str
) -> dict[str, Path]:
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d-%H%M%S")
    slug = slugify(deck_name_value)
    basename = f"{stamp}-{slug}"
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


def render_article_html(deck_name_value: str, cards: list[CandidateCard], article: str) -> str:
    paragraphs = [
        f"<p>{html.escape(block).replace(chr(10), '<br>')}</p>"
        for block in article.split("\n\n")
        if block.strip()
    ]
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
    .terms {{
      margin-top: 24px;
      color: #4e453d;
    }}
  </style>
</head>
<body>
  <main>
    <h1>{html.escape(deck_name_value)}</h1>
    <div class="meta">Generated {time.strftime('%Y-%m-%d %H:%M:%S')} from {len(cards)} studied cards.</div>
    <article>
      {''.join(paragraphs)}
    </article>
    <section class="terms">
      <h2>Source Terms</h2>
      <ul>{terms}</ul>
    </section>
  </main>
</body>
</html>
"""


def slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-")
    return slug[:80] or "deck"


def open_dialog() -> None:
    dialog = ReadingReinforcementDialog()
    dialog.exec()


def setup_menu() -> None:
    action = QAction("AI Reading Reinforcement", mw)
    action.triggered.connect(open_dialog)
    mw.form.menuTools.addAction(action)


try:
    setup_menu()
except Exception as exc:
    showWarning(f"Could not load AI Reading Reinforcement: {exc}")
