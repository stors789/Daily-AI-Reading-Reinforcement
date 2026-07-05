"""Tests for the Phase 9 MoMo API probe (pure functions only).

These tests never touch the network. They cover:
- dry-run does not trigger network
- missing credentials does not crash the real-run path
- parse functions against mock OpenAPI responses
- credential masking never leaks a full token/cookie
- importing the module does not perform any network call
"""

import importlib.util
import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

_mock_dir = Path(__file__).resolve().parent.parent / "desktop_mock"
if str(_mock_dir) not in sys.path:
    sys.path.insert(0, str(_mock_dir))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_probe = _load("momo_api_probe", _mock_dir / "momo_api_probe.py")


class TestImportSafety(unittest.TestCase):
    """Importing the probe module must not perform any network call."""

    def test_import_does_not_call_urlopen(self) -> None:
        with patch("urllib.request.urlopen") as fake:
            # Re-importing would hit the cached module; instead exercise
            # every module-level constant and helper to prove nothing
            # triggers a request at import / idle time.
            _ = _probe.CREDENTIAL_ENVS
            _ = _probe.CANDIDATE_ENDPOINTS
            _ = _probe.BASE_URL
            _ = _probe.DECK_ROW_FIELDS
            _ = _probe.CARD_FIELDS
            _probe.mask_credential("abcdef")
            _probe.load_credentials({})
            _probe.has_credentials({"MOMO_TOKEN": ""})
        self.assertFalse(
            fake.called, "urlopen must not be called at import / idle time"
        )


class TestDryRun(unittest.TestCase):
    def test_dry_run_returns_zero_and_does_not_call_network(self) -> None:
        with patch("urllib.request.urlopen") as fake:
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = _probe.main(["--dry-run"])
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("dry-run: no network", out)
        self.assertIn("MOMO_TOKEN", out)
        self.assertIn("study_progress", out)
        self.assertIn("markji_decks", out)
        self.assertFalse(fake.called, "dry-run must not call urlopen")

    def test_dry_run_masks_present_token(self) -> None:
        env = {"MOMO_TOKEN": "abcdefghij1234567", "MOMO_COOKIE": ""}
        with patch.dict("os.environ", env, clear=True):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = _probe.main(["--dry-run"])
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        # Full token must never appear; only first 4 / last 4.
        self.assertNotIn("abcdefghij1234567", out)
        self.assertIn("abcd***4567", out)


class TestMissingCredentials(unittest.TestCase):
    def test_real_run_with_no_credentials_returns_nonzero(self) -> None:
        env = {"MOMO_TOKEN": "", "MOMO_COOKIE": ""}
        with patch.dict("os.environ", env, clear=True):
            with patch("urllib.request.urlopen") as fake:
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = _probe.main([])
        self.assertEqual(rc, 2)
        self.assertIn("No credentials found", buf.getvalue())
        self.assertFalse(fake.called, "must not call network when no creds")


class TestMaskCredential(unittest.TestCase):
    def test_none_is_unset(self) -> None:
        self.assertEqual(_probe.mask_credential(None), "<unset>")

    def test_empty_is_empty(self) -> None:
        self.assertEqual(_probe.mask_credential(""), "<empty>")

    def test_short_value_fully_masked(self) -> None:
        self.assertEqual(_probe.mask_credential("abc"), "***")
        self.assertEqual(_probe.mask_credential("abcdefgh"), "***")

    def test_long_value_shows_only_edges(self) -> None:
        masked = _probe.mask_credential("abcdefghijklmnop")
        self.assertEqual(masked, "abcd***mnop")
        self.assertNotIn("efghijkl", masked)

    def test_masking_never_leaks_full_value(self) -> None:
        secret = "0123456789abcdef"
        masked = _probe.mask_credential(secret)
        self.assertNotIn(secret, masked)
        self.assertNotIn("56789abc", masked)


class TestLoadCredentials(unittest.TestCase):
    def test_returns_all_env_names_as_empty_when_unset(self) -> None:
        creds = _probe.load_credentials({})
        self.assertEqual(set(creds.keys()), set(_probe.CREDENTIAL_ENVS))
        for v in creds.values():
            self.assertEqual(v, "")

    def test_reads_present_values(self) -> None:
        creds = _probe.load_credentials({"MOMO_TOKEN": "tok", "MOMO_COOKIE": "ck"})
        self.assertEqual(creds["MOMO_TOKEN"], "tok")
        self.assertEqual(creds["MOMO_COOKIE"], "ck")

    def test_has_credentials_false_when_all_empty(self) -> None:
        self.assertFalse(_probe.has_credentials({"MOMO_TOKEN": "", "MOMO_COOKIE": ""}))

    def test_has_credentials_true_when_any_present(self) -> None:
        self.assertTrue(_probe.has_credentials({"MOMO_TOKEN": "x", "MOMO_COOKIE": ""}))


