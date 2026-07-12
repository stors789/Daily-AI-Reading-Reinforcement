# Tests for core/utils.py pure functions.

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "addon" / "daily_ai_reading_reinforcement"))

from core.config import PROVIDER_PROFILES, DEFAULT_CONFIG
from core.utils import (
    card_id_set,
    clamp_word_count,
    clean_base_url,
    clean_max_tokens,
    clean_max_words,
    clean_provider_id,
    clean_temperature,
    clean_text,
    slugify,
    word_range_bounds,
)


class TestCleanText(unittest.TestCase):

    def test_normal_text(self):
        self.assertEqual(clean_text("  Hello world  "), "Hello world")

    def test_html_tags(self):
        self.assertEqual(clean_text("<p>Hello <b>world</b></p>"), "Hello world")

    def test_html_entities(self):
        self.assertEqual(clean_text("AT&amp;T &amp; T"), "AT&T & T")

    def test_multiple_spaces(self):
        self.assertEqual(clean_text("a   b\n\tc"), "a b c")

    def test_empty_string(self):
        self.assertEqual(clean_text(""), "")

    def test_none(self):
        self.assertEqual(clean_text(None), "")

    def test_zero(self):
        self.assertEqual(clean_text(0), "")

    def test_int_value(self):
        self.assertEqual(clean_text(42), "42")

    def test_bool(self):
        self.assertEqual(clean_text(True), "True")


class TestCleanBaseUrl(unittest.TestCase):

    def test_normal_url(self):
        self.assertEqual(clean_base_url("https://api.example.com/v1"), "https://api.example.com/v1")

    def test_trailing_slash(self):
        self.assertEqual(clean_base_url("https://api.example.com/v1/"), "https://api.example.com/v1")

    def test_multiple_trailing_slashes(self):
        self.assertEqual(clean_base_url("https://api.example.com///"), "https://api.example.com")

    def test_empty(self):
        self.assertEqual(clean_base_url(""), "")

    def test_none(self):
        self.assertEqual(clean_base_url(None), "")

    def test_whitespace_only(self):
        self.assertEqual(clean_base_url("   "), "")

    def test_no_slash_to_strip(self):
        self.assertEqual(clean_base_url("http://localhost:8080"), "http://localhost:8080")

    def test_allows_loopback_ip_http(self):
        self.assertEqual(clean_base_url("http://127.0.0.1:8080/v1"), "http://127.0.0.1:8080/v1")

    def test_rejects_remote_http(self):
        with self.assertRaisesRegex(ValueError, "loopback"):
            clean_base_url("http://api.example.com/v1")

    def test_rejects_embedded_credentials(self):
        with self.assertRaisesRegex(ValueError, "embedded credentials"):
            clean_base_url("https://user:secret@api.example.com/v1")

    def test_rejects_non_http_scheme(self):
        with self.assertRaisesRegex(ValueError, "must use HTTPS"):
            clean_base_url("file:///tmp/api")

    def test_rejects_query_and_fragment(self):
        for url in ("https://api.example.com/v1?token=x", "https://api.example.com/v1#section"):
            with self.subTest(url=url), self.assertRaisesRegex(ValueError, "query string or fragment"):
                clean_base_url(url)


class TestSlugify(unittest.TestCase):

    def test_normal(self):
        self.assertEqual(slugify("My Deck Name!"), "My-Deck-Name")

    def test_chinese(self):
        self.assertEqual(slugify("我的牌组"), "deck")

    def test_mixed(self):
        self.assertEqual(slugify("Deck-123_test"), "Deck-123_test")

    def test_only_special_chars(self):
        self.assertEqual(slugify("!!!@@@###"), "deck")

    def test_empty_string(self):
        self.assertEqual(slugify(""), "deck")

    def test_long_string(self):
        long_name = "a" * 120
        self.assertEqual(slugify(long_name), "a" * 80)

    def test_strips_leading_dashes(self):
        self.assertEqual(slugify("--hello--"), "hello")


class TestClampWordCount(unittest.TestCase):

    def test_normal(self):
        self.assertEqual(clamp_word_count(300), 300)

    def test_below_minimum(self):
        self.assertEqual(clamp_word_count(10), 50)

    def test_at_minimum(self):
        self.assertEqual(clamp_word_count(50), 50)

    def test_above_maximum(self):
        self.assertEqual(clamp_word_count(20000), 10000)

    def test_at_maximum(self):
        self.assertEqual(clamp_word_count(10000), 10000)

    def test_zero(self):
        self.assertEqual(clamp_word_count(0), 50)

    def test_negative(self):
        self.assertEqual(clamp_word_count(-100), 50)

    def test_float(self):
        self.assertEqual(clamp_word_count(300.9), 300)


class TestCleanMaxWords(unittest.TestCase):

    def test_single_number(self):
        self.assertEqual(clean_max_words("300"), "300")

    def test_range(self):
        self.assertEqual(clean_max_words("200-400"), "200-400")

    def test_range_reverse(self):
        self.assertEqual(clean_max_words("400-200"), "200-400")

    def test_equal_range(self):
        self.assertEqual(clean_max_words("300-300"), "300")

    def test_html_text(self):
        self.assertEqual(clean_max_words("<b>300-500</b>"), "300-500")

    def test_empty(self):
        self.assertEqual(clean_max_words(""), "")

    def test_none(self):
        self.assertEqual(clean_max_words(None), "")

    def test_no_numbers(self):
        self.assertEqual(clean_max_words("hello world"), "")

    def test_clamped_low(self):
        self.assertEqual(clean_max_words("10"), "50")

    def test_clamped_high(self):
        self.assertEqual(clean_max_words("20000"), "10000")

    def test_range_with_clamping(self):
        self.assertEqual(clean_max_words("5-20000"), "50-10000")


