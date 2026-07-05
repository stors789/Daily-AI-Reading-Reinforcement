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

    def test_query_study_records_raw(self):
        self.provider.query_study_records_raw(next_study_date="2026-07-05", as_count=True, limit=20)
        req = self.opener.requests[0]
        self.assertEqual(req.full_url, "https://open.maimemo.com/open/api/v1/study/query_study_records")
        self.assertEqual(req.method, "POST")
        self.assertEqual(json.loads(req.data), {"next_study_date": "2026-07-05", "as_count": True, "limit": 20})

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

    def test_parse_study_progress_response(self):
        self.assertEqual(parse_study_progress_response({}), {})
        self.assertEqual(parse_study_progress_response([]), {})
        self.assertEqual(
            parse_study_progress_response({"progress": {"finished": 1, "total": 2, "study_time": 3, "extra": 4}}),
            {"finished": 1, "total": 2, "study_time": 3}
        )

    def test_parse_today_items_response(self):
        self.assertEqual(parse_today_items_response({}), [])
        self.assertEqual(
            parse_today_items_response({"today_items": [{"voc_id": 1}]}),
            [{"voc_id": 1}]
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

    def test_get_deck_cards_skeleton(self):
        res = self.provider.get_deck_cards("d1")
        self.assertEqual(res["deckId"], "d1")
        self.assertEqual(res["cards"], [])
        self.assertEqual(res["fields"], [])
        self.assertEqual(res["selectedFields"], [])

if __name__ == "__main__":
    unittest.main()
