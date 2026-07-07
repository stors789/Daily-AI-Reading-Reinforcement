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
from diagnostics import format_diagnostics, run_diagnostics


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

    def test_ankiconnect_missing_article_field_fails_clearly(self) -> None:
        fields = [field for field in ARTICLE_FIELDS if field != "Article"]
        opener = FakeAnkiConnectOpener(article_fields=fields)

        result = run_diagnostics("ankiconnect", environ={}, opener=opener)
        output = format_diagnostics(result)

        self.assertFalse(result["ok"])
        self.assertIn("missing field(s): Article", output)


if __name__ == "__main__":
    unittest.main()