class TestWordRangeBounds(unittest.TestCase):

    def test_single(self):
        self.assertEqual(word_range_bounds("300"), (300, 300))

    def test_range(self):
        self.assertEqual(word_range_bounds("200-400"), (200, 400))

    def test_range_reverse(self):
        self.assertEqual(word_range_bounds("400-200"), (200, 400))

    def test_empty(self):
        self.assertIsNone(word_range_bounds(""))

    def test_none(self):
        self.assertIsNone(word_range_bounds(None))

    def test_no_numbers(self):
        self.assertIsNone(word_range_bounds("hello"))

    def test_clamped(self):
        self.assertEqual(word_range_bounds("5"), (50, 50))


class TestCardIdSet(unittest.TestCase):

    def test_list_of_ints(self):
        self.assertEqual(card_id_set([1, 2, 3]), {1, 2, 3})

    def test_list_of_strings(self):
        self.assertEqual(card_id_set(["1", "2", "3"]), {1, 2, 3})

    def test_mixed_valid_invalid(self):
        self.assertEqual(card_id_set([1, "x", "3"]), {1, 3})

    def test_empty_list(self):
        self.assertEqual(card_id_set([]), set())

    def test_none(self):
        self.assertEqual(card_id_set(None), set())

    def test_dict(self):
        self.assertEqual(card_id_set({"a": 1}), set())

    def test_string(self):
        self.assertEqual(card_id_set("123"), set())

    def test_floats(self):
        self.assertEqual(card_id_set([1.0, 2.5]), {1, 2})


class TestCleanProviderId(unittest.TestCase):

    def test_known_provider(self):
        self.assertEqual(clean_provider_id("openai"), "openai")

    def test_another_known_provider(self):
        self.assertEqual(clean_provider_id("deepseek"), "deepseek")

    def test_custom_provider(self):
        self.assertEqual(clean_provider_id("custom"), "custom")

    def test_unknown(self):
        self.assertEqual(clean_provider_id("garbage"), "custom")

    def test_empty(self):
        self.assertEqual(clean_provider_id(""), "custom")

    def test_none(self):
        self.assertEqual(clean_provider_id(None), "custom")

    def test_whitespace_padded(self):
        self.assertEqual(clean_provider_id("  openai  "), "openai")


class TestCleanTemperature(unittest.TestCase):

    def test_normal(self):
        self.assertAlmostEqual(clean_temperature(0.7), 0.7)

    def test_int(self):
        self.assertAlmostEqual(clean_temperature(1), 1.0)

    def test_string_number(self):
        self.assertAlmostEqual(clean_temperature("0.5"), 0.5)

    def test_below_zero(self):
        self.assertAlmostEqual(clean_temperature(-1.0), 0.0)

    def test_above_two(self):
        self.assertAlmostEqual(clean_temperature(3.0), 2.0)

    def test_at_zero(self):
        self.assertAlmostEqual(clean_temperature(0.0), 0.0)

    def test_at_two(self):
        self.assertAlmostEqual(clean_temperature(2.0), 2.0)

    def test_invalid_falls_back(self):
        default = float(DEFAULT_CONFIG["temperature"])
        self.assertAlmostEqual(clean_temperature("garbage"), default)

    def test_none_falls_back(self):
        default = float(DEFAULT_CONFIG["temperature"])
        self.assertAlmostEqual(clean_temperature(None), default)

    def test_empty_string(self):
        default = float(DEFAULT_CONFIG["temperature"])
        self.assertAlmostEqual(clean_temperature(""), default)


class TestCleanMaxTokens(unittest.TestCase):

    def test_normal(self):
        self.assertEqual(clean_max_tokens(2048), 2048)

    def test_below_minimum(self):
        self.assertEqual(clean_max_tokens(50), 128)

    def test_at_minimum(self):
        self.assertEqual(clean_max_tokens(128), 128)

    def test_above_maximum(self):
        self.assertEqual(clean_max_tokens(100000), 32000)

    def test_at_maximum(self):
        self.assertEqual(clean_max_tokens(32000), 32000)

    def test_string_number(self):
        self.assertEqual(clean_max_tokens("4096"), 4096)

    def test_float_string(self):
        self.assertEqual(clean_max_tokens("2048.7"), 2048)

    def test_invalid_falls_back(self):
        default = int(DEFAULT_CONFIG["max_tokens"])
        self.assertEqual(clean_max_tokens("garbage"), default)

    def test_none_falls_back(self):
        default = int(DEFAULT_CONFIG["max_tokens"])
        self.assertEqual(clean_max_tokens(None), default)

    def test_empty_string_falls_back(self):
        default = int(DEFAULT_CONFIG["max_tokens"])
        self.assertEqual(clean_max_tokens(""), default)


if __name__ == "__main__":
    unittest.main()
