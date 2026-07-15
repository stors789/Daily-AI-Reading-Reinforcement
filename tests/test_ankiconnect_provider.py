"""Tests for the standalone AnkiConnect deck provider."""

from __future__ import annotations

import json
import socket
import unittest
import urllib.error
from pathlib import Path
import sys
from unittest.mock import MagicMock

_mock_dir = Path(__file__).resolve().parent.parent / "desktop_mock"
if str(_mock_dir) not in sys.path:
    sys.path.insert(0, str(_mock_dir))

from ankiconnect_provider import (
    AnkiConnectDeckProvider,
    AnkiConnectError,
    AnkiConnectFailure,
)


class FakeAnkiConnectOpener:
    def __init__(self) -> None:
        self.requests = []

    def __call__(self, req, timeout):
        self.requests.append(req)
        payload = json.loads(req.data.decode("utf-8"))
        action = payload["action"]
        params = payload.get("params") or {}

        if action == "findCards":
            query = params["query"]
            if query == "rated:1":
                result = [101, 102, 201]
            elif query == "rated:1:1":
                result = [102]
            elif query == "introduced:1":
                result = [101]
            else:
                result = []
        elif action == "multi":
            query_results = {
                "rated:1": [101, 102, 201],
                "rated:1:1": [102],
                "rated:1:2": [201],
                "rated:1:3": [101, 201],
                "rated:1:4": [],
                "introduced:1": [101],
            }
            result = [
                {"result": query_results[item["params"]["query"]], "error": None}
                for item in params["actions"]
            ]
        elif action == "cardsInfo":
            if params["cards"] != [101, 102, 201]:
                raise AssertionError(params["cards"])
            result = [
                {
                    "cardId": 101,
                    "note": 1001,
                    "deckName": "English::Unit 1",
                    "fields": {
                        "Front": {"value": "reinforcement"},
                        "Back": {"value": "strengthening"},
                    },
                    "type": 1,
                    "queue": 1,
                    "reps": 1,
                    "lapses": 0,
                },
                {
                    "cardId": 102,
                    "note": 1002,
                    "deckName": "English::Unit 1",
                    "fields": {
                        "Front": {"value": "retention"},
                        "Back": {"value": "memory"},
                    },
                    "type": 3,
                    "queue": 3,
                    "reps": 4,
                    "lapses": 1,
                },
                {
                    "cardId": 201,
                    "note": 2001,
                    "deckName": "Japanese",
                    "fields": {
                        "Front": {"value": "復習"},
                        "Back": {"value": "review"},
                    },
                    "type": 2,
                    "queue": 2,
                    "reps": 7,
                    "lapses": 0,
                },
            ]
        else:
            result = None

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "result": result,
            "error": None,
        }).encode("utf-8")

        mock_context = MagicMock()
        mock_context.__enter__.return_value = mock_resp
        return mock_context


