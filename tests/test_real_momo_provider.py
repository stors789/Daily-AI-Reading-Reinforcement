import json
import unittest
import urllib.error
from unittest.mock import MagicMock

from desktop_mock.real_momo_provider import (
    MoMoAPIError,
    RealMoMoDeckProvider,
    parse_markji_deck_list_response,
    parse_study_progress_response,
    parse_study_records_response,
    parse_today_items_response,
    parse_vocabulary_query_response,
    unwrap_api_response,
)


class MockOpener:
    """Fake opener to intercept urllib.request calls."""
    def __init__(self, response_data=b"{}", status=200):
        self.response_data = response_data
        self.status = status
        self.requests = []

    def __call__(self, req, timeout):
        self.requests.append(req)
        if self.status >= 400:
            raise urllib.error.HTTPError(req.full_url, self.status, "Error", req.headers, None)
        
        mock_resp = MagicMock()
        mock_resp.read.return_value = self.response_data
        
        mock_context = MagicMock()
        mock_context.__enter__.return_value = mock_resp
        return mock_context


class TestRealMoMoDeckProvider(unittest.TestCase):
    def setUp(self):
        self.token = "fake_test_token_123"
        self.opener = MockOpener()
        self.provider = RealMoMoDeckProvider(
            token=self.token,
            opener=self.opener
        )

    def test_constructor_requires_token(self):
        with self.assertRaises(ValueError):
            RealMoMoDeckProvider(token="")

    def test_constructor_strips_base_url_slash(self):
        p = RealMoMoDeckProvider(token="t", base_url="https://test.com/")
        self.assertEqual(p._base_url, "https://test.com")

    def test_token_not_in_repr(self):
        # We don't define a custom repr, but let's make sure if it exists, token isn't in it
        rep = repr(self.provider)
        self.assertNotIn(self.token, rep)

    def test_headers_contain_token(self):
        self.provider.get_markji_decks_raw()
        req = self.opener.requests[0]
        self.assertEqual(req.get_header("Authorization"), f"Bearer {self.token}")

    def test_get_study_progress_raw(self):
        self.provider.get_study_progress_raw()
        req = self.opener.requests[0]
        self.assertEqual(req.full_url, "https://open.maimemo.com/open/api/v1/study/get_study_progress")
        self.assertEqual(req.method, "POST")
        self.assertEqual(json.loads(req.data), {})

    def test_get_today_items_raw(self):
        self.provider.get_today_items_raw(is_finished=True, is_new=False, limit=10)
        req = self.opener.requests[0]
        self.assertEqual(req.full_url, "https://open.maimemo.com/open/api/v1/study/get_today_items")
        self.assertEqual(req.method, "POST")
        self.assertEqual(json.loads(req.data), {"is_finished": True, "is_new": False, "limit": 10})
        
        self.opener.requests.clear()
        self.provider.get_today_items_raw(limit=5)
        req = self.opener.requests[0]
        self.assertEqual(json.loads(req.data), {"limit": 5})

        self.opener.requests.clear()
        self.provider.get_today_items_raw()
        req = self.opener.requests[0]
        self.assertEqual(json.loads(req.data), {})

    def test_query_study_records_raw(self):
        self.provider.query_study_records_raw(next_study_date="2026-07-05", as_count=True, limit=20)
        req = self.opener.requests[0]
        self.assertEqual(req.full_url, "https://open.maimemo.com/open/api/v1/study/query_study_records")
        self.assertEqual(req.method, "POST")
        self.assertEqual(json.loads(req.data), {"next_study_date": "2026-07-05", "as_count": True, "limit": 20})
        
        self.opener.requests.clear()
        self.provider.query_study_records_raw(limit=5)
        req = self.opener.requests[0]
        self.assertEqual(json.loads(req.data), {"limit": 5})

    def test_get_markji_decks_raw(self):
        self.provider.get_markji_decks_raw()
        req = self.opener.requests[0]
        self.assertEqual(req.full_url, "https://open.maimemo.com/open/api/v1/markji/decks")
        self.assertEqual(req.method, "GET")
        self.assertIsNone(req.data)

    def test_query_vocabulary_raw(self):
        self.provider.query_vocabulary_raw(spellings=["apple"])
        req = self.opener.requests[0]
        self.assertEqual(json.loads(req.data), {"spellings": ["apple"]})

        self.opener.requests.clear()
        self.provider.query_vocabulary_raw(ids=[123])
        req = self.opener.requests[0]
        self.assertEqual(json.loads(req.data), {"ids": [123]})

    def test_query_vocabulary_raw_mutex(self):
        with self.assertRaises(ValueError):
            self.provider.query_vocabulary_raw(spellings=["a"], ids=[1])

    def test_http_error(self):
        self.opener.status = 401
        with self.assertRaises(MoMoAPIError):
            self.provider.get_markji_decks_raw()

    def test_invalid_json_error(self):
        self.opener.response_data = b"not json"
        with self.assertRaises(MoMoAPIError):
            self.provider.get_markji_decks_raw()

    # --- Parsing Tests ---

    def test_unwrap_api_response(self):
        # Non-envelope
        self.assertEqual(unwrap_api_response({"x": 1}), {"x": 1})
        self.assertEqual(unwrap_api_response([]), [])
        
        # Envelope success
        self.assertEqual(
            unwrap_api_response({"success": True, "data": {"x": 1}, "errors": {}}),
            {"x": 1}
        )
        self.assertEqual(
            unwrap_api_response({"success": True, "errors": {}}),
            {}
        )
        
        # Envelope error
        with self.assertRaisesRegex(MoMoAPIError, "MoMo API error: 400 - Bad Req"):
            unwrap_api_response({
                "success": False,
                "errors": [{"code": "400", "message": "Bad Req"}]
            })
            
        with self.assertRaisesRegex(MoMoAPIError, "MoMo API returned errors"):
            unwrap_api_response({"success": False, "errors": []})

    def test_parse_study_progress_response(self):
        self.assertEqual(parse_study_progress_response({}), {})
        self.assertEqual(parse_study_progress_response([]), {})
        self.assertEqual(
            parse_study_progress_response({"progress": {"finished": 1, "total": 2, "study_time": 3, "extra": 4}}),
            {"finished": 1, "total": 2, "study_time": 3}
        )
        # Envelope
        self.assertEqual(
            parse_study_progress_response({"success": True, "errors": {}, "data": {"progress": {"total": 5}}}),
            {"total": 5}
        )

    def test_parse_today_items_response(self):
        self.assertEqual(parse_today_items_response({}), [])
        self.assertEqual(
            parse_today_items_response({"today_items": [{"voc_id": 1}]}),
            [{"voc_id": 1}]
        )
        # Envelope
        self.assertEqual(
            parse_today_items_response({"success": True, "errors": {}, "data": {"today_items": [{"voc_id": 2}]}}),
            [{"voc_id": 2}]
        )

    def test_parse_study_records_response(self):
        self.assertEqual(parse_study_records_response({}), {"records": [], "count": 0})
        self.assertEqual(
            parse_study_records_response({"records": [{"id": 1}], "count": 10}),
            {"records": [{"id": 1}], "count": 10}
        )

    def test_parse_markji_deck_list_response(self):
        self.assertEqual(parse_markji_deck_list_response({}), [])
        self.assertEqual(
            parse_markji_deck_list_response({"decks": [{"id": "d1"}]}),
            [{"id": "d1"}]
        )

    def test_parse_vocabulary_query_response(self):
        self.assertEqual(parse_vocabulary_query_response({}), [])
        self.assertEqual(
            parse_vocabulary_query_response({"voc": [{"id": 1}]}),
            [{"id": 1}]
        )

    # --- Mapping Tests ---

    def test_get_today_decks(self):
        self.opener.response_data = json.dumps({
            "decks": [
                {"id": "d1", "name": "Deck 1", "card_count": 100},
                {"id": "d2", "name": "Deck 2"}
            ]
        }).encode("utf-8")
        decks = self.provider.get_today_decks()
        self.assertEqual(len(decks), 2)
        self.assertEqual(decks[0]["id"], "d1")
        self.assertEqual(decks[0]["name"], "Deck 1")
        self.assertEqual(decks[0]["totalCount"], 100)
        self.assertEqual(decks[0]["newCount"], 0)
        self.assertEqual(decks[0]["failedCount"], 0)
        self.assertFalse(decks[0]["isGroup"])

        self.assertEqual(decks[1]["totalCount"], 0)

    def test_get_today_decks_fallback(self):
        self.opener.status = 403
        decks = self.provider.get_today_decks()
        self.assertEqual(len(decks), 1)
        self.assertEqual(decks[0]["id"], "momo_today")
        self.assertEqual(decks[0]["totalCount"], 0) # without progress
        self.assertEqual(decks[0]["newCount"], 0)
        self.assertEqual(decks[0]["failedCount"], 0)

        # with progress fallback
        self.opener.requests.clear()
        
        def fake_opener(req, timeout):
            if "markji" in req.full_url:
                raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, None)
            
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({"progress": {"total": 42}}).encode("utf-8")
            mock_context = MagicMock()
            mock_context.__enter__.return_value = mock_resp
            return mock_context
            
        self.provider._opener = fake_opener
        decks = self.provider.get_today_decks()
        self.assertEqual(decks[0]["totalCount"], 42)

    def test_get_deck_cards_skeleton(self):
        res = self.provider.get_deck_cards("d1")
        self.assertEqual(res["deckId"], "d1")
        self.assertEqual(res["cards"], [])
        self.assertIn("term", res["fields"])
        self.assertIn("status", res["fields"])
        self.assertIn("source", res["fields"])
        self.assertIn("review_count_status", res["fields"])
        self.assertEqual(res["selectedFields"], ["term"])

    def test_get_deck_cards_momo_today(self):
        """Phase 16: full card mapping and conservative is_failed."""
        requests_seen = []
        def fake_opener(req, timeout):
            requests_seen.append(req)
            mock_resp = MagicMock()
            if "get_today_items" in req.full_url:
                mock_resp.read.return_value = json.dumps({
                    "today_items": [
                        {"voc_id": 1, "voc_spelling": "apple", "is_new": True, "is_finished": True, "first_response": "FORGET"},
                        {"voc_id": 2, "voc_spelling": "banana", "is_new": False, "is_finished": False, "first_response": "UNKNOWN"},
                        {"voc_id": 3, "voc_spelling": "cherry", "is_new": False, "is_finished": True, "first_response": "RECOGNIZE"},
                    ]
                }).encode("utf-8")
            elif "query_study_records" in req.full_url:
                mock_resp.read.return_value = json.dumps({
                    "records": [
                        {"voc_id": 1, "study_count": 5},
                        {"voc_id": 2, "study_count": 1},
                    ]
                }).encode("utf-8")
            else:
                mock_resp.read.return_value = b"{}"

            mock_context = MagicMock()
            mock_context.__enter__.return_value = mock_resp
            return mock_context

        self.provider._opener = fake_opener
        res = self.provider.get_deck_cards("momo_today")
        self.assertEqual(res["deckId"], "momo_today")
        cards = res["cards"]
        self.assertEqual(len(cards), 3)
        
        # apple: is_failed because first_response == FORGET; status "new" (is_new=True)
        self.assertEqual(cards[0]["term"], "apple")
        self.assertTrue(cards[0]["is_failed"])
        self.assertTrue(cards[0]["is_new"])
        self.assertEqual(cards[0]["review_count"], 5)
        self.assertEqual(cards[0]["fields"]["status"], "new")
        self.assertEqual(cards[0]["fields"]["source"], "MoMo Today")
        self.assertEqual(cards[0]["fields"]["review_count_status"], "provider_value_unverified")
        
        # banana: is_finished=False => status "unfinished", NOT is_failed
        self.assertEqual(cards[1]["term"], "banana")
        self.assertFalse(cards[1]["is_failed"])  # Phase 16: no longer failed
        self.assertFalse(cards[1]["is_new"])
        self.assertEqual(cards[1]["review_count"], 1)
        self.assertEqual(cards[1]["fields"]["status"], "unfinished")
        self.assertEqual(cards[1]["fields"]["review_count_status"], "provider_value_unverified")

        # cherry: is_failed = False, status "finished"
        self.assertEqual(cards[2]["term"], "cherry")
        self.assertFalse(cards[2]["is_failed"])
        self.assertEqual(cards[2]["review_count"], 0)
        self.assertEqual(cards[2]["fields"]["status"], "finished")
        self.assertEqual(cards[2]["fields"]["review_count_status"], "provider_value_unverified")

        # Verify fields list
        self.assertIn("term", res["fields"])
        self.assertIn("status", res["fields"])
        self.assertIn("source", res["fields"])
        self.assertIn("review_count_status", res["fields"])
        self.assertEqual(res["selectedFields"], ["term"])

        # Ensure no limit is sent by default in the high-level call
        for req in requests_seen:
            body = json.loads(req.data) if req.data else {}
            self.assertNotIn("limit", body)

    def test_get_deck_cards_momo_today_empty(self):
        """Empty today_items still returns base fields list."""
        def fake_opener(req, timeout):
            mock_resp = MagicMock()
            if "get_today_items" in req.full_url:
                mock_resp.read.return_value = json.dumps({"today_items": []}).encode("utf-8")
            elif "query_study_records" in req.full_url:
                mock_resp.read.return_value = json.dumps({"records": []}).encode("utf-8")
            else:
                mock_resp.read.return_value = b"{}"
            mock_context = MagicMock()
            mock_context.__enter__.return_value = mock_resp
            return mock_context

        self.provider._opener = fake_opener
        res = self.provider.get_deck_cards("momo_today")
        self.assertEqual(res["deckId"], "momo_today")
        self.assertEqual(res["cards"], [])
        self.assertIn("term", res["fields"])
        self.assertIn("status", res["fields"])
        self.assertIn("source", res["fields"])
        self.assertIn("review_count_status", res["fields"])
        self.assertEqual(res["selectedFields"], ["term"])

    def test_get_deck_cards_today_items_request_error(self):
        def fake_opener(req, timeout):
            if "get_today_items" in req.full_url:
                raise urllib.error.HTTPError(req.full_url, 500, "Internal Server Error", {}, None)
            mock_resp = MagicMock()
            mock_resp.read.return_value = b"{}"
            mock_context = MagicMock()
            mock_context.__enter__.return_value = mock_resp
            return mock_context
            
        self.provider._opener = fake_opener
        from desktop_mock.real_momo_provider import MoMoProviderDataError
        with self.assertRaises(MoMoProviderDataError) as cm:
            self.provider.get_deck_cards("momo_today")
        self.assertEqual(cm.exception.stage, "today_items_request")
        self.assertNotIn("Internal Server Error", str(cm.exception))

    def test_get_deck_cards_study_records_error_fallback(self):
        """When study_records fails, cards still return but review_count_status is unavailable."""
        def fake_opener(req, timeout):
            if "get_today_items" in req.full_url:
                mock_resp = MagicMock()
                mock_resp.read.return_value = json.dumps({
                    "today_items": [{"voc_id": 1, "voc_spelling": "apple"}]
                }).encode("utf-8")
                mock_context = MagicMock()
                mock_context.__enter__.return_value = mock_resp
                return mock_context
            elif "query_study_records" in req.full_url:
                raise urllib.error.HTTPError(req.full_url, 500, "Internal Server Error", {}, None)
            
            mock_resp = MagicMock()
            mock_resp.read.return_value = b"{}"
            mock_context = MagicMock()
            mock_context.__enter__.return_value = mock_resp
            return mock_context

        self.provider._opener = fake_opener
        res = self.provider.get_deck_cards("momo_today")
        # Should not raise, should fallback to review_count=0
        self.assertEqual(len(res["cards"]), 1)
        self.assertEqual(res["cards"][0]["term"], "apple")
        self.assertEqual(res["cards"][0]["review_count"], 0)
        self.assertEqual(res["cards"][0]["fields"]["review_count_status"], "unavailable")

    def test_get_deck_cards_study_records_parse_error_fallback(self):
        """When study_records returns invalid JSON, review_count_status is unavailable."""
        def fake_opener(req, timeout):
            mock_resp = MagicMock()
            if "get_today_items" in req.full_url:
                mock_resp.read.return_value = json.dumps({
                    "today_items": [{"voc_id": 1, "voc_spelling": "apple"}]
                }).encode("utf-8")
            elif "query_study_records" in req.full_url:
                # invalid json to trigger parse error
                mock_resp.read.return_value = b"invalid json"
            else:
                mock_resp.read.return_value = b"{}"
                
            mock_context = MagicMock()
            mock_context.__enter__.return_value = mock_resp
            return mock_context

        self.provider._opener = fake_opener
        res = self.provider.get_deck_cards("momo_today")
        # Should not raise, should fallback to review_count=0
        self.assertEqual(len(res["cards"]), 1)
        self.assertEqual(res["cards"][0]["term"], "apple")
        self.assertEqual(res["cards"][0]["review_count"], 0)
        self.assertEqual(res["cards"][0]["fields"]["review_count_status"], "unavailable")

    # --- Phase 16: Additional field/status coverage ---

    def test_is_failed_only_on_forget(self):
        """is_failed is True only when first_response == FORGET, not when is_finished == False."""
        def fake_opener(req, timeout):
            mock_resp = MagicMock()
            if "get_today_items" in req.full_url:
                mock_resp.read.return_value = json.dumps({
                    "today_items": [
                        # FORGET => is_failed=True
                        {"voc_id": 10, "voc_spelling": "w1", "is_new": False, "is_finished": False, "first_response": "FORGET"},
                        # unfinished, non-FORGET => is_failed=False
                        {"voc_id": 20, "voc_spelling": "w2", "is_new": False, "is_finished": False, "first_response": "VAGUE"},
                        # finished, non-FORGET => is_failed=False
                        {"voc_id": 30, "voc_spelling": "w3", "is_new": False, "is_finished": True, "first_response": "FAMILIAR"},
                        # no first_response, is_finished=None => is_failed=False
                        {"voc_id": 40, "voc_spelling": "w4", "is_new": False},
                    ]
                }).encode("utf-8")
            elif "query_study_records" in req.full_url:
                mock_resp.read.return_value = json.dumps({"records": []}).encode("utf-8")
            else:
                mock_resp.read.return_value = b"{}"
            mock_context = MagicMock()
            mock_context.__enter__.return_value = mock_resp
            return mock_context

        self.provider._opener = fake_opener
        res = self.provider.get_deck_cards("momo_today")
        cards = res["cards"]
        self.assertEqual(len(cards), 4)

        self.assertTrue(cards[0]["is_failed"])   # FORGET
        self.assertFalse(cards[1]["is_failed"])   # VAGUE, unfinished
        self.assertFalse(cards[2]["is_failed"])   # FAMILIAR, finished
        self.assertFalse(cards[3]["is_failed"])   # no first_response

    def test_status_derivation(self):
        """status field is correctly derived from is_new and is_finished."""
        def fake_opener(req, timeout):
            mock_resp = MagicMock()
            if "get_today_items" in req.full_url:
                mock_resp.read.return_value = json.dumps({
                    "today_items": [
                        {"voc_id": 1, "voc_spelling": "w_new", "is_new": True, "is_finished": False},
                        {"voc_id": 2, "voc_spelling": "w_finished", "is_new": False, "is_finished": True},
                        {"voc_id": 3, "voc_spelling": "w_unfinished", "is_new": False, "is_finished": False},
                        {"voc_id": 4, "voc_spelling": "w_unknown", "is_new": False},
                    ]
                }).encode("utf-8")
            elif "query_study_records" in req.full_url:
                mock_resp.read.return_value = json.dumps({"records": []}).encode("utf-8")
            else:
                mock_resp.read.return_value = b"{}"
            mock_context = MagicMock()
            mock_context.__enter__.return_value = mock_resp
            return mock_context

        self.provider._opener = fake_opener
        res = self.provider.get_deck_cards("momo_today")
        cards = res["cards"]

        self.assertEqual(cards[0]["fields"]["status"], "new")
        self.assertEqual(cards[1]["fields"]["status"], "finished")
        self.assertEqual(cards[2]["fields"]["status"], "unfinished")
        self.assertEqual(cards[3]["fields"]["status"], "unknown")

    def test_source_field_always_momo_today(self):
        """Every card's fields['source'] is always 'MoMo Today'."""
        def fake_opener(req, timeout):
            mock_resp = MagicMock()
            if "get_today_items" in req.full_url:
                mock_resp.read.return_value = json.dumps({
                    "today_items": [
                        {"voc_id": 1, "voc_spelling": "w1"},
                        {"voc_id": 2, "voc_spelling": "w2"},
                    ]
                }).encode("utf-8")
            elif "query_study_records" in req.full_url:
                mock_resp.read.return_value = json.dumps({"records": []}).encode("utf-8")
            else:
                mock_resp.read.return_value = b"{}"
            mock_context = MagicMock()
            mock_context.__enter__.return_value = mock_resp
            return mock_context

        self.provider._opener = fake_opener
        res = self.provider.get_deck_cards("momo_today")
        for card in res["cards"]:
            self.assertEqual(card["fields"]["source"], "MoMo Today")

    def test_review_count_status_available_when_records_succeed(self):
        """When study_records succeeds, review_count_status is 'provider_value_unverified'."""
        def fake_opener(req, timeout):
            mock_resp = MagicMock()
            if "get_today_items" in req.full_url:
                mock_resp.read.return_value = json.dumps({
                    "today_items": [{"voc_id": 1, "voc_spelling": "w1"}]
                }).encode("utf-8")
            elif "query_study_records" in req.full_url:
                mock_resp.read.return_value = json.dumps({
                    "records": [{"voc_id": 1, "study_count": 3}]
                }).encode("utf-8")
            else:
                mock_resp.read.return_value = b"{}"
            mock_context = MagicMock()
            mock_context.__enter__.return_value = mock_resp
            return mock_context

        self.provider._opener = fake_opener
        res = self.provider.get_deck_cards("momo_today")
        card = res["cards"][0]
        self.assertEqual(card["review_count"], 3)
        self.assertEqual(card["fields"]["review_count_status"], "provider_value_unverified")

    def test_card_toplevel_required_fields(self):
        """Each card must have all top-level required fields regardless of data."""
        required_keys = {"cid", "nid", "term", "fields", "is_new", "is_failed", "is_finished", "first_response", "last_response", "review_count"}
        def fake_opener(req, timeout):
            mock_resp = MagicMock()
            if "get_today_items" in req.full_url:
                mock_resp.read.return_value = json.dumps({
                    "today_items": [
                        {"voc_id": 99, "voc_spelling": "test_word"},
                    ]
                }).encode("utf-8")
            elif "query_study_records" in req.full_url:
                mock_resp.read.return_value = json.dumps({"records": []}).encode("utf-8")
            else:
                mock_resp.read.return_value = b"{}"
            mock_context = MagicMock()
            mock_context.__enter__.return_value = mock_resp
            return mock_context

        self.provider._opener = fake_opener
        res = self.provider.get_deck_cards("momo_today")
        for card in res["cards"]:
            self.assertTrue(required_keys.issubset(set(card.keys())),
                            f"Missing keys: {required_keys - set(card.keys())}")

    def test_fields_contain_term(self):
        """Card fields dict must always contain 'term'."""
        def fake_opener(req, timeout):
            mock_resp = MagicMock()
            if "get_today_items" in req.full_url:
                mock_resp.read.return_value = json.dumps({
                    "today_items": [{"voc_id": 1, "voc_spelling": "hello"}]
                }).encode("utf-8")
            elif "query_study_records" in req.full_url:
                mock_resp.read.return_value = json.dumps({"records": []}).encode("utf-8")
            else:
                mock_resp.read.return_value = b"{}"
            mock_context = MagicMock()
            mock_context.__enter__.return_value = mock_resp
            return mock_context

        self.provider._opener = fake_opener
        res = self.provider.get_deck_cards("momo_today")
        for card in res["cards"]:
           self.assertIn("term", card["fields"])
           self.assertEqual(card["fields"]["term"], card["term"])



if __name__ == "__main__":
    unittest.main()