class TestBuildHeaders(unittest.TestCase):
    def test_bearer_header_when_token_set(self) -> None:
        h = _probe.build_request_headers({"MOMO_TOKEN": "tok", "MOMO_COOKIE": ""})
        self.assertEqual(h["Authorization"], "Bearer tok")
        self.assertNotIn("Cookie", h)

    def test_cookie_header_when_cookie_set(self) -> None:
        h = _probe.build_request_headers({"MOMO_TOKEN": "", "MOMO_COOKIE": "k=v"})
        self.assertNotIn("Authorization", h)
        self.assertEqual(h["Cookie"], "k=v")

    def test_neither_when_unset(self) -> None:
        h = _probe.build_request_headers({"MOMO_TOKEN": "", "MOMO_COOKIE": ""})
        self.assertNotIn("Authorization", h)
        self.assertNotIn("Cookie", h)
        self.assertEqual(h["Accept"], "application/json")


class TestParseStudyProgress(unittest.TestCase):
    def test_parses_real_shape(self) -> None:
        data = {"progress": {"finished": 10, "total": 20, "study_time": 60000}}
        out = _probe.parse_study_progress_response(data)
        self.assertEqual(out, {"finished": 10, "total": 20, "study_time": 60000})

    def test_unknown_shape_returns_empty(self) -> None:
        self.assertEqual(_probe.parse_study_progress_response({}), {})
        self.assertEqual(_probe.parse_study_progress_response("x"), {})
        self.assertEqual(_probe.parse_study_progress_response(None), {})

    def test_partial_progress(self) -> None:
        out = _probe.parse_study_progress_response({"progress": {"finished": 5}})
        self.assertEqual(out, {"finished": 5})


class TestParseTodayItems(unittest.TestCase):
    def test_parses_real_shape(self) -> None:
        data = {"today_items": [
            {"voc_id": "v1", "voc_spelling": "apple", "order": 1,
             "is_new": True, "is_finished": False},
            {"voc_id": "v2", "voc_spelling": "bee", "order": 2,
             "is_new": False, "is_finished": True},
        ]}
        items = _probe.parse_today_items_response(data)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["voc_id"], "v1")
        self.assertTrue(items[0]["is_new"])

    def test_missing_key_returns_empty(self) -> None:
        self.assertEqual(_probe.parse_today_items_response({}), [])
        self.assertEqual(_probe.parse_today_items_response({"today_items": "x"}), [])

    def test_non_dict_items_filtered(self) -> None:
        self.assertEqual(_probe.parse_today_items_response({"today_items": [1, "x"]}), [])


class TestParseStudyRecords(unittest.TestCase):
    def test_parses_real_shape(self) -> None:
        data = {"records": [
            {"voc_id": "v1", "voc_spelling": "apple", "study_count": 3},
        ], "count": 42}
        out = _probe.parse_study_records_response(data)
        self.assertEqual(out["count"], 42)
        self.assertEqual(len(out["records"]), 1)

    def test_count_defaults_to_len_when_missing(self) -> None:
        data = {"records": [{"voc_id": "v1"}, {"voc_id": "v2"}]}
        out = _probe.parse_study_records_response(data)
        self.assertEqual(out["count"], 2)

    def test_unknown_shape(self) -> None:
        out = _probe.parse_study_records_response({})
        self.assertEqual(out, {"records": [], "count": 0})


class TestParseMarkjiDecks(unittest.TestCase):
    def test_parses_real_shape(self) -> None:
        data = {"decks": [
            {"id": "d1", "name": "GRE", "card_count": 100, "parent_id": None},
        ], "total": 1}
        decks = _probe.parse_markji_deck_list_response(data)
        self.assertEqual(len(decks), 1)
        self.assertEqual(decks[0]["name"], "GRE")

    def test_missing_decks_returns_empty(self) -> None:
        self.assertEqual(_probe.parse_markji_deck_list_response({}), [])
        self.assertEqual(_probe.parse_markji_deck_list_response({"decks": "x"}), [])


class TestParseVocabularyQuery(unittest.TestCase):
    def test_parses_real_shape(self) -> None:
        data = {"voc": [
            {"id": "5a7BFf4F63612e5AD9fdebB7a50D3881", "spelling": "apple"},
        ]}
        voc = _probe.parse_vocabulary_query_response(data)
        self.assertEqual(len(voc), 1)
        self.assertEqual(voc[0]["spelling"], "apple")

    def test_missing_voc_returns_empty(self) -> None:
        self.assertEqual(_probe.parse_vocabulary_query_response({}), [])


