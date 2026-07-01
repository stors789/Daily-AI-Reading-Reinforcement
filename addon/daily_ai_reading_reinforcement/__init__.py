from __future__ import annotations

import html
import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
from uuid import uuid4

from aqt import mw
try:
    from aqt import gui_hooks
except ImportError:
    gui_hooks = None
from aqt import deckbrowser
from aqt.qt import QAction, QDialog, QTimer, QVBoxLayout
from aqt.utils import showWarning
from aqt.webview import AnkiWebView


ADDON_PACKAGE = __name__
ADDON_DIR = Path(__file__).resolve().parent
WEB_DIR = ADDON_DIR / "web"
ARTICLES_DIR = ADDON_DIR / "user_files" / "articles"

PROVIDER_PROFILES = [
    {
        "id": "openai",
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4.1-mini",
    },
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
    },
    {
        "id": "qwen",
        "name": "Qwen DashScope",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
    },
    {
        "id": "openrouter",
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "model": "openai/gpt-4.1-mini",
    },
    {
        "id": "custom",
        "name": "Custom compatible API",
        "base_url": "",
        "model": "",
    },
]


DEFAULT_CONFIG = {
    "api_key": "",
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4.1-mini",
    "selected_provider_profile": "openai",
    "temperature": 0.7,
    "max_tokens": 1400,
    "language": "English",
    "prompt_template": "",
    "deck_field_config": {},
    "collapsed_deck_groups": [],
    "ui_language": "zh",
    "prompt_presets": [
        {
            "id": "default",
            "name": "Default",
            "language": "",
            "difficulty": "",
            "max_words": "",
            "instructions": "",
            "prompt_template": "",
        }
    ],
    "selected_prompt_preset_id": "default",
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
        css = (WEB_DIR / "style.css").read_text(encoding="utf-8")
        js = (WEB_DIR / "app.js").read_text(encoding="utf-8")
        guard = """
<script>
window.addEventListener("error", function (event) {
  document.body.innerHTML = '<main class="app-shell"><section class="panel" style="padding:24px;"><h1>AI Reading Reinforcement</h1><p>Page script error: ' + String(event.message || "unknown") + '</p></section></main>';
});
</script>
"""
        page = f"<style>{css}</style>\n{body}\n{guard}\n<script>{js}</script>"
        self.web.stdHtml(page, context=self)

    def _on_bridge_command(self, message: str) -> None:
        try:
            command = json.loads(message)
            action = command.get("action")
            payload = command.get("payload") or {}
            if action == "load":
                self._send_state()
            elif action == "selectDeck":
                self._send_deck_cards(str(payload.get("deckId", "")))
            elif action == "saveFieldConfig":
                self._save_field_config(
                    str(payload.get("deckId", "")),
                    list(payload.get("fields") or []),
                )
            elif action == "savePromptPreset":
                self._save_prompt_preset(dict(payload.get("preset") or {}))
            elif action == "deletePromptPreset":
                self._delete_prompt_preset(str(payload.get("presetId", "")))
            elif action == "selectPromptPreset":
                self._select_prompt_preset(str(payload.get("presetId", "")))
            elif action == "saveUiLanguage":
                self._save_ui_language(str(payload.get("uiLanguage", "")))
            elif action == "saveApiSettings":
                self._save_api_settings(dict(payload.get("settings") or {}))
            elif action == "saveCollapsedDeckGroups":
                self._save_collapsed_deck_groups(
                    list(payload.get("collapsedDeckGroups") or [])
                )
            elif action == "generate":
                self._generate_article(
                    str(payload.get("deckId", "")),
                    str(payload.get("presetId", "")),
                )
            else:
                self._emit("error", {"message": f"Unknown command: {action}"})
        except Exception as exc:
            self._emit("error", {"message": str(exc)})

    def _send_state(self) -> None:
        if mw.col is None:
            self._emit("error", {"message": "No Anki collection is open."})
            return

        self.deck_payloads = collect_today_decks()
        config = load_config()
        decks = [
            {
                "id": deck_id,
                "name": payload["name"],
                "newCount": payload["new_count"],
                "failedCount": payload["failed_count"],
                "totalCount": payload["total_count"],
                "isGroup": bool(payload.get("is_group")),
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
                "promptPresets": normalize_prompt_presets(config),
                "selectedPromptPresetId": config.get("selected_prompt_preset_id")
                or "default",
                "uiLanguage": config.get("ui_language") or "zh",
                "collapsedDeckGroups": list(config.get("collapsed_deck_groups") or []),
                "providerProfiles": PROVIDER_PROFILES,
                "apiSettings": api_settings_payload(config),
            },
        )

    def _send_deck_cards(self, deck_id: str) -> None:
        payload = self.deck_payloads.get(deck_id)
        if not payload:
            self._emit(
                "deckCards",
                {"deckId": deck_id, "cards": [], "fields": [], "selectedFields": []},
            )
            return
        fields = deck_field_names(payload["cards"])
        selected_fields = selected_fields_for_deck(deck_id, fields)
        self._emit(
            "deckCards",
            {
                "deckId": deck_id,
                "cards": [card.to_payload() for card in payload["cards"]],
                "fields": fields,
                "selectedFields": selected_fields,
            },
        )

    def _save_field_config(self, deck_id: str, fields: list[str]) -> None:
        payload = self.deck_payloads.get(deck_id)
        if not payload:
            self._emit("error", {"message": "Select a deck before saving fields."})
            return

        available_fields = deck_field_names(payload["cards"])
        selected_fields = [field for field in fields if field in available_fields]
        if not selected_fields:
            self._emit("error", {"message": "Choose at least one field for AI input."})
            return

        config = load_config()
        deck_field_config = dict(config.get("deck_field_config") or {})
        deck_field_config[deck_id] = selected_fields
        config["deck_field_config"] = deck_field_config
        mw.addonManager.writeConfig(ADDON_PACKAGE, config)
        self._emit(
            "fieldConfigSaved",
            {"deckId": deck_id, "selectedFields": selected_fields},
        )

    def _save_prompt_preset(self, preset: dict[str, Any]) -> None:
        config = load_config()
        presets = normalize_prompt_presets(config)
        preset_id = str(preset.get("id") or f"preset-{uuid4().hex[:10]}")
        clean_preset = {
            "id": preset_id,
            "name": clean_text(preset.get("name")) or "Untitled",
            "language": clean_text(preset.get("language")),
            "difficulty": clean_text(preset.get("difficulty")),
            "max_words": clean_max_words(preset.get("max_words")),
            "instructions": clean_text(preset.get("instructions")),
            "prompt_template": str(preset.get("prompt_template") or ""),
        }

        replaced = False
        for index, existing in enumerate(presets):
            if existing["id"] == preset_id:
                presets[index] = clean_preset
                replaced = True
                break
        if not replaced:
            presets.append(clean_preset)

        config["prompt_presets"] = presets
        config["selected_prompt_preset_id"] = preset_id
        mw.addonManager.writeConfig(ADDON_PACKAGE, config)
        self._emit(
            "promptPresets",
            {
                "promptPresets": presets,
                "selectedPromptPresetId": preset_id,
                "message": "Prompt preset saved.",
            },
        )

    def _delete_prompt_preset(self, preset_id: str) -> None:
        if preset_id == "default":
            self._emit("error", {"message": "The default preset cannot be deleted."})
            return
        config = load_config()
        presets = [
            preset
            for preset in normalize_prompt_presets(config)
            if preset.get("id") != preset_id
        ]
        config["prompt_presets"] = presets
        config["selected_prompt_preset_id"] = "default"
        mw.addonManager.writeConfig(ADDON_PACKAGE, config)
        self._emit(
            "promptPresets",
            {
                "promptPresets": presets,
                "selectedPromptPresetId": "default",
                "message": "Prompt preset deleted.",
            },
        )

    def _select_prompt_preset(self, preset_id: str) -> None:
        config = load_config()
        presets = normalize_prompt_presets(config)
        valid_ids = {preset["id"] for preset in presets}
        if preset_id not in valid_ids:
            preset_id = "default"
        config["selected_prompt_preset_id"] = preset_id
        mw.addonManager.writeConfig(ADDON_PACKAGE, config)

    def _save_ui_language(self, ui_language: str) -> None:
        if ui_language not in {"zh", "en", "ja"}:
            ui_language = "zh"
        config = load_config()
        config["ui_language"] = ui_language
        mw.addonManager.writeConfig(ADDON_PACKAGE, config)

    def _save_api_settings(self, settings: dict[str, Any]) -> None:
        provider_id = clean_provider_id(settings.get("providerId"))
        base_url = clean_base_url(settings.get("baseUrl"))
        model = clean_text(settings.get("model"))
        temperature = clean_temperature(settings.get("temperature"))
        max_tokens = clean_max_tokens(settings.get("maxTokens"))

        if not base_url:
            self._emit("error", {"message": "Enter an API base URL."})
            return
        if not model:
            self._emit("error", {"message": "Enter a model name."})
            return

        config = load_config()
        api_key = str(settings.get("apiKey") or "").strip()
        clear_api_key = bool(settings.get("clearApiKey"))
        if api_key:
            config["api_key"] = api_key
        elif clear_api_key:
            config["api_key"] = ""

        config["selected_provider_profile"] = provider_id
        config["base_url"] = base_url
        config["model"] = model
        config["temperature"] = temperature
        config["max_tokens"] = max_tokens
        mw.addonManager.writeConfig(ADDON_PACKAGE, config)
        self._emit(
            "apiSettingsSaved",
            {
                "apiSettings": api_settings_payload(config),
                "message": "API settings saved.",
            },
        )

    def _save_collapsed_deck_groups(self, collapsed_groups: list[str]) -> None:
        config = load_config()
        config["collapsed_deck_groups"] = [
            clean_text(group) for group in collapsed_groups if clean_text(group)
        ]
        mw.addonManager.writeConfig(ADDON_PACKAGE, config)

    def _generate_article(self, deck_id: str, preset_id: str) -> None:
        payload = self.deck_payloads.get(deck_id)
        if not payload:
            self._emit("error", {"message": "Select a deck with study activity first."})
            return

        cards = payload["cards"]
        if not cards:
            self._emit("error", {"message": "This deck has no candidate cards today."})
            return

        config = load_config()
        preset = prompt_preset_by_id(config, preset_id)
        available_fields = deck_field_names(cards)
        selected_fields = selected_fields_for_deck(deck_id, available_fields, config)
        if not selected_fields:
            self._emit("error", {"message": "Choose at least one field for AI input."})
            return

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

        def task() -> dict[str, Any]:
            article = generate_article(
                config,
                payload["name"],
                cards,
                selected_fields,
                preset,
            )
            if not article.strip():
                raise RuntimeError("The AI response was empty.")
            saved = save_article(payload["name"], cards, article)
            return {
                "deckId": deck_id,
                "deckName": payload["name"],
                "article": article,
                "markdownPath": str(saved["markdown"]),
                "htmlPath": str(saved["html"]),
            }

        def on_done(future: Any) -> None:
            try:
                result = future.result()
            except Exception as exc:
                self._emit("error", {"message": str(exc)})
                return
            self._emit(
                "article",
                result,
            )

        mw.taskman.run_in_background(task, on_done)

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
                "_cards_by_note": {},
            }

        cards_by_note = decks[deck_key]["_cards_by_note"]
        existing = cards_by_note.get(candidate.nid)
        if existing is None:
            cards_by_note[candidate.nid] = candidate
            decks[deck_key]["cards"].append(candidate)
        else:
            existing.is_new = existing.is_new or candidate.is_new
            existing.is_failed = existing.is_failed or candidate.is_failed
            existing.review_count += candidate.review_count

    for deck in decks.values():
        deck["cards"] = [
            card for card in deck["cards"] if card.is_new or card.is_failed
        ]
        refresh_deck_counts(deck)

    decks = {deck_id: deck for deck_id, deck in decks.items() if deck["cards"]}
    decks.update(aggregate_parent_decks(decks))
    for deck in decks.values():
        deck.pop("_cards_by_note", None)
    return decks


