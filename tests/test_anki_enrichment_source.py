import sys
import unittest
from pathlib import Path

_addon_root = Path(__file__).resolve().parent.parent / "addon" / "daily_ai_reading_reinforcement"
sys.path.insert(0, str(_addon_root))

from anki_enrichment_source import AnkiLocalEnrichmentSource, clean_field_text

class FakeNote:
    def __init__(self, fields: dict[str, str]):
        self._fields = fields
    
    def items(self):
        return self._fields.items()

class FakeCollection:
    def __init__(self):
        self.notes = {}
        self.find_results = {}
        self.find_error = False
        self.get_note_error = False

    def find_notes(self, query: str) -> list[int]:
        if self.find_error:
            raise Exception("Search failed")
        return self.find_results.get(query, [])

    def get_note(self, nid: int) -> FakeNote:
        if self.get_note_error:
            raise Exception("Get note failed")
        if nid not in self.notes:
            raise Exception("Note not found")
        return self.notes[nid]

class TestAnkiLocalEnrichmentSource(unittest.TestCase):
    def setUp(self):
        self.col = FakeCollection()
        self.source = AnkiLocalEnrichmentSource(self.col)

    def test_clean_field_text(self):
        self.assertEqual(clean_field_text(""), "")
        self.assertEqual(clean_field_text("  hello  "), "hello")
        self.assertEqual(clean_field_text("<div>hello</div>"), "hello")
        self.assertEqual(clean_field_text("hello <br> world"), "hello world")
        self.assertEqual(clean_field_text("  multiple   spaces  "), "multiple spaces")
        self.assertEqual(clean_field_text("[sound:test.mp3]"), "[sound:test.mp3]")

    def test_empty_terms(self):
        results = self.source.enrich_words([])
        self.assertEqual(results, {})
        
        results2 = self.source.enrich_words(["", "  ", None])
        self.assertEqual(results2, {})

    def test_deduplication(self):
        self.col.notes[1] = FakeNote({"Word": "apple", "Meaning": "fruit"})
        self.col.find_results['"apple"'] = [1]
        
        results = self.source.enrich_words(["apple", "apple"])
        self.assertIn("apple", results)
        self.assertEqual(results["apple"].interpretation, "fruit")

    def test_full_extraction(self):
        self.col.notes[1] = FakeNote({
            "Word": "apple",
            "Meaning": "fruit",
            "Phonetic": "æpl",
            "Example": "I eat an apple.",
            "ExampleTranslation": "我吃一个苹果。",
            "Audio": "[sound:apple.mp3]"
        })
        self.col.find_results['"apple"'] = [1]
        
        results = self.source.enrich_words(["apple"])
        self.assertIn("apple", results)
        enrichment = results["apple"]
        self.assertEqual(enrichment.interpretation, "fruit")
        self.assertEqual(enrichment.phonetic, "æpl")
        self.assertEqual(enrichment.phrase, "I eat an apple.")
        self.assertEqual(enrichment.phrase_translation, "我吃一个苹果。")
        self.assertEqual(enrichment.audio_url, "[sound:apple.mp3]")
        self.assertEqual(enrichment.source, "anki_local")

    def test_partial_extraction(self):
        self.col.notes[2] = FakeNote({
            "Word": "banana",
            "释义": "香蕉",
        })
        self.col.find_results['"banana"'] = [2]
        
        results = self.source.enrich_words(["banana"])
        self.assertIn("banana", results)
        enrichment = results["banana"]
        self.assertEqual(enrichment.interpretation, "香蕉")
        self.assertIsNone(enrichment.phonetic)

    def test_search_error_isolation(self):
        self.col.find_error = True
        # Should not raise exception
        results = self.source.enrich_words(["apple"])
        self.assertEqual(results, {})

    def test_no_match_returns_empty(self):
        self.col.find_results['"apple"'] = []
        results = self.source.enrich_words(["apple"])
        self.assertNotIn("apple", results)

    def test_quote_escaping(self):
        self.col.notes[3] = FakeNote({"Word": 'a"b', "Meaning": "test"})
        self.col.find_results['"a\\"b"'] = [3]
        
        results = self.source.enrich_words(['a"b'])
        self.assertIn('a"b', results)
        self.assertEqual(results['a"b'].interpretation, "test")

    def test_ignore_empty_matches(self):
        # A note matches the term but has none of the enrichment fields
        self.col.notes[4] = FakeNote({"Word": "apple", "Tags": "fruit"})
        self.col.find_results['"apple"'] = [4]
        
        results = self.source.enrich_words(["apple"])
        # Should return no enrichment if no fields were found
        self.assertNotIn("apple", results)

if __name__ == '__main__':
    unittest.main()
