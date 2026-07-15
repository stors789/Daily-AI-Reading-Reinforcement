from __future__ import annotations

import dataclasses
import sys
import unittest
from pathlib import Path


CORE_SRC = Path(__file__).resolve().parent.parent / "packages" / "dairr_core" / "src"
if str(CORE_SRC) not in sys.path:
    sys.path.insert(0, str(CORE_SRC))

from dairr_core.scoring import Normalization, ScoreResult, SelectionDefaults
from dairr_core.study_signals import CardIdentity, CardStudySignals
from dairr_core.target_selection import (
    ManualOverride,
    TargetCategory,
    select_targets,
)


def score(card_id: str, value: float) -> ScoreResult:
    card = CardStudySignals(CardIdentity("anki", card_id, card_id), f"term-{card_id}")
    return ScoreResult(card, value, value, Normalization.NONE, ())


class TargetSelectionTests(unittest.TestCase):
    def test_threshold_limit_and_categories_are_applied_by_rank(self) -> None:
        scores = [score("1", 50), score("2", 40), score("3", 30), score("4", 5)]
        policy = SelectionDefaults(10, 3, 1, 1, 1)
        selection = select_targets(scores, policy)
        self.assertEqual(
            [item.category for item in selection.assignments],
            [TargetCategory.REQUIRED, TargetCategory.PREFERRED, TargetCategory.OPTIONAL, TargetCategory.EXCLUDED],
        )
        self.assertIn("minimum inclusion", selection.assignments[-1].explanation)

    def test_manual_include_bypasses_threshold_and_manual_exclude_wins(self) -> None:
        scores = [score("1", 100), score("2", -10)]
        policy = SelectionDefaults(20, 1, 1, 0, 0)
        selection = select_targets(
            scores,
            policy,
            [
                ManualOverride("anki:1", TargetCategory.EXCLUDED),
                ManualOverride("anki:2", TargetCategory.REQUIRED),
            ],
        )
        by_id = {item.card_id: item for item in selection.assignments}
        self.assertFalse(by_id["anki:1"].selected)
        self.assertTrue(by_id["anki:2"].selected)
        self.assertTrue(by_id["anki:2"].manually_set)
        payload = selection.to_dict()
        self.assertEqual(payload["assignments"][0]["score"]["normalization"], "none")

    def test_manual_inclusions_are_not_silently_dropped_by_limit(self) -> None:
        scores = [score("1", 3), score("2", 2)]
        policy = SelectionDefaults(0, 1, 1, 0, 0)
        selection = select_targets(
            scores,
            policy,
            [
                ManualOverride("anki:1", TargetCategory.REQUIRED),
                ManualOverride("anki:2", TargetCategory.PREFERRED),
            ],
        )
        self.assertEqual(len(selection.selected), 2)
        self.assertTrue(selection.limit_exceeded_by_manual)

    def test_explicit_order_edits_final_target_order(self) -> None:
        scores = [score("1", 100), score("2", 50), score("3", 20)]
        policy = SelectionDefaults(0, 3, 1, 1, 1)
        selection = select_targets(scores, policy, explicit_order=["anki:3", "anki:1"])
        self.assertEqual([item.card_id for item in selection.assignments], ["anki:3", "anki:1", "anki:2"])
        self.assertEqual(selection.assignments[0].category, TargetCategory.REQUIRED)

    def test_overrides_serialize_safely_and_unknown_ids_fail(self) -> None:
        override = ManualOverride("anki:1", TargetCategory.OPTIONAL)
        self.assertEqual(ManualOverride.from_dict(override.to_dict()), override)
        with self.assertRaises(ValueError):
            select_targets([score("1", 10)], SelectionDefaults(), [ManualOverride("anki:missing", TargetCategory.REQUIRED)])
        with self.assertRaises(ValueError):
            select_targets([score("1", 10)], SelectionDefaults(), explicit_order=["anki:1", "anki:1"])

    def test_duplicate_scored_card_ids_are_rejected(self) -> None:
        first = score("1", 10)
        with self.assertRaises(ValueError):
            select_targets([first, dataclasses.replace(first, total=11)], SelectionDefaults())


if __name__ == "__main__":
    unittest.main()