def refresh_deck_counts(deck: dict[str, Any]) -> None:
    deck["total_count"] = len(deck["cards"])
    deck["new_count"] = sum(1 for card in deck["cards"] if card.is_new)
    deck["failed_count"] = sum(1 for card in deck["cards"] if card.is_failed)


def aggregate_parent_decks(decks: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    aggregates: dict[str, dict[str, Any]] = {}
    for deck in decks.values():
        parts = str(deck["name"]).split("::")
        for index in range(1, len(parts)):
            parent_name = "::".join(parts[:index])
            aggregate_id = f"group:{parent_name}"
            if aggregate_id not in aggregates:
                aggregates[aggregate_id] = {
                    "name": parent_name,
                    "new_count": 0,
                    "failed_count": 0,
                    "total_count": 0,
                    "cards": [],
                    "_cards_by_note": {},
                    "is_group": True,
                }
            cards_by_note = aggregates[aggregate_id]["_cards_by_note"]
            for card in deck["cards"]:
                existing = cards_by_note.get(card.nid)
                if existing is None:
                    copied_card = replace(card)
                    cards_by_note[card.nid] = copied_card
                    aggregates[aggregate_id]["cards"].append(copied_card)
                else:
                    existing.is_new = existing.is_new or card.is_new
                    existing.is_failed = existing.is_failed or card.is_failed
                    existing.review_count += card.review_count

    for aggregate in aggregates.values():
        refresh_deck_counts(aggregate)
    return aggregates


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


def deck_field_names(cards: list[CandidateCard]) -> list[str]:
    seen = set()
    names = []
    for card in cards:
        for name, value in card.fields.items():
            if name in seen or not value:
                continue
            seen.add(name)
            names.append(name)
    return names


def selected_fields_for_deck(
    deck_id: str, available_fields: list[str], config: dict[str, Any] | None = None
) -> list[str]:
    if config is None:
        config = load_config()
    deck_field_config = config.get("deck_field_config") or {}
    saved_fields = deck_field_config.get(deck_id) or []
    valid_saved_fields = [field for field in saved_fields if field in available_fields]
    return valid_saved_fields or available_fields


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


def clean_max_words(value: Any) -> str:
    text = clean_text(value)
    if not text:
        return ""
    match = re.search(r"\d+", text)
    if not match:
        return ""
    number = max(50, min(5000, int(match.group(0))))
    return str(number)


def clean_provider_id(value: Any) -> str:
    provider_id = clean_text(value)
    valid_ids = {profile["id"] for profile in PROVIDER_PROFILES}
    return provider_id if provider_id in valid_ids else "custom"


def clean_base_url(value: Any) -> str:
    return str(value or "").strip().rstrip("/")


def clean_temperature(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = float(DEFAULT_CONFIG["temperature"])
    return max(0.0, min(2.0, number))


def clean_max_tokens(value: Any) -> int:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        number = int(DEFAULT_CONFIG["max_tokens"])
    return max(128, min(32000, number))


def api_settings_payload(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "providerId": clean_provider_id(config.get("selected_provider_profile")),
        "baseUrl": clean_base_url(config.get("base_url") or DEFAULT_CONFIG["base_url"]),
        "model": clean_text(config.get("model") or DEFAULT_CONFIG["model"]),
        "temperature": clean_temperature(config.get("temperature")),
        "maxTokens": clean_max_tokens(config.get("max_tokens")),
        "hasApiKey": bool(str(config.get("api_key") or "").strip()),
    }


def load_config() -> dict[str, Any]:
    config = DEFAULT_CONFIG.copy()
    loaded = mw.addonManager.getConfig(ADDON_PACKAGE) or {}
    config.update(loaded)
    return config


def normalize_prompt_presets(config: dict[str, Any]) -> list[dict[str, str]]:
    raw_presets = config.get("prompt_presets") or []
    presets = []
    for raw in raw_presets:
        if not isinstance(raw, dict):
            continue
        preset_id = str(raw.get("id") or "").strip()
        if not preset_id:
            continue
        presets.append(
            {
                "id": preset_id,
                "name": clean_text(raw.get("name")) or preset_id,
                "language": clean_text(raw.get("language")),
                "difficulty": clean_text(raw.get("difficulty")),
                "max_words": clean_max_words(raw.get("max_words")),
                "instructions": clean_text(raw.get("instructions")),
                "prompt_template": str(raw.get("prompt_template") or ""),
            }
        )

    if not any(preset["id"] == "default" for preset in presets):
        presets.insert(
            0,
            {
                "id": "default",
                "name": "Default",
                "language": "",
                "difficulty": "",
                "max_words": "",
                "instructions": "",
                "prompt_template": "",
            },
        )
    return presets


def prompt_preset_by_id(config: dict[str, Any], preset_id: str) -> dict[str, str]:
    presets = normalize_prompt_presets(config)
    for preset in presets:
        if preset["id"] == preset_id:
            return preset
    selected_id = str(config.get("selected_prompt_preset_id") or "")
    for preset in presets:
        if preset["id"] == selected_id:
            return preset
    return presets[0]


def build_prompt(
    config: dict[str, Any],
    deck_name_value: str,
    cards: list[CandidateCard],
    selected_fields: list[str],
    preset: dict[str, str],
) -> str:
    language = str(
        preset.get("language")
        or writing_language_for_ui(str(config.get("ui_language") or "zh"))
        or config.get("language")
        or "English"
    )
    difficulty = str(preset.get("difficulty") or "appropriate for the learner")
    max_words = str(preset.get("max_words") or "")
    length_instruction = (
        f"Do not exceed about {max_words} words or characters."
        if max_words
        else "No fixed length limit."
    )
    instructions = str(preset.get("instructions") or "No extra instructions.")
    card_lines = []
    for index, card in enumerate(cards[:80], start=1):
        labels = []
        if card.is_new:
            labels.append("new")
        if card.is_failed:
            labels.append("failed")
        label = ", ".join(labels) if labels else "studied"
        field_context = "; ".join(
            f"{name}: {card.fields.get(name)}"
            for name in selected_fields
            if card.fields.get(name)
        )
        if field_context:
            card_lines.append(f"{index}. ({label}) {field_context}")
        else:
            card_lines.append(f"{index}. ({label})")

    default_prompt = (
        "You are helping an Anki learner reinforce vocabulary through reading.\n"
        "Write one coherent, enjoyable short article in {language} using the studied cards below.\n"
        "Target difficulty: {difficulty}.\n"
        "Length: {length_instruction}\n"
        "Extra instructions: {instructions}\n"
        "Prioritize failed cards naturally, then new cards. Keep the article readable and not list-like.\n"
        "After the article, include a short vocabulary review section with the most important terms.\n\n"
        "Deck: {deck_name}\n"
        "Cards:\n{cards}\n"
    )
    template = str(
        preset.get("prompt_template") or config.get("prompt_template") or default_prompt
    )
    return template.format(
        language=language,
        difficulty=difficulty,
        max_words=max_words,
        length_instruction=length_instruction,
        instructions=instructions,
        deck_name=deck_name_value,
        cards="\n".join(card_lines),
    )


def writing_language_for_ui(ui_language: str) -> str:
    return {
        "zh": "中文",
        "en": "English",
        "ja": "日本語",
    }.get(ui_language, "中文")


def max_tokens_for_request(config: dict[str, Any], preset: dict[str, str]) -> int:
    configured = int(config.get("max_tokens") or DEFAULT_CONFIG["max_tokens"])
    max_words = clean_max_words(preset.get("max_words"))
    if not max_words:
        return configured
    suggested = max(300, int(max_words) * 3)
    return min(configured, suggested)


def generate_article(
    config: dict[str, Any],
    deck_name_value: str,
    cards: list[CandidateCard],
    selected_fields: list[str],
    preset: dict[str, str],
) -> str:
    base_url = str(config.get("base_url") or DEFAULT_CONFIG["base_url"]).rstrip("/")
    url = f"{base_url}/chat/completions"
    prompt = build_prompt(config, deck_name_value, cards, selected_fields, preset)
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
        "max_tokens": max_tokens_for_request(config, preset),
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
    exec_method = getattr(dialog, "exec", None) or getattr(dialog, "exec_", None)
    exec_method()


def open_dialog_deferred() -> None:
    QTimer.singleShot(0, open_dialog)


def setup_menu() -> None:
    action = QAction("AI Reading Reinforcement", mw)
    action.triggered.connect(open_dialog)
    mw.form.menuTools.addAction(action)


def setup_home_entry() -> None:
    original_link_handler = deckbrowser.DeckBrowser._linkHandler
    if getattr(original_link_handler, "_dairr_patched", False):
        return

    def patched_link_handler(self: Any, url: str) -> Any:
        if url == "dairr-open":
            open_dialog_deferred()
            return False
        return original_link_handler(self, url)

    patched_link_handler._dairr_patched = True
    deckbrowser.DeckBrowser._linkHandler = patched_link_handler


def add_deck_browser_button(deck_browser: Any, content: Any) -> None:
    button_html = """
<div style="margin: 22px 0 8px; text-align: center;">
  <button onclick='pycmd("dairr-open")' style="
    background: #2f6f73;
    border: 0;
    border-radius: 8px;
    box-shadow: 0 8px 22px rgba(47, 111, 115, 0.18);
    color: #fff;
    cursor: pointer;
    font-weight: 700;
    padding: 9px 16px;
  ">AI Reading Reinforcement</button>
</div>
"""
    try:
        content.stats += button_html
    except Exception:
        pass


def register_web_exports() -> None:
    try:
        mw.addonManager.setWebExports(__name__, r"web/.*\.(css|js)")
    except Exception:
        pass


def handle_webview_message(handled: Any, message: str, context: Any) -> Any:
    if message == "dairr-open":
        open_dialog_deferred()
        return (True, None)
    return handled

def setup_global_webview_handler() -> None:
    if gui_hooks is None:
        return
    try:
        gui_hooks.deck_browser_will_render_content.append(add_deck_browser_button)
    except Exception:
        pass
    try:
        gui_hooks.webview_did_receive_js_message.append(handle_webview_message)
    except Exception:
        pass


try:
    register_web_exports()
    setup_menu()
    setup_home_entry()
    setup_global_webview_handler()
except Exception as exc:
    showWarning(f"Could not load AI Reading Reinforcement: {exc}")
