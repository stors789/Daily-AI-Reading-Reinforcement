"""Desktop-specific adapter implementations for DAIRR.

These concrete adapters implement the Protocol interfaces defined in
core/adapters.py without importing aqt / mw / Anki.  They let the
desktop mock server run the real article generation pipeline.

IMPORTANT: This file must NEVER import aqt, mw, or any Anki module.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Callable, TypeVar

_REPO_ROOT = Path(__file__).resolve().parent.parent
_ADDON_ROOT = _REPO_ROOT / "addon" / "daily_ai_reading_reinforcement"

# Import the core modules (pure, no Anki deps).
import importlib.util as _iu
import sys as _sys


# Meta-path finder so that core modules can use relative imports (e.g. from .rendering).
# Core modules live in addon/.../core/ and use a virtual package "dairr_core".
_CORE_DIR = _ADDON_ROOT / "core"


class _CoreModuleFinder:
    """sys.meta_path finder that resolves dairr_core.* module names.

    When a relative import like `from .rendering import ...` triggers,
    Python resolves it to `dairr_core.rendering`.  This finder locates
    the corresponding .py file in _CORE_DIR and loads it.
    """
    __slots__ = ()

    def _stem_from_fullname(self, fullname: str) -> str | None:
        prefix = "dairr_core."
        if not fullname.startswith(prefix):
            if fullname == "dairr_core":
                return "__init__"
            return None
        return fullname[len(prefix):]

    def find_spec(self, fullname: str, path: Any = None, target: Any = None) -> Any:
        stem = self._stem_from_fullname(fullname)
        if stem is None:
            return None

        # Already loaded? Return None to let the normal mechanism take over.
        if fullname in _sys.modules:
            return None

        # Core modules are flat; "__init__" for the package itself.
        if stem == "__init__":
            path = _CORE_DIR / "__init__.py"
        else:
            path = _CORE_DIR / f"{stem}.py"

        if not path.is_file():
            return None

        return _iu.spec_from_file_location(fullname, path)

    def exec_module(self, mod: Any) -> None:
        # __package__ must match our virtual package name so that
        # relative imports resolve correctly.
        if hasattr(mod, "__package__"):
            mod.__package__ = "dairr_core"


_CORE_FINDER = _CoreModuleFinder()
_sys.meta_path.insert(0, _CORE_FINDER)


def _import_core(stem: str) -> Any:
    """Lazy-import a core module without touching the addon package __init__.

    All core modules share the virtual package 'dairr_core', so that
    relative imports (e.g. from .rendering) work correctly.
    """
    module_name = f"dairr_core.{stem}"
    if module_name in _sys.modules:
        return _sys.modules[module_name]

    path = _CORE_DIR / f"{stem}.py"
    spec = _iu.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {path}")
    mod = _iu.module_from_spec(spec)
    mod.__package__ = "dairr_core"

    # Register the virtual package itself so relative imports resolve.
    if "dairr_core" not in _sys.modules:
        import types
        _pkg = types.ModuleType("dairr_core")
        _pkg.__package__ = "dairr_core"
        _pkg.__path__ = []
        _sys.modules["dairr_core"] = _pkg

    _sys.modules[module_name] = mod
    _CORE_FINDER.exec_module(mod)
    spec.loader.exec_module(mod)
    return mod


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
      2. A JSON config file at DESKTOP_CONFIG_PATH or ~/.dairr_config.json
      3. DEFAULT_CONFIG from core/config.py
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
            self._file_path = Path(
                os.environ.get("DESKTOP_CONFIG_PATH", os.path.expanduser("~/.dairr_config.json"))
            )
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
    (default: desktop_mock/output/).
    """

    __slots__ = ("_output_dir",)

    def __init__(self, output_dir: str | None = None) -> None:
        if output_dir:
            self._output_dir = Path(output_dir)
        else:
            env_dir = os.environ.get("DESKTOP_OUTPUT_DIR", "")
            if env_dir:
                self._output_dir = Path(env_dir)
            else:
                self._output_dir = _REPO_ROOT / "desktop_mock" / "output"

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
            _core_article.ARTICLES_DIR = self._output_dir / "articles"
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
