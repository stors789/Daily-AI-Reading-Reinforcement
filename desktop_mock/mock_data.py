# Mock data for the desktop mock server.
#
# This module is intentionally self-contained: it does NOT import the addon
# package __init__.py (which requires a running Anki / aqt runtime). It only
# reuses the pure, dependency-free core.config for provider profiles and the
# default config skeleton so the mock state stays close to the real one.
#
# Nothing here touches the real Anki collection, the momo API, or any
# real LLM endpoint.

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

_ADDON_ROOT = (
    Path(__file__).resolve().parent.parent
    / "addon" / "daily_ai_reading_reinforcement"
)


def _load_core_config() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Load core.config (pure module, no aqt) without importing the addon package."""
    mod_path = _ADDON_ROOT / "core" / "config.py"
    spec = importlib.util.spec_from_file_location("dairr_core_config", mod_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dairr_core_config"] = mod
    spec.loader.exec_module(mod)
    return list(mod.PROVIDER_PROFILES), dict(mod.DEFAULT_CONFIG)


_PROVIDER_PROFILES, DEFAULT_CONFIG = _load_core_config()


# Article card destination constants mirror the addon's module-level values.
# They are duplicated here on purpose so the mock never imports the aqt-bound
# __init__.py.
ARTICLE_PARENT_DECK = "Daily AI Reading Reinforcement"
ARTICLE_NOTE_TYPE = "Daily AI Reading Reinforcement Article"


def _provider_profiles_payload() -> list[dict[str, str]]:
    return [
        {
            "id": profile["id"],
            "name": profile["name"],
            "base_url": profile["base_url"],
            "model": profile["model"],
        }
        for profile in _PROVIDER_PROFILES
    ]


def _api_settings_payload(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "providerId": config.get("selected_provider_profile") or "openai",
        "baseUrl": config.get("base_url") or DEFAULT_CONFIG["base_url"],
        "model": config.get("model") or DEFAULT_CONFIG["model"],
        "temperature": config.get("temperature", DEFAULT_CONFIG["temperature"]),
        "maxTokens": config.get("max_tokens", DEFAULT_CONFIG["max_tokens"]),
        "hasApiKey": bool(str(config.get("api_key") or "").strip()),
    }


def _article_card_settings_payload() -> dict[str, Any]:
    return {
        "parentDeck": ARTICLE_PARENT_DECK,
        "noteType": ARTICLE_NOTE_TYPE,
    }


def _prompt_presets() -> list[dict[str, str]]:
    presets = DEFAULT_CONFIG.get("prompt_presets") or []
    return [dict(preset) for preset in presets]


# Two decks, each with three candidate cards. Field names mirror a typical
# vocabulary deck (Front / Back / Example) so the shared UI's field picker has
# something realistic to render.
MOCK_CARDS: list[dict[str, Any]] = [
    {
        "cid": 1001,
        "nid": 2001,
        "deck_id": "deck-japanese",
        "term": "勉強",
        "fields": {
            "Front": "勉強",
            "Back": "study / learning",
            "Example": "毎日日本語を勉強しています。",
        },
        "is_new": True,
        "is_failed": False,
        "review_count": 0,
    },
    {
        "cid": 1002,
        "nid": 2002,
        "deck_id": "deck-japanese",
        "term": "復習",
        "fields": {
            "Front": "復習",
            "Back": "review",
            "Example": "夜は復習の時間にしています。",
        },
        "is_new": False,
        "is_failed": True,
        "review_count": 2,
    },
    {
        "cid": 1003,
        "nid": 2003,
        "deck_id": "deck-japanese",
        "term": "記憶",
        "fields": {
            "Front": "記憶",
            "Back": "memory",
            "Example": "記憶を頼りに答えた。",
        },
        "is_new": False,
        "is_failed": False,
        "review_count": 5,
    },
    {
        "cid": 2001,
        "nid": 3001,
        "deck_id": "deck-english",
        "term": "reinforcement",
        "fields": {
            "Front": "reinforcement",
            "Back": "the act of strengthening",
            "Example": "Spaced repetition relies on reinforcement.",
        },
        "is_new": True,
        "is_failed": False,
        "review_count": 0,
    },
    {
        "cid": 2002,
        "nid": 3002,
        "deck_id": "deck-english",
        "term": "retention",
        "fields": {
            "Front": "retention",
            "Back": "keeping something in memory",
            "Example": "Sleep improves memory retention.",
        },
        "is_new": False,
        "is_failed": True,
        "review_count": 1,
    },
    {
        "cid": 2003,
        "nid": 3003,
        "deck_id": "deck-english",
        "term": "consolidation",
        "fields": {
            "Front": "consolidation",
            "Back": "making something more solid",
            "Example": "Consolidation happens during review.",
        },
        "is_new": False,
        "is_failed": False,
        "review_count": 4,
    },
]


MOCK_DECKS: dict[str, dict[str, Any]] = {
    "deck-japanese": {
        "id": "deck-japanese",
        "name": "Japanese Vocab",
        "new_count": 1,
        "failed_count": 1,
        "total_count": 3,
        "is_group": False,
        "cards": [c for c in MOCK_CARDS if c["deck_id"] == "deck-japanese"],
    },
    "deck-english": {
        "id": "deck-english",
        "name": "English Vocab",
        "new_count": 1,
        "failed_count": 1,
        "total_count": 3,
        "is_group": False,
        "cards": [c for c in MOCK_CARDS if c["deck_id"] == "deck-english"],
    },
}


# A couple of saved articles so the history panel has content to render.
MOCK_ARTICLES: list[dict[str, str]] = [
    {
        "path": "mock/2026-07-04-japanese-vocab-101530.md",
        "filename": "2026-07-04-japanese-vocab-101530.md",
        "deck": "Japanese Vocab",
        "generated_at": "2026-07-04 10:15:30",
        "card_count": "3",
    },
    {
        "path": "mock/2026-07-05-english-vocab-081012.md",
        "filename": "2026-07-05-english-vocab-081012.md",
        "deck": "English Vocab",
        "generated_at": "2026-07-05 08:10:12",
        "card_count": "3",
    },
]


_MOCK_ARTICLE_BODY = """[ARTICLE_TITLE]
Mock Reading Article

