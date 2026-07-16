# Desktop mock server for Daily AI Reading Reinforcement.
#
# Serves the SAME shared web UI (addon/daily_ai_reading_reinforcement/web/*)
# that the Anki addon uses, but in a plain Python http.server with no Anki /
# aqt / momo / LLM dependencies. A mock window.__DAIRR_BRIDGE__ is injected so
# app.js's send() talks to /api/bridge, which returns mock responses that
# match the real addon's event payloads.
#
# Run:  python3 desktop_mock/main.py
# Open: http://127.0.0.1:8755

from __future__ import annotations

import json
import os
import secrets
import sys
import threading
import urllib.parse
from datetime import datetime, timedelta
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping

from mock_data import (
    DEFAULT_CONFIG as MOCK_DEFAULT_CONFIG,
    build_article_list_payload,
    build_article_payload,
    build_deck_cards_payload,
    build_loaded_article_payload,
    build_state_payload,
)
from ankiconnect_provider import AnkiConnectDeckProvider, AnkiConnectError, DEFAULT_ANKICONNECT_URL
from momo_provider import MockMoMoDeckProvider
from real_momo_provider import RealMoMoDeckProvider
from dairr_core_runtime import enable_dairr_core_imports

enable_dairr_core_imports()

from dairr_core.learning_sources import LearningSourceRegistry, SourceScopedId
from dairr_core.application_host import OperationRegistry
from dairr_core.article_generation import (
    ArticleGenerationRequest,
    GenerationTarget,
    generate_target_aware_article,
)
from dairr_core.article import apply_article_history_evidence
from dairr_core.bridge_contract import (
    ASYNC_ACTIONS,
    BRIDGE_VERSION,
    RELEASE_ACTIONS,
    SYNC_EVENT_BY_ACTION,
    BridgeRequest,
    failure_envelope,
    response_envelope,
)
from dairr_core.capabilities import (
    Capability,
    CapabilityId,
    CapabilityReason,
    CapabilitySet,
    CapabilityStatus,
    Provenance,
)
from dairr_core.config import (
    export_prompt_registry_overrides,
    normalize_config,
    normalize_prompt_config,
    prompt_registry_from_config,
    reasoning_intent_from_config,
    reasoning_intent_to_dict,
)
from dairr_core.llm import OpenAICompatibleTransport
from dairr_core.operations import ModelRequestSettings, OperationContext, OperationError
from dairr_core.practice import (
    ArticleReference,
    PracticeSegment,
    PracticeSession,
    TranslationDirection,
)
from dairr_core.practice_repository import PracticeRepository, session_document
from dairr_core.practice_service import PracticeService
from dairr_core.prompt_templates import (
    PromptTask,
    PromptTemplate,
    PromptTemplateError,
    ResponseMode,
    default_prompt_registry,
    render_prompt,
)
from dairr_core.provider_capabilities import (
    ProviderConfigurationError,
    ReasoningControl,
    ReasoningIntent,
    ReasoningMode,
    known_provider_capabilities,
)
from dairr_core.scoring import (
    ScoringPreset,
    SettingsMode,
    export_preset,
    import_preset,
    recommended_preset,
    score_cards,
    signal_metadata,
)
from dairr_core.target_selection import ManualOverride, TargetCategory, select_targets
from learning_sources import LegacyDeckProviderSource, source_descriptor

# Desktop adapters and real generation pipeline
try:
    from desktop_adapters import (
        DesktopConfigAdapter,
        DesktopDeckAdapter,
        DesktopEnvironmentAdapter,
    )
    _DESKTOP_ADAPTERS_AVAILABLE = True
except Exception:
    _DESKTOP_ADAPTERS_AVAILABLE = False

REPO_ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = REPO_ROOT / "addon" / "daily_ai_reading_reinforcement" / "web"
HOST = "127.0.0.1"
# 8765 is AnkiConnect's default port; pick a distinct one to avoid clashes
# when Anki is running alongside the mock.
PORT = 8755
APP_NAME = "DAIRR"
APP_DISPLAY_NAME = "Daily AI Reading Reinforcement"
APP_VERSION = "0.1.0"
APP_MODE = "desktop"
BRIDGE_TOKEN_HEADER = "X-DAIRR-Bridge-Token"
MAX_BRIDGE_BODY_BYTES = 2_000_000
PRACTICE_LIMITS_PAYLOAD = {
    "maxCharacters": 100_000,
    "maxSourceCharacters": 100_000,
    "maxSegments": 500,
    "maxSegmentCharacters": 20_000,
}

_BRIDGE_TOKEN = secrets.token_urlsafe(32)
_OPERATIONS = OperationRegistry(max_workers=4, max_records=128, terminal_ttl_seconds=900)
_PRACTICE_LOCK = threading.RLock()
_PRACTICE_DRAFTS: dict[str, PracticeSession] = {}
_PRACTICE_REVISIONS: dict[str, int] = {}
_PRACTICE_MUTATIONS: dict[str, str] = {}
_LAST_ANKI_CAPABILITIES: CapabilitySet | None = None


def _load_provider_config() -> dict[str, Any]:
    if not _DESKTOP_ADAPTERS_AVAILABLE:
        return {}
    try:
        return DesktopConfigAdapter().load() or {}
    except Exception:
        return {}


def _momo_api_key(
    environ: Mapping[str, str] | None = None,
    config: dict[str, Any] | None = None,
) -> str:
    if environ is None:
        environ = os.environ
    token = environ.get("MOMO_TOKEN") or environ.get("Maimemo_key")
    if token:
        return str(token).strip()
    if config is None:
        config = _load_provider_config()
    return str(config.get("momo_api_key") or "").strip()


def _time_setting(value: Any, fallback: str = "04:00") -> str:
    text = str(value or "").strip()
    try:
        hour_text, minute_text = text.split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
    except (TypeError, ValueError):
        return fallback
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return fallback
    return f"{hour:02d}:{minute:02d}"


def _study_window(config: dict[str, Any]) -> tuple[int, int]:
    start_text = _time_setting(config.get("momo_day_start"))
    end_text = _time_setting(config.get("momo_day_end"))
    now = datetime.now()
    start_hour, start_minute = [int(part) for part in start_text.split(":", 1)]
    end_hour, end_minute = [int(part) for part in end_text.split(":", 1)]
    start = now.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
    if now < start:
        start = start - timedelta(days=1)
    end = start.replace(hour=end_hour, minute=end_minute)
    if end <= start:
        end = end + timedelta(days=1)
    return int(start.timestamp()), int(end.timestamp())


def _desktop_settings_payload(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "hasMomoApiKey": bool(_momo_api_key(config=config)),
        "momoDayStart": _time_setting(config.get("momo_day_start")),
        "momoDayEnd": _time_setting(config.get("momo_day_end")),
    }


def build_deck_provider(environ: Mapping[str, str] | None = None) -> Any:
    if environ is None:
        environ = os.environ
       

    provider_type = environ.get("DAIRR_DESKTOP_PROVIDER", "mock")
    if provider_type == "ankiconnect":
        base_url = environ.get("DAIRR_ANKICONNECT_URL", DEFAULT_ANKICONNECT_URL)
        print(f"Using AnkiConnectDeckProvider ({base_url})")
        return AnkiConnectDeckProvider(base_url=base_url)
    elif provider_type == "real_momo":
        token = _momo_api_key(environ)
        if not token:
            raise ValueError("MOMO_TOKEN is missing. Cannot start real_momo provider.")
        print("Using RealMoMoDeckProvider (MOMO_TOKEN present)")
        return RealMoMoDeckProvider(token=token)
    elif provider_type == "mock":
        print("Using MockMoMoDeckProvider")
        return MockMoMoDeckProvider()
    else:
        raise ValueError(f"Unknown DAIRR_DESKTOP_PROVIDER: {provider_type}")


