# Tests for core/llm.py functions using mock for network I/O.

import json
import sys
import unittest
import urllib.error
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "addon" / "daily_ai_reading_reinforcement"))

from core.config import DEFAULT_CONFIG
from core.llm import (
    fetch_openai_compatible_models,
    generate_article,
    max_tokens_for_request,
    test_openai_compatible_config,
)


class MockHTTPResponse:
    """Minimal mock for urlopen response."""
    def __init__(self, body_bytes, status=200):
        self.body = body_bytes
        self.status = status

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class TestMaxTokensForRequest(unittest.TestCase):

    def test_returns_config_value(self):
        config = {"max_tokens": 4096}
        self.assertEqual(max_tokens_for_request(config, {}), 4096)

    def test_falls_back_to_default(self):
        config = {}
        self.assertEqual(max_tokens_for_request(config, {}), DEFAULT_CONFIG["max_tokens"])

    def test_none_falls_back(self):
        config = {"max_tokens": None}
        self.assertEqual(max_tokens_for_request(config, {}), DEFAULT_CONFIG["max_tokens"])


class TestFetchOpenAICompatibleModels(unittest.TestCase):

    def test_successful_fetch(self):
        body = json.dumps({
            "data": [
                {"id": "gpt-4o-mini"},
                {"id": "gpt-4o"},
                {"id": "gpt-3.5-turbo"},
            ]
        }).encode("utf-8")

        def mock_urlopen(request, timeout=None):
            # Verify request details
            self.assertIn("/models", request.get_full_url())
            self.assertEqual(request.get_header("Authorization"), "Bearer test-key")
            self.assertEqual(request.get_method(), "GET")
            return MockHTTPResponse(body)

        with patch("urllib.request.urlopen", mock_urlopen):
            models = fetch_openai_compatible_models("https://api.example.com/v1", "test-key")

        self.assertEqual(models, ["gpt-3.5-turbo", "gpt-4o", "gpt-4o-mini"])

    def test_empty_data(self):
        body = json.dumps({"data": []}).encode("utf-8")

        with patch("urllib.request.urlopen", lambda req, timeout=None: MockHTTPResponse(body)):
            models = fetch_openai_compatible_models("https://api.example.com/v1", "test-key")

        self.assertEqual(models, [])

    def test_deduplicates_models(self):
        body = json.dumps({
            "data": [
                {"id": "gpt-4o"},
                {"id": "gpt-4o"},
            ]
        }).encode("utf-8")

        with patch("urllib.request.urlopen", lambda req, timeout=None: MockHTTPResponse(body)):
            models = fetch_openai_compatible_models("https://api.example.com/v1", "test-key")

        self.assertEqual(models, ["gpt-4o"])

    def test_strips_trailing_slash(self):
        body = json.dumps({"data": []}).encode("utf-8")
        urls_seen = []

        def mock_urlopen(request, timeout=None):
            urls_seen.append(request.get_full_url())
            return MockHTTPResponse(body)

        with patch("urllib.request.urlopen", mock_urlopen):
            fetch_openai_compatible_models("https://api.example.com/v1/", "test-key")

        self.assertEqual(urls_seen[0], "https://api.example.com/v1/models")

    def test_http_error(self):
        def mock_urlopen(request, timeout=None):
            raise urllib.error.HTTPError(
                request.get_full_url(), 401, "Unauthorized", {}, BytesIO(b'{"error":"invalid_token"}')
            )

        with patch("urllib.request.urlopen", mock_urlopen):
            with self.assertRaises(RuntimeError) as ctx:
                fetch_openai_compatible_models("https://api.example.com/v1", "bad-key")
            self.assertIn("HTTP 401", str(ctx.exception))

    def test_url_error(self):
        def mock_urlopen(request, timeout=None):
            raise urllib.error.URLError("connection refused")

        with patch("urllib.request.urlopen", mock_urlopen):
            with self.assertRaises(RuntimeError) as ctx:
                fetch_openai_compatible_models("https://invalid.example.com/v1", "key")
            self.assertNotIn("connection refused", str(ctx.exception))
            self.assertIn("could not be reached", str(ctx.exception))

    def test_authorization_is_not_forwarded_on_redirect(self):
        request = None

        def capture(req, timeout=None):
            nonlocal request
            request = req
            return MockHTTPResponse(b'{"data": []}')

        with patch("urllib.request.urlopen", capture):
            fetch_openai_compatible_models("https://api.example.com/v1", "secret")
        self.assertEqual(request.get_header("Authorization"), "Bearer secret")
        self.assertNotIn("Authorization", request.headers)
        self.assertEqual(request.unredirected_hdrs["Authorization"], "Bearer secret")


class TestOpenAICompatibleConfig(unittest.TestCase):
    def test_success_makes_minimal_chat_request(self):
        body = json.dumps({"choices": [{"message": {"content": "OK"}}]}).encode()

        def mock_urlopen(request, timeout=None):
            self.assertEqual(request.get_full_url(), "https://api.example.com/v1/chat/completions")
            self.assertEqual(request.get_header("Authorization"), "Bearer secret")
            payload = json.loads(request.data)
            self.assertEqual(payload["model"], "model-a")
            self.assertEqual(payload["max_tokens"], 8)
            return MockHTTPResponse(body)

        with patch("urllib.request.urlopen", mock_urlopen):
            result = test_openai_compatible_config("https://api.example.com/v1/", "secret", "model-a")
        self.assertEqual(result, {"model": "model-a", "response": "OK"})

    def test_invalid_response_is_rejected(self):
        with patch("urllib.request.urlopen", lambda *_args, **_kwargs: MockHTTPResponse(b'{}')):
            with self.assertRaisesRegex(RuntimeError, "invalid chat completion"):
                test_openai_compatible_config("https://api.example.com/v1", "secret", "model-a")


