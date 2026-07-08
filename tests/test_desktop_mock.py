"""Tests for the desktop mock bridge handler.

These exercise the pure Python handler (handle_action) and mock data shape
without starting the HTTP server or opening a browser.
"""

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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

    def test_save_collapsed_deck_groups_is_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(
            os.environ,
            {"DESKTOP_CONFIG_PATH": str(Path(tmpdir) / "config.json")},
        ):
            result = _main.handle_action(
                "saveCollapsedDeckGroups",
                {"collapsedDeckGroups": ["Parent::Child"]},
            )

        self.assertEqual(result["event"], "noop")

    def test_save_field_config_returns_saved_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(
            os.environ,
            {"DESKTOP_CONFIG_PATH": str(Path(tmpdir) / "config.json")},
        ):
            result = _main.handle_action(
                "saveFieldConfig",
                {"deckId": "deck-japanese", "fields": ["Front"]},
            )

        self.assertEqual(result["event"], "fieldConfigSaved")
        self.assertEqual(result["payload"]["selectedFields"], ["Front"])

    def test_debug_prompt_uses_payload_preset_id_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(
            os.environ,
            {"DESKTOP_CONFIG_PATH": str(Path(tmpdir) / "config.json")},
        ):
            self._write_debug_config(Path(tmpdir) / "config.json")
            result = _main.handle_action(
                "debugPrompt",
                {
                    "deckId": "deck-japanese",
                    "presetId": "english",
                    "cardIds": [1001, 1002, 1003],
                },
            )

        self.assertEqual(result["event"], "debugPrompt")
        payload = result["payload"]
        self.assertEqual(payload["selectedPromptPresetId"], "japanese")
        self.assertEqual(payload["requestedPresetId"], "english")
        self.assertEqual(payload["resolvedPreset"]["id"], "english")
        self.assertEqual(payload["articleLanguage"], "English")

    def test_debug_prompt_falls_back_to_selected_preset(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(
            os.environ,
            {"DESKTOP_CONFIG_PATH": str(Path(tmpdir) / "config.json")},
        ):
            self._write_debug_config(Path(tmpdir) / "config.json")
            result = _main.handle_action(
                "debugPrompt",
                {"deckId": "deck-japanese", "cardIds": [1001, 1002, 1003]},
            )

        self.assertEqual(result["event"], "debugPrompt")
        payload = result["payload"]
        self.assertEqual(payload["requestedPresetId"], "")
        self.assertEqual(payload["resolvedPreset"]["id"], "japanese")
        self.assertEqual(payload["articleLanguage"], "Japanese")

    def test_debug_prompt_preview_contains_article_language(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(
            os.environ,
            {"DESKTOP_CONFIG_PATH": str(Path(tmpdir) / "config.json")},
        ):
            self._write_debug_config(Path(tmpdir) / "config.json")
            result = _main.handle_action(
                "debugPrompt",
                {"deckId": "deck-japanese", "presetId": "japanese"},
            )

        self.assertEqual(result["event"], "debugPrompt")
        payload = result["payload"]
        self.assertIn("Japanese", payload["promptPreview"])
        self.assertTrue(payload["promptContainsArticleLanguage"])

    def test_debug_prompt_does_not_leak_api_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(
            os.environ,
            {"DESKTOP_CONFIG_PATH": str(Path(tmpdir) / "config.json")},
        ):
            self._write_debug_config(Path(tmpdir) / "config.json")
            result = _main.handle_action(
                "debugPrompt",
                {"deckId": "deck-japanese", "presetId": "japanese"},
            )

        self.assertEqual(result["event"], "debugPrompt")
        serialized = json.dumps(result["payload"], ensure_ascii=False)
        self.assertNotIn("super-secret-key", serialized)
        self.assertNotIn("api_key", serialized.lower())

    def test_debug_prompt_selected_card_ids_affect_card_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(
            os.environ,
            {"DESKTOP_CONFIG_PATH": str(Path(tmpdir) / "config.json")},
        ):
            self._write_debug_config(Path(tmpdir) / "config.json")
            result = _main.handle_action(
                "debugPrompt",
                {
                    "deckId": "deck-japanese",
                    "presetId": "japanese",
                    "cardIds": [1001, 1003],
                },
            )

        self.assertEqual(result["event"], "debugPrompt")
        self.assertEqual(result["payload"]["cardCount"], 2)

    def test_debug_prompt_provider_failure_returns_safe_error(self) -> None:
        with patch.object(_main, "get_deck_provider", side_effect=Exception("secret")):
            result = _main.handle_action("debugPrompt", {"deckId": "deck-japanese"})

        self.assertEqual(result["event"], "error")
        self.assertIn("Failed to build debug prompt", result["payload"]["message"])
        self.assertNotIn("secret", result["payload"]["message"])

    def _write_debug_config(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "api_key": "super-secret-key",
                    "ui_language": "en",
                    "selected_prompt_preset_id": "japanese",
                    "prompt_presets": [
                        {
                            "id": "default",
                            "name": "Default",
                            "reader_native_language": "",
                            "article_language": "",
                            "difficulty": "",
                            "max_words": "",
                            "instructions": "",
                            "prompt_template": "",
                        },
                        {
                            "id": "japanese",
                            "name": "Japanese",
                            "reader_native_language": "English",
                            "article_language": "Japanese",
                            "difficulty": "N4",
                            "max_words": "",
                            "instructions": "Use short paragraphs.",
                            "prompt_template": "",
                        },
                        {
                            "id": "english",
                            "name": "English",
                            "reader_native_language": "中文",
                            "article_language": "English",
                            "difficulty": "B1",
                            "max_words": "",
                            "instructions": "",
                            "prompt_template": "",
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )


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


class TestProviderIntegration(unittest.TestCase):
    """Verify handle_action routes through the provider correctly."""

    def test_load_passes_decks_from_provider(self) -> None:
        result = _main.handle_action("load", {})
        payload = result["payload"]
        self.assertEqual(len(payload["decks"]), 2)
        names = [d["name"] for d in payload["decks"]]
        self.assertEqual(names, sorted(names, key=str.lower))

    def test_select_deck_passes_cards_from_provider(self) -> None:
        result = _main.handle_action("selectDeck", {"deckId": "deck-japanese"})
        payload = result["payload"]
        self.assertEqual(payload["deckId"], "deck-japanese")
        self.assertEqual(len(payload["cards"]), 3)


if __name__ == "__main__":
    unittest.main()
