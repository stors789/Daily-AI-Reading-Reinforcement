from __future__ import annotations

import json
import sys
import unittest
import urllib.error
from pathlib import Path
from typing import Any


_mock_dir = Path(__file__).resolve().parent.parent / "desktop_mock"
if str(_mock_dir) not in sys.path:
    sys.path.insert(0, str(_mock_dir))

from ankiconnect_card_saver import ARTICLE_FIELDS, ARTICLE_NOTE_TYPE
from diagnostics import format_diagnostics, run_diagnostics, run_write_diagnostics


class FakeResponse:
    def __init__(self, body: Any) -> None:
        self._body = body

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: Any) -> None:
        return None

    def read(self) -> bytes:
        if isinstance(self._body, bytes):
            return self._body
        return json.dumps(self._body).encode("utf-8")


class FakeAnkiConnectOpener:
    def __init__(
        self,
        *,
        model_names: list[str] | None = None,
        article_fields: list[str] | None = None,
        error_action: str | None = None,
        http_error_action: str | None = None,
    ) -> None:
        self.requests: list[dict[str, Any]] = []
        self.model_names = model_names if model_names is not None else [ARTICLE_NOTE_TYPE]
        self.article_fields = article_fields if article_fields is not None else list(ARTICLE_FIELDS)
        self.error_action = error_action
        self.http_error_action = http_error_action

    def __call__(self, req: Any, timeout: float = 0) -> FakeResponse:
        del timeout
        payload = json.loads(req.data.decode("utf-8"))
        self.requests.append(payload)
        action = payload["action"]
        if action == self.http_error_action:
            raise urllib.error.HTTPError(
                req.full_url,
                500,
                "sk-secret should not appear",
                req.headers,
                None,
            )
        if action == self.error_action:
            return FakeResponse({"result": None, "error": "server leaked sk-secret in error"})
        if action == "version":
            return FakeResponse({"result": 6, "error": None})
        if action == "modelNames":
            return FakeResponse({"result": self.model_names, "error": None})
        if action == "findCards":
            return FakeResponse({"result": [101], "error": None})
        if action == "cardsInfo":
            return FakeResponse({"result": [{"cardId": 101, "deckName": "Deck"}], "error": None})
        if action == "modelFieldNames":
            return FakeResponse({"result": self.article_fields, "error": None})
        if action == "createDeck":
            return FakeResponse({"result": 201, "error": None})
        if action == "addNote":
            return FakeResponse({"result": 123456, "error": None})
        if action == "suspend":
            return FakeResponse({"result": True, "error": None})
        return FakeResponse({"result": None, "error": None})