[MAIN_ARTICLE]
This is a mock article generated from the selected cards. In the desktop mock
it is produced locally without calling any real LLM endpoint, so you can verify
that the shared web UI renders the article, review notes, and saved paths.

[REVIEW_NOTES]
- mock note 1: the desktop mock does not call the real API
- mock note 2: data comes from desktop_mock/mock_data.py
"""


def build_state_payload(
    last_selected_deck_id: str = "",
    decks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Mimic the addon's _send_state() payload using mock data only."""
    config = dict(DEFAULT_CONFIG)
    config["last_selected_deck_id"] = last_selected_deck_id
    if decks is None:
        decks = [
            {
                "id": deck["id"],
                "name": deck["name"],
                "newCount": deck["new_count"],
                "failedCount": deck["failed_count"],
                "totalCount": deck["total_count"],
                "isGroup": bool(deck["is_group"]),
            }
            for deck in sorted(
                MOCK_DECKS.values(), key=lambda d: d["name"].lower()
            )
        ]
    return {
        "decks": decks,
        "dayStart": 1751606400,
        "dayEnd": 1751692800,
        "promptPresets": _prompt_presets(),
        "selectedPromptPresetId": config.get("selected_prompt_preset_id") or "default",
        "uiLanguage": config.get("ui_language") or "zh",
        "collapsedDeckGroups": list(config.get("collapsed_deck_groups") or []),
        "lastSelectedDeckId": last_selected_deck_id,
        "providerProfiles": _provider_profiles_payload(),
        "apiSettings": _api_settings_payload(config),
        "articleCardSettings": _article_card_settings_payload(),
    }


def build_deck_cards_payload(
    deck_id: str = "",
    cards_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if cards_data is not None:
        cards = cards_data.get("cards") or []
        fields = _deck_field_names(cards)
        return {
            "deckId": cards_data.get("deckId", deck_id),
            "cards": cards,
            "fields": fields,
            "selectedFields": list(fields),
        }
    deck = MOCK_DECKS.get(deck_id)
    if not deck:
        return {
            "deckId": deck_id,
            "cards": [],
            "fields": [],
            "selectedFields": [],
        }
    fields = _deck_field_names(deck["cards"])
    return {
        "deckId": deck_id,
        "cards": [_card_payload(card) for card in deck["cards"]],
        "fields": fields,
        "selectedFields": list(fields),
    }


def _deck_field_names(cards: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    names: list[str] = []
    for card in cards:
        for name, value in card.get("fields", {}).items():
            if name in seen or not value:
                continue
            seen.add(name)
            names.append(name)
    return names


def _card_payload(card: dict[str, Any]) -> dict[str, Any]:
    return {
        "cid": card["cid"],
        "nid": card["nid"],
        "term": card["term"],
        "fields": dict(card["fields"]),
        "is_new": card["is_new"],
        "is_failed": card["is_failed"],
        "review_count": card["review_count"],
    }


def build_article_payload(deck_id: str) -> dict[str, Any]:
    deck = MOCK_DECKS.get(deck_id)
    deck_name = deck["name"] if deck else "Mock Deck"
    return {
        "deckId": deck_id,
        "deckName": deck_name,
        "article": _MOCK_ARTICLE_BODY,
        "markdownPath": f"mock/{deck_id}-article.md",
        "htmlPath": f"mock/{deck_id}-article.html",
        "articleCard": None,
    }


def build_article_list_payload() -> dict[str, Any]:
    return {"articles": list(MOCK_ARTICLES)}


def build_loaded_article_payload(path: str) -> dict[str, Any]:
    for item in MOCK_ARTICLES:
        if item["path"] == path:
            return {
                "path": item["path"],
                "deck": item["deck"],
                "generated_at": item["generated_at"],
                "card_count": item["card_count"],
                "article": _MOCK_ARTICLE_BODY,
                "htmlPath": item["path"].replace(".md", ".html"),
            }
    return {
        "path": path,
        "deck": "",
        "generated_at": "",
        "card_count": "",
        "article": _MOCK_ARTICLE_BODY,
        "htmlPath": "",
    }
