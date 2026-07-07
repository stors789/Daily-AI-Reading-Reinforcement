from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch


_repo_root = Path(__file__).resolve().parent.parent
_mock_dir = _repo_root / "desktop_mock"
if str(_mock_dir) not in sys.path:
    sys.path.insert(0, str(_mock_dir))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_saver_mod = _load("ankiconnect_card_saver", _mock_dir / "ankiconnect_card_saver.py")
_adapters_mod = _load("desktop_adapters_for_saver_tests", _mock_dir / "desktop_adapters.py")

AnkiConnectArticleCardSaver = _saver_mod.AnkiConnectArticleCardSaver
AnkiConnectCardSaverError = _saver_mod.AnkiConnectCardSaverError
ARTICLE_NOTE_TYPE = _saver_mod.ARTICLE_NOTE_TYPE


class FakeResponse:
    def __init__(self, body: dict[str, Any]) -> None:
        self._body = body

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: Any) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._body).encode("utf-8")


class RecordingOpener:
    def __init__(self, responses: dict[str, dict[str, Any]] | None = None) -> None:
        self.requests: list[dict[str, Any]] = []
        self._responses = responses or {}

    def __call__(self, req: Any, timeout: float = 0) -> FakeResponse:
        del timeout
        payload = json.loads(req.data.decode("utf-8"))
        self.requests.append(payload)
        action = payload["action"]
        if action in self._responses:
            return FakeResponse(self._responses[action])
        if action == "createDeck":
            return FakeResponse({"result": 101, "error": None})
        if action == "modelNames":
            return FakeResponse({"result": [ARTICLE_NOTE_TYPE], "error": None})
        if action == "addNote":
            return FakeResponse({"result": 123456, "error": None})
        if action == "findCards":
            return FakeResponse({"result": [987654], "error": None})
        if action == "suspend":
            return FakeResponse({"result": True, "error": None})
        return FakeResponse({"result": None, "error": None})


class Card:
    term = "komorebi"


