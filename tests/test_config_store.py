"""Tests for AnkiConfigStore adapter and config loading behaviour.

Tests use a fake aqt module injected into sys.modules so they run
outside Anki.  The adapter is loaded directly (not via the package
__init__.py) to avoid pulling in full aqt.qt / aqt.utils deps.
"""

import importlib.util
import sys
import types
import unittest
from copy import deepcopy
from pathlib import Path
from typing import Any

# -- fake aqt (only what anki_config_store.py needs) --------------------


class _FakeAddonManager:
    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}
        self._get_calls: list[str] = []
        self._write_calls: list[tuple[str, dict[str, Any]]] = []

    def getConfig(self, name: str) -> dict[str, Any] | None:
        self._get_calls.append(name)
        return self._store.get(name)

    def writeConfig(self, name: str, config: dict[str, Any]) -> None:
        self._write_calls.append((name, config))
        self._store[name] = config


class _FakeMw:
    def __init__(self) -> None:
        self.addonManager = _FakeAddonManager()


_fake_mw = _FakeMw()

_aqt = types.ModuleType("aqt")
_aqt.mw = _fake_mw
sys.modules["aqt"] = _aqt

# -- direct import of anki_config_store (avoids addon package __init__) --

_addon_root = (
    Path(__file__).resolve().parent.parent
    / "addon" / "daily_ai_reading_reinforcement"
)

_anki_cfg_path = _addon_root / "anki_config_store.py"
_spec = importlib.util.spec_from_file_location(
    "anki_config_store", _anki_cfg_path
)
_anki_cfg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_anki_cfg)
AnkiConfigStore = _anki_cfg.AnkiConfigStore

# Import the independently installable core config (pure Python, no aqt deps).
_core_cfg_path = (
    Path(__file__).resolve().parent.parent
    / "packages"
    / "dairr_core"
    / "src"
    / "dairr_core"
    / "config.py"
)
_core_spec = importlib.util.spec_from_file_location(
    "core_config", _core_cfg_path
)
_core_mod = importlib.util.module_from_spec(_core_spec)
_core_spec.loader.exec_module(_core_mod)
DEFAULT_CONFIG = _core_mod.DEFAULT_CONFIG


# -- unit tests --------------------------------------------------------


class TestAnkiConfigStore(unittest.TestCase):
    def setUp(self) -> None:
        self.addon_name = "test_addon"
        self.store: AnkiConfigStore = AnkiConfigStore(self.addon_name)
        self.mgr: _FakeAddonManager = _fake_mw.addonManager
        self.mgr._store.clear()
        self.mgr._get_calls.clear()
        self.mgr._write_calls.clear()

    def test_load_delegates_to_getConfig(self) -> None:
        self.mgr._store[self.addon_name] = {"key": "val"}
        result = self.store.load()
        self.assertEqual(result, {"key": "val"})
        self.assertEqual(self.mgr._get_calls, [self.addon_name])

    def test_load_returns_none_when_empty(self) -> None:
        self.assertIsNone(self.store.load())

    def test_save_delegates_to_writeConfig(self) -> None:
        cfg = {"api_key": "sk-test", "model": "gpt-4"}
        self.store.save(cfg)
        self.assertEqual(self.mgr._write_calls, [(self.addon_name, cfg)])
        self.assertEqual(self.mgr._store[self.addon_name], cfg)

    def test_save_round_trip(self) -> None:
        cfg = {"a": 1, "b": [1, 2], "c": {"x": "y"}}
        self.store.save(cfg)
        self.assertEqual(self.store.load(), cfg)


class TestConfigMerging(unittest.TestCase):
    """Test load_config-style merge logic using the adapter directly."""

    def setUp(self) -> None:
        self.addon_name = "merge_test"
        self.store: AnkiConfigStore = AnkiConfigStore(self.addon_name)
        self.mgr: _FakeAddonManager = _fake_mw.addonManager
        self.mgr._store.clear()

    def _load_via_store(self) -> dict[str, Any]:
        """Replicate the load_config() merge logic."""
        config = DEFAULT_CONFIG.copy()
        loaded = self.store.load() or {}
        config.update(loaded)
        return config

    def test_empty_store_yields_full_defaults(self) -> None:
        self.assertEqual(self._load_via_store(), DEFAULT_CONFIG)

    def test_store_value_overrides_default(self) -> None:
        self.mgr._store[self.addon_name] = {"temperature": 0.2}
        result = self._load_via_store()
        self.assertEqual(result["temperature"], 0.2)
        self.assertEqual(result["model"], DEFAULT_CONFIG["model"])

    def test_new_field_added_to_config(self) -> None:
        self.mgr._store[self.addon_name] = {"extra": "hello"}
        result = self._load_via_store()
        self.assertEqual(result["extra"], "hello")
        self.assertIn("base_url", result)

    def test_nested_defaults_preserved(self) -> None:
        self.mgr._store[self.addon_name] = {"api_key": "sk-test"}
        result = self._load_via_store()
        self.assertEqual(result["prompt_presets"], DEFAULT_CONFIG["prompt_presets"])

    def test_save_merge_load_cycle(self) -> None:
        cfg = {"api_key": "sk-abc", "temperature": 0.5}
        self.store.save(cfg)
        result = self._load_via_store()
        self.assertEqual(result["api_key"], "sk-abc")
        self.assertEqual(result["temperature"], 0.5)
        self.assertIn("prompt_presets", result)



if __name__ == "__main__":
    unittest.main()