class TestAnkiConnectDeckProvider(unittest.TestCase):
    def setUp(self) -> None:
        self.opener = FakeAnkiConnectOpener()
        self.provider = AnkiConnectDeckProvider(
            base_url="http://anki.test/",
            opener=self.opener,
        )

    def test_get_today_decks_maps_rows_and_parent_groups(self) -> None:
        decks = {deck["id"]: deck for deck in self.provider.get_today_decks()}

        self.assertIn("English::Unit 1", decks)
        self.assertIn("group:English", decks)
        self.assertIn("Japanese", decks)

        english = decks["English::Unit 1"]
        self.assertEqual(english["name"], "English::Unit 1")
        self.assertEqual(english["newCount"], 1)
        self.assertEqual(english["failedCount"], 1)
        self.assertEqual(english["totalCount"], 2)
        self.assertFalse(english["isGroup"])

        group = decks["group:English"]
        self.assertEqual(group["name"], "English")
        self.assertEqual(group["newCount"], 1)
        self.assertEqual(group["failedCount"], 1)
        self.assertEqual(group["totalCount"], 2)
        self.assertTrue(group["isGroup"])

    def test_get_deck_cards_returns_frontend_contract(self) -> None:
        result = self.provider.get_deck_cards("English::Unit 1")

        self.assertEqual(result["deckId"], "English::Unit 1")
        self.assertEqual(result["name"], "English::Unit 1")
        self.assertEqual(result["fields"], ["Front", "Back"])
        self.assertEqual(result["selectedFields"], ["Front", "Back"])
        self.assertEqual(len(result["cards"]), 2)

        cards = {card["cid"]: card for card in result["cards"]}
        self.assertEqual(cards[101]["term"], "reinforcement")
        self.assertTrue(cards[101]["is_new"])
        self.assertFalse(cards[101]["is_failed"])
        self.assertEqual(cards[101]["review_count"], 1)
        self.assertEqual(cards[101]["fields"]["Back"], "strengthening")

        self.assertFalse(cards[102]["is_new"])
        self.assertTrue(cards[102]["is_failed"])
        self.assertEqual(cards[102]["first_response"], "FORGET")
        self.assertEqual(cards[102]["response_grades"], [1])
        self.assertEqual(cards[102]["review_count"], 4)

        japanese = self.provider.get_deck_cards("Japanese")["cards"][0]
        self.assertEqual(japanese["first_response"], "VAGUE")
        self.assertEqual(japanese["response_grades"], [2, 3])

    def test_unknown_deck_returns_empty_contract(self) -> None:
        result = self.provider.get_deck_cards("Missing")
        self.assertEqual(result["deckId"], "Missing")
        self.assertEqual(result["name"], "")
        self.assertEqual(result["cards"], [])
        self.assertEqual(result["fields"], [])
        self.assertEqual(result["selectedFields"], [])

    def test_request_uses_standard_ankiconnect_envelope(self) -> None:
        self.provider.get_today_decks()
        first_req = self.opener.requests[0]
        self.assertEqual(first_req.full_url, "http://anki.test")
        self.assertEqual(first_req.method, "POST")
        payload = json.loads(first_req.data.decode("utf-8"))
        self.assertEqual(payload["action"], "multi")
        self.assertEqual(payload["version"], 6)
        self.assertEqual(payload["params"]["actions"][0], {
            "action": "findCards",
            "params": {"query": "rated:1"},
        })

    def test_ankiconnect_error_raises_safe_provider_error(self) -> None:
        def opener(req, timeout):
            raise urllib.error.HTTPError(req.full_url, 500, "Error", req.headers, None)

        provider = AnkiConnectDeckProvider(opener=opener)
        with self.assertRaises(AnkiConnectError) as error:
            provider.get_today_decks()
        self.assertEqual(error.exception.failure, AnkiConnectFailure.CONNECTION_FAILED)
        self.assertNotIn("500", str(error.exception))

    def test_timeout_malformed_partial_and_incompatible_version_are_classified(self) -> None:
        def timeout_opener(req, timeout):
            raise socket.timeout("secret transport detail")

        with self.assertRaises(AnkiConnectError) as timeout_error:
            AnkiConnectDeckProvider(opener=timeout_opener).get_today_decks()
        self.assertEqual(timeout_error.exception.failure, AnkiConnectFailure.TIMEOUT)
        self.assertNotIn("secret", str(timeout_error.exception))

        for raw, expected in (
            (b"not json", AnkiConnectFailure.MALFORMED_RESPONSE),
            (json.dumps({"error": None}).encode(), AnkiConnectFailure.PARTIAL_RESPONSE),
        ):
            def opener(req, timeout, response=raw):
                mock_resp = MagicMock()
                mock_resp.read.return_value = response
                context = MagicMock()
                context.__enter__.return_value = mock_resp
                return context

            with self.subTest(expected=expected), self.assertRaises(AnkiConnectError) as error:
                AnkiConnectDeckProvider(opener=opener).get_today_decks()
            self.assertEqual(error.exception.failure, expected)

        def old_version_opener(req, timeout):
            response = MagicMock()
            response.read.return_value = json.dumps({"result": 5, "error": None}).encode()
            context = MagicMock()
            context.__enter__.return_value = response
            return context

        with self.assertRaises(AnkiConnectError) as version_error:
            AnkiConnectDeckProvider(opener=old_version_opener).api_version()
        self.assertEqual(version_error.exception.failure, AnkiConnectFailure.INCOMPATIBLE_VERSION)

    def test_cancellation_is_checked_before_network_access(self) -> None:
        opener = MagicMock()
        provider = AnkiConnectDeckProvider(opener=opener, cancelled=lambda: True)

        with self.assertRaises(AnkiConnectError) as error:
            provider.get_today_decks()

        self.assertEqual(error.exception.failure, AnkiConnectFailure.CANCELLED)
        opener.assert_not_called()


if __name__ == "__main__":
    unittest.main()