class TestDeckRowMappingReport(unittest.TestCase):
    def test_markji_deck_direct_and_defaulted(self) -> None:
        raw = {"id": "d1", "name": "GRE", "card_count": 100, "parent_id": None}
        report = _probe.deck_row_mapping_report(raw)
        self.assertEqual(report["id"], {"status": "direct", "source": "id"})
        self.assertEqual(report["name"], {"status": "direct", "source": "name"})
        self.assertEqual(report["totalCount"], {"status": "direct", "source": "card_count"})
        # newCount / failedCount have no source -> defaulted
        self.assertEqual(report["newCount"]["status"], "defaulted")
        self.assertEqual(report["failedCount"]["status"], "defaulted")
        # isGroup: parent_id presence could imply grouping, but our alias set
        # does not list parent_id, so it is defaulted.
        self.assertEqual(report["isGroup"]["status"], "defaulted")

    def test_empty_deck_all_missing_or_defaulted(self) -> None:
        report = _probe.deck_row_mapping_report({})
        for field in _probe.DECK_ROW_FIELDS:
            self.assertIn(report[field]["status"], ("defaulted", "missing"))


class TestCardMappingReport(unittest.TestCase):
    def test_study_today_item_mapping(self) -> None:
        raw = {
            "voc_id": "v1", "voc_spelling": "apple", "order": 1,
            "is_new": True, "is_finished": False,
        }
        report = _probe.today_item_mapping_report(raw)
        self.assertEqual(report["cid"]["status"], "direct")
        self.assertEqual(report["term"]["status"], "direct")
        self.assertEqual(report["is_new"]["status"], "direct")
        # nid / fields / is_failed / review_count have no source
        self.assertEqual(report["nid"]["status"], "defaulted")
        self.assertEqual(report["fields"]["status"], "defaulted")
        self.assertEqual(report["is_failed"]["status"], "defaulted")
        self.assertEqual(report["review_count"]["status"], "defaulted")

    def test_markji_card_mapping(self) -> None:
        raw = {"id": "c1", "content": "front|back", "deck_id": "d1"}
        report = _probe.card_mapping_report(raw)
        self.assertEqual(report["cid"]["status"], "direct")
        self.assertEqual(report["fields"]["status"], "direct")
        # term has no default and no spelling source on a bare markji card
        self.assertEqual(report["term"]["status"], "missing")
        self.assertEqual(report["is_new"]["status"], "defaulted")


class TestSummarizeShape(unittest.TestCase):
    def test_summarize_shape_redacts_strings(self) -> None:
        self.assertEqual(_probe.summarize_shape("secret"), "<redacted str>")

    def test_summarize_shape_primitives(self) -> None:
        self.assertEqual(_probe.summarize_shape(True), "bool")
        self.assertEqual(_probe.summarize_shape(False), "bool")
        self.assertEqual(_probe.summarize_shape(42), "int")
        self.assertEqual(_probe.summarize_shape(3.14), "float")
        self.assertEqual(_probe.summarize_shape(None), "null")

    def test_summarize_shape_dict(self) -> None:
        data = {"a": 1, "b": "str", "c": {"d": True}}
        expected = {"a": "int", "b": "<redacted str>", "c": {"d": "bool"}}
        self.assertEqual(_probe.summarize_shape(data), expected)

    def test_summarize_shape_list(self) -> None:
        data = [{"id": 1}, {"id": 2}, {"id": 3}, {"id": 4}]
        expected = {
            "_count": 4,
            "_items": [
                {"id": "int"},
                {"id": "int"}
            ]
        }
        self.assertEqual(_probe.summarize_shape(data, max_items=2), expected)

    def test_summarize_shape_empty_list(self) -> None:
        self.assertEqual(_probe.summarize_shape([]), {"_count": 0})


class TestNoRealCredentialsInCode(unittest.TestCase):
    """Guardrail: the probe source must not hardcode real credentials."""

    def test_source_has_no_literal_bearer_token(self) -> None:
        src = (_mock_dir / "momo_api_probe.py").read_text(encoding="utf-8")
        # The literal "Bearer " is fine (header scheme); a hardcoded token
        # would look like "Bearer <non-placeholder>". We check that no
        # obvious long token literal is present.
        import re
        # Disallow "Bearer " followed by a long hex/alnum literal that is
        # not the placeholder "<token>" or "{token}".
        bad = re.findall(r"Bearer\s+[A-Za-z0-9]{20,}", src)
        self.assertEqual(bad, [], f"hardcoded bearer tokens found: {bad}")


if __name__ == "__main__":
    unittest.main()
