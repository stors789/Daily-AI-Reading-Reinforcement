"""Tests for provider switch in desktop_mock/main.py."""

import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

_mock_dir = Path(__file__).resolve().parent.parent / "desktop_mock"
if str(_mock_dir) not in sys.path:
    sys.path.insert(0, str(_mock_dir))

def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

_main = _load("dairr_mock_main", _mock_dir / "main.py")
from ankiconnect_provider import AnkiConnectDeckProvider, AnkiConnectError
from momo_provider import MockMoMoDeckProvider
from real_momo_provider import RealMoMoDeckProvider


class TestProviderFactory(unittest.TestCase):
    def test_default_returns_mock(self):
        provider = _main.build_deck_provider({})
        self.assertIsInstance(provider, MockMoMoDeckProvider)

    def test_explicit_mock_returns_mock(self):
        provider = _main.build_deck_provider({"DAIRR_DESKTOP_PROVIDER": "mock"})
        self.assertIsInstance(provider, MockMoMoDeckProvider)

    def test_real_momo_with_token_returns_real(self):
        provider = _main.build_deck_provider({
            "DAIRR_DESKTOP_PROVIDER": "real_momo",
            "MOMO_TOKEN": "abc123secret"
        })
        self.assertIsInstance(provider, RealMoMoDeckProvider)
        self.assertEqual(provider._token, "abc123secret")

    def test_real_momo_with_maimemo_key_returns_real(self):
        provider = _main.build_deck_provider({
            "DAIRR_DESKTOP_PROVIDER": "real_momo",
            "Maimemo_key": "legacysecret"
        })
        self.assertIsInstance(provider, RealMoMoDeckProvider)
        self.assertEqual(provider._token, "legacysecret")

    def test_ankiconnect_returns_ankiconnect_provider(self):
        provider = _main.build_deck_provider({
            "DAIRR_DESKTOP_PROVIDER": "ankiconnect",
        })
        self.assertIsInstance(provider, AnkiConnectDeckProvider)
        self.assertEqual(provider._base_url, "http://127.0.0.1:8765")

    def test_ankiconnect_url_can_be_overridden(self):
        provider = _main.build_deck_provider({
            "DAIRR_DESKTOP_PROVIDER": "ankiconnect",
            "DAIRR_ANKICONNECT_URL": "http://127.0.0.1:18765/",
        })
        self.assertIsInstance(provider, AnkiConnectDeckProvider)
        self.assertEqual(provider._base_url, "http://127.0.0.1:18765")

    def test_real_momo_without_token_raises_error(self):
        with patch.object(_main, "_load_provider_config", return_value={}):
            with self.assertRaises(ValueError) as cm:
                _main.build_deck_provider({"DAIRR_DESKTOP_PROVIDER": "real_momo"})
        self.assertIn("MOMO_TOKEN is missing", str(cm.exception))

    def test_unknown_provider_raises_error(self):
        with self.assertRaises(ValueError) as cm:
            _main.build_deck_provider({"DAIRR_DESKTOP_PROVIDER": "unknown_provider"})
        self.assertIn("Unknown DAIRR_DESKTOP_PROVIDER", str(cm.exception))



class TestHandleActionWithFakeProvider(unittest.TestCase):
    def setUp(self):
        self.original_provider = _main.DECK_PROVIDER
        self.fake_provider = MagicMock()
        _main.DECK_PROVIDER = self.fake_provider

    def tearDown(self):
        _main.DECK_PROVIDER = self.original_provider

    def test_load_success_returns_state(self):
        self.fake_provider.get_today_decks.return_value = [{"id": "test_deck", "name": "Test", "isGroup": False, "totalCount": 10, "newCount": 0, "failedCount": 0}]
        result = _main.handle_action("load", {})
        self.assertEqual(result["event"], "state")
        self.assertEqual(result["payload"]["decks"][0]["id"], "test_deck")

    def test_load_error_returns_safe_error_event(self):
        self.fake_provider.get_today_decks.side_effect = Exception("Super secret token 123 failed")
        result = _main.handle_action("load", {})
        self.assertEqual(result["event"], "error")
        # Should not leak the exception message to the payload
        self.assertNotIn("secret", result["payload"]["message"])
        self.assertIn("Failed to load decks", result["payload"]["message"])

    def test_ankiconnect_offline_returns_retryable_provider_event(self):
        self.fake_provider.get_today_decks.side_effect = AnkiConnectError("secret endpoint detail")
        result = _main.handle_action("load", {})
        self.assertEqual(result["event"], "providerOffline")
        self.assertEqual(result["payload"]["provider"], "ankiconnect")
        self.assertTrue(result["payload"]["retryable"])
        self.assertEqual(
            result["payload"]["message"],
            "无法连接 AnkiConnect。请启动 Anki，并确认 AnkiConnect 已安装和启用。",
        )
        self.assertNotIn("secret", result["payload"]["message"])

    def test_select_deck_success_returns_cards(self):
        self.fake_provider.get_deck_cards.return_value = {"deckId": "test_deck", "cards": [], "fields": ["term"], "selectedFields": ["term"]}
        result = _main.handle_action("selectDeck", {"deckId": "test_deck"})
        self.assertEqual(result["event"], "deckCards")
        self.assertEqual(result["payload"]["deckId"], "test_deck")

    @patch('sys.stderr')
    def test_select_deck_error_returns_safe_error_event(self, mock_stderr):
        err = Exception("Super secret token 123 failed")
        err.__cause__ = Exception("Inner secret")
        self.fake_provider.get_deck_cards.side_effect = err
        result = _main.handle_action("selectDeck", {"deckId": "test_deck"})
        self.assertEqual(result["event"], "error")
        # Should not leak the exception message to the payload
        self.assertNotIn("secret", result["payload"]["message"])
        self.assertIn("Failed to load deck cards", result["payload"]["message"])
        mock_stderr.write.assert_called_with("[mock] Provider error on selectDeck: Exception cause=Exception\n")

    @patch('sys.stderr')
    def test_select_deck_error_with_stage_returns_safe_error_event(self, mock_stderr):
        err = Exception("Super secret token 123 failed")
        err.stage = "today_items_request"
        class DummyHTTPError(Exception):
            def __init__(self, code):
                self.code = code
        err.__cause__ = DummyHTTPError(401)
        self.fake_provider.get_deck_cards.side_effect = err
        result = _main.handle_action("selectDeck", {"deckId": "test_deck"})
        self.assertEqual(result["event"], "error")
        # Should not leak the exception message to the payload
        self.assertNotIn("secret", result["payload"]["message"])
        self.assertEqual("Failed to load deck cards from provider. Stage: today_items_request", result["payload"]["message"])
        mock_stderr.write.assert_called_with("[mock] Provider error on selectDeck: Exception stage=today_items_request cause=DummyHTTPError(code=401)\n")


if __name__ == "__main__":
    unittest.main()
