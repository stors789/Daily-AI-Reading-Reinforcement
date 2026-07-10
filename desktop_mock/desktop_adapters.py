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

    __slots__ = ("_file_path", "_cache")

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

    def load(self) -> dict[str, Any] | None:
        if self._cache is not None:
            return self._cache

        config: dict[str, Any] = DEFAULT_CONFIG.copy()

        # Layer 2: JSON file
        if self._file_path.is_file():
            try:
                with open(self._file_path, encoding="utf-8") as fh:
                    file_config = json.load(fh)
                if isinstance(file_config, dict):
                    config.update(file_config)
            except Exception:
                pass

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

        self._cache = config
        return config

    def save(self, config: dict[str, Any]) -> None:
        self._cache = dict(config)
        try:
            self._file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._file_path, "w", encoding="utf-8") as fh:
                json.dump(config, fh, ensure_ascii=False, indent=2)
        except Exception:
            pass


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
    ) -> dict[str, Path]:
        """Persist article using the pure core function, but to the desktop output dir."""
        # Override the articles directory temporarily so core_article saves to our output dir.
        original_dir = _core_article.ARTICLES_DIR
        try:
            _core_article.ARTICLES_DIR = self._articles_dir
            return _core_article.save_article(deck_name_value, cards, article)
        finally:
            _core_article.ARTICLES_DIR = original_dir

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
