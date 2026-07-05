# Tests for core/rendering.py pure functions.

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "addon" / "daily_ai_reading_reinforcement"))

from core.rendering import (
    extract_article_block,
    parse_article_response,
    parse_review_notes,
    render_article_fragment_html,
    render_article_html,
    render_paragraph_html,
    render_review_notes_html,
)


class TestExtractArticleBlock(unittest.TestCase):

    def test_extracts_between_markers(self):
        raw = "[TITLE]\nHello World\n[MAIN]"
        self.assertEqual(extract_article_block(raw, "[TITLE]", "[MAIN]"), "Hello World")

    def test_no_start_marker(self):
        self.assertEqual(extract_article_block("No marker here", "[TITLE]"), "")

    def test_no_end_marker(self):
        raw = "[TITLE]\nSome content"
        self.assertEqual(extract_article_block(raw, "[TITLE]"), "Some content")

    def test_start_marker_not_found(self):
        raw = "Some content"
        self.assertEqual(extract_article_block(raw, "[TITLE]"), "")

    def test_empty_content(self):
        raw = "[TITLE]\n[MAIN]"
        self.assertEqual(extract_article_block(raw, "[TITLE]", "[MAIN]"), "")

    def test_multiline_content(self):
        raw = "[TITLE]\nLine 1\nLine 2\n[MAIN]"
        self.assertEqual(extract_article_block(raw, "[TITLE]", "[MAIN]"), "Line 1\nLine 2")


class TestParseReviewNotes(unittest.TestCase):

    def test_double_colon(self):
        raw = "term :: explanation"
        result = parse_review_notes(raw)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["term"], "term")
        self.assertEqual(result[0]["note"], "explanation")

    def test_chinese_colon(self):
        raw = "term ： explanation"
        result = parse_review_notes(raw)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["term"], "term")
        self.assertEqual(result[0]["note"], "explanation")

    def test_single_colon(self):
        raw = "term: explanation"
        result = parse_review_notes(raw)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["term"], "term")
        self.assertEqual(result[0]["note"], "explanation")

    def test_no_colon(self):
        raw = "just a note without term"
        result = parse_review_notes(raw)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["term"], "")
        self.assertEqual(result[0]["note"], "just a note without term")

    def test_bullet_lines(self):
        raw = "- term :: explanation\n* term2 :: explanation2"
        result = parse_review_notes(raw)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["term"], "term")
        self.assertEqual(result[1]["term"], "term2")

    def test_multiple_lines(self):
        raw = "term1 :: note1\nterm2 :: note2"
        result = parse_review_notes(raw)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["term"], "term1")
        self.assertEqual(result[1]["term"], "term2")

    def test_empty_string(self):
        result = parse_review_notes("")
        self.assertEqual(result, [])

    def test_none(self):
        result = parse_review_notes(None)
        self.assertEqual(result, [])

    def test_blank_lines_skipped(self):
        raw = "term :: note\n\n\nterm2 :: note2"
        result = parse_review_notes(raw)
        self.assertEqual(len(result), 2)


class TestParseArticleResponse(unittest.TestCase):

    def test_standard_format(self):
        article = (
            "[ARTICLE_TITLE]\nMy Title\n[MAIN_ARTICLE]\n"
            "Paragraph one.\n[T] Translation one.\n\n"
            "Paragraph two.\n[T] Translation two.\n"
            "[REVIEW_NOTES]\nterm1 :: note1\nterm2 :: note2"
        )
        result = parse_article_response(article)
        self.assertEqual(result["title"], "My Title")
        self.assertIn("Paragraph one.", result["main_article"])
        self.assertIn("Translation one.", result["main_article"])
        self.assertEqual(len(result["review_notes"]), 2)

    def test_missing_title(self):
        article = (
            "[MAIN_ARTICLE]\nParagraph one.\n"
            "[REVIEW_NOTES]\nterm :: note"
        )
        result = parse_article_response(article)
        self.assertEqual(result["title"], "Reading Article")
        self.assertIn("Paragraph one.", result["main_article"])

    def test_missing_review_notes(self):
        article = (
            "[ARTICLE_TITLE]\nMy Title\n[MAIN_ARTICLE]\nBody text."
        )
        result = parse_article_response(article)
        self.assertEqual(result["title"], "My Title")
        self.assertEqual(result["review_notes"], [])

    def test_no_blocks_at_all(self):
        article = "Just a plain text article."
        result = parse_article_response(article)
        self.assertEqual(result["title"], "Reading Article")
        self.assertEqual(result["main_article"], "Just a plain text article.")
        self.assertEqual(result["review_notes"], [])

    def test_empty_string(self):
        result = parse_article_response("")
        self.assertEqual(result["title"], "Reading Article")
        self.assertEqual(result["main_article"], "")
        self.assertEqual(result["review_notes"], [])

    def test_none(self):
        result = parse_article_response(None)
        self.assertEqual(result["title"], "Reading Article")
        self.assertEqual(result["main_article"], "")
        self.assertEqual(result["review_notes"], [])