def build_health_payload(environ: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Return a stable health payload for desktop shells.

    Tauri uses this endpoint before reusing port 8755 so it does not attach to
    an unrelated local service that happens to be listening on the same port.
    Keep this payload dependency-free and safe to call before providers do any
    network work.
    """
    if environ is None:
        environ = os.environ
    provider = str(environ.get("DAIRR_DESKTOP_PROVIDER") or "mock")
    return {
        "app": APP_NAME,
        "name": APP_DISPLAY_NAME,
        "version": APP_VERSION,
        "mode": APP_MODE,
        "provider": provider,
        "instanceId": str(environ.get("DAIRR_INSTANCE_ID") or ""),
        "parentPid": int(environ.get("DAIRR_PARENT_PID") or 0),
        "bridge": {
            "available": True,
            "type": "http",
            "protocolVersion": BRIDGE_VERSION,
            "endpoint": "/api/bridge",
            "windowObject": "__DAIRR_BRIDGE__",
            "tokenRequired": True,
            "maxRequestBytes": MAX_BRIDGE_BODY_BYTES,
        },
    }


# Single provider instance used by handle_action() for load / selectDeck.
# It is initialized lazily so importing this module never starts network-backed
# providers or exits the process.
DECK_PROVIDER: Any | None = None
MOMO_PROVIDER: Any | None = None


def get_deck_provider() -> Any:
    global DECK_PROVIDER
    if DECK_PROVIDER is None:
        DECK_PROVIDER = build_deck_provider()
    return DECK_PROVIDER


def get_momo_provider() -> Any | None:
    global MOMO_PROVIDER
    token = _momo_api_key()
    if not token:
        return None
    if MOMO_PROVIDER is None or getattr(MOMO_PROVIDER, "_token", "") != token:
        MOMO_PROVIDER = RealMoMoDeckProvider(token=token)
    return MOMO_PROVIDER


def _primary_source() -> dict[str, str]:
    provider_type = str(os.environ.get("DAIRR_DESKTOP_PROVIDER") or "mock")
    names = {
        "ankiconnect": "AnkiConnect",
        "real_momo": "MoMo",
        "mock": "Demo",
    }
    return {
        "id": "primary",
        "name": names.get(provider_type, provider_type),
        "provider": provider_type,
    }


def _available_sources() -> list[dict[str, Any]]:
    """List configured sources without requesting study data from them."""
    primary = _primary_source()
    sources = [
        source_descriptor(
            primary["id"],
            primary["name"],
            supports_article_card_write=primary["provider"] == "ankiconnect",
        ).to_bridge_dict()
    ]
    # A MoMo primary source is already represented above. A separately
    # configured MoMo account is only contacted after it is selected.
    if primary["provider"] != "real_momo" and _momo_api_key():
        sources.append(source_descriptor("momo", "MoMo").to_bridge_dict())
    return sources


def _source_registry() -> LearningSourceRegistry:
    """Build adapters only after a source/deck operation asks for them.

    Listing source descriptors remains network-free; the legacy provider is
    instantiated lazily only when it is selected or when a scoped deck id is
    resolved.
    """
    primary = _primary_source()
    sources = [
        LegacyDeckProviderSource(
            source_descriptor(
                primary["id"],
                primary["name"],
                supports_article_card_write=primary["provider"] == "ankiconnect",
            ),
            get_deck_provider(),
        )
    ]
    if primary["provider"] != "real_momo" and _momo_api_key():
        momo_provider = get_momo_provider()
        if momo_provider is not None:
            sources.append(
                LegacyDeckProviderSource(source_descriptor("momo", "MoMo"), momo_provider)
            )
    return LearningSourceRegistry(sources)


def _resolve_deck_source(deck_id: str) -> tuple[LegacyDeckProviderSource, SourceScopedId]:
    """Resolve a bridge deck id through the source registry, never by prefix.

    The unscoped fallback is a temporary migration path for a saved desktop
    selection from before contract v1.  New bridge responses always emit the
    opaque scoped form, so a value can never be mistaken for another source
    after it has passed through the current UI.
    """
    registry = _source_registry()
    try:
        source, scoped_deck_id = registry.resolve_deck(deck_id)
    except ValueError:
        scoped_deck_id = SourceScopedId("primary", deck_id)
        source = registry.get("primary")
    return source, scoped_deck_id


# Actions the mock understands. Anything else returns an error event so the
# shared UI's error handling path is exercised without crashing the server.
SUPPORTED_ACTIONS = {
    "load",
    "selectSource",
    "selectDeck",
    "generate",
    "debugPrompt",
    "saveArticleCard",
    "saveCollapsedDeckGroups",
    "saveFieldConfig",
    "listArticles",
    "loadArticle",
}


def safe_exception_summary(exc: BaseException | None) -> str:
    if exc is None:
        return "-"
    # For urllib.error.HTTPError, include only status code and class name.
    code = getattr(exc, "code", None)
    if code is not None:
        return f"{type(exc).__name__}(code={code})"
    reason = getattr(exc, "reason", None)
    if reason is not None:
        return f"{type(exc).__name__}"
    return type(exc).__name__


def _load_desktop_config() -> dict[str, Any]:
    if not _DESKTOP_ADAPTERS_AVAILABLE:
        return {}
    try:
        return DesktopConfigAdapter().load() or {}
    except Exception:
        return {}


def _save_desktop_config(config: dict[str, Any]) -> None:
    if not _DESKTOP_ADAPTERS_AVAILABLE:
        return
    DesktopConfigAdapter().save(config)


def _state_payload(
    last_selected_deck_id: str,
    decks: list[dict[str, Any]],
    *,
    sources: list[dict[str, Any]] | None = None,
    selected_source_id: str = "",
) -> dict[str, Any]:
    config = _load_desktop_config()
    payload = build_state_payload(last_selected_deck_id, decks=decks)
    active_config = config or _desktop_default_config()
    day_start, day_end = _study_window(active_config)
    payload["dayStart"] = day_start
    payload["dayEnd"] = day_end
    payload["desktopSettings"] = _desktop_settings_payload(active_config)
    payload["sources"] = sources if sources is not None else _available_sources()
    payload["selectedSourceId"] = selected_source_id
    if not config:
        return payload
    payload["promptPresets"] = list(config.get("prompt_presets") or payload["promptPresets"])
    payload["selectedPromptPresetId"] = (
        config.get("selected_prompt_preset_id") or payload["selectedPromptPresetId"]
    )
    payload["uiLanguage"] = config.get("ui_language") or payload["uiLanguage"]
    payload["collapsedDeckGroups"] = list(
        config.get("collapsed_deck_groups") or payload["collapsedDeckGroups"]
    )
    available_deck_ids = {str(deck.get("id") or "") for deck in decks}
    saved_deck_id = str(config.get("last_selected_deck_id") or "")
    requested_deck_id = str(last_selected_deck_id or "")
    payload["lastSelectedDeckId"] = (
        saved_deck_id
        if saved_deck_id in available_deck_ids
        else requested_deck_id
        if requested_deck_id in available_deck_ids
        else ""
    )
    try:
        payload["apiSettings"] = _safe_api_settings_payload(config)
    except Exception:
        pass
    return payload


def _deck_fields_from_cards(cards: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    fields: list[str] = []
    for card in cards:
        card_fields = card.get("fields")
        if not isinstance(card_fields, dict):
            continue
        for name, value in card_fields.items():
            if name in seen or not value:
                continue
            seen.add(name)
            fields.append(str(name))
    return fields


def _selected_fields_for_deck(deck_id: str, available_fields: list[str]) -> list[str]:
    config = _load_desktop_config()
    deck_field_config = config.get("deck_field_config") or {}
    saved_fields = deck_field_config.get(deck_id) or []
    selected = [field for field in saved_fields if field in available_fields]
    return selected or available_fields


def _deck_cards_payload(deck_id: str, cards_data: dict[str, Any]) -> dict[str, Any]:
    payload = build_deck_cards_payload(deck_id, cards_data=cards_data)
    fields = list(payload.get("fields") or [])
    payload["selectedFields"] = _selected_fields_for_deck(deck_id, fields)
    return payload


class _GenerationCard:
    __slots__ = ("cid", "nid", "term", "is_new", "is_failed", "fields")

    def __init__(self, data: dict[str, Any]) -> None:
        self.cid = data.get("cid")
        self.nid = data.get("nid")
        self.term = data.get("term")
        self.is_new = data.get("is_new")
        self.is_failed = data.get("is_failed")
        self.fields = data.get("fields", {})


def _desktop_default_config() -> dict[str, Any]:
    if _DESKTOP_ADAPTERS_AVAILABLE:
        try:
            from desktop_adapters import DEFAULT_CONFIG
            return dict(DEFAULT_CONFIG)
        except Exception:
            pass
    return dict(MOCK_DEFAULT_CONFIG)


def _load_generation_config() -> dict[str, Any]:
    config = _desktop_default_config()
    loaded = _load_desktop_config()
    if isinstance(loaded, dict):
        config.update(loaded)
    return config


def _preset_by_id(presets: list[Any], preset_id: str) -> dict[str, Any] | None:
    for preset in presets:
        if isinstance(preset, dict) and str(preset.get("id")) == preset_id:
            return preset
    return None


def _payload_preset_override(payload: dict[str, Any], requested_preset_id: str) -> dict[str, Any] | None:
    preset = payload.get("preset")
    if not isinstance(preset, dict):
        return None
    preset_id = str(preset.get("id") or "")
    if not preset_id or preset_id != requested_preset_id:
        return None
    try:
        from desktop_adapters import _import_core
        _utils = _import_core("utils")
        return {
            "id": preset_id,
            "name": _utils.clean_text(preset.get("name")) or "Untitled",
            "reader_native_language": _utils.clean_text(preset.get("reader_native_language")),
            "article_language": _utils.clean_text(preset.get("article_language")),
            "difficulty": _utils.clean_text(preset.get("difficulty")),
            "max_words": _utils.clean_max_words(preset.get("max_words")),
            "instructions": _utils.clean_text(preset.get("instructions")),
            "prompt_template": str(preset.get("prompt_template") or ""),
        }
    except Exception:
        return dict(preset)


def resolve_generation_context(deck_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Resolve cards, fields, config, and preset exactly once for generation.

    This mirrors the standalone generate path and is shared by debugPrompt so
    the diagnostic prompt is built from the same provider cards and preset
    resolution as the real LLM request.
    """
    source, scoped_deck_id = _resolve_deck_source(deck_id)
    cards_data = source.get_deck(scoped_deck_id).to_bridge_cards()
    deck_name = str(cards_data.get("name") or "Desktop Deck")
    raw_cards = cards_data.get("cards", [])
    if not isinstance(raw_cards, list):
        raw_cards = []

    requested_preset_id = str(payload.get("presetId") or "")
    selected_card_ids = payload.get("cardIds")
    if selected_card_ids is not None:
        selected_ids_set = {str(cid) for cid in selected_card_ids}
        raw_cards = [
            card for card in raw_cards
            if isinstance(card, dict)
            and (
                str(card.get("cid")) in selected_ids_set
                or _local_card_id(str(card.get("cid") or "")) in selected_ids_set
            )
        ]

    config = _load_generation_config()
    presets = list(config.get("prompt_presets") or [])
    selected_preset_id = str(config.get("selected_prompt_preset_id") or "")
    preset = (
        _payload_preset_override(payload, requested_preset_id)
        if requested_preset_id
        else None
    )
    if not preset:
        preset = _preset_by_id(presets, requested_preset_id) if requested_preset_id else None
    if not preset:
        preset = _preset_by_id(presets, selected_preset_id)
    if not preset and presets:
        first_preset = presets[0]
        preset = first_preset if isinstance(first_preset, dict) else None
    if not preset:
        preset = {}

    provider_fields = cards_data.get("selectedFields", cards_data.get("fields"))
    if not provider_fields:
        provider_fields = _deck_fields_from_cards(
            [card for card in raw_cards if isinstance(card, dict)]
        )
    selected_fields = [str(field) for field in (provider_fields or [])]
    cards = [_GenerationCard(card) for card in raw_cards if isinstance(card, dict)]

    return {
        "config": config,
        "deckName": deck_name,
        "cards": cards,
        "selectedFields": selected_fields,
        "preset": preset,
        "requestedPresetId": requested_preset_id,
        "selectedPromptPresetId": selected_preset_id,
    }


def _local_card_id(card_id: str) -> str:
    """Accept legacy raw card selections while the UI migrates to v1 IDs."""
    try:
        return SourceScopedId.parse(card_id).local_id
    except ValueError:
        return card_id


def _safe_debug_value(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            key_lower = key_text.lower()
            if key_lower in {"api_key", "apikey"} or "authorization" in key_lower:
                continue
            cleaned[key_text] = _safe_debug_value(item)
        return cleaned
    if isinstance(value, list):
        return [_safe_debug_value(item) for item in value]
    return value


def handle_debug_prompt(deck_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        context = resolve_generation_context(deck_id, payload)
        if _DESKTOP_ADAPTERS_AVAILABLE:
            from desktop_adapters import _import_core
            prompt_module = _import_core("prompt")
        else:
            raise RuntimeError("Desktop core prompt module is unavailable.")

        config = context["config"]
        preset = context["preset"]
        prompt = prompt_module.build_prompt(
            config,
            context["deckName"],
            context["cards"],
            context["selectedFields"],
            preset,
        )
        ui_language = prompt_module.writing_language_for_ui(
            str(config.get("ui_language") or "zh")
        )
        article_language = str(
            preset.get("article_language") or "the language being learned"
        )
        reader_native_language = str(
            preset.get("reader_native_language") or ui_language or "English"
        )
        return {
            "event": "debugPrompt",
            "payload": {
                "selectedPromptPresetId": context["selectedPromptPresetId"],
                "requestedPresetId": context["requestedPresetId"],
                "resolvedPreset": _safe_debug_value(preset),
                "selectedFields": context["selectedFields"],
                "cardCount": len(context["cards"]),
                "promptPreview": prompt[:2000],
                "promptContainsArticleLanguage": bool(
                    article_language and article_language in prompt
                ),
                "articleLanguage": article_language,
                "readerNativeLanguage": reader_native_language,
            },
        }
    except Exception as exc:
        err_type = type(exc).__name__
        sys.stderr.write(f"[mock] Provider error on debugPrompt: {err_type}\n")
        return {
            "event": "error",
            "payload": {"message": "Failed to build debug prompt from provider data."},
        }


def handle_generate_real(deck_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Run the real article generation pipeline using Desktop adapters.

    Returns an {event, payload} envelope matching the addon contract.
    """
    source, _ = _resolve_deck_source(deck_id)
    if isinstance(source.provider, MockMoMoDeckProvider):
        return _mock_generate(deck_id)

    if not _DESKTOP_ADAPTERS_AVAILABLE:
        return {"event": "error", "payload": {"message": "Article generation is unavailable in this build."}}

    config_adapter = DesktopConfigAdapter()
    deck_adapter = DesktopDeckAdapter()
    env_adapter = DesktopEnvironmentAdapter()

    try:
        context = resolve_generation_context(deck_id, payload)
    except Exception:
        return {"event": "error", "payload": {"message": "Failed to load generation input from the selected source."}}

    deck_name = context["deckName"]
    cards = context["cards"]
    if not cards:
        return {"event": "error", "payload": {"message": "No cards available for generation."}}

    preset = context["preset"]
    selected_fields = context["selectedFields"]

    # Use the core_article_generator already imported by desktop_adapters.
    try:
        from desktop_adapters import _core_article_generator
        run_article_generation = _core_article_generator.run_article_generation
    except Exception as exc:
        sys.stderr.write(f"[desktop] Article generator unavailable: {type(exc).__name__}\n")
        return {"event": "error", "payload": {"message": "Article generation is unavailable in this build."}}

    try:
        result = run_article_generation(
            config_adapter, deck_adapter, deck_name, cards, selected_fields, preset,
        )
        return {"event": "article", "payload": result}
    except Exception as exc:
        sys.stderr.write(f"[desktop] Real generation failed: {type(exc).__name__}\n")
        public_message = getattr(exc, "public_message", None)
        if not isinstance(public_message, str) or not public_message.strip():
            public_message = "Article generation failed. Check the provider settings and try again."
        return {"event": "error", "payload": {"message": public_message}}


def _mock_generate(deck_id: str) -> dict[str, Any]:
    """Return the mock article payload (kept for backward compatibility)."""
    _, scoped_deck_id = _resolve_deck_source(deck_id)
    payload = build_article_payload(scoped_deck_id.local_id)
    payload["deckId"] = scoped_deck_id.encode()
    return {"event": "article", "payload": payload}


def _list_desktop_articles() -> dict[str, Any]:
    """Read persisted desktop articles instead of the UI demonstration data.

    The mock article list exists only for the dependency-free server fixture.
    A packaged desktop app always has ``DesktopDeckAdapter`` available and must
    show the Markdown files written to its own DAIRR application-data folder.
    """
    if not _DESKTOP_ADAPTERS_AVAILABLE:
        return build_article_list_payload()
    return {"articles": DesktopDeckAdapter().list_saved_articles()}


def _load_desktop_article(path: str) -> dict[str, Any]:
    """Restore one persisted desktop article, with the mock fallback for tests."""
    if not _DESKTOP_ADAPTERS_AVAILABLE:
        return build_loaded_article_payload(path)
    return DesktopDeckAdapter().load_saved_article(path)


def _article_practice_material(raw_article: str, direction: TranslationDirection) -> tuple[str, list[str | None], str]:
    from dairr_core.rendering import parse_article_response

    parsed = parse_article_response(raw_article)
    lines = str(parsed.get("main_article") or "").splitlines()
    pairs: list[tuple[str, str | None]] = []
    paragraph: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.lower().startswith("[t]"):
            translation = stripped[3:].strip()
            if paragraph:
                pairs.append(("\n".join(paragraph).strip(), translation or None))
                paragraph = []
            elif pairs:
                previous, _old = pairs[-1]
                pairs[-1] = (previous, translation or None)
        elif not stripped:
            if paragraph:
                pairs.append(("\n".join(paragraph).strip(), None))
                paragraph = []
        else:
            paragraph.append(line)
    if paragraph:
        pairs.append(("\n".join(paragraph).strip(), None))
    pairs = [(source, reference) for source, reference in pairs if source]
    if not pairs:
        main = str(parsed.get("main_article") or raw_article).strip()
        return main, [None] if main else [], str(parsed.get("title") or "")
    if direction is TranslationDirection.BACK_TRANSLATION and any(reference for _source, reference in pairs):
        source_values = [reference if reference else source for source, reference in pairs]
        references = [source if reference else None for source, reference in pairs]
    else:
        source_values = [source for source, _reference in pairs]
        references = [reference for _source, reference in pairs]
    return "\n\n".join(source_values), references, str(parsed.get("title") or "")


def _practice_repository() -> PracticeRepository:
    if not _DESKTOP_ADAPTERS_AVAILABLE:
        root = Path(os.environ.get("DESKTOP_OUTPUT_DIR") or (REPO_ROOT / "desktop_mock" / "output"))
    else:
        root = DesktopDeckAdapter()._output_dir
    return PracticeRepository(root / "practice_sessions")


def _practice_service() -> PracticeService:
    return PracticeService(_practice_repository())


def _session_payload(session: PracticeSession) -> dict[str, Any]:
    with _PRACTICE_LOCK:
        revision = _PRACTICE_REVISIONS.get(session.id, 0)
    return {
        "id": session.id,
        "kind": session.kind.value,
        "direction": session.direction.value,
        "sourceLanguage": session.source_language,
        "targetLanguage": session.target_language,
        "sourceText": session.source_text,
        "segments": [
            {
                "id": segment.id,
                "position": segment.position,
                "sourceText": segment.source_text,
                "referenceText": segment.reference_text,
            }
            for segment in session.segments
        ],
        "createdAt": session.created_at,
        "updatedAt": session.updated_at,
        "status": session.status.value,
        "proficiencyLevel": session.proficiency_level,
        "customReviewInstructions": session.custom_review_instructions,
        "articleReference": (
            {
                "relativePath": session.article_reference.relative_path,
                "title": session.article_reference.title,
                "sourceSnapshot": session.article_reference.source_snapshot,
                "referenceSnapshot": session.article_reference.reference_snapshot,
            }
            if session.article_reference else None
        ),
        "attempts": [
            {
                "id": attempt.id,
                "scope": attempt.scope.value,
                "translation": attempt.translation,
                "createdAt": attempt.created_at,
                "segmentIds": list(attempt.segment_ids),
                "revisionOf": attempt.revision_of,
                "review": (
                    {
                        "id": attempt.review.id,
                        "createdAt": attempt.review.created_at,
                        "categories": dict(attempt.review.categories),
                        "summary": attempt.review.summary,
                        "suggestedTranslation": attempt.review.suggested_translation,
                        "score": attempt.review.score,
                        "promptSnapshot": attempt.review.prompt_snapshot,
                        "modelSettings": attempt.review.model_settings,
                    }
                    if attempt.review else None
                ),
            }
            for attempt in session.attempts
        ],
        "segmentDrafts": dict(session.segment_drafts),
        "completeTextDraft": session.complete_text_draft,
        "lastAutosavedAt": session.last_autosaved_at,
        "revision": revision,
    }


def _remember_session(session: PracticeSession, *, increment_revision: bool = False) -> PracticeSession:
    with _PRACTICE_LOCK:
        _PRACTICE_DRAFTS[session.id] = session
        current = _PRACTICE_REVISIONS.get(session.id, 0)
        _PRACTICE_REVISIONS[session.id] = current + (1 if increment_revision else 0)
        while len(_PRACTICE_DRAFTS) > 64:
            oldest = next(iter(_PRACTICE_DRAFTS))
            _PRACTICE_DRAFTS.pop(oldest, None)
            _PRACTICE_REVISIONS.pop(oldest, None)
    return session


def _load_practice_session(session_id: str) -> PracticeSession:
    with _PRACTICE_LOCK:
        session = _PRACTICE_DRAFTS.get(session_id)
    if session is None:
        session = _practice_service().load_session(session_id)
        _remember_session(session)
    return session


def _check_practice_revision(session_id: str, payload: Mapping[str, Any]) -> None:
    with _PRACTICE_LOCK:
        _check_practice_revision_locked(session_id, payload)


def _check_practice_revision_locked(session_id: str, payload: Mapping[str, Any]) -> None:
    if payload.get("revision") is None:
        return
    try:
        received = int(payload["revision"])
    except (TypeError, ValueError) as exc:
        raise OperationError("invalid_revision", "The practice revision is invalid.") from exc
    current = _PRACTICE_REVISIONS.get(session_id, 0)
    if received != current:
        raise OperationError(
            "stale_practice_revision",
            "This practice session changed in another request. Reload it before saving.",
            retryable=True,
            safe_details={"currentRevision": current},
        )


def _claim_practice_mutation(
    session_id: str, payload: Mapping[str, Any]
) -> tuple[PracticeSession, str]:
    _load_practice_session(session_id)
    with _PRACTICE_LOCK:
        if session_id in _PRACTICE_MUTATIONS:
            raise OperationError(
                "practice_session_busy",
                "This practice session is being updated. Wait for that operation and reload before saving.",
                retryable=True,
            )
        _check_practice_revision_locked(session_id, payload)
        session = _PRACTICE_DRAFTS.get(session_id)
        if session is None:
            raise OperationError("practice_not_found", "The practice session is unavailable.")
        token = secrets.token_hex(16)
        _PRACTICE_MUTATIONS[session_id] = token
        return session, token


def _commit_practice_mutation(
    session: PracticeSession, token: str
) -> PracticeSession:
    with _PRACTICE_LOCK:
        if _PRACTICE_MUTATIONS.get(session.id) != token:
            raise OperationError(
                "stale_practice_revision",
                "This practice session changed in another request. Reload it before saving.",
                retryable=True,
            )
        _PRACTICE_DRAFTS[session.id] = session
        _PRACTICE_REVISIONS[session.id] = _PRACTICE_REVISIONS.get(session.id, 0) + 1
        _PRACTICE_MUTATIONS.pop(session.id, None)
    return session


def _abort_practice_mutation(session_id: str, token: str) -> None:
    with _PRACTICE_LOCK:
        if _PRACTICE_MUTATIONS.get(session_id) == token:
            _PRACTICE_MUTATIONS.pop(session_id, None)


def _practice_review_snapshot(
    session_id: str, payload: Mapping[str, Any]
) -> tuple[PracticeSession, int]:
    _load_practice_session(session_id)
    with _PRACTICE_LOCK:
        _check_practice_revision_locked(session_id, payload)
        session = _PRACTICE_DRAFTS.get(session_id)
        if session is None:
            raise OperationError("practice_not_found", "The practice session is unavailable.")
        return session, _PRACTICE_REVISIONS.get(session_id, 0)


def _commit_practice_review(
    session: PracticeSession,
    expected_revision: int,
    *,
    expected_session: PracticeSession,
    persist: bool,
) -> PracticeSession:
    """CAS a provider result without blocking concurrent draft autosaves."""
    with _PRACTICE_LOCK:
        current = _PRACTICE_REVISIONS.get(session.id, 0)
        if (
            current != expected_revision
            or _PRACTICE_DRAFTS.get(session.id) is not expected_session
        ):
            raise OperationError(
                "stale_practice_revision",
                "This practice session changed while the review was running. Your newer draft was preserved; submit it again when ready.",
                retryable=True,
                safe_details={"currentRevision": current},
            )
        if persist:
            _practice_service().save_session(session)
        _PRACTICE_DRAFTS[session.id] = session
        _PRACTICE_REVISIONS[session.id] = current + 1
    return session


def _safe_config_payload(config: Mapping[str, Any]) -> dict[str, Any]:
    """Return configuration metadata without local credentials or private extras."""
    normalized = normalize_config(config)
    try:
        public_base_url = _safe_public_base_url(normalized.get("base_url"), allow_empty=True)
    except OperationError:
        public_base_url = ""
    return {
        "configSchemaVersion": normalized.get("config_schema_version"),
        "apiSettings": {
            "providerId": normalized.get("selected_provider_profile") or "custom",
            "baseUrl": public_base_url,
            "model": normalized.get("model") or "",
            "temperature": normalized.get("temperature"),
            "maxTokens": normalized.get("max_tokens"),
            "hasApiKey": bool(normalized.get("api_key")),
            "selectedProfileId": normalized.get("selected_llm_api_profile_id") or "",
        },
        "desktopSettings": _desktop_settings_payload(normalized),
        "reasoning": reasoning_intent_to_dict(reasoning_intent_from_config(normalized.get("reasoning"))),
        "selectedScoringPresetId": normalized.get("selected_scoring_preset_id"),
        "selectedPromptPresetId": normalized.get("selected_prompt_preset_id"),
        "uiLanguage": normalized.get("ui_language") or "zh",
        "uiTheme": normalized.get("ui_theme") or "light",
    }


def _safe_public_base_url(value: Any, *, allow_empty: bool = False) -> str:
    text = str(value or "").strip().rstrip("/")
    if not text and allow_empty:
        return ""
    try:
        parsed = urllib.parse.urlsplit(text)
        port = parsed.port
    except (ValueError, TypeError) as exc:
        raise OperationError("invalid_base_url", "Enter a valid HTTP or HTTPS provider base URL.") from exc
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise OperationError(
            "invalid_base_url",
            "Provider base URLs must use HTTP or HTTPS and cannot contain credentials, query parameters, or fragments.",
        )
    hostname = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    authority = f"{hostname}:{port}" if port is not None else hostname
    return urllib.parse.urlunsplit((parsed.scheme, authority, parsed.path.rstrip("/"), "", ""))


def _safe_api_settings_payload(config: Mapping[str, Any]) -> dict[str, Any]:
    from mock_data import _api_settings_payload

    result = _api_settings_payload(dict(config))
    try:
        result["baseUrl"] = _safe_public_base_url(result.get("baseUrl"), allow_empty=True)
    except OperationError:
        result["baseUrl"] = ""
    profiles = []
    for raw in result.get("profiles") or []:
        if not isinstance(raw, Mapping):
            continue
        profile = dict(raw)
        try:
            profile["baseUrl"] = _safe_public_base_url(profile.get("baseUrl"), allow_empty=True)
        except OperationError:
            profile["baseUrl"] = ""
        profiles.append(profile)
    result["profiles"] = profiles
    return result


def _provider_context(config: Mapping[str, Any]) -> tuple[str, Any, ModelRequestSettings, OpenAICompatibleTransport]:
    provider_id = str(config.get("selected_provider_profile") or "custom")
    capabilities = known_provider_capabilities(provider_id)
    settings = ModelRequestSettings(
        model=str(config.get("model") or ""),
        max_output_tokens=int(config.get("max_tokens") or 30000),
        temperature=(float(config["temperature"]) if config.get("temperature") is not None else None),
        top_p=(float(config["top_p"]) if config.get("top_p") is not None else None),
        reasoning=reasoning_intent_from_config(config.get("reasoning")),
        use_native_structured_output=bool(config.get("use_native_structured_output", False)),
        extra_body=(config.get("extra_body") if isinstance(config.get("extra_body"), Mapping) else {}),
    )
    return provider_id, capabilities, settings, OpenAICompatibleTransport(dict(config), timeout=90)


def _strict_reasoning_intent(raw: Any) -> ReasoningIntent:
    if not isinstance(raw, Mapping):
        raise OperationError("invalid_reasoning", "Reasoning settings must be an object.")
    try:
        mode = ReasoningMode(str(raw.get("mode") or "provider_default"))
        control = ReasoningControl(str(raw["control"])) if raw.get("control") else None
        effort = str(raw["effort"]) if raw.get("effort") is not None else None
        budget_raw = raw.get("budgetTokens", raw.get("budget_tokens"))
        budget = int(budget_raw) if budget_raw is not None else None
        return ReasoningIntent(mode, control, effort, budget)
    except (ValueError, TypeError, ProviderConfigurationError) as exc:
        code = getattr(exc, "code", "invalid_reasoning")
        message = str(exc) if isinstance(exc, ProviderConfigurationError) else "Reasoning settings are invalid."
        raise OperationError(code, message) from exc


def _reasoning_bridge_payload(intent: ReasoningIntent) -> dict[str, Any]:
    result: dict[str, Any] = {"mode": intent.mode.value}
    if intent.mode is ReasoningMode.EXPLICIT:
        result["control"] = intent.control.value if intent.control else None
        if intent.control is ReasoningControl.EFFORT:
            result["effort"] = intent.effort
        else:
            result["budgetTokens"] = intent.budget_tokens
    return result


def _build_reasoning_settings(
    config: Mapping[str, Any], intent: ReasoningIntent
):
    capabilities = known_provider_capabilities(
        str(config.get("selected_provider_profile") or "custom")
    )
    settings = ModelRequestSettings(
        model=str(config.get("model") or ""),
        max_output_tokens=int(config.get("max_tokens") or 30000),
        temperature=(float(config["temperature"]) if config.get("temperature") is not None else None),
        top_p=(float(config["top_p"]) if config.get("top_p") is not None else None),
        reasoning=intent,
        use_native_structured_output=bool(config.get("use_native_structured_output", False)),
        extra_body=(dict(config.get("extra_body") or {}) if isinstance(config.get("extra_body"), Mapping) else {}),
    )
    from dairr_core.prompt_templates import RenderedPrompt
    preview = RenderedPrompt(
        PromptTask.PREPROCESSING,
        "",
        "Preview request settings only. Response contract: {}",
        ResponseMode.STRUCTURED,
        "{}",
        1,
        (),
    )
    return settings.build(capabilities, preview), capabilities


def _strict_prompt_registry_import(imported: Mapping[str, Any]) -> Any:
    registry = default_prompt_registry()
    task_overrides = imported.get("task_overrides", {})
    provider_overrides = imported.get("provider_overrides", {})
    profile_overrides = imported.get("profile_overrides", {})
    if not all(isinstance(value, Mapping) for value in (task_overrides, provider_overrides, profile_overrides)):
        raise OperationError("invalid_prompt_import", "Prompt override groups must be JSON objects.")
    try:
        for task_name, raw in task_overrides.items():
            task = PromptTask(str(task_name))
            if not isinstance(raw, Mapping):
                raise ValueError
            registry.register_default(_prompt_template_from_payload(task, raw))
        for provider_id, tasks in provider_overrides.items():
            if not str(provider_id).strip() or not isinstance(tasks, Mapping):
                raise ValueError
            for task_name, raw in tasks.items():
                task = PromptTask(str(task_name))
                if not isinstance(raw, Mapping):
                    raise ValueError
                registry.register_override(
                    _prompt_template_from_payload(task, raw), provider_id=str(provider_id)
                )
        for profile_id, tasks in profile_overrides.items():
            if not str(profile_id).strip() or not isinstance(tasks, Mapping):
                raise ValueError
            for task_name, raw in tasks.items():
                task = PromptTask(str(task_name))
                if not isinstance(raw, Mapping):
                    raise ValueError
                registry.register_override(
                    _prompt_template_from_payload(task, raw), profile_id=str(profile_id)
                )
    except (ValueError, TypeError, PromptTemplateError) as exc:
        raise OperationError("invalid_prompt_import", "A prompt override is invalid.") from exc
    return registry


def _capability_message(capability: Capability) -> str:
    if capability.available:
        return "Available."
    return {
        CapabilityReason.CONNECTION_FAILED: "Start Anki and enable standard AnkiConnect, then try again.",
        CapabilityReason.TIMEOUT: "AnkiConnect timed out. Check Anki and retry.",
        CapabilityReason.FSRS_NOT_AVAILABLE: "This signal is not exposed by standard AnkiConnect.",
        CapabilityReason.HOST_MODE_LIMITATION: "Unavailable in standalone mode.",
        CapabilityReason.PROVIDER_LIMITATION: "The selected provider does not support this setting.",
        CapabilityReason.OPTIONAL_EXTENSION_NOT_INSTALLED: "An optional extension is required.",
    }.get(capability.reason, "Temporarily unavailable.")


def _capability_snapshot() -> dict[str, Any]:
    config = _load_generation_config()
    provider = known_provider_capabilities(str(config.get("selected_provider_profile") or "custom"))
    values: dict[CapabilityId, Capability] = {
        CapabilityId.INTERNAL_ANKI_APIS: Capability(
            CapabilityId.INTERNAL_ANKI_APIS, CapabilityStatus.UNAVAILABLE_IN_MODE,
            CapabilityReason.HOST_MODE_LIMITATION, Provenance.ANKICONNECT_STANDARD,
            "Standalone mode never imports Anki internals.",
        ),
        CapabilityId.ARTICLE_HISTORY: Capability(
            CapabilityId.ARTICLE_HISTORY, CapabilityStatus.AVAILABLE,
            provenance=Provenance.LOCAL_HISTORY, detail="Local Markdown article history.",
        ),
        CapabilityId.PASTED_TEXT_PRACTICE: Capability(
            CapabilityId.PASTED_TEXT_PRACTICE, CapabilityStatus.AVAILABLE,
            provenance=Provenance.SHARED_CORE, detail="Works independently of Anki.",
        ),
        CapabilityId.CUSTOM_PROMPTS: Capability(
            CapabilityId.CUSTOM_PROMPTS, CapabilityStatus.AVAILABLE,
            provenance=Provenance.USER_CONFIGURED, detail="All model task templates are visible and editable.",
        ),
        CapabilityId.PROVIDER_REASONING: Capability(
            CapabilityId.PROVIDER_REASONING,
            CapabilityStatus.AVAILABLE if provider.supports_reasoning else CapabilityStatus.PROVIDER_UNSUPPORTED,
            CapabilityReason.NONE if provider.supports_reasoning else CapabilityReason.PROVIDER_LIMITATION,
            Provenance.PROVIDER_DECLARED,
            "Explicit controls are limited to declared provider capabilities.",
        ),
        CapabilityId.CANCELLATION: Capability(
            CapabilityId.CANCELLATION, CapabilityStatus.AVAILABLE,
            provenance=Provenance.SHARED_CORE, detail="Long operations support cooperative cancellation.",
        ),
    }
    if _LAST_ANKI_CAPABILITIES is not None:
        for capability_id in (CapabilityId.ANKI_CONNECTION, CapabilityId.REVIEW_HISTORY,
                              CapabilityId.FSRS_VALUES, CapabilityId.TARGET_CARD_SCORING):
            try:
                values[capability_id] = _LAST_ANKI_CAPABILITIES.get(capability_id)
            except KeyError:
                pass
    for capability_id in (CapabilityId.ANKI_CONNECTION, CapabilityId.REVIEW_HISTORY,
                          CapabilityId.FSRS_VALUES, CapabilityId.TARGET_CARD_SCORING):
        values.setdefault(
            capability_id,
            Capability(
                capability_id, CapabilityStatus.TEMPORARILY_UNAVAILABLE,
                CapabilityReason.UNKNOWN, Provenance.ANKICONNECT_STANDARD,
                "Run the Anki signal check to refresh this state.",
            ),
        )
    serialized = CapabilitySet(values.values()).to_dict()
    for row in serialized.values():
        capability = values[CapabilityId(row["id"])]
        row["message"] = _capability_message(capability)
    return {"capabilities": serialized, "practiceLimits": dict(PRACTICE_LIMITS_PAYLOAD)}


def _prompt_template_payload(template: PromptTemplate) -> dict[str, Any]:
    return {
        "task": template.task.value,
        "name": template.name,
        "version": template.version,
        "systemTemplate": template.system_template,
        "userTemplate": template.user_template,
        "responseMode": template.response_mode.value,
        "responseContract": template.response_contract,
        "variables": [
            {
                "name": variable.name,
                "description": variable.description,
                "required": variable.required,
                "example": variable.example,
            }
            for variable in template.documented_variables
        ],
    }


def _prompt_template_from_payload(task: PromptTask, payload: Mapping[str, Any]) -> PromptTemplate:
    base = default_prompt_registry().defaults[task]
    return PromptTemplate(
        task=task,
        name=str(payload.get("name") or base.name),
        version=int(payload.get("version") or base.version),
        system_template=str(payload.get("systemTemplate") if "systemTemplate" in payload else payload.get("system_template") or ""),
        user_template=str(payload.get("userTemplate") if "userTemplate" in payload else payload.get("user_template") or ""),
        response_mode=ResponseMode(str(payload.get("responseMode") or payload.get("response_mode") or base.response_mode.value)),
        response_contract=str(payload.get("responseContract") if "responseContract" in payload else payload.get("response_contract") or ""),
        variables=base.variables,
    )


def _prompt_scope(payload: Mapping[str, Any]) -> tuple[str, str, str]:
    scope = str(payload.get("scope") or "task")
    provider_id = str(payload.get("providerId") or "").strip()
    profile_id = str(payload.get("profileId") or "").strip()
    if scope == "provider" and not provider_id:
        raise OperationError("missing_provider", "Choose a provider for this prompt override.")
    if scope == "profile" and not profile_id:
        raise OperationError("missing_profile", "Choose a profile for this prompt override.")
    if scope not in {"task", "provider", "profile"}:
        raise OperationError("invalid_prompt_scope", "The prompt override scope is invalid.")
    return scope, provider_id, profile_id


def _save_prompt_registry(config: dict[str, Any], registry: Any) -> None:
    config["ai_prompt_config"] = export_prompt_registry_overrides(
        registry,
        existing=config.get("ai_prompt_config"),
    )
    _save_desktop_config(config)


def _remove_prompt_override(config: dict[str, Any], task: PromptTask, payload: Mapping[str, Any]) -> None:
    scope, provider_id, profile_id = _prompt_scope(payload)
    stored = normalize_prompt_config(config.get("ai_prompt_config"))
    if scope == "task":
        stored["task_overrides"].pop(task.value, None)
    elif scope == "provider":
        tasks = stored["provider_overrides"].get(provider_id)
        if isinstance(tasks, dict):
            tasks.pop(task.value, None)
            if not tasks:
                stored["provider_overrides"].pop(provider_id, None)
    else:
        tasks = stored["profile_overrides"].get(profile_id)
        if isinstance(tasks, dict):
            tasks.pop(task.value, None)
            if not tasks:
                stored["profile_overrides"].pop(profile_id, None)
    config["ai_prompt_config"] = stored
    _save_desktop_config(config)


def _load_study_signals(payload: Mapping[str, Any]) -> tuple[list[Any], CapabilitySet, list[dict[str, str]]]:
    global _LAST_ANKI_CAPABILITIES
    if str(os.environ.get("DAIRR_DESKTOP_PROVIDER") or "mock") != "ankiconnect":
        raise OperationError(
            "ankiconnect_not_selected",
            "Select the AnkiConnect source to load Anki study signals. Pasted-text practice remains available.",
        )
    from ankiconnect_data_adapter import AnkiConnectDataAdapter

    provider = get_deck_provider()
    adapter = AnkiConnectDataAdapter(provider)
    authoritative_bounds = bool(payload.get("dayBoundsAuthoritative"))
    day_start = payload.get("dayStartMs") if authoritative_bounds else None
    day_end = payload.get("dayEndMs") if authoritative_bounds else None
    if authoritative_bounds and (day_start is None or day_end is None):
        raise OperationError(
            "missing_anki_day_bounds",
            "Authoritative Anki-day bounds require both start and end timestamps.",
        )
    try:
        signals = adapter.collect_today_signals(
            day_start_ms=(int(day_start) if day_start is not None else None),
            day_end_ms=(int(day_end) if day_end is not None else None),
        )
    except AnkiConnectError as exc:
        _LAST_ANKI_CAPABILITIES = adapter.capabilities(authoritative_day_bounds=authoritative_bounds)
        raise OperationError(
            "ankiconnect_unavailable",
            str(exc),
            retryable=exc.failure is not getattr(type(exc.failure), "INCOMPATIBLE_VERSION", None),
            safe_details={"failure": exc.failure.value},
        ) from exc
    _LAST_ANKI_CAPABILITIES = adapter.capabilities(authoritative_day_bounds=authoritative_bounds)
    signals = apply_article_history_evidence(
        signals,
        articles_dir=DesktopDeckAdapter()._articles_dir,
    )
    issues = [
        {"reason": issue.reason.value, "action": issue.action, "detail": issue.detail}
        for issue in adapter.issues
    ]
    return signals, _LAST_ANKI_CAPABILITIES, issues


def _run_release_operation(action: str, payload: dict[str, Any], context: OperationContext) -> dict[str, Any]:
    if action == "loadStudySignals":
        signals, capabilities, issues = _load_study_signals(payload)
        return {
            "candidateCount": len(signals),
            "candidates": [
                {
                    "cardId": item.identity.stable_id,
                    "sourceId": item.identity.source_id,
                    "localCardId": item.identity.card_id,
                    "noteId": item.identity.note_id,
                    "term": item.term,
                    "metadata": {
                        key: value for key, value in item.metadata.items()
                        if key not in {"fields"}
                    },
                }
                for item in signals
            ],
            "capabilities": capabilities.to_dict(),
            "issues": issues,
        }
    if action == "previewScoring":
        signals, capabilities, issues = _load_study_signals(payload)
        preset_payload = payload.get("preset")
        if isinstance(preset_payload, Mapping):
            preset = ScoringPreset.from_dict(preset_payload)
        else:
            config = _load_generation_config()
            selected_id = str(payload.get("presetId") or config.get("selected_scoring_preset_id") or "")
            stored = next((item for item in config.get("scoring_presets", []) if item.get("id") == selected_id), None)
            preset = ScoringPreset.from_dict(stored) if isinstance(stored, Mapping) else recommended_preset()
        scores = score_cards(signals, preset)
        overrides = tuple(
            ManualOverride.from_dict(item) for item in (payload.get("manualOverrides") or [])
            if isinstance(item, Mapping)
        )
        selection = select_targets(scores, preset.selection, overrides, tuple(payload.get("explicitOrder") or ()))
        return {
            "preset": preset.to_dict(),
            "selection": selection.to_dict(),
            "capabilities": capabilities.to_dict(),
            "issues": issues,
        }
    if action == "submitPracticeReview":
        session_id = str(payload.get("sessionId") or "")
        session, expected_revision = _practice_review_snapshot(session_id, payload)
        config = _load_generation_config()
        provider_id, capabilities, settings, transport = _provider_context(config)
        completed = _practice_service().review(
            session,
            str(payload.get("translation") or ""),
            registry=prompt_registry_from_config(config),
            provider_capabilities=capabilities,
            request_settings=settings,
            transport=transport,
            context=context,
            segment_id=(str(payload.get("segmentId")) if payload.get("segmentId") else None),
            revision_of=(str(payload.get("revisionOf")) if payload.get("revisionOf") else None),
            provider_id=provider_id,
            profile_id=str(config.get("selected_llm_api_profile_id") or ""),
            # Persistence happens only after the revision compare-and-swap.
            persist=False,
        )
        _commit_practice_review(
            completed.session,
            expected_revision,
            expected_session=session,
            persist=bool(payload.get("persist", True)),
        )
        result = completed.result
        return {
            "session": _session_payload(completed.session),
            "attemptId": completed.attempt_id,
            "review": {
                "categories": {key: list(values) for key, values in result.categories.items()},
                "suggestedRevision": result.suggested_revision,
                "overall": result.overall,
                "plainText": result.plain_text,
                "referenceUsed": result.reference_used,
                "warnings": list(result.warnings),
                "possiblyTruncated": result.possibly_truncated,
            },
        }
    if action == "generateTargetAware":
        config = _load_generation_config()
        provider_id, capabilities, settings, transport = _provider_context(config)
        targets = tuple(
            GenerationTarget(
                str(item.get("id") or ""),
                str(item.get("text") or item.get("target") or ""),
                TargetCategory(str(item.get("category") or "optional")),
                tuple(str(value) for value in (item.get("equivalentForms") or ()) if str(value).strip()),
            )
            for item in (payload.get("targets") or ()) if isinstance(item, Mapping)
        )
        request = ArticleGenerationRequest(
            target_language=str(payload.get("targetLanguage") or ""),
            targets=targets,
            source_text=str(payload.get("sourceText") or ""),
            source_language=str(payload.get("sourceLanguage") or ""),
            proficiency_level=str(payload.get("proficiencyLevel") or ""),
            genre=str(payload.get("genre") or ""),
            desired_length=str(payload.get("desiredLength") or ""),
            style=str(payload.get("style") or ""),
            custom_instructions=str(payload.get("customInstructions") or ""),
        )
        result = generate_target_aware_article(
            request,
            registry=prompt_registry_from_config(config),
            provider_capabilities=capabilities,
            request_settings=settings,
            transport=transport,
            context=context,
            provider_id=provider_id,
            profile_id=str(config.get("selected_llm_api_profile_id") or ""),
        )
        response = result.to_dict()
        if payload.get("saveArticle"):
            legacy_article = "[ARTICLE_TITLE]\n" + result.title + "\n[MAIN_ARTICLE]\n" + result.article
            outcomes = [item.to_dict() for item in result.target_outcomes]
            saved = DesktopDeckAdapter().save_article(
                str(payload.get("deckName") or "DAIRR"),
                [],
                legacy_article,
                generation_metadata={
                    "targets": [item.prompt_dict() for item in targets],
                    "target_usage": [item for item in outcomes if item["used"]],
                    "unused_targets": [item for item in outcomes if not item["used"]],
                },
            )
            response["savedArticle"] = {key: str(value) for key, value in saved.items()}
        return response
    raise OperationError("unknown_action", "The requested bridge action is unavailable.")


def _handle_release_action(action: str, payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    config = _load_generation_config()
    if action == "getCapabilities":
        return "capabilitiesLoaded", _capability_snapshot()
    if action == "createPastedPractice":
        session = _practice_service().create_pasted(
            str(payload.get("sourceText") or ""),
            str(payload.get("sourceLanguage") or "auto"),
            str(payload.get("targetLanguage") or ""),
            direction=TranslationDirection(str(payload.get("direction") or "source_to_target")),
            proficiency_level=(str(payload.get("proficiencyLevel")) if payload.get("proficiencyLevel") else None),
            custom_review_instructions=str(payload.get("customReviewInstructions") or ""),
            save=bool(payload.get("save", False)),
        )
        _remember_session(session)
        return "practiceSessionCreated", {"session": _session_payload(session), "saved": bool(payload.get("save", False))}
    if action == "createArticlePractice":
        article_path = str(payload.get("articlePath") or "")
        loaded = _load_desktop_article(article_path)
        direction = TranslationDirection(str(payload.get("direction") or "back_translation"))
        derived_source, derived_references, derived_title = _article_practice_material(
            str(loaded.get("article") or ""), direction
        )
        source_text = str(payload.get("sourceText") or derived_source)
        reference_values = payload.get("referenceParagraphs")
        references = (
            [str(value) if value is not None else None for value in reference_values]
            if isinstance(reference_values, list) else derived_references
        )
        article_root = DesktopDeckAdapter()._articles_dir.resolve()
        try:
            relative_path = Path(article_path).resolve().relative_to(article_root).as_posix()
        except (OSError, ValueError) as exc:
            raise OperationError("invalid_article_reference", "Choose an article from DAIRR history.") from exc
        session = _practice_service().create_from_article(
            source_text,
            str(payload.get("sourceLanguage") or ""),
            str(payload.get("targetLanguage") or ""),
            ArticleReference(
                relative_path,
                str(payload.get("title") or loaded.get("title") or derived_title),
                source_text,
                ("\n\n".join(value or "" for value in references) if references else None),
            ),
            reference_paragraphs=references,
            direction=direction,
            proficiency_level=(str(payload.get("proficiencyLevel")) if payload.get("proficiencyLevel") else None),
            custom_review_instructions=str(payload.get("customReviewInstructions") or ""),
            save=bool(payload.get("save", True)),
        )
        _remember_session(session)
        return "practiceSessionCreated", {"session": _session_payload(session), "saved": bool(payload.get("save", True))}
    if action == "listPracticeSessions":
        sessions = []
        for session_id in _practice_repository().list_ids():
            try:
                session = _practice_repository().load(session_id)
            except Exception:
                continue
            sessions.append({
                "id": session.id, "kind": session.kind.value, "direction": session.direction.value,
                "sourceLanguage": session.source_language, "targetLanguage": session.target_language,
                "status": session.status.value, "updatedAt": session.updated_at,
                "attemptCount": len(session.attempts),
                "articleTitle": session.article_reference.title if session.article_reference else "",
            })
        sessions.sort(key=lambda item: item["updatedAt"], reverse=True)
        return "practiceSessionsLoaded", {"sessions": sessions}
    if action == "loadPracticeSession":
        session = _load_practice_session(str(payload.get("sessionId") or ""))
        return "practiceSessionLoaded", {"session": _session_payload(session)}
    if action == "savePracticeDraft":
        session_id = str(payload.get("sessionId") or "")
        session, claim = _claim_practice_mutation(session_id, payload)
        try:
            updated = _practice_service().save_draft(
                session,
                str(payload.get("translation") or ""),
                segment_id=(str(payload.get("segmentId")) if payload.get("segmentId") else None),
                persist=bool(payload.get("persist", True)),
            )
            _commit_practice_mutation(updated, claim)
        except BaseException:
            _abort_practice_mutation(session_id, claim)
            raise
        return "practiceDraftSaved", {"session": _session_payload(updated), "persisted": bool(payload.get("persist", True))}
    if action == "updatePracticeSegments":
        session_id = str(payload.get("sessionId") or "")
        session, claim = _claim_practice_mutation(session_id, payload)
        try:
            if session.attempts:
                raise OperationError("segmentation_locked", "Source segmentation cannot change after review attempts exist.")
            raw_segments = payload.get("segments")
            if not isinstance(raw_segments, list) or not raw_segments:
                raise OperationError("invalid_segments", "Provide at least one ordered practice segment.")
            segments = tuple(
                PracticeSegment(
                    str(item.get("id") or ""), index,
                    str(item.get("sourceText") or ""),
                    (str(item.get("referenceText")) if item.get("referenceText") is not None else None),
                )
                for index, item in enumerate(raw_segments) if isinstance(item, Mapping)
            )
            if len(segments) != len(raw_segments):
                raise OperationError("invalid_segments", "Each practice segment must be an object.")
            updated = session.with_segments(segments)
            if payload.get("persist", True):
                _practice_service().save_session(updated)
            _commit_practice_mutation(updated, claim)
        except BaseException:
            _abort_practice_mutation(session_id, claim)
            raise
        return "practiceSegmentsUpdated", {"session": _session_payload(updated)}
    if action == "deletePracticeSession":
        session_id = str(payload.get("sessionId") or "")
        deleted = _practice_repository().delete(session_id)
        with _PRACTICE_LOCK:
            if session_id in _PRACTICE_MUTATIONS:
                raise OperationError(
                    "practice_session_busy",
                    "This practice session is being updated. Wait for that operation before deleting it.",
                    retryable=True,
                )
            _PRACTICE_DRAFTS.pop(session_id, None)
            _PRACTICE_REVISIONS.pop(session_id, None)
            _PRACTICE_MUTATIONS.pop(session_id, None)
        return "practiceSessionDeleted", {"sessionId": session_id, "deleted": deleted}
    if action in {"getScoringConfig", "resetScoringConfig", "saveScoringConfig", "importScoringConfig", "exportScoringConfig"}:
        presets = list(config.get("scoring_presets") or [recommended_preset().to_dict()])
        selected_id = str(config.get("selected_scoring_preset_id") or presets[0]["id"])
        if action == "resetScoringConfig":
            preset = recommended_preset()
            presets = [item for item in presets if item.get("id") != preset.id] + [preset.to_dict()]
            selected_id = preset.id
        elif action == "saveScoringConfig":
            raw = payload.get("preset")
            if not isinstance(raw, Mapping):
                raise OperationError("invalid_scoring_preset", "The scoring preset must be an object.")
            preset = ScoringPreset.from_dict(raw)
            presets = [item for item in presets if item.get("id") != preset.id] + [preset.to_dict()]
            selected_id = preset.id
        elif action == "importScoringConfig":
            preset = import_preset(str(payload.get("serialized") or ""))
            presets = [item for item in presets if item.get("id") != preset.id] + [preset.to_dict()]
            selected_id = preset.id
        elif action == "exportScoringConfig":
            stored = next((item for item in presets if item.get("id") == str(payload.get("presetId") or selected_id)), None)
            preset = ScoringPreset.from_dict(stored) if isinstance(stored, Mapping) else recommended_preset()
            return "scoringConfigExported", {"serialized": export_preset(preset), "presetId": preset.id}
        if action != "getScoringConfig":
            config["scoring_presets"] = presets
            config["selected_scoring_preset_id"] = selected_id
            _save_desktop_config(config)
        metadata = {
            mode.value: [
                {"signal": item.name.value, "label": item.label, "explanation": item.explanation,
                 "simpleControl": item.simple_control}
                for item in signal_metadata(mode)
            ]
            for mode in (SettingsMode.SIMPLE, SettingsMode.ADVANCED)
        }
        return "scoringConfigLoaded", {"presets": presets, "selectedPresetId": selected_id, "signalMetadata": metadata}
    if action in {"listPromptTemplates", "getPromptTemplate", "savePromptTemplate", "resetPromptTemplate", "importPromptTemplates", "exportPromptTemplates", "previewPrompt"}:
        registry = prompt_registry_from_config(config)
        if action == "listPromptTemplates":
            return "promptTemplatesLoaded", {"templates": [_prompt_template_payload(registry.resolve(task)) for task in PromptTask]}
        if action == "importPromptTemplates":
            try:
                imported = json.loads(str(payload.get("serialized") or ""))
            except json.JSONDecodeError as exc:
                raise OperationError("invalid_prompt_import", "Prompt presets are not valid JSON.") from exc
            if not isinstance(imported, Mapping):
                raise OperationError("invalid_prompt_import", "Prompt presets must be a JSON object.")
            # Validate every imported override; invalid entries are rejected
            # rather than silently disappearing during normalization.
            candidate_registry = _strict_prompt_registry_import(imported)
            config["ai_prompt_config"] = normalize_prompt_config(imported)
            _save_desktop_config(config)
            registry = candidate_registry
            return "promptTemplatesLoaded", {"templates": [_prompt_template_payload(registry.resolve(task)) for task in PromptTask]}
        if action == "exportPromptTemplates":
            return "promptTemplatesExported", {"serialized": json.dumps(config.get("ai_prompt_config") or {}, ensure_ascii=False, indent=2)}
        task = PromptTask(str(payload.get("task") or ""))
        scope, provider_id, profile_id = _prompt_scope(payload)
        if action == "savePromptTemplate":
            raw_template = payload.get("template")
            if not isinstance(raw_template, Mapping):
                raise OperationError("invalid_prompt_template", "The prompt template must be an object.")
            template = _prompt_template_from_payload(task, raw_template)
            if scope == "task":
                registry.register_default(template)
            else:
                registry.register_override(template, provider_id=provider_id if scope == "provider" else "", profile_id=profile_id if scope == "profile" else "")
            _save_prompt_registry(config, registry)
            return "promptTemplateSaved", {"template": _prompt_template_payload(template), "scope": scope}
        if action == "resetPromptTemplate":
            _remove_prompt_override(config, task, payload)
            template = prompt_registry_from_config(config).resolve(task, provider_id=provider_id, profile_id=profile_id)
            return "promptTemplateReset", {"template": _prompt_template_payload(template), "scope": scope}
        template = registry.resolve(task, provider_id=provider_id, profile_id=profile_id)
        if action == "getPromptTemplate":
            return "promptTemplateLoaded", {"template": _prompt_template_payload(template), "scope": scope}
        preview_template = payload.get("template")
        if isinstance(preview_template, Mapping):
            template = _prompt_template_from_payload(task, preview_template)
        values = payload.get("values") if isinstance(payload.get("values"), Mapping) else {}
        referenced = {item.name for item in template.documented_variables if "{" + item.name in (template.system_template + template.user_template)}
        missing = sorted(name for name in referenced if name != "output_format_contract" and (name not in values or values[name] is None))
        if missing:
            return "promptPreview", {
                "task": task.value, "system": "", "user": "", "responseContract": template.response_contract,
                "messages": [], "missingVariables": missing, "effectiveSettings": None,
            }
        rendered = render_prompt(template, values)
        _provider_id, capabilities, settings, _transport = _provider_context(config)
        built = settings.build(capabilities, rendered)
        return "promptPreview", {
            "task": task.value, "system": rendered.system, "user": rendered.user,
            "responseContract": rendered.response_contract, "messages": list(rendered.messages),
            "missingVariables": [], "effectiveSettings": built.effective_settings.to_safe_dict(),
        }
    if action in {"getReasoningSettings", "saveReasoningSettings", "previewReasoningSettings"}:
        if action == "saveReasoningSettings":
            intent = _strict_reasoning_intent(payload.get("reasoning"))
            # Validate the proposed intent against every currently effective
            # request setting before persisting it.
            _build_reasoning_settings(config, intent)
            config["reasoning"] = reasoning_intent_to_dict(intent)
            _save_desktop_config(config)
        elif action == "previewReasoningSettings":
            intent = _strict_reasoning_intent(payload.get("reasoning") if payload.get("reasoning") is not None else config.get("reasoning"))
            built, capabilities = _build_reasoning_settings(config, intent)
            return "reasoningSettingsPreview", {
                "reasoning": _reasoning_bridge_payload(intent),
                "capabilities": {
                    "supportsReasoning": capabilities.supports_reasoning,
                    "controls": sorted(item.value for item in capabilities.reasoning_controls),
                    "effortLevels": list(capabilities.effort_levels),
                    "minimumBudgetTokens": capabilities.minimum_budget_tokens,
                    "maximumBudgetTokens": capabilities.maximum_budget_tokens,
                },
                "effectiveSettings": built.effective_settings.to_safe_dict(),
            }
        intent = reasoning_intent_from_config(config.get("reasoning"))
        capabilities = known_provider_capabilities(str(config.get("selected_provider_profile") or "custom"))
        return "reasoningSettingsLoaded", {
            "reasoning": _reasoning_bridge_payload(intent),
            "capabilities": {
                "supportsReasoning": capabilities.supports_reasoning,
                "controls": sorted(item.value for item in capabilities.reasoning_controls),
                "effortLevels": list(capabilities.effort_levels),
                "minimumBudgetTokens": capabilities.minimum_budget_tokens,
                "maximumBudgetTokens": capabilities.maximum_budget_tokens,
            },
        }
    raise OperationError("unknown_action", "The requested bridge action is unavailable.")

def handle_action(action: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Dispatch one bridge action and return an {event, payload} envelope.

    This is the unit-testable core: it does no I/O and touches no network.
    The HTTP handler below is a thin wrapper around it.
    """
    if action == "load":
        last_selected = str((payload or {}).get("lastSelectedDeckId") or "")
        return {
            "event": "state",
            "payload": _state_payload(last_selected, [], sources=_available_sources()),
        }

    if action == "selectSource":
        source_id = str((payload or {}).get("sourceId") or "")
        sources = _available_sources()
        if source_id not in {source["id"] for source in sources}:
            return {"event": "error", "payload": {"message": "Unknown or unconfigured source."}}
        try:
            registry = _source_registry()
            try:
                source = registry.get(source_id)
            except KeyError:
                return {"event": "error", "payload": {"message": "MoMo API key is not configured."}}
            decks = [deck.to_bridge_row() for deck in source.list_today_decks()]
            last_selected = str((payload or {}).get("lastSelectedDeckId") or "")
            return {
                "event": "state",
                "payload": _state_payload(
                    last_selected,
                    decks,
                    sources=sources,
                    selected_source_id=source_id,
                ),
            }
        except AnkiConnectError as exc:
            sys.stderr.write(f"[desktop] AnkiConnect unavailable on selectSource: {type(exc).__name__}\n")
            return {
                "event": "providerOffline",
                "payload": {
                    "provider": "ankiconnect",
                    "retryable": True,
                    "message": "无法连接 AnkiConnect。请启动 Anki，并确认 AnkiConnect 已安装和启用。",
                },
            }
        except Exception as exc:
            err_type = type(exc).__name__
            sys.stderr.write(f"[mock] Provider error on selectSource: {err_type}\n")
            return {"event": "error", "payload": {"message": "Failed to load decks from provider."}}

    if action == "selectDeck":
        deck_id = str((payload or {}).get("deckId") or "")
        try:
            source, scoped_deck_id = _resolve_deck_source(deck_id)
            cards_data = source.get_deck(scoped_deck_id).to_bridge_cards()
            config = _load_desktop_config()
            if config:
                config["last_selected_deck_id"] = deck_id
                _save_desktop_config(config)
            return {"event": "deckCards", "payload": _deck_cards_payload(deck_id, cards_data)}
        except AnkiConnectError as exc:
            sys.stderr.write(f"[desktop] AnkiConnect unavailable on selectDeck: {type(exc).__name__}\n")
            return {
                "event": "providerOffline",
                "payload": {
                    "provider": "ankiconnect",
                    "retryable": True,
                    "message": "无法连接 AnkiConnect。请启动 Anki，并确认 AnkiConnect 已安装和启用。",
                },
            }
        except Exception as exc:
            err_type = type(exc).__name__
            stage = getattr(exc, "stage", None)
            cause_summary = safe_exception_summary(getattr(exc, "__cause__", None))
            if stage:
                msg = f"Failed to load deck cards from provider. Stage: {stage}"
                sys.stderr.write(f"[mock] Provider error on selectDeck: {err_type} stage={stage} cause={cause_summary}\n")
            else:
                msg = "Failed to load deck cards from provider."
                sys.stderr.write(f"[mock] Provider error on selectDeck: {err_type} cause={cause_summary}\n")
            return {"event": "error", "payload": {"message": msg}}

    if action == "saveCollapsedDeckGroups":
        config = _load_desktop_config()
        config["collapsed_deck_groups"] = [
            str(group).strip()
            for group in (payload.get("collapsedDeckGroups") or [])
            if str(group).strip()
        ]
        _save_desktop_config(config)
        return {"event": "noop", "payload": {}}

    if action == "saveFieldConfig":
        deck_id = str((payload or {}).get("deckId") or "")
        try:
            source, scoped_deck_id = _resolve_deck_source(deck_id)
            cards_data = source.get_deck(scoped_deck_id).to_bridge_cards()
        except Exception:
            return {"event": "error", "payload": {"message": "Select a deck before saving fields."}}
        cards = cards_data.get("cards") or []
        available_fields = _deck_fields_from_cards([card for card in cards if isinstance(card, dict)])
        selected_fields = [
            str(field)
            for field in (payload.get("fields") or [])
            if str(field) in available_fields
        ]
        if not selected_fields:
            return {"event": "error", "payload": {"message": "Choose at least one field for AI input."}}
        config = _load_desktop_config()
        deck_field_config = dict(config.get("deck_field_config") or {})
        deck_field_config[deck_id] = selected_fields
        config["deck_field_config"] = deck_field_config
        _save_desktop_config(config)
        return {
            "event": "fieldConfigSaved",
            "payload": {"deckId": deck_id, "selectedFields": selected_fields},
        }

    if action == "generate":
        # delegate to real handler which falls back to mock on failure
        return handle_generate_real(str((payload or {}).get("deckId") or ""), payload)

    if action == "debugPrompt":
        return handle_debug_prompt(str((payload or {}).get("deckId") or ""), payload)

    if action == "saveArticleCard":
        if not _DESKTOP_ADAPTERS_AVAILABLE:
            return {"event": "articleCardSaved", "payload": {"articleCard": None}}
        deck_id = str((payload or {}).get("deckId") or "")
        try:
            source, scoped_deck_id = _resolve_deck_source(deck_id)
            cards_data = source.get_deck(scoped_deck_id).to_bridge_cards()
            deck_name = str(cards_data.get("name") or "Desktop Deck")
            raw_cards = cards_data.get("cards", [])
            selected_card_ids = payload.get("cardIds")
            if selected_card_ids is not None:
                selected_ids = {str(cid) for cid in selected_card_ids}
                raw_cards = [
                    card for card in raw_cards
                    if isinstance(card, dict) and str(card.get("cid")) in selected_ids
                ]
            deck_adapter = DesktopDeckAdapter()
            article_card = deck_adapter.save_article_card(
                deck_name,
                [card for card in raw_cards if isinstance(card, dict)],
                str(payload.get("article") or ""),
                Path(str(payload.get("markdownPath") or "")),
                Path(str(payload.get("htmlPath") or "")),
            )
            return {"event": "articleCardSaved", "payload": {"articleCard": article_card}}
        except Exception as exc:
            message = getattr(exc, "public_message", None)
            if not isinstance(message, str) or not message.strip():
                message = "Failed to create article card."
            return {"event": "articleCardSaved", "payload": {"articleCardError": message}}

    if action == "listArticles":
        return {"event": "articleList", "payload": _list_desktop_articles()}

    if action == "loadArticle":
        path = str((payload or {}).get("path") or "")
        return {"event": "articleLoaded", "payload": _load_desktop_article(path)}

    if action == "deleteArticle":
        if not _DESKTOP_ADAPTERS_AVAILABLE:
            return {"event": "error", "payload": {"message": "Article deletion is unavailable."}}
        path = str((payload or {}).get("path") or "")
        try:
            deleted = DesktopDeckAdapter().delete_saved_article(path)
            return {"event": "articleDeleted", "payload": deleted}
        except RuntimeError:
            return {"event": "error", "payload": {"message": "The selected article could not be deleted."}}

    if action == "deleteAllArticles":
        if not _DESKTOP_ADAPTERS_AVAILABLE:
            return {"event": "error", "payload": {"message": "Article deletion is unavailable."}}
        deleted = DesktopDeckAdapter().delete_all_saved_articles()
        return {"event": "articlesDeleted", "payload": deleted}

    if action == "deleteArticlesByDay":
        if not _DESKTOP_ADAPTERS_AVAILABLE:
            return {"event": "error", "payload": {"message": "Article deletion is unavailable."}}
        try:
            deleted = DesktopDeckAdapter().delete_saved_articles_by_day(
                str((payload or {}).get("generatedDay") or "")
            )
            return {"event": "articlesDeletedByDay", "payload": deleted}
        except RuntimeError:
            return {"event": "error", "payload": {"message": "The selected article group could not be deleted."}}

    if action == "fetchModels":
        if _DESKTOP_ADAPTERS_AVAILABLE:
            try:
                from desktop_adapters import _import_core
                _llm = _import_core("llm")
                _utils = _import_core("utils")
                config_adapter = DesktopConfigAdapter()
                config = config_adapter.load() or {}
                
                settings = payload.get("settings") or {}
                api_key = str(settings.get("apiKey") or config.get("api_key") or "").strip()
                base_url = _safe_public_base_url(
                    _utils.clean_base_url(settings.get("baseUrl") or config.get("base_url"))
                )
                
                if not api_key:
                    return {"event": "error", "payload": {"message": "Enter or save an API key before fetching models."}}
                if not base_url:
                    return {"event": "error", "payload": {"message": "Enter an API base URL before fetching models."}}
                
                models = _llm.fetch_openai_compatible_models(base_url, api_key)
                if not models:
                    return {"event": "error", "payload": {"message": "No models were returned by this provider."}}
                return {"event": "modelsFetched", "payload": {"models": models}}
            except Exception:
                return {"event": "error", "payload": {"message": "Could not fetch models. Check the provider settings and connection."}}
        else:
            return {"event": "modelsFetched", "payload": {"models": ["mock-model-1", "mock-model-2"]}}

    if action == "testApiSettings":
        if not _DESKTOP_ADAPTERS_AVAILABLE:
            return {"event": "apiSettingsTested", "payload": {"model": "mock-model", "response": "OK"}}
        try:
            from desktop_adapters import _import_core
            _llm = _import_core("llm")
            config = DesktopConfigAdapter().load() or {}
            settings = payload.get("settings") or {}
            api_key = str(settings.get("apiKey") or config.get("api_key") or "").strip()
            base_url = _safe_public_base_url(settings.get("baseUrl") or config.get("base_url"))
            model = str(settings.get("model") or config.get("model") or "").strip()
            if not api_key or not base_url or not model:
                return {"event": "error", "payload": {"message": "API key, base URL, and model are required for testing."}}
            result = _llm.test_openai_compatible_config(base_url, api_key, model)
            return {"event": "apiSettingsTested", "payload": result}
        except Exception:
            return {"event": "error", "payload": {"message": "The API settings test failed. Check the provider settings and connection."}}

    if _DESKTOP_ADAPTERS_AVAILABLE:
        config_adapter = DesktopConfigAdapter()
        config = config_adapter.load() or {}

        if action == "getConfig":
            return {"event": "configLoaded", "payload": _safe_config_payload(config)}
        if action == "saveDesktopSettings":
            settings = payload.get("settings") or {}
            momo_key = str(settings.get("momoApiKey") or "").strip()
            clear_momo_key = bool(settings.get("clearMomoApiKey"))
            if momo_key:
                config["momo_api_key"] = momo_key
            elif clear_momo_key:
                config["momo_api_key"] = ""
            config["momo_day_start"] = _time_setting(settings.get("momoDayStart"))
            config["momo_day_end"] = _time_setting(settings.get("momoDayEnd"))
            config_adapter.save(config)
            global MOMO_PROVIDER
            MOMO_PROVIDER = None
            day_start, day_end = _study_window(config)
            return {
                "event": "desktopSettingsSaved",
                "payload": {
                    "desktopSettings": _desktop_settings_payload(config),
                    "dayStart": day_start,
                    "dayEnd": day_end,
                    "message": "Desktop settings saved.",
                },
            }
        if action == "saveApiSettings":
            settings = payload.get("settings") or {}
            # This validation path is mandatory.  Falling back to a raw
            # mapping after an import/validation failure can turn the entire
            # credential-bearing config into a bridge response on a later
            # exception path.
            from desktop_adapters import _import_core
            _utils = _import_core("utils")
            provider_id = _utils.clean_provider_id(settings.get("providerId"))
            base_url = _safe_public_base_url(_utils.clean_base_url(settings.get("baseUrl")))
            model = _utils.clean_text(settings.get("model"))
            temperature = _utils.clean_temperature(settings.get("temperature"))
            max_tokens = _utils.clean_max_tokens(settings.get("maxTokens"))

            if not base_url:
                return {"event": "error", "payload": {"message": "Enter an API base URL."}}
            if not model:
                return {"event": "error", "payload": {"message": "Enter a model name."}}

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
            import uuid
            from dairr_core.config import normalize_llm_api_profiles
            profile_id = str(settings.get("profileId") or uuid.uuid4().hex).strip()
            profile_name = str(settings.get("profileName") or model).strip()
            profiles = normalize_llm_api_profiles(config)
            profile = {"id": profile_id, "name": profile_name, "provider_id": provider_id,
                       "base_url": base_url, "model": model, "api_key": config.get("api_key") or "",
                       "temperature": temperature, "max_tokens": max_tokens}
            config["llm_api_profiles"] = [item for item in profiles if item["id"] != profile_id] + [profile]
            config["selected_llm_api_profile_id"] = profile_id

            config_adapter.save(config)

            # Never substitute raw config here: it contains API keys in both
            # the active profile and the profile list. Unknown failures are
            # redacted by the outer bridge boundary.
            api_settings_resp = _safe_api_settings_payload(config)

            return {"event": "apiSettingsSaved", "payload": {"apiSettings": api_settings_resp, "message": "API settings saved."}}
        if action == "selectApiProfile":
            from dairr_core.config import activate_llm_api_profile
            if not activate_llm_api_profile(config, str(payload.get("profileId") or "")):
                return {"event": "error", "payload": {"message": "API profile not found."}}
            config_adapter.save(config)
            return {"event": "apiSettingsSaved", "payload": {"apiSettings": _safe_api_settings_payload(config)}}
        if action == "savePromptPreset":
            preset = payload.get("preset") or {}
            try:
                from desktop_adapters import _import_core
                import uuid
                _utils = _import_core("utils")
                preset_id = str(preset.get("id") or f"preset-{uuid.uuid4().hex[:10]}")
                clean_preset = {
                    "id": preset_id,
                    "name": _utils.clean_text(preset.get("name")) or "Untitled",
                    "reader_native_language": _utils.clean_text(preset.get("reader_native_language")),
                    "article_language": _utils.clean_text(preset.get("article_language")),
                    "difficulty": _utils.clean_text(preset.get("difficulty")),
                    "max_words": _utils.clean_max_words(preset.get("max_words")),
                    "instructions": _utils.clean_text(preset.get("instructions")),
                    "prompt_template": str(preset.get("prompt_template") or ""),
                }
            except Exception:
                import uuid
                preset_id = str(preset.get("id") or f"preset-{uuid.uuid4().hex[:10]}")
                clean_preset = preset
                clean_preset["id"] = preset_id

            presets = config.get("prompt_presets", [])
            replaced = False
            for i, p in enumerate(presets):
                if p.get("id") == preset_id:
                    presets[i] = clean_preset
                    replaced = True
                    break
            if not replaced:
                presets.append(clean_preset)
                
            config["prompt_presets"] = presets
            config["selected_prompt_preset_id"] = preset_id
            config_adapter.save(config)
            
            return {"event": "promptPresets", "payload": {
                "promptPresets": presets,
                "selectedPromptPresetId": preset_id,
                "message": "Prompt preset saved."
            }}
        if action == "selectPromptPreset":
            preset_id = str(payload.get("presetId", ""))
            config["selected_prompt_preset_id"] = preset_id
            config_adapter.save(config)
            # The real addon emits no event for this, so we return a noop
            return {"event": "noop", "payload": {}}
        if action == "deletePromptPreset":
            preset_id = str(payload.get("presetId", ""))
            presets = [p for p in config.get("prompt_presets", []) if p.get("id") != preset_id]
            config["prompt_presets"] = presets
            if config.get("selected_prompt_preset_id") == preset_id:
                config["selected_prompt_preset_id"] = "default"
            config_adapter.save(config)
            return {"event": "promptPresets", "payload": {
                "promptPresets": presets,
                "selectedPromptPresetId": config.get("selected_prompt_preset_id") or "default",
                "message": "Prompt preset deleted."
            }}
        if action == "saveUiLanguage":
            ui_lang = str(payload.get("uiLanguage", ""))
            config["ui_language"] = ui_lang
            config_adapter.save(config)
            return {"event": "uiLanguageSaved", "payload": {"uiLanguage": ui_lang}}

    return {"event": "error", "payload": {"message": f"Unknown command: {action}"}}


def handle_bridge_message(message: Mapping[str, Any]) -> dict[str, Any]:
    """Dispatch one versioned bridge request without exposing private failures."""
    request_id = secrets.token_hex(16)
    try:
        request = BridgeRequest.from_mapping(message)
        request_id = request.request_id
        payload = dict(request.payload)
        if request.action == "operationStatus":
            operation_id = str(payload.get("operationId") or "")
            if not operation_id:
                raise OperationError("missing_operation_id", "An operation identifier is required.")
            return _OPERATIONS.status(operation_id)
        if request.action == "cancelOperation":
            operation_id = str(payload.get("operationId") or "")
            if not operation_id:
                raise OperationError("missing_operation_id", "An operation identifier is required.")
            return _OPERATIONS.cancel(operation_id)
        if request.action in ASYNC_ACTIONS:
            return _OPERATIONS.submit(
                request.action,
                request.request_id,
                lambda context: _run_release_operation(request.action, payload, context),
            )
        if request.action in RELEASE_ACTIONS:
            event, result = _handle_release_action(request.action, payload)
            return response_envelope(
                request.request_id,
                SYNC_EVENT_BY_ACTION.get(request.action, event),
                result,
            )

        legacy = handle_action(request.action, payload)
        event = str(legacy.get("event") or "error")
        result = legacy.get("payload") if isinstance(legacy.get("payload"), Mapping) else {}
        if event == "error":
            # Some legacy branches predate privacy-safe error types and may
            # contain third-party exception text. Never forward that text on
            # the network bridge.
            raise OperationError(
                "legacy_action_failed",
                "The requested action could not be completed. Check the relevant settings and try again.",
                retryable=True,
            )
        return response_envelope(request.request_id, event, result)
    except (OperationError, PromptTemplateError, ProviderConfigurationError, ValueError, KeyError) as exc:
        if isinstance(exc, OperationError):
            safe = exc
        elif isinstance(exc, (PromptTemplateError, ProviderConfigurationError)):
            safe = OperationError(getattr(exc, "code", "invalid_settings"), str(exc))
        else:
            safe = OperationError("invalid_request", "The request contains invalid or stale data.")
        return failure_envelope(request_id, safe)
    except Exception:
        return failure_envelope(
            request_id,
            OperationError("operation_failed", "The operation failed."),
        )


def _build_index_page(bridge_token: str | None = None) -> str:
    """Inline css + index.html body + mock bridge + app.js, mirroring _load_page."""
    body = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    css = (WEB_DIR / "style.css").read_text(encoding="utf-8")
    js = (WEB_DIR / "app.js").read_text(encoding="utf-8")
    guard = (
        '<script>\n'
        'window.addEventListener("error", function (event) {\n'
        '  document.body.innerHTML = \'<main class="app-shell"><section class="panel" style="padding:24px;"><h1>AI Reading Reinforcement</h1><p>Page script error: \' + String(event.message || "unknown") + \'</p></section></main>\';\n'
        '});\n'
        '</script>\n'
    )
    # The mock bridge replaces the Anki pycmd path. It posts to /api/bridge and
    # feeds the response straight into the shared app.js receive handler
    # (window.DAIRR.receive), which expects { event, payload }.
    token = bridge_token or _BRIDGE_TOKEN
    bridge = (
        '<script>\n'
        f'window.__DAIRR_BRIDGE_TOKEN__ = {json.dumps(token)};\n'
        'window.__DAIRR_BRIDGE__ = {\n'
        '  send(action, payload, envelope) {\n'
        '    var requestId = (envelope && envelope.requestId) || ((window.crypto && window.crypto.randomUUID) ? window.crypto.randomUUID() : (Date.now().toString(36) + Math.random().toString(36).slice(2)));\n'
        '    fetch("/api/bridge", {\n'
        '      method: "POST",\n'
        f'      headers: {{"Content-Type": "application/json", "{BRIDGE_TOKEN_HEADER}": window.__DAIRR_BRIDGE_TOKEN__}},\n'
        f'      body: JSON.stringify({{version: (envelope && envelope.version) || {BRIDGE_VERSION}, requestId: requestId, action: action, payload: payload || {{}}}})\n'
        '    })\n'
        '      .then(function (r) { return r.json(); })\n'
        '      .then(function (data) {\n'
        '        if (window.DAIRR && typeof window.DAIRR.receive === "function") {\n'
        '          window.DAIRR.receive(data);\n'
        '        }\n'
        '      })\n'
        '      .catch(function () { if (window.DAIRR) { window.DAIRR.receive({version:2, requestId:requestId, event:"operationFailed", payload:{status:"failed", error:{code:"bridge_unavailable", message:"The local DAIRR bridge is unavailable.", retryable:true, details:{}}}}); } });\n'
        '  },\n'
        '  sendRequest(request) { return this.send(request.action, request.payload, request); }\n'
        '};\n'
        '</script>\n'
    )
    return f"<style>{css}</style>\n{body}\n{guard}{bridge}<script>{js}</script>"


class MockHandler(BaseHTTPRequestHandler):
    server_version = "DAIRR/2.0"

    def _allowed_origins(self) -> set[str]:
        host, port = self.server.server_address[:2]
        origins = {
            f"http://127.0.0.1:{port}",
            f"http://localhost:{port}",
            f"http://[::1]:{port}",
        }
        if str(host) in {"127.0.0.1", "localhost", "::1"}:
            origins.add(f"http://{host}:{port}" if ":" not in str(host) else f"http://[{host}]:{port}")
        return origins

    def _valid_host(self) -> bool:
        supplied = (self.headers.get("Host") or "").strip().lower()
        _host, port = self.server.server_address[:2]
        return supplied in {f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"}

    def _valid_origin(self) -> bool:
        origin = (self.headers.get("Origin") or "").strip()
        return not origin or origin in self._allowed_origins()

    def _valid_bridge_token(self) -> bool:
        supplied = self.headers.get(BRIDGE_TOKEN_HEADER) or ""
        return bool(supplied) and secrets.compare_digest(supplied, _BRIDGE_TOKEN)

    def _security_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
            "img-src data:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'",
        )

    def _cors_header(self) -> None:
        origin = (self.headers.get("Origin") or "").strip()
        if origin in self._allowed_origins():
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    def _send_json(self, status: int, obj: dict[str, Any]) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._security_headers()
        self._cors_header()
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if not self._valid_host():
            self._send_json(403, {"error": "invalid_host"})
            return
        if self.path == "/api/health":
            self._send_json(200, build_health_payload())
            return
        if self.path == "/" or self.path == "/index.html":
            self._send_html(_build_index_page())
            return
        self.send_error(404, "Not found")

    def do_OPTIONS(self) -> None:
        if self.path != "/api/bridge" or not self._valid_host() or not self._valid_origin():
            self._send_json(403, {"error": "request_rejected"})
            return
        self.send_response(204)
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", f"Content-Type, {BRIDGE_TOKEN_HEADER}")
        self.send_header("Access-Control-Max-Age", "600")
        self._security_headers()
        self._cors_header()
        self.end_headers()

    def do_POST(self) -> None:
        if not self._valid_host() or not self._valid_origin():
            self._send_json(403, {"error": "request_rejected"})
            return
        if self.path == "/api/shutdown":
            expected = os.environ.get("DAIRR_SHUTDOWN_TOKEN") or ""
            supplied = self.headers.get("X-DAIRR-Shutdown-Token") or ""
            if not expected or supplied != expected:
                self._send_json(403, {"ok": False})
                return
            self._send_json(200, {"ok": True})
            _OPERATIONS.shutdown(wait=False)
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        if self.path != "/api/bridge":
            self.send_error(404, "Not found")
            return
        if not self._valid_bridge_token():
            self._send_json(403, failure_envelope(
                secrets.token_hex(16),
                OperationError("bridge_authorization_failed", "The local bridge request was rejected."),
            ))
            return
        content_type = (self.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            self._send_json(415, failure_envelope(
                secrets.token_hex(16),
                OperationError("unsupported_content_type", "The bridge accepts JSON requests only."),
            ))
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length < 0 or length > MAX_BRIDGE_BODY_BYTES:
                raise OperationError("request_too_large", "The bridge request exceeds the explicit size limit.")
            raw = self.rfile.read(length) if length else b"{}"
            message = json.loads(raw.decode("utf-8") or "{}")
            if not isinstance(message, Mapping):
                raise OperationError("invalid_request", "The bridge request must be a JSON object.")
        except OperationError as exc:
            self._send_json(400, failure_envelope(secrets.token_hex(16), exc))
            return
        except Exception:
            self._send_json(400, failure_envelope(
                secrets.token_hex(16),
                OperationError("invalid_json", "The bridge request is not valid JSON."),
            ))
            return
        self._send_json(200, handle_bridge_message(message))

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("[mock] " + (fmt % args) + "\n")


def run_server(host: str = HOST, port: int = PORT) -> None:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("DAIRR's local bridge may bind only to a loopback interface.")
    get_deck_provider()
    server = ThreadingHTTPServer((host, port), MockHandler)
    server.daemon_threads = True
    parent_pid = int(os.environ.get("DAIRR_PARENT_PID") or 0)
    if parent_pid > 0:
        def stop_when_parent_exits() -> None:
            while True:
                try:
                    os.kill(parent_pid, 0)
                except OSError:
                    sys.stderr.write("[desktop] Tauri parent exited; stopping sidecar.\n")
                    server.shutdown()
                    return
                threading.Event().wait(0.5)

        threading.Thread(target=stop_when_parent_exits, daemon=True).start()
    print(f"DAIRR desktop mock running at http://{host}:{port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        _OPERATIONS.shutdown(wait=False)
        server.server_close()


def main() -> None:
    try:
        run_server()
    except Exception as e:
        print(f"Failed to start desktop mock server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
