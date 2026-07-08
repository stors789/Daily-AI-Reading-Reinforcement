import contextlib
import importlib.util
import io
import json
import unittest
import urllib.error
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT_PATH = _ROOT / "tools" / "debug_prompt.py"
_SPEC = importlib.util.spec_from_file_location("debug_prompt", _SCRIPT_PATH)
debug_prompt = importlib.util.module_from_spec(_SPEC)
assert _SPEC and _SPEC.loader
_SPEC.loader.exec_module(debug_prompt)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class FakeOpener:
    def __init__(self, payload=None, error=None):
        self.payload = payload or {"event": "debugPrompt", "payload": {}}
        self.error = error
        self.requests = []
        self.timeouts = []

    def open(self, request, timeout=0):
        self.requests.append(request)
        self.timeouts.append(timeout)
        if self.error:
            raise self.error
        return FakeResponse(self.payload)


class DebugPromptToolTest(unittest.TestCase):
    def test_request_body_is_correct(self):
        opener = FakeOpener()

        with contextlib.redirect_stdout(io.StringIO()):
            rc = debug_prompt.main(
                [
                    "--url",
                    "http://127.0.0.1:8755",
                    "--deck-id",
                    "deck-japanese",
                    "--preset-id",
                    "japanese",
                ],
                opener=opener,
            )

        self.assertEqual(rc, 0)
        self.assertEqual(len(opener.requests), 1)
        request = opener.requests[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:8755/api/bridge")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Content-type"), "application/json")
        self.assertEqual(
            json.loads(request.data.decode("utf-8")),
            {
                "action": "debugPrompt",
                "payload": {"deckId": "deck-japanese", "presetId": "japanese"},
            },
        )

    def test_repeated_card_id_enters_payload_card_ids(self):
        opener = FakeOpener()

        with contextlib.redirect_stdout(io.StringIO()):
            rc = debug_prompt.main(
                [
                    "--deck-id",
                    "deck-japanese",
                    "--card-id",
                    "1001",
                    "--card-id",
                    "1002",
                ],
                opener=opener,
            )

        self.assertEqual(rc, 0)
        body = json.loads(opener.requests[0].data.decode("utf-8"))
        self.assertEqual(body["payload"]["cardIds"], ["1001", "1002"])

    def test_default_summary_does_not_include_api_key(self):
        opener = FakeOpener(
            {
                "event": "debugPrompt",
                "payload": {
                    "selectedPromptPresetId": "japanese",
                    "requestedPresetId": "japanese",
                    "articleLanguage": "Japanese",
                    "readerNativeLanguage": "English",
                    "cardCount": 2,
                    "selectedFields": ["Front"],
                    "promptContainsArticleLanguage": True,
                    "promptPreview": "Write in Japanese.",
                    "resolvedPreset": {"api_key": "super-secret-key"},
                },
            }
        )
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            rc = debug_prompt.main(["--deck-id", "deck-japanese"], opener=opener)

        self.assertEqual(rc, 0)
        output = stdout.getvalue()
        self.assertIn("articleLanguage: Japanese", output)
        self.assertNotIn("super-secret-key", output)
        self.assertNotIn("api_key", output.lower())

    def test_json_outputs_complete_json(self):
        payload = {
            "event": "debugPrompt",
            "payload": {
                "selectedPromptPresetId": "japanese",
                "resolvedPreset": {"id": "japanese"},
            },
        }
        opener = FakeOpener(payload)
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            rc = debug_prompt.main(["--deck-id", "deck-japanese", "--json"], opener=opener)

        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(stdout.getvalue()), payload)

    def test_url_error_returns_nonzero(self):
        opener = FakeOpener(error=urllib.error.URLError("connection refused"))
        stderr = io.StringIO()

        with contextlib.redirect_stderr(stderr):
            rc = debug_prompt.main(["--deck-id", "deck-japanese"], opener=opener)

        self.assertNotEqual(rc, 0)
        self.assertIn("Could not reach standalone server", stderr.getvalue())

    def test_http_error_returns_nonzero(self):
        opener = FakeOpener(
            error=urllib.error.HTTPError(
                "http://127.0.0.1:8755/api/bridge",
                500,
                "Internal Server Error",
                {},
                None,
            )
        )
        stderr = io.StringIO()

        with contextlib.redirect_stderr(stderr):
            rc = debug_prompt.main(["--deck-id", "deck-japanese"], opener=opener)

        self.assertNotEqual(rc, 0)
        self.assertIn("HTTP error from standalone server: 500", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