class TestRenderParagraphHtml(unittest.TestCase):

    def test_single_paragraph(self):
        result = render_paragraph_html("Hello world")
        self.assertEqual(result, "<p>Hello world</p>")

    def test_multiple_paragraphs(self):
        result = render_paragraph_html("Para one.\n\nPara two.\n\nPara three.")
        self.assertIn("<p>Para one.</p>", result)
        self.assertIn("<p>Para two.</p>", result)
        self.assertIn("<p>Para three.</p>", result)

    def test_html_escaping(self):
        result = render_paragraph_html("<script>alert('xss')</script>")
        self.assertNotIn("<script>", result)
        self.assertIn("&lt;script&gt;", result)

    def test_single_newline_to_br(self):
        result = render_paragraph_html("Line one\nLine two")
        self.assertIn("<br>", result)
        self.assertIn("Line one", result)

    def test_empty_string(self):
        result = render_paragraph_html("")
        self.assertEqual(result, "")

    def test_none(self):
        result = render_paragraph_html(None)
        self.assertEqual(result, "")

    def test_blank_paragraphs_skipped(self):
        result = render_paragraph_html("Para one.\n\n\n\nPara two.")
        self.assertIn("<p>Para one.</p>", result)
        self.assertIn("<p>Para two.</p>", result)
        self.assertEqual(result.count("<p>"), 2)

    def test_ampersand_escaping(self):
        result = render_paragraph_html("A & B")
        self.assertIn("A &amp; B", result)


class TestRenderReviewNotesHtml(unittest.TestCase):

    def test_with_terms(self):
        notes = [{"term": "hello", "note": "a greeting"}, {"term": "world", "note": "the planet"}]
        result = render_review_notes_html(notes)
        self.assertIn("<dt>hello</dt>", result)
        self.assertIn("<dd>a greeting</dd>", result)
        self.assertIn("<dt>world</dt>", result)

    def test_no_terms(self):
        result = render_review_notes_html([])
        self.assertEqual(result, "")

    def test_html_escaping(self):
        notes = [{"term": "<b>bold</b>", "note": "<i>italic</i>"}]
        result = render_review_notes_html(notes)
        self.assertIn("&lt;b&gt;bold&lt;/b&gt;", result)
        self.assertIn("&lt;i&gt;italic&lt;/i&gt;", result)

    def test_empty_term_renders_no_dt(self):
        notes = [{"term": "", "note": "just a note"}]
        result = render_review_notes_html(notes)
        self.assertNotIn("<dt>", result)
        self.assertIn("<dd>just a note</dd>", result)


class TestRenderArticleFragmentHtml(unittest.TestCase):

    def test_standard_article(self):
        article = (
            "[ARTICLE_TITLE]\nMy Title\n[MAIN_ARTICLE]\n"
            "Paragraph text.\n"
            "[REVIEW_NOTES]\nterm :: note"
        )
        result = render_article_fragment_html(article)
        self.assertIn("reading-body", result)
        self.assertIn("Paragraph text.", result)
        self.assertIn("review-notes", result)

    def test_no_review_notes(self):
        article = (
            "[ARTICLE_TITLE]\nMy Title\n[MAIN_ARTICLE]\n"
            "Paragraph text."
        )
        result = render_article_fragment_html(article)
        self.assertIn("reading-body", result)
        self.assertNotIn("review-notes", result)


class TestRenderArticleHtml(unittest.TestCase):

    def setUp(self):
        self.mock_card = Mock()
        self.mock_card.term = "test term"

    def test_complete_html_output(self):
        article = (
            "[ARTICLE_TITLE]\nMy Reading\n[MAIN_ARTICLE]\n"
            "Body text.\n"
            "[REVIEW_NOTES]\nterm :: note"
        )
        cards = [self.mock_card]
        result = render_article_html("Test Deck", cards, article)
        self.assertIn("<!doctype html>", result.lower())
        self.assertIn("<title>Test Deck Reading Reinforcement</title>", result)
        self.assertIn("My Reading", result)
        self.assertIn("Body text.", result)
        self.assertIn("test term", result)

    def test_html_title_escaping(self):
        article = "[ARTICLE_TITLE]\n<script>alert('xss')</script>\n[MAIN_ARTICLE]\nBody\n"
        cards = [self.mock_card]
        result = render_article_html("Test Deck", cards, article)
        self.assertNotIn("<script>alert", result)
        self.assertIn("&lt;script&gt;", result)

    def test_deck_name_escaping(self):
        article = "[ARTICLE_TITLE]\nTitle\n[MAIN_ARTICLE]\nBody\n"
        cards = [self.mock_card]
        result = render_article_html('<b>Deck</b>', cards, article)
        self.assertNotIn("<b>Deck</b>", result)
        self.assertIn("&lt;b&gt;Deck&lt;/b&gt;", result)

    def test_empty_cards(self):
        article = "[ARTICLE_TITLE]\nTitle\n[MAIN_ARTICLE]\nBody\n"
        result = render_article_html("Test Deck", [], article)
        self.assertIn("from 0 studied cards", result)

    def test_cards_without_term(self):
        article = "[ARTICLE_TITLE]\nTitle\n[MAIN_ARTICLE]\nBody\n"
        mock_card_no_term = Mock()
        mock_card_no_term.term = ""
        result = render_article_html("Test Deck", [mock_card_no_term], article)
        self.assertIn("Source Terms", result)


if __name__ == "__main__":
    unittest.main()
