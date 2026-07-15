from __future__ import annotations

import re
import unittest
from pathlib import Path


APP_JS = Path(__file__).parents[1] / "addon" / "daily_ai_reading_reinforcement" / "web" / "app.js"


def _translation_keys(source: str, language: str, next_language: str | None) -> set[str]:
    start_match = re.search(rf"^\s+{language}: \{{", source, re.MULTILINE)
    assert start_match is not None
    start = start_match.start()
    if next_language:
        end_match = re.search(rf"^\s+{next_language}: \{{", source[start_match.end():], re.MULTILINE)
        assert end_match is not None
        end = start_match.end() + end_match.start()
    else:
        end = source.index("  };", start)
    block = source[start:end]
    return set(re.findall(r'^\s{6}([A-Za-z][A-Za-z0-9_]*):', block, re.MULTILINE))


class WebI18nTests(unittest.TestCase):
    def test_all_supported_languages_have_identical_translation_keys(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        zh = _translation_keys(source, "zh", "en")
        en = _translation_keys(source, "en", "ja")
        ja = _translation_keys(source, "ja", None)
        self.assertEqual(zh, en)
        self.assertEqual(en, ja)

    def test_api_profile_controls_and_dynamic_messages_use_i18n(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        for key in (
            "apiProfiles",
            "newApiProfile",
            "apiProfileName",
            "apiProfileNamePlaceholder",
        ):
            self.assertIn(f'tr("{key}")', source)
        self.assertIn('setStatus("savingToCard")', source)
        self.assertIn('newApiProfileOption.textContent = tr("newApiProfile")', source)
        self.assertNotIn('state.uiLanguage === "zh" ? "新建配置"', source)
        self.assertNotIn('{ message: "Saving to card..." }', source)

if __name__ == "__main__":
    unittest.main()
