from __future__ import annotations

import json
import time
from dataclasses import dataclass, replace
from datetime import datetime
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

from .anki_config_store import AnkiConfigStore
from .anki_deck_provider import AnkiDeckProvider
from .anki_card_saver import AnkiCardSaver
from .core.article import (
    list_saved_articles,
    load_saved_article,
    parse_article_frontmatter,
    save_article,
)
from .core.config import DEFAULT_CONFIG, PROVIDER_PROFILES, activate_llm_api_profile, normalize_llm_api_profiles
from .core.llm import fetch_openai_compatible_models, generate_article, test_openai_compatible_config
from .core.prompt import build_prompt
from .core.article_generator import run_article_generation
from .anki_adapters import AnkiConfigAdapter, AnkiDeckAdapter
from .core.rendering import (
    article_card_title,
    render_article_fragment_html,
    render_article_html,
    render_paragraph_html,
    render_review_notes_html,
)
from .core.utils import (
    card_id_set,
    clamp_word_count,
    clean_base_url,
    clean_max_tokens,
    clean_max_words,
    clean_provider_id,
    clean_temperature,
    clean_text,
    slugify,
    word_range_bounds,
)



ADDON_PACKAGE = __name__
CONFIG_STORE = AnkiConfigStore(ADDON_PACKAGE)
ADDON_DIR = Path(__file__).resolve().parent
WEB_DIR = ADDON_DIR / "web"
ANKI_CONFIG_ADAPTER = AnkiConfigAdapter(ADDON_PACKAGE)
ANKI_DECK_ADAPTER: AnkiDeckAdapter | None = None  # set after CARD_SAVER is created
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
            elif action == "fetchModels":
                self._fetch_models(dict(payload.get("settings") or {}))
            elif action == "testApiSettings":
                self._test_api_settings(dict(payload.get("settings") or {}))
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
            elif action == "selectApiProfile":
                self._select_api_profile(str(payload.get("profileId") or ""))
            elif action == "saveDesktopSettings":
                self._save_desktop_settings(dict(payload.get("settings") or {}))
            elif action == "saveArticleCardSettings":
                self._save_article_card_settings(dict(payload.get("settings") or {}))
            elif action == "saveCollapsedDeckGroups":
                self._save_collapsed_deck_groups(
                    list(payload.get("collapsedDeckGroups") or [])
                )
            elif action == "saveArticleCard":
                self._save_article_card(
                    str(payload.get("deckId", "")),
                    payload.get("cardIds"),
                    str(payload.get("article", "")),
                    str(payload.get("markdownPath", "")),
                    str(payload.get("htmlPath", "")),
                )
            elif action == "generate":
                self._generate_article(
                    str(payload.get("deckId", "")),
                    str(payload.get("presetId", "")),
                    payload.get("cardIds"),
                    dict(payload.get("preset") or {}),
                )
            elif action == "listArticles":
                self._list_articles()
            elif action == "loadArticle":
                self._load_article(str(payload.get("path", "")))
            else:
                self._emit("error", {"message": f"Unknown command: {action}"})
        except Exception as exc:
            self._emit("error", {"message": str(exc)})

    def _send_state(self) -> None:
        if mw.col is None:
            self._emit("error", {"message": "No Anki collection is open."})
            return

        self.deck_payloads = DECK_PROVIDER.get_today_decks()
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
        day_start, day_end = study_window_payload(config)
        self._emit(
            "state",
            {
                "decks": decks,
                "dayStart": day_start,
                "dayEnd": day_end,
                "promptPresets": normalize_prompt_presets(config),
                "selectedPromptPresetId": config.get("selected_prompt_preset_id")
                or "default",
                "uiLanguage": config.get("ui_language") or "zh",
                "collapsedDeckGroups": list(config.get("collapsed_deck_groups") or []),
                "lastSelectedDeckId": clean_text(config.get("last_selected_deck_id")),
                "providerProfiles": provider_profiles_payload(),
                "apiSettings": api_settings_payload(config),
                "articleCardSettings": article_card_settings_payload(config),
                "desktopSettings": desktop_settings_payload(config),
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
        config = load_config()
        config["last_selected_deck_id"] = deck_id
        CONFIG_STORE.save(config)
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

    def _fetch_models(self, settings: dict[str, Any]) -> None:
        config = load_config()
        api_key = str(settings.get("apiKey") or config.get("api_key") or "").strip()
        base_url = clean_base_url(settings.get("baseUrl") or config.get("base_url"))
        if not api_key:
            self._emit("error", {"message": "Enter or save an API key before fetching models."})
            return
        if not base_url:
            self._emit("error", {"message": "Enter an API base URL before fetching models."})
            return

        def task() -> dict[str, Any]:
            models = fetch_openai_compatible_models(base_url, api_key)
            if not models:
                raise RuntimeError("No models were returned by this provider.")
            return {"models": models}

        def on_done(future: Any) -> None:
            try:
                result = future.result()
            except Exception as exc:
                self._emit("error", {"message": str(exc)})
                return
            self._emit("modelsFetched", result)

        mw.taskman.run_in_background(task, on_done)

    def _test_api_settings(self, settings: dict[str, Any]) -> None:
        config = load_config()
        api_key = str(settings.get("apiKey") or config.get("api_key") or "").strip()
        base_url = clean_base_url(settings.get("baseUrl") or config.get("base_url"))
        model = clean_text(settings.get("model") or config.get("model"))
        if not api_key or not base_url or not model:
            self._emit("error", {"message": "API key, base URL, and model are required for testing."})
            return

        def task() -> dict[str, Any]:
            return test_openai_compatible_config(base_url, api_key, model)

        def on_done(future: Any) -> None:
            try:
                result = future.result()
            except Exception as exc:
                self._emit("error", {"message": str(exc)})
                return
            self._emit("apiSettingsTested", result)

        mw.taskman.run_in_background(task, on_done)

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
        CONFIG_STORE.save(config)
        self._emit(
            "fieldConfigSaved",
            {"deckId": deck_id, "selectedFields": selected_fields},
        )

    def _save_prompt_preset(self, preset: dict[str, Any]) -> None:
        config = load_config()
        presets = normalize_prompt_presets(config)
        preset_id = str(preset.get("id") or f"preset-{uuid4().hex[:10]}")
        clean_preset = clean_prompt_preset(preset, preset_id)

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
        CONFIG_STORE.save(config)
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
        CONFIG_STORE.save(config)
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
        CONFIG_STORE.save(config)

    def _save_ui_language(self, ui_language: str) -> None:
        if ui_language not in {"zh", "en", "ja"}:
            ui_language = "zh"
        config = load_config()
        config["ui_language"] = ui_language
        CONFIG_STORE.save(config)

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

        profile_id = clean_text(settings.get("profileId")) or uuid4().hex
        profile_name = clean_text(settings.get("profileName")) or model
        profiles = normalize_llm_api_profiles(config)
        saved_key = api_key or ("" if clear_api_key else str(config.get("api_key") or ""))
        profile = {"id": profile_id, "name": profile_name, "provider_id": provider_id,
                   "base_url": base_url, "model": model, "api_key": saved_key,
                   "temperature": temperature, "max_tokens": max_tokens}
        profiles = [item for item in profiles if item["id"] != profile_id] + [profile]
        config["llm_api_profiles"] = profiles
        config["selected_llm_api_profile_id"] = profile_id
        config["selected_provider_profile"] = provider_id
        config["base_url"] = base_url
        config["model"] = model
        config["temperature"] = temperature
        config["max_tokens"] = max_tokens
        CONFIG_STORE.save(config)
        self._emit(
            "apiSettingsSaved",
            {
                "apiSettings": api_settings_payload(config),
                "message": "API settings saved.",
            },
        )

    def _select_api_profile(self, profile_id: str) -> None:
        config = load_config()
        if not activate_llm_api_profile(config, profile_id):
            self._emit("error", {"message": "API profile not found."})
            return
        CONFIG_STORE.save(config)
        self._emit("apiSettingsSaved", {"apiSettings": api_settings_payload(config)})

    def _save_desktop_settings(self, settings: dict[str, Any]) -> None:
        config = load_config()
        momo_api_key = clean_text(settings.get("momoApiKey"))
        clear_momo_key = bool(settings.get("clearMomoApiKey"))
        if momo_api_key:
            config["momo_api_key"] = momo_api_key
        elif clear_momo_key:
            config["momo_api_key"] = ""
        config["momo_day_start"] = clean_time_setting(settings.get("momoDayStart"))
        config["momo_day_end"] = clean_time_setting(settings.get("momoDayEnd"))
        CONFIG_STORE.save(config)
        day_start, day_end = study_window_payload(config)
        self._emit(
            "desktopSettingsSaved",
            {
                "desktopSettings": desktop_settings_payload(config),
                "dayStart": day_start,
                "dayEnd": day_end,
                "message": "Desktop settings saved.",
            },
        )

    def _save_article_card_settings(self, settings: dict[str, Any]) -> None:
        config = load_config()
        CONFIG_STORE.save(config)
        self._emit(
            "articleCardSettingsSaved",
            {
                "articleCardSettings": article_card_settings_payload(config),
                "message": "Article card setting saved.",
            },
        )

    def _save_collapsed_deck_groups(self, collapsed_groups: list[str]) -> None:
        config = load_config()
        config["collapsed_deck_groups"] = [
            clean_text(group) for group in collapsed_groups if clean_text(group)
        ]
        CONFIG_STORE.save(config)

    def _save_article_card(
        self,
        deck_id: str,
        selected_card_ids: Any,
        article: str,
        markdown_path: str,
        html_path: str,
    ) -> None:
        payload = self.deck_payloads.get(deck_id)
        if not payload:
            self._emit("error", {"message": "Select a deck with study activity first."})
            return

        cards = payload["cards"]
        if selected_card_ids is not None:
            selected_ids = card_id_set(selected_card_ids)
            if selected_ids:
                cards = [card for card in cards if card.cid in selected_ids]

        def task() -> dict[str, Any]:
            return CARD_SAVER.save_article_card(
                payload["name"],
                cards,
                article,
                Path(markdown_path),
                Path(html_path),
            )

        def on_done(future: Any) -> None:
            try:
                article_card = future.result()
                self._emit("articleCardSaved", {"articleCard": article_card})
            except Exception as exc:
                self._emit("articleCardSaved", {"articleCardError": str(exc)})

        mw.taskman.run_in_background(task, on_done)

    def _generate_article(
        self,
        deck_id: str,
        preset_id: str,
        selected_card_ids: Any = None,
        preset_override: dict[str, Any] | None = None,
    ) -> None:
        payload = self.deck_payloads.get(deck_id)
        if not payload:
            self._emit("error", {"message": "Select a deck with study activity first."})
            return

        cards = payload["cards"]
        if not cards:
            self._emit("error", {"message": "This deck has no candidate cards today."})
            return
        if selected_card_ids is not None:
            selected_ids = card_id_set(selected_card_ids)
            if not selected_ids:
                self._emit("error", {"message": "Choose at least one card for generation."})
                return
            cards = [card for card in cards if card.cid in selected_ids]
            if not cards:
                self._emit("error", {"message": "Selected cards are no longer available."})
                return

        config = load_config()
        preset = prompt_preset_by_id(config, preset_id)
        if preset_override and str(preset_override.get("id") or "") == preset_id:
            preset = clean_prompt_preset(preset_override, preset_id)
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

        deck_name = payload["name"]

        def task() -> dict[str, Any]:
            result = run_article_generation(
                ANKI_CONFIG_ADAPTER,
                ANKI_DECK_ADAPTER,  # type: ignore[arg-type]
                deck_name, cards, selected_fields, preset,
            )
            result["deckId"] = deck_id
            return result

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

    def _list_articles(self) -> None:
        def task() -> dict[str, Any]:
            return {"articles": list_saved_articles()}

        def on_done(future: Any) -> None:
            try:
                result = future.result()
            except Exception as exc:
                self._emit("error", {"message": str(exc)})
                return
            self._emit("articleList", result)

        mw.taskman.run_in_background(task, on_done)

    def _load_article(self, path: str) -> None:
        def task() -> dict[str, Any]:
            return load_saved_article(path)

        def on_done(future: Any) -> None:
            try:
                result = future.result()
            except Exception as exc:
                self._emit("error", {"message": str(exc)})
                return
            self._emit("articleLoaded", result)

        mw.taskman.run_in_background(task, on_done)

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

DECK_PROVIDER = AnkiDeckProvider(collect_today_decks)

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




def api_settings_payload(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "providerId": clean_provider_id(config.get("selected_provider_profile")),
        "baseUrl": clean_base_url(config.get("base_url") or DEFAULT_CONFIG["base_url"]),
        "model": clean_text(config.get("model") or DEFAULT_CONFIG["model"]),
        "temperature": clean_temperature(config.get("temperature")),
        "maxTokens": clean_max_tokens(config.get("max_tokens")),
        "hasApiKey": bool(str(config.get("api_key") or "").strip()),
        "profileId": str(config.get("selected_llm_api_profile_id") or ""),
        "profiles": [{"id": p["id"], "name": p.get("name") or p.get("model") or "API",
                      "providerId": p.get("provider_id") or "custom", "baseUrl": p.get("base_url") or "",
                      "model": p.get("model") or "", "temperature": p.get("temperature", 0.7),
                      "maxTokens": p.get("max_tokens", 30000), "hasApiKey": bool(p.get("api_key"))}
                     for p in normalize_llm_api_profiles(config)],
    }


def provider_profiles_payload() -> list[dict[str, str]]:
    return [
        {
            "id": profile["id"],
            "name": profile["name"],
            "base_url": profile["base_url"],
            "model": profile["model"],
        }
        for profile in PROVIDER_PROFILES
    ]


def article_card_settings_payload(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "parentDeck": ARTICLE_PARENT_DECK,
        "noteType": ARTICLE_NOTE_TYPE,
    }


def clean_time_setting(value: Any, fallback: str = "04:00") -> str:
    text = clean_text(value)
    try:
        hour_text, minute_text = text.split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
    except (TypeError, ValueError):
        return fallback
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return fallback
    return f"{hour:02d}:{minute:02d}"


def desktop_settings_payload(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "hasMomoApiKey": bool(clean_text(config.get("momo_api_key"))),
        "momoDayStart": clean_time_setting(config.get("momo_day_start")),
        "momoDayEnd": clean_time_setting(config.get("momo_day_end")),
    }


def study_window_payload(config: dict[str, Any], now: float | None = None) -> tuple[int, int]:
    now_ts = time.time() if now is None else now
    now_parts = time.localtime(now_ts)
    start_hour, start_minute = [int(part) for part in clean_time_setting(config.get("momo_day_start")).split(":")]
    end_hour, end_minute = [int(part) for part in clean_time_setting(config.get("momo_day_end")).split(":")]
    start_ts = int(time.mktime(now_parts[:3] + (start_hour, start_minute, 0, -1, -1, -1)))
    end_ts = int(time.mktime(now_parts[:3] + (end_hour, end_minute, 0, -1, -1, -1)))
    if end_ts <= start_ts:
        end_ts += 86400
    if now_ts < start_ts:
        start_ts -= 86400
        end_ts -= 86400
    return start_ts, end_ts


def load_config() -> dict[str, Any]:
    config = DEFAULT_CONFIG.copy()
    loaded = CONFIG_STORE.load() or {}
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
        legacy_language = clean_text(raw.get("language"))
        presets.append(
            {
                "id": preset_id,
                "name": clean_text(raw.get("name")) or preset_id,
                "reader_native_language": clean_text(raw.get("reader_native_language")),
                "article_language": clean_text(raw.get("article_language")) or legacy_language,
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
                "reader_native_language": "",
                "article_language": "",
                "difficulty": "",
                "max_words": "",
                "instructions": "",
                "prompt_template": "",
            },
        )
    return presets


def clean_prompt_preset(preset: dict[str, Any], preset_id: str) -> dict[str, str]:
    return {
        "id": preset_id,
        "name": clean_text(preset.get("name")) or "Untitled",
        "reader_native_language": clean_text(preset.get("reader_native_language")),
        "article_language": clean_text(preset.get("article_language")),
        "difficulty": clean_text(preset.get("difficulty")),
        "max_words": clean_max_words(preset.get("max_words")),
        "instructions": clean_text(preset.get("instructions")),
        "prompt_template": str(preset.get("prompt_template") or ""),
    }


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


def create_article_card(
    source_deck_name: str,
    cards: list[CandidateCard],
    article: str,
    markdown_path: Path,
    html_path: Path,
) -> dict[str, Any]:
    if mw.col is None:
        raise RuntimeError("No Anki collection is open.")

    deck_name_value = article_deck_name(source_deck_name)
    deck_id = get_or_create_deck_id(deck_name_value)
    model = get_or_create_article_model()
    note = mw.col.new_note(model)
    date_value = article_card_date()
    title = article_card_title(article, date_value)
    values = {
        "Date": date_value,
        "Source Deck": source_deck_name,
        "Title": title,
        "Article": render_article_fragment_html(article),
        "Source Terms": "\n".join(card.term for card in cards if card.term),
        "Markdown Path": str(markdown_path),
        "HTML Path": str(html_path),
    }
    for field in ARTICLE_FIELDS:
        note[field] = values.get(field, "")

    add_note_to_deck(note, deck_id)
    try:
        card_ids = [c.id for c in note.cards()]
        if card_ids:
            mw.col.sched.suspendCards(card_ids)
    except Exception:
        pass
    return {
        "noteId": int(getattr(note, "id", 0) or 0),
        "deckName": deck_name_value,
        "noteType": ARTICLE_NOTE_TYPE,
        "date": values["Date"],
    }


CARD_SAVER = AnkiCardSaver(create_article_card)
# Now that CARD_SAVER exists, instantiate the AnkiDeckAdapter.
ANKI_DECK_ADAPTER = AnkiDeckAdapter(CARD_SAVER)


def article_deck_name(source_deck_name: str) -> str:
    source = clean_text(source_deck_name).replace("::", "::")
    return f"{ARTICLE_PARENT_DECK}::{source or 'Generated Articles'}"


def article_card_date() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")


def get_or_create_deck_id(deck_name_value: str) -> int:
    decks = mw.col.decks
    id_for_name = getattr(decks, "id_for_name", None)
    if callable(id_for_name):
        existing_id = id_for_name(deck_name_value)
        if existing_id is not None:
            return int(existing_id)

    legacy_id = getattr(decks, "id", None)
    if callable(legacy_id):
        deck_id = legacy_id(deck_name_value)
        if deck_id is not None:
            return int(deck_id)

    add_normal_deck = getattr(decks, "add_normal_deck_with_name", None)
    if callable(add_normal_deck):
        deck = add_normal_deck(deck_name_value)
        deck_id = getattr(deck, "id", None)
        if deck_id is not None:
            return int(deck_id)

    raise RuntimeError(f"Could not create article card deck: {deck_name_value}")


def get_or_create_article_model() -> Any:
    models = mw.col.models
    by_name = getattr(models, "by_name", None) or getattr(models, "byName", None)
    model = by_name(ARTICLE_NOTE_TYPE) if callable(by_name) else None
    if model is not None:
        return model

    model = models.new(ARTICLE_NOTE_TYPE)
    for field_name in ARTICLE_FIELDS:
        add_model_field(models, model, new_model_field(models, field_name))

    template = new_model_template(models, "Article")
    template["qfmt"] = """
<section class="dairr-card">
  <div class="dairr-date">{{Date}}</div>
  <h1>{{Title}}</h1>
  <div class="dairr-source">{{Source Deck}}</div>
</section>
"""
    template["afmt"] = """
{{FrontSide}}
<hr id="answer">
<article class="dairr-article">{{Article}}</article>
<section class="dairr-terms">
  <h2>Source Terms</h2>
  <pre>{{Source Terms}}</pre>
</section>
"""
    add_model_template(models, model, template)
    css = """
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
    model["css"] = css
    models.add(model)
    return model


def new_model_field(models: Any, field_name: str) -> Any:
    new_field = getattr(models, "new_field", None) or getattr(models, "newField", None)
    return new_field(field_name)


def add_model_field(models: Any, model: Any, field: Any) -> None:
    add_field = getattr(models, "add_field", None) or getattr(models, "addField", None)
    add_field(model, field)


def new_model_template(models: Any, template_name: str) -> Any:
    new_template = getattr(models, "new_template", None) or getattr(models, "newTemplate", None)
    return new_template(template_name)


def add_model_template(models: Any, model: Any, template: Any) -> None:
    add_template = getattr(models, "add_template", None) or getattr(models, "addTemplate", None)
    add_template(model, template)


def add_note_to_deck(note: Any, deck_id: int) -> None:
    add_note = getattr(mw.col, "add_note", None)
    if callable(add_note):
        add_note(note, deck_id)
        return
    try:
        note.model()["did"] = deck_id
    except Exception:
        pass
    mw.col.addNote(note)


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
