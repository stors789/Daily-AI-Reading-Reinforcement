"""Desktop-specific adapter implementations for DAIRR.

These concrete adapters implement the Protocol interfaces defined in
dairr_core.adapters without importing aqt / mw / Anki. They let the
desktop mock server run the real article generation pipeline.

IMPORTANT: This file must NEVER import aqt, mw, or any Anki module.
"""

from __future__ import annotations

import importlib
import json
import os
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, TypeVar

from dairr_core_runtime import enable_dairr_core_imports
from desktop_paths import app_config_path, app_output_dir, legacy_config_path

enable_dairr_core_imports()


def _import_core(stem: str) -> Any:
    """Import a named DAIRR core module through Python's standard importer."""
    return importlib.import_module(f"dairr_core.{stem}")


_core_config = _import_core("config")
_core_article = _import_core("article")
_core_article_generator = _import_core("article_generator")
_core_llm = _import_core("llm")
_core_rendering = _import_core("rendering")
_core_atomic = _import_core("atomic_persistence")

DEFAULT_CONFIG = dict(_core_config.DEFAULT_CONFIG)

_T = TypeVar("_T")

# ---------------------------------------------------------------------------
# Desktop future -- a minimal stand-in for concurrent.futures.Future
# ---------------------------------------------------------------------------


class DesktopFuture:
    """Minimal Future-like wrapper returned by DesktopEnvironmentAdapter."""

    __slots__ = ("_event", "_result", "_exc")

    def __init__(self) -> None:
        self._event = threading.Event()
        self._result: Any = None
        self._exc: BaseException | None = None

    def set_result(self, value: Any) -> None:
        self._result = value
        self._event.set()

    def set_exception(self, exc: BaseException) -> None:
        self._exc = exc
        self._event.set()

    def result(self) -> Any:
        self._event.wait()
        if self._exc is not None:
            raise self._exc
        return self._result


# ---------------------------------------------------------------------------
# ConfigAdapter
# ---------------------------------------------------------------------------


class DesktopConfigAdapter:
    """ConfigAdapter backed by env vars and an optional local JSON file.

    Priority (highest first):
      1. Environment variables (DAIRR_API_KEY, DAIRR_BASE_URL, DAIRR_MODEL, etc.)
      2. A JSON config file at DESKTOP_CONFIG_PATH
      3. Legacy ~/.dairr_config.json, when it already exists
      4. Packaged-app config path under the user's application data directory
      5. DEFAULT_CONFIG from dairr_core.config
    """

    ENV_MAP: dict[str, str] = {
        "api_key": "DAIRR_API_KEY",
        "base_url": "DAIRR_BASE_URL",
        "model": "DAIRR_MODEL",
        "temperature": "DAIRR_TEMPERATURE",
        "max_tokens": "DAIRR_MAX_TOKENS",
        "selected_provider_profile": "DAIRR_PROVIDER",
        "ui_language": "DAIRR_UI_LANGUAGE",
    }

    __slots__ = ("_file_path", "_cache", "_lock")

    def __init__(self, file_path: str | None = None) -> None:
        if file_path:
            self._file_path = Path(file_path)
        else:
            env_path = os.environ.get("DESKTOP_CONFIG_PATH")
            if env_path:
                self._file_path = Path(env_path)
            else:
                legacy_path = legacy_config_path()
                self._file_path = legacy_path if legacy_path.is_file() else app_config_path()
        self._cache: dict[str, Any] | None = None
        self._lock = threading.RLock()

    def load(self) -> dict[str, Any] | None:
        with self._lock:
            if self._cache is not None:
                return deepcopy(self._cache)

            config: dict[str, Any] = deepcopy(DEFAULT_CONFIG)

            # Layer 2: JSON file. A corrupt file is left untouched and the
            # defaults remain usable; no private values are included in errors.
            if self._file_path.is_file():
                try:
                    with open(self._file_path, encoding="utf-8") as fh:
                        file_config = json.load(fh)
                    if isinstance(file_config, dict):
                        config.update(file_config)
                    else:
                        config["config_load_warning"] = "invalid_config_root"
                except (OSError, UnicodeError, json.JSONDecodeError):
                    config["config_load_warning"] = "unreadable_config"

            # Layer 1: environment variables (highest priority)
            for config_key, env_key in self.ENV_MAP.items():
                env_value = os.environ.get(env_key)
                if env_value is not None:
                    if config_key in ("temperature",):
                        try:
                            config[config_key] = float(env_value)
                        except ValueError:
                            pass
                    elif config_key in ("max_tokens",):
                        try:
                            config[config_key] = int(env_value)
                        except ValueError:
                            pass
                    else:
                        config[config_key] = env_value

            self._cache = _core_config.normalize_config(config)
            return deepcopy(self._cache)

    def save(self, config: dict[str, Any]) -> None:
        normalized = _core_config.normalize_config(config)
        with self._lock:
            try:
                _core_atomic.atomic_write_json(self._file_path, normalized, private=True)
            except PermissionError:
                # Sandboxed/read-only hosts can continue the current session;
                # retain an explicit warning in memory rather than fabricating
                # a durable save or exposing the path/private config values.
                normalized["config_save_warning"] = "permission_denied"
            self._cache = deepcopy(normalized)


