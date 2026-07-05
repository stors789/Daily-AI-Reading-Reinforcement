"""Tests for AnkiCardSaver adapter.

The adapter has no Anki dependencies, so we import it directly via
importlib rather than going through the full addon package __init__.py.
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from typing import Any

_addon_root = (
    Path(__file__).resolve().parent.parent
    / "addon" / "daily_ai_reading_reinforcement"
)

_saver_path = _addon_root / "anki_card_saver.py"
_spec = importlib.util.spec_from_file_location(
    "anki_card_saver", _saver_path
)
_saver_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_saver_mod)  # type: ignore[union-attr]
AnkiCardSaver = _saver_mod.AnkiCardSaver


class TestAnkiCardSaver(unittest.TestCase):
    """Verify that AnkiCardSaver faithfully delegates to the injected function."""

    def test_calls_injected_function(self) -> None:
        called: list[bool] = []

        def fake_create(*args: Any, **kwargs: Any) -> dict[str, str]:
            called.append(True)
            return {"status": "ok"}

        saver = AnkiCardSaver(fake_create)
        result = saver.save_article_card("deck", [], "text")

        self.assertTrue(called)
        self.assertEqual(result, {"status": "ok"})

    def test_passes_positional_args(self) -> None:
        received: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

        def fake_create(*args: Any, **kwargs: Any) -> None:
            received.append((args, kwargs))

        saver = AnkiCardSaver(fake_create)
        saver.save_article_card("deck-a", ["card1", "card2"], "article-body")

        args, kwargs = received[0]
        self.assertEqual(args, ("deck-a", ["card1", "card2"], "article-body"))
        self.assertEqual(kwargs, {})

    def test_passes_keyword_args(self) -> None:
        received: list[dict[str, Any]] = []

        def fake_create(**kwargs: Any) -> None:
            received.append(kwargs)

        saver = AnkiCardSaver(fake_create)
        saver.save_article_card(
            source_deck_name="math",
            cards=[],
            article="hello",
            markdown_path=Path("/tmp/a.md"),
            html_path=Path("/tmp/a.html"),
        )

        kwargs = received[0]
        self.assertEqual(kwargs["source_deck_name"], "math")
        self.assertEqual(kwargs["cards"], [])
        self.assertEqual(kwargs["article"], "hello")
        self.assertEqual(kwargs["markdown_path"], Path("/tmp/a.md"))
        self.assertEqual(kwargs["html_path"], Path("/tmp/a.html"))

    def test_transparent_return_value(self) -> None:
        def fake_create(*args: Any, **kwargs: Any) -> int:
            return 42

        saver = AnkiCardSaver(fake_create)
        self.assertEqual(saver.save_article_card(), 42)

    def test_propagates_exception(self) -> None:
        class TestError(Exception):
            pass

        def fake_create(*args: Any, **kwargs: Any) -> None:
            raise TestError("boom")

        saver = AnkiCardSaver(fake_create)
        with self.assertRaises(TestError):
            saver.save_article_card("deck", [], "text")

    def test_multiple_calls_delegate_independently(self) -> None:
        call_args: list[tuple[Any, ...]] = []

        def fake_create(*args: Any, **kwargs: Any) -> str:
            call_args.append(args)
            return f"saved-{len(call_args)}"

        saver = AnkiCardSaver(fake_create)
        r1 = saver.save_article_card("deck1")
        r2 = saver.save_article_card("deck2", extra=True)
        r3 = saver.save_article_card("deck3")

        self.assertEqual(len(call_args), 3)
        self.assertEqual(r1, "saved-1")
        self.assertEqual(r2, "saved-2")
        self.assertEqual(r3, "saved-3")
        self.assertEqual(call_args[0], ("deck1",))
        self.assertEqual(call_args[1], ("deck2",))
        self.assertEqual(call_args[2], ("deck3",))


if __name__ == "__main__":
    unittest.main()
