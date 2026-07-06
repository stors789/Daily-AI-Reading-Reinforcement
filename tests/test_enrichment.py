"""Tests for enrichment source and mock implementation."""

import unittest

from desktop_mock.enrichment import MockEnrichmentSource, WordEnrichment


class TestEnrichment(unittest.TestCase):
    def test_word_enrichment_defaults(self):
        we = WordEnrichment()
        self.assertIsNone(we.phonetic)
        self.assertIsNone(we.audio_url)
        self.assertIsNone(we.interpretation)
        self.assertIsNone(we.phrase)
        self.assertIsNone(we.phrase_translation)
        self.assertIsNone(we.source)

    def test_mock_enrichment_source_returns_hit(self):
        source = MockEnrichmentSource({
            "apple": WordEnrichment(phonetic="/æpl/", interpretation="n. 苹果")
        })
        res = source.enrich_words(["apple", "banana"])
        self.assertIn("apple", res)
        self.assertEqual(res["apple"].phonetic, "/æpl/")
        self.assertEqual(res["apple"].interpretation, "n. 苹果")
        self.assertNotIn("banana", res)

    def test_mock_enrichment_source_ignores_empty(self):
        source = MockEnrichmentSource({"apple": WordEnrichment()})
        res = source.enrich_words(["", "apple", None]) # type: ignore
        self.assertNotIn("", res)
        self.assertNotIn(None, res)
        self.assertIn("apple", res)

    def test_mock_enrichment_source_no_mutate_input(self):
        source = MockEnrichmentSource({"apple": WordEnrichment()})
        terms = ["apple"]
        source.enrich_words(terms)
        self.assertEqual(terms, ["apple"])


if __name__ == "__main__":
    unittest.main()
