"""Regression checks for shared-web card selection interactions."""

from __future__ import annotations

import unittest
from pathlib import Path


APP_JS = Path(__file__).parents[1] / "addon" / "daily_ai_reading_reinforcement" / "web" / "app.js"


class WebCardInteractionTests(unittest.TestCase):
    def test_card_body_click_does_not_toggle_label_checkbox_twice(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        self.assertIn('el.cardList.addEventListener("click", (e) => {', source)
        self.assertIn('e.target.closest(".card-item")', source)
        self.assertIn("e.preventDefault();", source)

    def test_vague_tag_uses_the_complete_response_grade_set(self) -> None:
        source = APP_JS.read_text(encoding="utf-8")
        self.assertIn('const isVague = f === "VAGUE" || grades.includes(2);', source)


if __name__ == "__main__":
    unittest.main()
