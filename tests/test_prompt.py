# Tests for core/prompt.py pure functions.

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "addon" / "daily_ai_reading_reinforcement"))

from core.prompt import build_prompt, writing_language_for_ui


class TestWritingLanguageForUi(unittest.TestCase):

    def test_zh(self):
        self.assertEqual(writing_language_for_ui("zh"), "中文")

    def test_en(self):
        self.assertEqual(writing_language_for_ui("en"), "English")

    def test_ja(self):
        self.assertEqual(writing_language_for_ui("ja"), "日本語")

    def test_unknown(self):
        self.assertEqual(writing_language_for_ui("fr"), "中文")

    def test_empty(self):
        self.assertEqual(writing_language_for_ui(""), "中文")

    def test_none_like(self):
        self.assertEqual(writing_language_for_ui("None"), "中文")


class TestBuildPrompt(unittest.TestCase):

    def setUp(self):
        self.base_config = {
            "ui_language": "zh",
            "prompt_template": "",
        }
        self.base_preset = {
            "reader_native_language": "",
            "article_language": "",
            "difficulty": "",
            "max_words": "",
            "instructions": "",
            "prompt_template": "",
        }

    def _make_mock_card(self, term_value="term", is_new=False, is_failed=False, fields=None):
        card = Mock()
        card.term = term_value
        card.is_new = is_new
        card.is_failed = is_failed
        card.fields = fields or {"Front": "hello", "Back": "world"}
        return card

    def test_default_prompt(self):
        card = self._make_mock_card()
        result = build_prompt(self.base_config, "Test Deck", [card], ["Front", "Back"], self.base_preset)
        self.assertIn("reading reinforcement", result)
        self.assertIn("Front: hello", result)
        self.assertIn("Back: world", result)

    def test_custom_language(self):
        config = dict(self.base_config)
        config["ui_language"] = "en"
        result = build_prompt(config, "Deck", [], ["Front"], self.base_preset)
        self.assertIn("English", result)

    def test_word_range(self):
        preset = dict(self.base_preset)
        preset["max_words"] = "200-400"
        result = build_prompt(self.base_config, "Deck", [], ["Front"], preset)
        self.assertIn("between about 200 and 400", result)

    def test_single_word_count(self):
        preset = dict(self.base_preset)
        preset["max_words"] = "300"
        result = build_prompt(self.base_config, "Deck", [], ["Front"], preset)
        self.assertIn("about 300", result)

    def test_no_limit(self):
        preset = dict(self.base_preset)
        preset["max_words"] = ""
        result = build_prompt(self.base_config, "Deck", [], ["Front"], preset)
        self.assertIn("No fixed length limit", result)

    def test_new_card_label(self):
        card = self._make_mock_card(is_new=True)
        result = build_prompt(self.base_config, "Deck", [card], ["Front"], self.base_preset)
        self.assertIn("(new)", result)

    def test_failed_card_label(self):
        card = self._make_mock_card(is_failed=True)
        result = build_prompt(self.base_config, "Deck", [card], ["Front"], self.base_preset)
        self.assertIn("(failed)", result)

    def test_new_and_failed_label(self):
        card = self._make_mock_card(is_new=True, is_failed=True)
        result = build_prompt(self.base_config, "Deck", [card], ["Front"], self.base_preset)
        self.assertIn("(new, failed)", result)

    def test_studied_label(self):
        card = self._make_mock_card(is_new=False, is_failed=False)
        result = build_prompt(self.base_config, "Deck", [card], ["Front"], self.base_preset)
        self.assertIn("(studied)", result)

    def test_card_without_selected_fields(self):
        card = self._make_mock_card(fields={"Front": "hello"})
        result = build_prompt(self.base_config, "Deck", [card], ["Back"], self.base_preset)
        self.assertIn("(studied)", result)
        self.assertNotIn("Back:", result)

    def test_instructions_in_prompt(self):
        preset = dict(self.base_preset)
        preset["instructions"] = "Use bullet points."
        result = build_prompt(self.base_config, "Deck", [], ["Front"], preset)
        self.assertIn("Use bullet points.", result)

    def test_custom_prompt_template(self):
        preset = dict(self.base_preset)
        preset["prompt_template"] = "CUSTOM TEMPLATE {deck_name}"
        result = build_prompt(self.base_config, "MyDeck", [], ["Front"], preset)
        self.assertIn("CUSTOM TEMPLATE MyDeck", result)

    def test_config_prompt_template_fallback(self):
        config = dict(self.base_config)
        config["prompt_template"] = "CONFIG TEMPLATE {deck_name}"
        result = build_prompt(config, "MyDeck", [], ["Front"], self.base_preset)
        self.assertIn("CONFIG TEMPLATE MyDeck", result)

    def test_reader_native_language_falls_back(self):
        preset = dict(self.base_preset)
        preset["reader_native_language"] = "日本語"
        result = build_prompt(self.base_config, "Deck", [], ["Front"], preset)
        self.assertIn("日本語", result)

    def test_more_than_80_cards_truncated(self):
        cards = [self._make_mock_card(term_value=f"term{i}") for i in range(100)]
        result = build_prompt(self.base_config, "Deck", cards, ["Front"], self.base_preset)
        # card 81 starts with "81." - should not appear
        self.assertIn("80.", result)
        self.assertNotIn("81.", result)


if __name__ == "__main__":
    unittest.main()
