from __future__ import annotations

import sys
import unittest
from pathlib import Path


CORE_SRC = Path(__file__).resolve().parent.parent / "packages" / "dairr_core" / "src"
if str(CORE_SRC) not in sys.path:
    sys.path.insert(0, str(CORE_SRC))

from dairr_core.capabilities import CapabilityReason, Provenance
from dairr_core.study_signals import (
    CardIdentity,
    CardStudySignals,
    Observation,
    ReviewEvent,
    ReviewGrade,
    SchedulingSignals,
)


class StudySignalTests(unittest.TestCase):
    def test_card_and_note_identity_remain_distinct(self) -> None:
        first = CardIdentity("anki", "101", "10")
        sibling = CardIdentity("anki", "102", "10")
        self.assertNotEqual(first.stable_id, sibling.stable_id)
        self.assertEqual(first.note_id, sibling.note_id)

    def test_source_scoped_identity_escapes_ambiguous_colons(self) -> None:
        self.assertNotEqual(
            CardIdentity("a:b", "c", "").stable_id,
            CardIdentity("a", "b:c", "").stable_id,
        )

    def test_unavailable_value_cannot_fabricate_zero(self) -> None:
        missing = Observation.unavailable(
            CapabilityReason.UNSUPPORTED_ACTION,
            Provenance.ANKICONNECT_STANDARD,
        )
        self.assertFalse(missing.is_available)
        self.assertIsNone(missing.value)
        with self.assertRaises(ValueError):
            Observation.available(None, Provenance.ANKICONNECT_STANDARD)

    def test_review_events_are_ordered_and_can_retain_repeated_grades(self) -> None:
        reviews = Observation.available(
            (
                ReviewEvent(ReviewGrade.AGAIN, 0, 1000),
                ReviewEvent(ReviewGrade.AGAIN, 1, 2000),
                ReviewEvent(ReviewGrade.GOOD, 2, 3000),
            ),
            Provenance.ANKI_INTERNAL,
        )
        card = CardStudySignals(CardIdentity("anki", "1", "2"), "term", reviews=reviews)
        self.assertEqual([event.grade for event in card.reviews.value], [1, 1, 3])

    def test_unordered_or_duplicate_review_sequences_are_rejected(self) -> None:
        for events in (
            (ReviewEvent(ReviewGrade.GOOD, 1), ReviewEvent(ReviewGrade.AGAIN, 0)),
            (ReviewEvent(ReviewGrade.GOOD, 0), ReviewEvent(ReviewGrade.AGAIN, 0)),
        ):
            with self.subTest(events=events), self.assertRaises(ValueError):
                CardStudySignals(
                    CardIdentity("anki", "1", "2"),
                    "term",
                    reviews=Observation.available(events, Provenance.ANKI_INTERNAL),
                )

    def test_fsrs_ranges_are_validated_but_absence_is_allowed(self) -> None:
        SchedulingSignals(
            retrievability=Observation.unavailable(
                CapabilityReason.FSRS_NOT_AVAILABLE,
                Provenance.ANKICONNECT_STANDARD,
            )
        )
        with self.assertRaises(ValueError):
            SchedulingSignals(
                retrievability=Observation.available(1.1, Provenance.ANKI_INTERNAL)
            )

    def test_target_key_normalizes_equivalent_surface_whitespace_and_case(self) -> None:
        card = CardStudySignals(
            CardIdentity("anki", "1", "2"),
            "Fallback",
            normalized_target="  Take   PART ",
        )
        self.assertEqual(card.target_key, "take part")


if __name__ == "__main__":
    unittest.main()
