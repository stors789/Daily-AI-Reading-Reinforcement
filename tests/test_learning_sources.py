"""Tests for the platform-neutral learning source contract."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CORE_SRC = ROOT / "packages" / "dairr_core" / "src"
MOCK_DIR = ROOT / "desktop_mock"
for path in (str(CORE_SRC), str(MOCK_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from dairr_core.learning_sources import (
    LearningSourceDescriptor,
    LearningSourceRegistry,
    SourceCapability,
    SourceScopedId,
    StudyCardSnapshot,
    StudyDeckSnapshot,
)
from learning_sources import LegacyDeckProviderSource


class _FakeSource:
    def __init__(self, source_id: str) -> None:
        self._descriptor = LearningSourceDescriptor(source_id, source_id.title())

    @property
    def descriptor(self) -> LearningSourceDescriptor:
        return self._descriptor

    def list_today_decks(self) -> list[StudyDeckSnapshot]:
        return []

    def get_deck(self, deck_id: SourceScopedId) -> StudyDeckSnapshot:
        return StudyDeckSnapshot(deck_id, "Unused")


class _LegacyProvider:
    def get_today_decks(self):
        return [{"id": "Unit 1::A/B", "name": "Unit 1", "newCount": 1, "failedCount": 0, "totalCount": 1, "isGroup": False}]

    def get_deck_cards(self, deck_id):
        return {
            "deckId": deck_id,
            "name": "Unit 1",
            "cards": [{"cid": "card/1", "nid": 7, "term": "word", "fields": {"Front": "word"}, "is_new": True, "is_failed": False}],
            "selectedFields": ["Front"],
        }


class TestSourceScopedId(unittest.TestCase):
    def test_round_trip_preserves_provider_local_punctuation(self) -> None:
        original = SourceScopedId("ankiconnect", "English::Unit 1/A")
        self.assertEqual(SourceScopedId.parse(original.encode()), original)

    def test_rejects_unscoped_legacy_ids(self) -> None:
        with self.assertRaises(ValueError):
            SourceScopedId.parse("momo_today")


class TestLearningSourceContracts(unittest.TestCase):
    def test_descriptor_exposes_versioned_capabilities_to_bridge(self) -> None:
        descriptor = LearningSourceDescriptor(
            "momo",
            "MoMo",
            frozenset({SourceCapability.READ_TODAY_DECKS, SourceCapability.READ_DECK_CARDS}),
        )
        self.assertEqual(descriptor.to_bridge_dict()["contractVersion"], "v1")
        self.assertEqual(descriptor.to_bridge_dict()["capabilities"], ["read_deck_cards", "read_today_decks"])

    def test_registry_routes_only_to_the_scoped_source(self) -> None:
        anki = _FakeSource("anki")
        momo = _FakeSource("momo")
        registry = LearningSourceRegistry([anki, momo])
        source, deck_id = registry.resolve_deck(SourceScopedId("momo", "today").encode())
        self.assertIs(source, momo)
        self.assertEqual(deck_id.local_id, "today")

    def test_legacy_provider_adapter_emits_scoped_decks_and_cards(self) -> None:
        descriptor = LearningSourceDescriptor("demo", "Demo")
        source = LegacyDeckProviderSource(descriptor, _LegacyProvider())
        deck = source.list_today_decks()[0]
        self.assertEqual(deck.id.encode(), "dairr:v1:demo:Unit%201%3A%3AA%2FB")
        snapshot = source.get_deck(deck.id)
        bridge = snapshot.to_bridge_cards()
        self.assertEqual(bridge["deckId"], deck.id.encode())
        self.assertEqual(bridge["cards"][0]["cid"], "dairr:v1:demo:card%2F1")


if __name__ == "__main__":
    unittest.main()
