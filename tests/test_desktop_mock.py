"""Tests for the desktop mock bridge handler.

These exercise the pure Python handler (handle_action) and mock data shape
without starting the HTTP server or opening a browser.
"""

import importlib.util
import sys
import unittest
from pathlib import Path

_mock_dir = Path(__file__).resolve().parent.parent / "desktop_mock"
# main.py imports mock_data as a top-level module, so make the mock dir
# importable both when running the server and when importing it from tests.
if str(_mock_dir) not in sys.path:
    sys.path.insert(0, str(_mock_dir))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_main = _load("dairr_mock_main", _mock_dir / "main.py")
_data = _load("dairr_mock_data", _mock_dir / "mock_data.py")


class TestHandleAction(unittest.TestCase):
    def test_load_returns_state_with_required_fields(self) -> None:
        result = _main.handle_action("load", {})
        self.assertEqual(result["event"], "state")
        payload = result["payload"]
        for key in (
            "decks",
            "dayStart",
            "dayEnd",
            "promptPresets",
            "selectedPromptPresetId",
            "uiLanguage",
            "collapsedDeckGroups",
            "lastSelectedDeckId",
            "providerProfiles",
            "apiSettings",
            "articleCardSettings",
        ):
            self.assertIn(key, payload, f"state payload missing {key}")

    def test_load_returns_two_decks(self) -> None:
        result = _main.handle_action("load", {})
        self.assertEqual(len(result["payload"]["decks"]), 2)

    def test_select_deck_returns_cards(self) -> None:
        result = _main.handle_action("selectDeck", {"deckId": "deck-japanese"})
        self.assertEqual(result["event"], "deckCards")
        payload = result["payload"]
        self.assertEqual(payload["deckId"], "deck-japanese")
        self.assertEqual(len(payload["cards"]), 3)
        self.assertTrue(payload["fields"])
        self.assertTrue(payload["selectedFields"])

    def test_select_unknown_deck_returns_empty(self) -> None:
        result = _main.handle_action("selectDeck", {"deckId": "nope"})
        self.assertEqual(result["event"], "deckCards")
        self.assertEqual(result["payload"]["cards"], [])

    def test_generate_returns_mock_article_without_network(self) -> None:
        result = _main.handle_action("generate", {"deckId": "deck-english"})
        self.assertEqual(result["event"], "article")
        payload = result["payload"]
        self.assertIn("[ARTICLE_TITLE]", payload["article"])
        self.assertIn("[MAIN_ARTICLE]", payload["article"])
        self.assertIn("[REVIEW_NOTES]", payload["article"])
        self.assertEqual(payload["deckName"], "English Vocab")
        self.assertIsNone(payload["articleCard"])

    def test_list_articles_returns_list(self) -> None:
        result = _main.handle_action("listArticles", {})
        self.assertEqual(result["event"], "articleList")
        self.assertIsInstance(result["payload"]["articles"], list)
        self.assertTrue(result["payload"]["articles"])

    def test_load_article_returns_loaded_article(self) -> None:
        path = "mock/2026-07-05-english-vocab-081012.md"
        result = _main.handle_action("loadArticle", {"path": path})
        self.assertEqual(result["event"], "articleLoaded")
        self.assertEqual(result["payload"]["path"], path)
        self.assertIn("[ARTICLE_TITLE]", result["payload"]["article"])

    def test_unknown_action_returns_error_without_raising(self) -> None:
        result = _main.handle_action("doesNotExist", {})
        self.assertEqual(result["event"], "error")
        self.assertIn("Unknown command", result["payload"]["message"])


class TestMockDataShape(unittest.TestCase):
    def test_two_decks_each_with_three_cards(self) -> None:
        self.assertEqual(len(_data.MOCK_DECKS), 2)
        for deck in _data.MOCK_DECKS.values():
            self.assertEqual(len(deck["cards"]), 3)

    def test_card_payload_has_required_fields(self) -> None:
        for card in _data.MOCK_CARDS:
            for field in (
                "cid",
                "nid",
                "deck_id",
                "term",
                "fields",
                "is_new",
                "is_failed",
                "review_count",
            ):
                self.assertIn(field, card, f"mock card missing {field}")

    def test_state_deck_rows_match_frontend_contract(self) -> None:
        decks = _data.build_state_payload()["decks"]
        for deck in decks:
            for key in ("id", "name", "newCount", "failedCount", "totalCount", "isGroup"):
                self.assertIn(key, deck, f"deck row missing {key}")


if __name__ == "__main__":
    unittest.main()