class TestDiagnostics(unittest.TestCase):
    def test_mock_check_ok(self) -> None:
        result = run_diagnostics("mock", environ={})

        self.assertTrue(result["ok"])
        self.assertEqual(result["provider"], "mock")
        self.assertTrue(any(check["name"] == "deck list" for check in result["checks"]))
        self.assertTrue(any(check["name"] == "card list" for check in result["checks"]))

    def test_ankiconnect_check_ok(self) -> None:
        opener = FakeAnkiConnectOpener()

        result = run_diagnostics("ankiconnect", environ={}, opener=opener)

        self.assertTrue(result["ok"])
        self.assertEqual(
            [request["action"] for request in opener.requests],
            ["version", "modelNames", "findCards", "cardsInfo", "modelFieldNames"],
        )
        self.assertTrue(
            any(check["name"] == "article fields compatible" and check["ok"] for check in result["checks"])
        )

    def test_ankiconnect_missing_note_type_is_not_failure(self) -> None:
        opener = FakeAnkiConnectOpener(model_names=["Basic"])

        result = run_diagnostics("ankiconnect", environ={}, opener=opener)

        self.assertTrue(result["ok"])
        output = format_diagnostics(result)
        self.assertIn("will create on first save", output)

    def test_ankiconnect_error_output_is_sanitized(self) -> None:
        opener = FakeAnkiConnectOpener(error_action="modelNames")

        result = run_diagnostics("ankiconnect", environ={}, opener=opener)
        output = format_diagnostics(result)

        self.assertFalse(result["ok"])
        self.assertNotIn("sk-secret", json.dumps(result))
        self.assertNotIn("sk-secret", output)
        self.assertIn("AnkiConnect returned an error", output)

    def test_ankiconnect_http_error_output_is_sanitized(self) -> None:
        opener = FakeAnkiConnectOpener(http_error_action="findCards")

        result = run_diagnostics("ankiconnect", environ={}, opener=opener)
        output = format_diagnostics(result)

        self.assertFalse(result["ok"])
        self.assertNotIn("sk-secret", json.dumps(result))
        self.assertNotIn("sk-secret", output)
        self.assertIn("HTTP 500", output)

    def test_arbitrary_value_error_never_echoes_credential_or_content(self) -> None:
        credential = "exact-credential-value-9381"

        def factory(_provider):
            raise ValueError(f"bad URL with {credential} and PRIVATE CARD CONTENT")

        result = run_diagnostics(
            "real_momo",
            environ={"MOMO_TOKEN": "present"},
            provider_factory=factory,
        )
        output = format_diagnostics(result)
        serialized = json.dumps(result)
        self.assertFalse(result["ok"])
        self.assertNotIn(credential, serialized)
        self.assertNotIn("PRIVATE CARD CONTENT", serialized)
        self.assertNotIn(credential, output)
        self.assertEqual(
            result["checks"][-1]["message"],
            "Diagnostic input or provider configuration is invalid.",
        )

        # Construction failures in every diagnostic mode cross the same
        # fixed-message privacy boundary.
        mock_result = run_diagnostics("mock", environ={}, provider_factory=factory)
        self.assertFalse(mock_result["ok"])
        self.assertNotIn(credential, json.dumps(mock_result))
        self.assertEqual(
            mock_result["checks"][0]["message"],
            "Diagnostic input or provider configuration is invalid.",
        )

    def test_ankiconnect_missing_article_field_fails_clearly(self) -> None:
        fields = [field for field in ARTICLE_FIELDS if field != "Article"]
        opener = FakeAnkiConnectOpener(article_fields=fields)

        result = run_diagnostics("ankiconnect", environ={}, opener=opener)
        output = format_diagnostics(result)

        self.assertFalse(result["ok"])
        self.assertIn("missing field(s): Article", output)

    def test_write_diagnostics_success_writes_and_suspends(self) -> None:
        opener = FakeAnkiConnectOpener()

        result = run_write_diagnostics(environ={}, opener=opener)
        output = format_diagnostics(result)

        self.assertTrue(result["ok"])
        self.assertEqual(result["provider"], "ankiconnect")
        self.assertEqual(result["noteId"], 123456)
        actions = [request["action"] for request in opener.requests]
        for action in ["createDeck", "modelNames", "addNote", "findCards", "suspend"]:
            self.assertIn(action, actions)
        self.assertIn("DAIRR desktop write check: OK", output)
        self.assertIn("AnkiConnect reachable", output)
        self.assertIn("article note created", output)
        self.assertIn("returned noteId: 123456", output)
        self.assertIn("suspend attempted", output)
        self.assertIn("suspend succeeded", output)

        add_note = next(request for request in opener.requests if request["action"] == "addNote")
        note = add_note["params"]["note"]
        self.assertEqual(note["fields"]["Source Deck"], "DAIRR Smoke Test")
        self.assertEqual(note["fields"]["Source Terms"], "dairr-smoke-term")

    def test_write_diagnostics_rejects_non_ankiconnect_provider(self) -> None:
        result = run_write_diagnostics("mock", environ={})
        output = format_diagnostics(result)

        self.assertFalse(result["ok"])
        self.assertIn("--check-write requires provider ankiconnect", output)

    def test_write_diagnostics_add_note_error_is_sanitized(self) -> None:
        opener = FakeAnkiConnectOpener(error_action="addNote")

        result = run_write_diagnostics(environ={}, opener=opener)
        output = format_diagnostics(result)

        self.assertFalse(result["ok"])
        self.assertNotIn("sk-secret", json.dumps(result))
        self.assertNotIn("sk-secret", output)
        self.assertIn("Failed to create article card through AnkiConnect.", output)

    def test_plain_check_does_not_write(self) -> None:
        opener = FakeAnkiConnectOpener()

        run_diagnostics("ankiconnect", environ={}, opener=opener)

        self.assertNotIn("addNote", [request["action"] for request in opener.requests])


if __name__ == "__main__":
    unittest.main()