# ---------------------------------------------------------------------------
# DeckAdapter
# ---------------------------------------------------------------------------


class DesktopDeckAdapter:
    """DeckAdapter that saves articles as local Markdown + HTML files.

    Unlike the Anki adapter, it does NOT write into the Anki collection.
    Instead it writes to a local articles/ directory under DESKTOP_OUTPUT_DIR
    (default: the packaged-app user data directory).
    """

    __slots__ = ("_output_dir", "_articles_dir")

    def __init__(self, output_dir: str | None = None) -> None:
        if output_dir:
            self._output_dir = Path(output_dir)
            self._articles_dir = self._output_dir / "articles"
        else:
            env_dir = os.environ.get("DESKTOP_OUTPUT_DIR", "")
            if env_dir:
                self._output_dir = Path(env_dir)
                self._articles_dir = self._output_dir / "articles"
            else:
                self._articles_dir = app_output_dir()
                self._output_dir = self._articles_dir.parent

    def save_article(
        self,
        deck_name_value: str,
        cards: list[Any],
        article: str,
        *,
        generation_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Path]:
        """Persist article using the pure core function, but to the desktop output dir."""
        return _core_article.save_article(
            deck_name_value,
            cards,
            article,
            articles_dir=self._articles_dir,
            generation_metadata=generation_metadata,
        )

    def list_saved_articles(self) -> list[dict[str, str]]:
        """Return the real history stored in this desktop app's data folder."""
        return _core_article.list_saved_articles(articles_dir=self._articles_dir)

    def load_saved_article(self, path: str) -> dict[str, Any]:
        """Load one real desktop article while enforcing its storage boundary."""
        return _core_article.load_saved_article(path, articles_dir=self._articles_dir)

    def delete_saved_article(self, path: str) -> dict[str, Any]:
        """Delete one desktop article and its rendered companion."""
        return _core_article.delete_saved_article(path, articles_dir=self._articles_dir)

    def delete_all_saved_articles(self) -> dict[str, int]:
        """Delete every article stored by this desktop app."""
        return _core_article.delete_all_saved_articles(articles_dir=self._articles_dir)

    def delete_saved_articles_by_day(self, generated_day: str) -> dict[str, Any]:
        """Delete desktop articles generated on one calendar day."""
        return _core_article.delete_saved_articles_by_day(
            generated_day,
            articles_dir=self._articles_dir,
        )

    def save_article_card(
        self,
        source_deck_name: str,
        cards: list[Any],
        article: str,
        markdown_path: Path,
        html_path: Path,
    ) -> dict[str, Any]:
        """Create an article card for AnkiConnect desktop mode, otherwise stub."""
        if os.environ.get("DAIRR_DESKTOP_PROVIDER") == "ankiconnect":
            from ankiconnect_card_saver import AnkiConnectArticleCardSaver
            from ankiconnect_provider import DEFAULT_ANKICONNECT_URL

            saver = AnkiConnectArticleCardSaver(
                base_url=os.environ.get("DAIRR_ANKICONNECT_URL", DEFAULT_ANKICONNECT_URL),
                render_article_fragment_html=_core_rendering.render_article_fragment_html,
            )
            return saver.save_article_card(
                source_deck_name,
                cards,
                article,
                markdown_path,
                html_path,
            )
        return {
            "noteId": 0,
            "deckName": source_deck_name,
            "noteType": "Desktop (no Anki card created)",
            "date": "",
            "_desktop_stub": True,
        }


# ---------------------------------------------------------------------------
# EnvironmentAdapter
# ---------------------------------------------------------------------------


class DesktopEnvironmentAdapter:
    """EnvironmentAdapter backed by threading.Thread.

    Runs *task* on a daemon thread and calls *on_done* with a
    DesktopFuture on the same thread (not the main/GUI thread).
    """

    __slots__ = ()

    def run_in_background(
        self,
        task: Callable[[], _T],
        on_done: Callable[[Any], None],
    ) -> None:
        future: DesktopFuture = DesktopFuture()

        def wrapper() -> None:
            try:
                result = task()
                future.set_result(result)
            except Exception as exc:
                future.set_exception(exc)
            on_done(future)

        thread = threading.Thread(target=wrapper, daemon=True)
        thread.start()
