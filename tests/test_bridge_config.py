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
        config = {}
        payload = api_settings_payload(config)
        self.assertNotIn("enableAnkiLocalEnrichment", payload)
        self.assertNotIn("ankiLocalEnrichmentMaxMatchesPerTerm", payload)

    def test_api_settings_payload_clamp(self):
        config = {}
        payload = api_settings_payload(config)
        self.assertNotIn("enableAnkiLocalEnrichment", payload)
        self.assertNotIn("ankiLocalEnrichmentMaxMatchesPerTerm", payload)

if __name__ == '__main__':
    unittest.main()
