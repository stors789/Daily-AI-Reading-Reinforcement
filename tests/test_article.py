# Tests for core/article.py functions using tmp_path.

import sys
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "addon" / "daily_ai_reading_reinforcement"))

import core.article as article_mod
from core.article import (
    parse_article_frontmatter,
    save_article,
    list_saved_articles,
    load_saved_article,
)


class TestParseArticleFrontmatter(unittest.TestCase):

    def test_standard_frontmatter(self):
        text = "---\ndeck: My Deck\ngenerated_at: 2025-01-01 12:00:00\ncard_count: 5\n---\n\nBody text."
        result = parse_article_frontmatter(text)
        self.assertEqual(result["deck"], "My Deck")
        self.assertEqual(result["generated_at"], "2025-01-01 12:00:00")
        self.assertEqual(result["card_count"], "5")

    def test_no_frontmatter(self):
        text = "Just body text without frontmatter."
        result = parse_article_frontmatter(text)
        self.assertEqual(result, {})

    def test_only_opening_dashes(self):
        text = "---\ndeck: Test\nNo closing dashes."
        result = parse_article_frontmatter(text)
        self.assertEqual(result, {})

    def test_empty_frontmatter(self):
        text = "---\n---\nBody text."
        result = parse_article_frontmatter(text)
        self.assertEqual(result, {})

    def test_empty_string(self):
        result = parse_article_frontmatter("")
        self.assertEqual(result, {})

    def test_no_colon_line(self):
        text = "---\ndeck\nname: value\n---\nBody"
        result = parse_article_frontmatter(text)
        self.assertEqual(result, {"name": "value"})


class TestSaveListLoadArticle(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = Path(__file__).resolve().parent / "_test_articles"
        self.tmp_dir.mkdir(exist_ok=True)
        # Monkey-patch ARTICLES_DIR to use tmp
        self._orig_dir = article_mod.ARTICLES_DIR
        article_mod.ARTICLES_DIR = self.tmp_dir

    def tearDown(self):
        article_mod.ARTICLES_DIR = self._orig_dir
        # Clean up test files
        import shutil
        if self.tmp_dir.exists():
            shutil.rmtree(self.tmp_dir)

    def _make_mock_card(self, term_value="test term", is_new=False, is_failed=False):
        card = Mock()
        card.term = term_value
        card.is_new = is_new
        card.is_failed = is_failed
        card.fields = {"Front": "Hello", "Back": "World"}
        return card

    def test_save_article_creates_files(self):
        cards = [self._make_mock_card("hello")]
        deck_name = "Test Deck"
        article_text = (
            "[ARTICLE_TITLE]\nSample Title\n[MAIN_ARTICLE]\n"
            "Body paragraph.\n"
            "[REVIEW_NOTES]\nterm :: note"
        )
        result = save_article(deck_name, cards, article_text)
        self.assertIn("markdown", result)
        self.assertIn("html", result)
        self.assertTrue(result["markdown"].exists())
        self.assertTrue(result["html"].exists())

    def test_save_article_markdown_content(self):
        cards = [self._make_mock_card("hello")]
        deck_name = "My Deck"
        article_text = "Article body here."
        result = save_article(deck_name, cards, article_text)
        md_content = result["markdown"].read_text(encoding="utf-8")
        self.assertIn("deck: My Deck", md_content)
        self.assertIn("Article body here.", md_content)
        self.assertIn("---", md_content)

    def test_save_article_html_content(self):
        cards = [self._make_mock_card("hello")]
        deck_name = "My Deck"
        article_text = (
            "[ARTICLE_TITLE]\nTitle\n[MAIN_ARTICLE]\n"
            "Hello world.\n"
            "[REVIEW_NOTES]\nterm :: note"
        )
        result = save_article(deck_name, cards, article_text)
        html_content = result["html"].read_text(encoding="utf-8")
        self.assertIn("<!doctype html>", html_content.lower())
        self.assertIn("Title", html_content)

    def test_list_saved_articles_empty(self):
        articles = list_saved_articles()
        self.assertEqual(articles, [])

    def test_list_saved_articles_with_data(self):
        cards = [self._make_mock_card("term1")]
        save_article("Deck A", cards, "Article content A.")
        time.sleep(0.1)  # ensure different filename timestamps
        save_article("Deck B", cards, "Article content B.")
        articles = list_saved_articles()
        self.assertEqual(len(articles), 2)
        # Most recent first
        self.assertEqual(articles[0]["deck"], "Deck B")
        self.assertEqual(articles[1]["deck"], "Deck A")

    def test_load_saved_article(self):
        cards = [self._make_mock_card("term1")]
        deck_name = "Load Test"
        article_text = (
            "[ARTICLE_TITLE]\nLoad Title\n[MAIN_ARTICLE]\n"
            "Load body.\n"
            "[REVIEW_NOTES]\nterm :: note"
        )
        result = save_article(deck_name, cards, article_text)
        loaded = load_saved_article(str(result["markdown"]))
        self.assertEqual(loaded["deck"], "Load Test")
        self.assertIn("Load body.", loaded["article"])
        self.assertIn("Load Title", loaded["article"])

    def test_load_saved_article_not_found(self):
        with self.assertRaises(RuntimeError) as ctx:
            load_saved_article("/nonexistent/path/article.md")
        self.assertIn("not found", str(ctx.exception))

    def test_load_saved_article_outside_dir(self):
        # Create a real file outside ARTICLES_DIR to test path restriction
        outside_path = Path("/tmp/_test_outside_article.md")
        outside_path.write_text("---\ndeck: Outside\n---\nBody.", encoding="utf-8")
        try:
            with self.assertRaises(RuntimeError) as ctx:
                load_saved_article(str(outside_path))
            self.assertIn("Access denied", str(ctx.exception))
        finally:
            if outside_path.exists():
                outside_path.unlink()

    def test_save_article_slugifies_deck_name(self):
        cards = [self._make_mock_card("term")]
        deck_name = "Deck! With@ Special# Chars"
        result = save_article(deck_name, cards, "Content.")
        filename = result["markdown"].name
        self.assertIn("Deck-With-Special-Chars", filename)
        self.assertNotIn("!", filename)

    def test_save_article_same_second_uses_unique_filenames(self):
        cards = [self._make_mock_card("term")]

        class FakeUUID:
            def __init__(self, value):
                self.hex = value

        with (
            patch.object(article_mod.time, "strftime", side_effect=lambda fmt: {
                "%Y-%m-%d": "2026-07-08",
                "%H%M%S": "123456",
                "%Y-%m-%d %H:%M:%S": "2026-07-08 12:34:56",
            }.get(fmt, "2026-07-08")),
            patch.object(article_mod.time, "time", return_value=123456.789),
            patch.object(
                article_mod.uuid,
                "uuid4",
                side_effect=[FakeUUID("abcdef123456"), FakeUUID("123456abcdef")],
            ),
        ):
            first = save_article("Deck", cards, "First.")
            second = save_article("Deck", cards, "Second.")

        self.assertNotEqual(first["markdown"], second["markdown"])
        self.assertTrue(first["markdown"].exists())
        self.assertTrue(second["markdown"].exists())


if __name__ == "__main__":
    unittest.main()
