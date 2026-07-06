import unittest
import sys
from unittest.mock import MagicMock

# Mock Anki dependencies
sys.modules['aqt'] = MagicMock()
sys.modules['aqt.qt'] = MagicMock()
sys.modules['aqt.webview'] = MagicMock()
sys.modules['aqt.utils'] = MagicMock()
sys.modules['anki'] = MagicMock()
sys.modules['anki.hooks'] = MagicMock()
sys.modules['gui_hooks'] = MagicMock()

from addon.daily_ai_reading_reinforcement.__init__ import api_settings_payload

class TestBridgeConfig(unittest.TestCase):
    def test_api_settings_payload_default(self):
        config = {
            "enable_anki_local_enrichment": False,
            "anki_local_enrichment_max_matches_per_term": 3
        }
        payload = api_settings_payload(config)
        self.assertEqual(payload.get("enableAnkiLocalEnrichment"), False)
        self.assertEqual(payload.get("ankiLocalEnrichmentMaxMatchesPerTerm"), 3)

    def test_api_settings_payload_clamp(self):
        config = {
            "enable_anki_local_enrichment": True,
            "anki_local_enrichment_max_matches_per_term": 999
        }
        payload = api_settings_payload(config)
        self.assertEqual(payload.get("enableAnkiLocalEnrichment"), True)
        self.assertEqual(payload.get("ankiLocalEnrichmentMaxMatchesPerTerm"), 10)

if __name__ == '__main__':
    unittest.main()