class TestAnkiConnectArticleCardSaver(unittest.TestCase):
    def test_add_note_request_envelope_is_correct(self) -> None:
        opener = RecordingOpener()
        saver = AnkiConnectArticleCardSaver(
            opener=opener,
            render_article_fragment_html=lambda article: f"<p>{article}</p>",
        )

        saver.save_article_card(
            "Japanese Vocab",
            [Card()],
            "article body",
            Path("/tmp/article.md"),
            Path("/tmp/article.html"),
        )

        add_note = next(req for req in opener.requests if req["action"] == "addNote")
        self.assertEqual(add_note["version"], 6)
        note = add_note["params"]["note"]
        self.assertEqual(note["deckName"], "Daily AI Reading Reinforcement::Japanese Vocab")
        self.assertEqual(note["modelName"], ARTICLE_NOTE_TYPE)
        self.assertEqual(note["fields"]["Source Deck"], "Japanese Vocab")
        self.assertEqual(note["fields"]["Article"], "<p>article body</p>")
        self.assertEqual(note["fields"]["Source Terms"], "komorebi")
        self.assertEqual(note["fields"]["Markdown Path"], "/tmp/article.md")
        self.assertEqual(note["fields"]["HTML Path"], "/tmp/article.html")
        self.assertFalse(note["options"]["allowDuplicate"])

    def test_success_returns_article_card_identity(self) -> None:
        opener = RecordingOpener()
        saver = AnkiConnectArticleCardSaver(opener=opener)

        result = saver.save_article_card(
            "English Vocab",
            [],
            "article",
            Path("/tmp/a.md"),
            Path("/tmp/a.html"),
        )

        self.assertEqual(result["noteId"], 123456)
        self.assertEqual(result["deckName"], "Daily AI Reading Reinforcement::English Vocab")
        self.assertEqual(result["noteType"], ARTICLE_NOTE_TYPE)
        self.assertRegex(result["date"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertNotIn("_desktop_stub", result)

    def test_missing_note_type_is_created(self) -> None:
        opener = RecordingOpener({"modelNames": {"result": [], "error": None}})
        saver = AnkiConnectArticleCardSaver(opener=opener)

        saver.save_article_card("Deck", [], "article", Path("/tmp/a.md"), Path("/tmp/a.html"))

        create_model = next(req for req in opener.requests if req["action"] == "createModel")
        self.assertEqual(create_model["params"]["modelName"], ARTICLE_NOTE_TYPE)
        self.assertEqual(create_model["params"]["inOrderFields"][0], "Date")
        self.assertTrue(create_model["params"]["cardTemplates"])

    def test_ankiconnect_error_is_publicly_sanitized(self) -> None:
        opener = RecordingOpener(
            {"addNote": {"result": None, "error": "token sk-secret leaked by server"}}
        )
        saver = AnkiConnectArticleCardSaver(opener=opener)

        with self.assertRaises(AnkiConnectCardSaverError) as ctx:
            saver.save_article_card("Deck", [], "article", Path("/tmp/a.md"), Path("/tmp/a.html"))

        self.assertEqual(
            ctx.exception.public_message,
            "Failed to create article card through AnkiConnect.",
        )
        self.assertNotIn("sk-secret", str(ctx.exception))


class TestArticleGenerationCardErrorPayload(unittest.TestCase):
    def test_ankiconnect_error_detail_is_not_returned_to_frontend_payload(self) -> None:
        article_generator = _adapters_mod._core_article_generator
        original_generate_article = article_generator.generate_article
        article_generator.generate_article = lambda *args, **kwargs: "generated article"

        class ConfigAdapter:
            def load(self) -> dict[str, Any]:
                return {"api_key": "test-key", "create_article_cards": True}

            def save(self, config: dict[str, Any]) -> None:
                del config

        class DeckAdapter:
            def save_article(self, *args: Any, **kwargs: Any) -> dict[str, Path]:
                return {"markdown": Path("/tmp/a.md"), "html": Path("/tmp/a.html")}

            def save_article_card(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
                raise AnkiConnectCardSaverError(
                    "Failed to create article card through AnkiConnect.",
                    "server included sk-secret in error",
                )

        try:
            result = article_generator.run_article_generation(
                ConfigAdapter(),
                DeckAdapter(),
                "Deck",
                [],
                [],
                {},
            )
        finally:
            article_generator.generate_article = original_generate_article

        self.assertIsNone(result["articleCard"])
        self.assertEqual(
            result["articleCardError"],
            "Failed to create article card through AnkiConnect.",
        )
        self.assertNotIn("sk-secret", json.dumps(result))


class TestDesktopDeckAdapterProviderCompatibility(unittest.TestCase):
    def test_mock_provider_save_article_card_remains_stub(self) -> None:
        with patch.dict("os.environ", {"DAIRR_DESKTOP_PROVIDER": "mock"}, clear=False):
            adapter = _adapters_mod.DesktopDeckAdapter()
            result = adapter.save_article_card(
                "Mock Deck",
                [],
                "article",
                Path("/tmp/a.md"),
                Path("/tmp/a.html"),
            )
        self.assertTrue(result["_desktop_stub"])
        self.assertEqual(result["noteId"], 0)

    def test_real_momo_provider_save_article_card_remains_stub(self) -> None:
        with patch.dict("os.environ", {"DAIRR_DESKTOP_PROVIDER": "real_momo"}, clear=False):
            adapter = _adapters_mod.DesktopDeckAdapter()
            result = adapter.save_article_card(
                "MoMo Deck",
                [],
                "article",
                Path("/tmp/a.md"),
                Path("/tmp/a.html"),
            )
        self.assertTrue(result["_desktop_stub"])
        self.assertEqual(result["noteType"], "Desktop (no Anki card created)")


if __name__ == "__main__":
    unittest.main()
