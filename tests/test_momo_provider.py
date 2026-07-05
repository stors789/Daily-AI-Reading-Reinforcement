"""Tests for MockMoMoDeckProvider.

Verify the mock-first provider returns data that matches the shared web UI's
frontend contract and never touches the real MoMo API, Anki, or network.
"""

import importlib.util
import sys
import unittest
from pathlib import Path

_mock_dir = Path(__file__).resolve().parent.parent / "desktop_mock"
if str(_mock_dir) not in sys.path:
    sys.path.insert(0, str(_mock_dir))

_prov_spec = importlib.util.spec_from_file_location(
    "momo_provider", _mock_dir / "momo_provider.py"
)
assert _prov_spec is not None and _prov_spec.loader is not None
_prov_mod = importlib.util.module_from_spec(_prov_spec)
_prov_spec.loader.exec_module(_prov_mod)
MockMoMoDeckProvider = _prov_mod.MockMoMoDeckProvider


class TestMockMoMoDeckProvider(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.provider = MockMoMoDeckProvider()

    def test_get_today_decks_returns_two_decks(self) -> None:
        decks = self.provider.get_today_decks()
        self.assertEqual(len(decks), 2)

    def test_get_today_decks_returns_sorted_by_name(self) -> None:
        decks = self.provider.get_today_decks()
        names = [d["name"] for d in decks]
        self.assertEqual(names, sorted(names, key=str.lower))

    def test_deck_rows_contain_frontend_fields(self) -> None:
        for deck in self.provider.get_today_decks():
            for key in (
                "id",
                "name",
                "newCount",
                "failedCount",
                "totalCount",
                "isGroup",
            ):
                self.assertIn(key, deck, f"deck row missing {key}")

    def test_deck_rows_have_expected_values(self) -> None:
        decks = {d["id"]: d for d in self.provider.get_today_decks()}
        self.assertIn("deck-japanese", decks)
        self.assertIn("deck-english", decks)
        jp = decks["deck-japanese"]
        self.assertEqual(jp["name"], "Japanese Vocab")
        self.assertEqual(jp["newCount"], 1)
        self.assertEqual(jp["failedCount"], 1)
        self.assertEqual(jp["totalCount"], 3)
        self.assertFalse(jp["isGroup"])

    def test_get_deck_cards_known_deck_returns_three_cards(self) -> None:
        result = self.provider.get_deck_cards("deck-japanese")
        self.assertEqual(result["deckId"], "deck-japanese")
        self.assertEqual(len(result["cards"]), 3)

    def test_card_contains_frontend_fields(self) -> None:
        result = self.provider.get_deck_cards("deck-english")
        for card in result["cards"]:
            for key in (
                "cid",
                "nid",
                "term",
                "fields",
                "is_new",
                "is_failed",
                "review_count",
            ):
                self.assertIn(key, card, f"card missing {key}")

    def test_get_deck_cards_unknown_deck_returns_empty_cards(self) -> None:
        result = self.provider.get_deck_cards("nonexistent")
        self.assertEqual(result["deckId"], "nonexistent")
        self.assertEqual(result["cards"], [])

    def test_provider_does_not_trigger_network_calls(self) -> None:
        self.provider.get_today_decks()
        self.provider.get_deck_cards("deck-japanese")
        self.provider.get_deck_cards("nonexistent")


class TestProviderIntegrationWithPayloadBuilders(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _data_spec = importlib.util.spec_from_file_location(
            "mock_data", _mock_dir / "mock_data.py"
        )
        assert _data_spec is not None and _data_spec.loader is not None
        cls._data = importlib.util.module_from_spec(_data_spec)
        _data_spec.loader.exec_module(cls._data)
        cls.provider = MockMoMoDeckProvider()

    def test_state_payload_with_provider_decks(self) -> None:
        decks = self.provider.get_today_decks()
        payload = self._data.build_state_payload("deck-japanese", decks=decks)
        self.assertEqual(payload["decks"], decks)
        self.assertEqual(payload["lastSelectedDeckId"], "deck-japanese")
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

    def test_deck_cards_payload_with_provider_cards(self) -> None:
        cards_data = self.provider.get_deck_cards("deck-japanese")
        payload = self._data.build_deck_cards_payload(
            "deck-japanese", cards_data=cards_data
        )
        self.assertEqual(payload["deckId"], "deck-japanese")
        self.assertEqual(len(payload["cards"]), 3)
        self.assertTrue(payload["fields"])
        self.assertTrue(payload["selectedFields"])

    def test_deck_cards_payload_unknown_deck_via_provider(self) -> None:
        cards_data = self.provider.get_deck_cards("nope")
        payload = self._data.build_deck_cards_payload("nope", cards_data=cards_data)
        self.assertEqual(payload["deckId"], "nope")
        self.assertEqual(payload["cards"], [])
        self.assertEqual(payload["fields"], [])
        self.assertEqual(payload["selectedFields"], [])


if __name__ == "__main__":
    unittest.main()
