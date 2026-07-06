"""Tests for desktop_mock/enrichment_factory.py."""

import os
import sys
import unittest
from pathlib import Path

_mock_dir = Path(__file__).resolve().parent.parent / "desktop_mock"
if str(_mock_dir) not in sys.path:
    sys.path.insert(0, str(_mock_dir))

from enrichment_factory import build_enrichment_source
from desktop_mock.enrichment import MockEnrichmentSource
from anki_enrichment_source import AnkiLocalEnrichmentSource


class FakeCollection:
    pass


class TestDesktopEnrichmentFactory(unittest.TestCase):
    def test_env_unset_returns_none(self):
        self.assertIsNone(build_enrichment_source({}))

    def test_env_empty_returns_none(self):
        self.assertIsNone(build_enrichment_source({"DAIRR_DESKTOP_ENRICHMENT": ""}))
        self.assertIsNone(build_enrichment_source({"DAIRR_DESKTOP_ENRICHMENT": "   "}))

    def test_env_none_or_disabled_returns_none(self):
        self.assertIsNone(build_enrichment_source({"DAIRR_DESKTOP_ENRICHMENT": "none"}))
        self.assertIsNone(build_enrichment_source({"DAIRR_DESKTOP_ENRICHMENT": "disabled"}))
        self.assertIsNone(build_enrichment_source({"DAIRR_DESKTOP_ENRICHMENT": " NONE "}))

    def test_env_mock_returns_mock_source(self):
        source = build_enrichment_source({"DAIRR_DESKTOP_ENRICHMENT": "mock"})
        self.assertIsInstance(source, MockEnrichmentSource)
        # Verify it has some mock entries
        self.assertIn("example", source.entries)

    def test_env_anki_local_with_collection_returns_anki_source(self):
        fake_col = FakeCollection()
        source = build_enrichment_source(
            {"DAIRR_DESKTOP_ENRICHMENT": "anki_local"}, collection=fake_col
        )
        self.assertIsInstance(source, AnkiLocalEnrichmentSource)
        self.assertIs(source.col, fake_col)

    def test_env_anki_local_without_collection_raises_value_error(self):
        with self.assertRaises(ValueError) as cm:
            build_enrichment_source({"DAIRR_DESKTOP_ENRICHMENT": "anki_local"})
        self.assertIn("requires a collection", str(cm.exception))
        # Ensure it doesn't leak paths or user info
        self.assertNotIn("/", str(cm.exception))
        self.assertNotIn("\\", str(cm.exception))

    def test_unknown_env_raises_value_error(self):
        with self.assertRaises(ValueError) as cm:
            build_enrichment_source({"DAIRR_DESKTOP_ENRICHMENT": "unknown_value"})
        self.assertIn("Unknown desktop enrichment source: unknown_value", str(cm.exception))
        self.assertNotIn("/", str(cm.exception))
        self.assertNotIn("\\", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
