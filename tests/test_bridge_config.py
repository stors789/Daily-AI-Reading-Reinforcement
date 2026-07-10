import unittest
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from unittest.mock import patch

# Mock Anki dependencies
sys.modules['aqt'] = MagicMock()
sys.modules['aqt.qt'] = MagicMock()
sys.modules['aqt.webview'] = MagicMock()
sys.modules['aqt.utils'] = MagicMock()
sys.modules['anki'] = MagicMock()
sys.modules['anki.hooks'] = MagicMock()
sys.modules['gui_hooks'] = MagicMock()

import addon.daily_ai_reading_reinforcement.__init__ as addon_module
from addon.daily_ai_reading_reinforcement.__init__ import api_settings_payload

class TestBridgeConfig(unittest.TestCase):
    def test_api_settings_payload_default(self):
        config = {}
        payload = api_settings_payload(config)
        self.assertNotIn("enableAnkiLocalEnrichment", payload)
        self.assertNotIn("ankiLocalEnrichmentMaxMatchesPerTerm", payload)

    def test_api_settings_payload_clamp(self):
        config = {}
        payload = api_settings_payload(config)
        self.assertNotIn("enableAnkiLocalEnrichment", payload)
        self.assertNotIn("ankiLocalEnrichmentMaxMatchesPerTerm", payload)

    def test_create_article_card_uses_timestamp_and_generated_title(self):
        class FakeNote(dict):
            def cards(self):
                return []

        note = FakeNote()
        fake_mw = SimpleNamespace(
            col=SimpleNamespace(
                new_note=lambda model: note,
                sched=SimpleNamespace(suspendCards=lambda card_ids: None),
            )
        )
        article = "[ARTICLE_TITLE]\nA <b>safe</b> title\n[MAIN_ARTICLE]\nBody."

        with (
            patch.object(addon_module, "mw", fake_mw),
            patch.object(addon_module, "get_or_create_deck_id", return_value=42),
            patch.object(addon_module, "get_or_create_article_model", return_value=object()),
            patch.object(addon_module, "add_note_to_deck"),
            patch.object(addon_module, "article_card_date", return_value="2026-07-11 10:20:30.123456"),
        ):
            addon_module.create_article_card(
                "Source Deck", [], article, Path("/tmp/a.md"), Path("/tmp/a.html")
            )

        self.assertEqual(note["Date"], "2026-07-11 10:20:30.123456")
        self.assertEqual(note["Title"], "2026-07-11 10:20:30 · A safe title")

if __name__ == '__main__':
    unittest.main()