class TestGenerateArticle(unittest.TestCase):

    def setUp(self):
        self.base_config = {
            "api_key": "test-key",
            "selected_provider_profile": "openai",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o-mini",
            "temperature": 0.7,
            "max_tokens": 2048,
            "ui_language": "en",
        }
        self.preset = {
            "reader_native_language": "English",
            "article_language": "Spanish",
            "difficulty": "beginner",
            "max_words": "200",
            "instructions": "",
            "prompt_template": "",
        }

    def _make_mock_card(self, term_value="hello", is_new=False, is_failed=False):
        card = Mock()
        card.term = term_value
        card.is_new = is_new
        card.is_failed = is_failed
        card.fields = {"Front": "Hola", "Back": "Hello"}
        return card

    def test_successful_generation(self):
        response_body = json.dumps({
            "choices": [{
                "message": {
                    "content": "[ARTICLE_TITLE]\nTitle\n[MAIN_ARTICLE]\nBody.\n"
                }
            }]
        }).encode("utf-8")

        requests_made = []

        def mock_urlopen(request, timeout=None):
            requests_made.append(request)
            return MockHTTPResponse(response_body)

        with patch("urllib.request.urlopen", mock_urlopen):
            article = generate_article(
                self.base_config, "My Deck",
                [self._make_mock_card()], ["Front"],
                self.preset
            )

        self.assertIn("Title", article)
        self.assertIn("Body.", article)
        self.assertEqual(len(requests_made), 1)
        req = requests_made[0]
        self.assertEqual(req.get_method(), "POST")
        self.assertIn("Bearer test-key", req.get_header("Authorization"))
        self.assertEqual(req.get_full_url(), "https://api.openai.com/v1/chat/completions")

    def test_payload_contains_expected_fields(self):
        response_body = json.dumps({
            "choices": [{"message": {"content": "test"}}]
        }).encode("utf-8")

        payloads = []

        def mock_urlopen(request, timeout=None):
            payloads.append(json.loads(request.data.decode("utf-8")))
            return MockHTTPResponse(response_body)

        with patch("urllib.request.urlopen", mock_urlopen):
            generate_article(
                self.base_config, "Deck",
                [self._make_mock_card()], ["Front"],
                self.preset
            )

        payload = payloads[0]
        self.assertEqual(payload["model"], "gpt-4o-mini")
        self.assertEqual(payload["temperature"], 0.7)
        self.assertEqual(payload["max_tokens"], 2048)
        self.assertEqual(len(payload["messages"]), 2)
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertEqual(payload["messages"][1]["role"], "user")

    def test_http_error(self):
        def mock_urlopen(request, timeout=None):
            raise urllib.error.HTTPError(
                request.get_full_url(), 403, "Forbidden", {}, BytesIO(b'{"error":"forbidden"}')
            )

        with patch("urllib.request.urlopen", mock_urlopen):
            with self.assertRaises(RuntimeError) as ctx:
                generate_article(
                    self.base_config, "Deck",
                    [self._make_mock_card()], ["Front"],
                    self.preset
                )
            self.assertIn("HTTP 403", str(ctx.exception))

    def test_url_error(self):
        def mock_urlopen(request, timeout=None):
            raise urllib.error.URLError("timeout")

        with patch("urllib.request.urlopen", mock_urlopen):
            with self.assertRaises(RuntimeError) as ctx:
                generate_article(
                    self.base_config, "Deck",
                    [self._make_mock_card()], ["Front"],
                    self.preset
                )
            self.assertNotIn("timeout", str(ctx.exception))
            self.assertIn("could not be reached", str(ctx.exception))

    def test_malformed_response(self):
        response_body = json.dumps({
            "choices": [{"message": {}}]  # no "content" key
        }).encode("utf-8")

        with patch("urllib.request.urlopen", lambda req, timeout=None: MockHTTPResponse(response_body)):
            with self.assertRaises(RuntimeError) as ctx:
                generate_article(
                    self.base_config, "Deck",
                    [self._make_mock_card()], ["Front"],
                    self.preset
                )
            self.assertIn("did not contain", str(ctx.exception))

    def test_custom_provider_url(self):
        config = dict(self.base_config)
        config["selected_provider_profile"] = "custom"
        config["base_url"] = "https://my-api.example.com"

        response_body = json.dumps({
            "choices": [{"message": {"content": "test"}}]
        }).encode("utf-8")

        urls = []

        def mock_urlopen(request, timeout=None):
            urls.append(request.get_full_url())
            return MockHTTPResponse(response_body)

        with patch("urllib.request.urlopen", mock_urlopen):
            generate_article(config, "Deck", [self._make_mock_card()], ["Front"], self.preset)

        self.assertEqual(urls[0], "https://my-api.example.com/chat/completions")


if __name__ == "__main__":
    unittest.main()
