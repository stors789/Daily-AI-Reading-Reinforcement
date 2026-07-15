from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CORE_SRC = ROOT / "packages" / "dairr_core" / "src"
if str(CORE_SRC) not in sys.path:
    sys.path.insert(0, str(CORE_SRC))

from dairr_core.practice import (
    ArticleReference,
    PracticeScope,
    TranslationDirection,
    create_article_session,
    create_pasted_session,
    new_review,
)
from dairr_core.segmentation import (
    SegmentationLimits,
    TextLimitExceeded,
    merge_segments,
    reorder_segments,
    split_segment,
    update_segment,
)


class PracticeDomainTests(unittest.TestCase):
    def test_pasted_workflow_is_platform_independent_and_reference_optional(self) -> None:
        session = create_pasted_session(
            "First paragraph.\n\nSecond paragraph.", "English", "Japanese",
            proficiency_level="N3", custom_review_instructions="Focus on register.",
        )
        self.assertEqual(len(session.segments), 2)
        self.assertIsNone(session.article_reference)
        self.assertTrue(all(segment.reference_text is None for segment in session.segments))

        session = session.save_draft("第一段", session.segments[0].id)
        session, first = session.submit("第一段", segment_id=session.segments[0].id)
        session, revision = session.submit(
            "最初の段落", segment_id=session.segments[0].id, revision_of=first.id,
        )
        feedback = new_review({"meaning": "Accurate", "naturalness": "Prefer 最初."})
        session = session.attach_review(revision.id, feedback)

        self.assertEqual(first.scope, PracticeScope.SEGMENT)
        self.assertEqual(revision.revision_of, first.id)
        self.assertEqual(session.attempts[-1].review.categories["meaning"], "Accurate")
        self.assertIsNotNone(session.last_autosaved_at)

    def test_complete_text_attempt_and_configurable_direction(self) -> None:
        session = create_pasted_session(
            "A whole text.", "English", "Chinese",
            direction=TranslationDirection.BACK_TRANSLATION,
        )
        session, attempt = session.submit("整篇文本。")
        self.assertEqual(attempt.scope, PracticeScope.COMPLETE_TEXT)
        self.assertEqual(attempt.segment_ids, (session.segments[0].id,))

    def test_article_reference_is_relative_and_has_snapshot_fallback(self) -> None:
        reference = ArticleReference(
            "Japanese/2026-07-16/example.md", "Example", "Source snapshot", "Reference snapshot"
        )
        session = create_article_session(
            "Source one.\n\nSource two.", "English", "Japanese", reference,
            reference_paragraphs=["参照一。", "参照二。"],
        )
        self.assertEqual(session.article_reference.source_snapshot, "Source snapshot")
        self.assertEqual(session.segments[1].reference_text, "参照二。")
        with self.assertRaises(ValueError):
            ArticleReference("../../private.txt")
        with self.assertRaises(ValueError):
            ArticleReference("C:/private.txt")

    def test_segmentation_edit_split_merge_and_reorder_keep_stable_ids(self) -> None:
        session = create_pasted_session("Alpha beta.\n\nGamma.", "en", "ja")
        first_id, second_id = (item.id for item in session.segments)
        edited = update_segment(session.segments, first_id, "Alpha revised beta.")
        split = split_segment(edited, first_id, 5, new_id="stable-new-id")
        self.assertEqual([item.id for item in split], [first_id, "stable-new-id", second_id])
        reordered = reorder_segments(split, [second_id, first_id, "stable-new-id"])
        self.assertEqual([item.position for item in reordered], [0, 1, 2])
        merged = merge_segments(reordered, first_id, "stable-new-id", separator=" ")
        self.assertEqual([item.id for item in merged], [second_id, first_id])
        updated_session = session.with_segments(merged)
        self.assertEqual(updated_session.source_text, "Gamma.\n\nAlpha revised beta.")

    def test_long_text_and_manual_edit_limits_never_truncate(self) -> None:
        limits = SegmentationLimits(max_text_characters=5, max_segments=2, max_segment_characters=5)
        with self.assertRaises(TextLimitExceeded) as caught:
            create_pasted_session("123456", "en", "ja", limits=limits)
        self.assertEqual(caught.exception.code, "text_too_long")
        self.assertEqual(caught.exception.actual, 6)

        session = create_pasted_session("12345", "en", "ja")
        with self.assertRaises(TextLimitExceeded) as edited:
            update_segment(session.segments, session.segments[0].id, "123456", limits=limits)
        self.assertEqual(edited.exception.code, "text_too_long")

    def test_invalid_revision_and_segment_are_rejected(self) -> None:
        session = create_pasted_session("Text", "en", "ja")
        with self.assertRaises(KeyError):
            session.submit("Translation", segment_id="missing")
        with self.assertRaises(KeyError):
            session.submit("Translation", revision_of="missing")


if __name__ == "__main__":
    unittest.main()
