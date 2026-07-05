
"""Tests for AnkiDeckProvider.

The adapter is loaded directly via importlib to avoid pulling in the
full addon package __init__.py (which requires a running Anki / aqt).
"""

import importlib.util
import unittest
from pathlib import Path

_addon_root = (
    Path(__file__).resolve().parent.parent
    / "addon" / "daily_ai_reading_reinforcement"
)

_provider_path = _addon_root / "anki_deck_provider.py"
_spec = importlib.util.spec_from_file_location(
    "anki_deck_provider", _provider_path
)
_provider_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_provider_mod)
AnkiDeckProvider = _provider_mod.AnkiDeckProvider


class TestAnkiDeckProvider(unittest.TestCase):
    def test_get_today_decks_calls_injected_function(self) -> None:
        called: list[bool] = []

        def fake_collect() -> dict[str, dict[str, object]]:
            called.append(True)
            return {"deck1": {"name": "Test"}}

        provider = AnkiDeckProvider(fake_collect)
        result = provider.get_today_decks()

        self.assertTrue(called)
        self.assertEqual(result, {"deck1": {"name": "Test"}})

    def test_get_today_decks_transparently_returns_result(self) -> None:
        expected: dict[str, dict[str, object]] = {
            "deck1": {"name": "Test"},
            "deck2": {"name": "Test2"},
        }
        provider = AnkiDeckProvider(lambda: expected)
        self.assertIs(provider.get_today_decks(), expected)

    def test_get_today_decks_propagates_exception(self) -> None:
        class TestError(Exception):
            pass

        def raise_error() -> dict[str, dict[str, object]]:
            raise TestError("boom")

        provider = AnkiDeckProvider(raise_error)
        with self.assertRaises(TestError):
            provider.get_today_decks()

    def test_get_today_decks_can_be_called_multiple_times(self) -> None:
        count: list[int] = [0]

        def counter() -> int:
            count[0] += 1
            return count[0]

        provider = AnkiDeckProvider(counter)
        self.assertEqual(provider.get_today_decks(), 1)
        self.assertEqual(provider.get_today_decks(), 2)
        self.assertEqual(provider.get_today_decks(), 3)


if __name__ == "__main__":
    unittest.main()
