"""AnkiConnect article-card saver for standalone desktop mode.

This module intentionally uses only the Python standard library and never
imports Anki's ``aqt`` runtime.  It mirrors the add-on's article card
conventions through AnkiConnect.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from ankiconnect_provider import ANKICONNECT_VERSION, DEFAULT_ANKICONNECT_URL


ARTICLE_PARENT_DECK = "Daily AI Reading Reinforcement"
ARTICLE_NOTE_TYPE = "Daily AI Reading Reinforcement Article"
ARTICLE_FIELDS = [
    "Date",
    "Source Deck",
    "Title",
    "Article",
    "Source Terms",
    "Markdown Path",
    "HTML Path",
]

ARTICLE_MODEL_CSS = """
.card {
  color: #28231e;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  line-height: 1.65;
  text-align: left;
}
.dairr-date,
.dairr-source {
  color: #776d61;
  font-size: 13px;
}
.dairr-card h1 {
  font-size: 24px;
  margin: 8px 0;
}
.dairr-article {
  font-size: 17px;
  margin-top: 16px;
}
.dairr-terms pre {
  white-space: pre-wrap;
}
"""

ARTICLE_CARD_TEMPLATES = [
    {
        "Name": "Article",
        "Front": """
<section class="dairr-card">
  <div class="dairr-date">{{Date}}</div>
  <h1>{{Title}}</h1>
  <div class="dairr-source">{{Source Deck}}</div>
</section>
""",
        "Back": """
{{FrontSide}}
<hr id="answer">
<article class="dairr-article">{{Article}}</article>
<section class="dairr-terms">
  <h2>Source Terms</h2>
  <pre>{{Source Terms}}</pre>
</section>
""",
    }
]


class AnkiConnectCardSaverError(RuntimeError):
    """Error with a frontend-safe public message."""

    def __init__(self, public_message: str, detail: str | None = None) -> None:
        super().__init__(public_message)
        self.public_message = public_message
        self.detail = detail or public_message


class AnkiConnectArticleCardSaver:
    """Create DAIRR article notes through AnkiConnect."""

    def __init__(
        self,
        base_url: str = DEFAULT_ANKICONNECT_URL,
        timeout: float = 10.0,
        opener: Callable[..., Any] | None = None,
        render_article_fragment_html: Callable[[str], str] | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._opener = opener or urllib.request.urlopen
        self._render_article_fragment_html = render_article_fragment_html or (
            lambda article: str(article or "")
        )

    def save_article_card(
        self,
        source_deck_name: str,
        cards: list[Any],
        article: str,
        markdown_path: Path,
        html_path: Path,
    ) -> dict[str, Any]:
        deck_name_value = article_deck_name(source_deck_name)
        date_value = article_card_date()
        self._ensure_deck(deck_name_value)
        self._ensure_article_model()

        fields = {
            "Date": date_value,
            "Source Deck": source_deck_name,
            "Title": article_card_title(source_deck_name),
            "Article": self._render_article_fragment_html(article),
            "Source Terms": "\n".join(term for term in (_card_term(card) for card in cards) if term),
            "Markdown Path": str(markdown_path),
            "HTML Path": str(html_path),
        }
        note = {
            "deckName": deck_name_value,
            "modelName": ARTICLE_NOTE_TYPE,
            "fields": {field: fields.get(field, "") for field in ARTICLE_FIELDS},
            "options": {"allowDuplicate": True},
            "tags": ["dairr", "reading-reinforcement"],
        }
        note_id = self._invoke_public(
            "addNote",
            {"note": note},
            "Failed to create article card through AnkiConnect.",
        )
        if not isinstance(note_id, int):
            raise AnkiConnectCardSaverError(
                "AnkiConnect did not return a note id for the article card."
            )
        self._suspend_note_cards(note_id)
        return {
            "noteId": int(note_id),
            "deckName": deck_name_value,
            "noteType": ARTICLE_NOTE_TYPE,
            "date": date_value,
        }

    def _ensure_deck(self, deck_name_value: str) -> None:
        self._invoke_public(
            "createDeck",
            {"deck": deck_name_value},
            "Failed to create the article card deck through AnkiConnect.",
        )

    def _ensure_article_model(self) -> None:
        model_names = self._invoke_public(
            "modelNames",
            {},
            "Failed to inspect Anki note types through AnkiConnect.",
        )
        if isinstance(model_names, list) and ARTICLE_NOTE_TYPE in model_names:
            return

        self._invoke_public(
            "createModel",
            {
                "modelName": ARTICLE_NOTE_TYPE,
                "inOrderFields": ARTICLE_FIELDS,
                "css": ARTICLE_MODEL_CSS,
                "cardTemplates": ARTICLE_CARD_TEMPLATES,
            },
            "Article note type is missing and AnkiConnect could not create it.",
        )

    def _suspend_note_cards(self, note_id: int) -> None:
        try:
            card_ids = self._invoke("findCards", {"query": f"nid:{note_id}"})
            if isinstance(card_ids, list) and card_ids:
                self._invoke("suspend", {"cards": card_ids})
        except AnkiConnectCardSaverError:
            pass

    def _invoke_public(
        self,
        action: str,
        params: dict[str, Any],
        public_message: str,
    ) -> Any:
        try:
            return self._invoke(action, params)
        except AnkiConnectCardSaverError as exc:
            raise AnkiConnectCardSaverError(public_message, exc.detail) from exc

    def _invoke(self, action: str, params: dict[str, Any] | None = None) -> Any:
        payload = {
            "action": action,
            "version": ANKICONNECT_VERSION,
            "params": params or {},
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self._base_url,
            data=data,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "dairr-ankiconnect-card-saver/0.1",
            },
            method="POST",
        )
        try:
            with self._opener(req, timeout=self._timeout) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            raise AnkiConnectCardSaverError(
                "AnkiConnect returned an HTTP error.",
                f"HTTP {exc.code}",
            ) from exc
        except urllib.error.URLError as exc:
            raise AnkiConnectCardSaverError(
                "Could not reach AnkiConnect.",
                type(exc.reason).__name__ if getattr(exc, "reason", None) else "URL error",
            ) from exc

        try:
            body = json.loads(raw.decode("utf-8", errors="replace") if raw else "{}")
        except json.JSONDecodeError as exc:
            raise AnkiConnectCardSaverError("Invalid JSON from AnkiConnect.") from exc

        if not isinstance(body, dict):
            raise AnkiConnectCardSaverError("Invalid AnkiConnect response.")
        error = body.get("error")
        if error:
            raise AnkiConnectCardSaverError("AnkiConnect returned an error.", str(error))
        if "result" not in body:
            raise AnkiConnectCardSaverError("AnkiConnect response missing result.")
        return body.get("result")


def article_deck_name(source_deck_name: str) -> str:
    source = _clean_text(source_deck_name).replace("::", "::")
    return f"{ARTICLE_PARENT_DECK}::{source or 'Generated Articles'}"


def article_card_title(source_deck_name: str) -> str:
    return f"{time.strftime('%Y-%m-%d')} Reading - {source_deck_name}"


def article_card_date() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")


def _card_term(card: Any) -> str:
    if isinstance(card, dict):
        return _clean_text(card.get("term"))
    return _clean_text(getattr(card, "term", ""))


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split())
