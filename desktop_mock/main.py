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
import sys
import threading
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
            "endpoint": "/api/bridge",
            "windowObject": "__DAIRR_BRIDGE__",
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
        from mock_data import _api_settings_payload
        payload["apiSettings"] = _api_settings_payload(config)
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

    Falls back to the mock payload if:
    - Desktop adapters cannot be imported
    - The API key is missing
    - The LLM call or article save fails

    Returns an {event, payload} envelope matching the addon contract.
    """
    source, _ = _resolve_deck_source(deck_id)
    if isinstance(source.provider, MockMoMoDeckProvider):
        return _mock_generate(deck_id)

    if not _DESKTOP_ADAPTERS_AVAILABLE:
        return _mock_generate(deck_id)

    config_adapter = DesktopConfigAdapter()
    deck_adapter = DesktopDeckAdapter()
    env_adapter = DesktopEnvironmentAdapter()

    try:
        context = resolve_generation_context(deck_id, payload)
    except Exception:
        return _mock_generate(deck_id)

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
        sys.stderr.write(f"[mock] Failed to load article_generator: {exc}. Falling back to mock.\n")
        return _mock_generate(deck_id)

    try:
        result = run_article_generation(
            config_adapter, deck_adapter, deck_name, cards, selected_fields, preset,
        )
        return {"event": "article", "payload": result}
    except Exception as exc:
        sys.stderr.write(f"[mock] Real generation failed: {exc}. Falling back to mock.\n")
        return _mock_generate(deck_id)


def _mock_generate(deck_id: str) -> dict[str, Any]:
    """Return the mock article payload (kept for backward compatibility)."""
    _, scoped_deck_id = _resolve_deck_source(deck_id)
    payload = build_article_payload(scoped_deck_id.local_id)
    payload["deckId"] = scoped_deck_id.encode()
    return {"event": "article", "payload": payload}

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
        return {"event": "articleList", "payload": build_article_list_payload()}

    if action == "loadArticle":
        path = str((payload or {}).get("path") or "")
        return {"event": "articleLoaded", "payload": build_loaded_article_payload(path)}

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
                base_url = _utils.clean_base_url(settings.get("baseUrl") or config.get("base_url"))
                
                if not api_key:
                    return {"event": "error", "payload": {"message": "Enter or save an API key before fetching models."}}
                if not base_url:
                    return {"event": "error", "payload": {"message": "Enter an API base URL before fetching models."}}
                
                models = _llm.fetch_openai_compatible_models(base_url, api_key)
                if not models:
                    return {"event": "error", "payload": {"message": "No models were returned by this provider."}}
                return {"event": "modelsFetched", "payload": {"models": models}}
            except Exception as exc:
                return {"event": "error", "payload": {"message": str(exc)}}
        else:
            return {"event": "modelsFetched", "payload": {"models": ["mock-model-1", "mock-model-2"]}}

    if _DESKTOP_ADAPTERS_AVAILABLE:
        config_adapter = DesktopConfigAdapter()
        config = config_adapter.load() or {}

        if action == "getConfig":
            return {"event": "configLoaded", "payload": config}
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
            try:
                from desktop_adapters import _import_core
                _utils = _import_core("utils")
                provider_id = _utils.clean_provider_id(settings.get("providerId"))
                base_url = _utils.clean_base_url(settings.get("baseUrl"))
                model = _utils.clean_text(settings.get("model"))
                temperature = _utils.clean_temperature(settings.get("temperature"))
                max_tokens = _utils.clean_max_tokens(settings.get("maxTokens"))
            except Exception:
                provider_id = str(settings.get("providerId") or "").strip()
                base_url = str(settings.get("baseUrl") or "").strip().rstrip("/")
                model = str(settings.get("model") or "").strip()
                try:
                    temperature = float(settings.get("temperature"))
                except (TypeError, ValueError):
                    temperature = 0.7
                try:
                    max_tokens = int(settings.get("maxTokens"))
                except (TypeError, ValueError):
                    max_tokens = 0

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

            config_adapter.save(config)

            try:
                from mock_data import _api_settings_payload
                api_settings_resp = _api_settings_payload(config)
            except Exception:
                api_settings_resp = config

            return {"event": "apiSettingsSaved", "payload": {"apiSettings": api_settings_resp, "message": "API settings saved."}}
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
            return {"event": "uiLanguageSaved", "payload": config}

    return {"event": "error", "payload": {"message": f"Unknown command: {action}"}}


@lru_cache(maxsize=1)
def _build_index_page() -> str:
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
    bridge = (
        '<script>\n'
        'window.__DAIRR_BRIDGE__ = {\n'
        '  send(action, payload) {\n'
        '    fetch("/api/bridge", {\n'
        '      method: "POST",\n'
        '      headers: {"Content-Type": "application/json"},\n'
        '      body: JSON.stringify({action: action, payload: payload})\n'
        '    })\n'
        '      .then(function (r) { return r.json(); })\n'
        '      .then(function (data) {\n'
        '        if (window.DAIRR && typeof window.DAIRR.receive === "function") {\n'
        '          window.DAIRR.receive(data);\n'
        '        }\n'
        '      })\n'
        '      .catch(function (err) { console.error("Mock bridge error", err); });\n'
        '  }\n'
        '};\n'
        '</script>\n'
    )
    return f"<style>{css}</style>\n{body}\n{guard}{bridge}<script>{js}</script>"


class MockHandler(BaseHTTPRequestHandler):
    server_version = "DAIRRMock/1.0"

    def _send_json(self, status: int, obj: dict[str, Any]) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/api/health":
            self._send_json(200, build_health_payload())
            return
        if self.path == "/" or self.path == "/index.html":
            self._send_html(_build_index_page())
            return
        self.send_error(404, "Not found")

    def do_POST(self) -> None:
        if self.path == "/api/shutdown":
            expected = os.environ.get("DAIRR_SHUTDOWN_TOKEN") or ""
            supplied = self.headers.get("X-DAIRR-Shutdown-Token") or ""
            if not expected or supplied != expected:
                self._send_json(403, {"ok": False})
                return
            self._send_json(200, {"ok": True})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        if self.path != "/api/bridge":
            self.send_error(404, "Not found")
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            message = json.loads(raw.decode("utf-8") or "{}")
        except Exception as exc:
            self._send_json(400, {"event": "error", "payload": {"message": f"Bad request: {exc}"}})
            return

        action = str(message.get("action") or "")
        payload = message.get("payload") or {}
        if not isinstance(payload, dict):
            payload = {}
        try:
            self._send_json(200, handle_action(action, payload))
        except Exception as exc:
            self._send_json(200, {"event": "error", "payload": {"message": str(exc)}})

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("[mock] " + (fmt % args) + "\n")


def run_server(host: str = HOST, port: int = PORT) -> None:
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
        server.server_close()


def main() -> None:
    try:
        run_server()
    except Exception as e:
        print(f"Failed to start desktop mock server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
