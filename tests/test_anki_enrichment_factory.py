"""Tests for anki_enrichment_factory.py"""

import sys
import types
import unittest
from pathlib import Path

class _FakeMw:
    def __init__(self, has_col: bool = True):
        self.col = "FAKE_COL" if has_col else None
    
    class form:
        class menuTools:
            @staticmethod
            def addAction(action): pass

    class taskman:
        @staticmethod
        def run_in_background(*args): pass

# Fake aqt module before importing anything from the addon
_fake_mw = _FakeMw(has_col=True)
_aqt = types.ModuleType("aqt")
_aqt.mw = _fake_mw

_deckbrowser = types.ModuleType("deckbrowser")
_deckbrowser.DeckBrowser = type("DeckBrowser", (), {"_linkHandler": None})
_aqt.deckbrowser = _deckbrowser

_qt = types.ModuleType("qt")
_qt.QAction = type("QAction", (), {"triggered": type("Triggered", (), {"connect": lambda self, x: None})()})
_qt.QDialog = type("QDialog", (), {})
_qt.QTimer = type("QTimer", (), {"singleShot": lambda *args: None})
_qt.QVBoxLayout = type("QVBoxLayout", (), {"setContentsMargins": lambda *args: None, "addWidget": lambda *args: None})
_aqt.qt = _qt

_utils = types.ModuleType("utils")
_utils.showWarning = lambda *args: None
_aqt.utils = _utils

_webview = types.ModuleType("webview")
_webview.AnkiWebView = type("AnkiWebView", (), {"set_bridge_command": lambda *args: None, "stdHtml": lambda *args: None, "eval": lambda *args: None})
_aqt.webview = _webview

sys.modules["aqt"] = _aqt
sys.modules["aqt.deckbrowser"] = _deckbrowser
sys.modules["aqt.qt"] = _qt
sys.modules["aqt.utils"] = _utils
sys.modules["aqt.webview"] = _webview

_addon_root = Path(__file__).resolve().parent.parent / "addon"
sys.path.insert(0, str(_addon_root))

from daily_ai_reading_reinforcement.core.config import DEFAULT_CONFIG
from daily_ai_reading_reinforcement.anki_enrichment_factory import build_anki_enrichment_source
import daily_ai_reading_reinforcement.anki_enrichment_factory as factory_module
from daily_ai_reading_reinforcement.anki_enrichment_source import AnkiLocalEnrichmentSource


class TestAnkiEnrichmentFactory(unittest.TestCase):
    def setUp(self):
        self.original_mw = getattr(factory_module, "mw", None)
        self.config = DEFAULT_CONFIG.copy()

    def tearDown(self):
        factory_module.mw = self.original_mw

    def test_default_config_has_new_fields(self):
        self.assertIn("enable_anki_local_enrichment", DEFAULT_CONFIG)
        self.assertIn("anki_local_enrichment_field_map", DEFAULT_CONFIG)
        self.assertIn("anki_local_enrichment_search_fields", DEFAULT_CONFIG)
        self.assertIn("anki_local_enrichment_max_matches_per_term", DEFAULT_CONFIG)
        self.assertFalse(DEFAULT_CONFIG["enable_anki_local_enrichment"])

    def test_build_returns_none_when_disabled(self):
        self.config["enable_anki_local_enrichment"] = False
        factory_module.mw = _FakeMw(has_col=True)
        self.assertIsNone(build_anki_enrichment_source(self.config))

    def test_build_returns_none_when_no_collection(self):
        self.config["enable_anki_local_enrichment"] = True
        factory_module.mw = _FakeMw(has_col=False)
        self.assertIsNone(build_anki_enrichment_source(self.config))
        
    def test_build_returns_none_when_mw_is_none(self):
        self.config["enable_anki_local_enrichment"] = True
        factory_module.mw = None
        self.assertIsNone(build_anki_enrichment_source(self.config))

    def test_build_returns_source_when_enabled(self):
        self.config["enable_anki_local_enrichment"] = True
        factory_module.mw = _FakeMw(has_col=True)
        source = build_anki_enrichment_source(self.config)
        self.assertIsInstance(source, AnkiLocalEnrichmentSource)
        self.assertEqual(source.col, "FAKE_COL")

    def test_build_with_invalid_field_map_fallback(self):
        self.config["enable_anki_local_enrichment"] = True
        self.config["anki_local_enrichment_field_map"] = "invalid_type"
        factory_module.mw = _FakeMw(has_col=True)
        source = build_anki_enrichment_source(self.config)
        self.assertIsInstance(source, AnkiLocalEnrichmentSource)
        self.assertEqual(source.field_map, DEFAULT_CONFIG["anki_local_enrichment_field_map"])

    def test_build_with_invalid_search_fields_fallback(self):
        self.config["enable_anki_local_enrichment"] = True
        self.config["anki_local_enrichment_search_fields"] = [1, 2, 3]
        factory_module.mw = _FakeMw(has_col=True)
        source = build_anki_enrichment_source(self.config)
        self.assertIsInstance(source, AnkiLocalEnrichmentSource)
        self.assertEqual(source.search_field_names, DEFAULT_CONFIG["anki_local_enrichment_search_fields"])

    def test_build_with_max_matches_clamp(self):
        self.config["enable_anki_local_enrichment"] = True
        self.config["anki_local_enrichment_max_matches_per_term"] = 999
        factory_module.mw = _FakeMw(has_col=True)
        source = build_anki_enrichment_source(self.config)
        self.assertIsInstance(source, AnkiLocalEnrichmentSource)
        self.assertEqual(source.max_matches_per_term, 10)  # clamped
        
        self.config["anki_local_enrichment_max_matches_per_term"] = -1
        source = build_anki_enrichment_source(self.config)
        self.assertEqual(source.max_matches_per_term, 1)  # clamped

    def test_build_with_bool_clean(self):
        self.config["enable_anki_local_enrichment"] = "true"
        factory_module.mw = _FakeMw(has_col=True)
        source = build_anki_enrichment_source(self.config)
        self.assertIsNotNone(source)


if __name__ == "__main__":
    unittest.main()
