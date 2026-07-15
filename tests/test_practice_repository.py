from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent.parent
CORE_SRC = ROOT / "packages" / "dairr_core" / "src"
if str(CORE_SRC) not in sys.path:
    sys.path.insert(0, str(CORE_SRC))

from dairr_core.practice import ArticleReference, create_article_session, create_pasted_session, new_review
from dairr_core.practice_repository import (
    CURRENT_SCHEMA_VERSION,
    CorruptPracticeRecord,
    InvalidPracticeId,
    PracticeRepository,
    UnsupportedPracticeSchema,
    session_document,
    session_from_document,
)


class PracticeRepositoryTests(unittest.TestCase):
    def test_round_trip_preserves_attempt_review_drafts_and_unknown_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = PracticeRepository(Path(directory) / "practice_sessions")
            session = create_pasted_session("Private diary text.", "en", "ja")
            session.unknown_fields["future_session_field"] = {"keep": True}
            session.envelope_unknown_fields["future_envelope_field"] = [1, 2]
            session.segments[0].unknown_fields["future_segment_field"] = "keep"
            session = session.save_draft("下書き", session.segments[0].id)
            session, attempt = session.submit("翻訳", segment_id=session.segments[0].id)
            review = new_review({"meaning": "Good"}, suggested_translation="改善案")
            review.unknown_fields["future_review_field"] = 7
            session = session.attach_review(attempt.id, review)

            path = repository.autosave(session)
            loaded = repository.load(session.id)

            self.assertEqual(path.parent.name, "practice_sessions")
            self.assertEqual(loaded.segment_drafts, session.segment_drafts)
            self.assertEqual(loaded.attempts[0].review.suggested_translation, "改善案")
            self.assertEqual(loaded.unknown_fields["future_session_field"], {"keep": True})
            self.assertEqual(loaded.envelope_unknown_fields["future_envelope_field"], [1, 2])
            self.assertEqual(loaded.segments[0].unknown_fields["future_segment_field"], "keep")
            self.assertEqual(loaded.attempts[0].review.unknown_fields["future_review_field"], 7)
            self.assertEqual(json.loads(path.read_text())["schema_version"], CURRENT_SCHEMA_VERSION)

    def test_article_record_keeps_relative_reference_and_snapshots(self) -> None:
        session = create_article_session(
            "English source", "en", "ja",
            ArticleReference("deck/day/article.md", "Title", "source fallback", "reference fallback"),
            reference_paragraphs=["参照"],
        )
        restored = session_from_document(session_document(session))
        self.assertEqual(restored.article_reference.relative_path, "deck/day/article.md")
        self.assertEqual(restored.article_reference.reference_snapshot, "reference fallback")

    def test_legacy_flat_and_v1_envelope_migrate_non_destructively(self) -> None:
        session = create_pasted_session("Legacy", "en", "zh")
        current = session_document(session)["session"]
        flat = dict(current)
        flat["instructions"] = "legacy review instruction"
        flat.pop("custom_review_instructions")
        flat["draft"] = "legacy draft"
        flat.pop("complete_text_draft")
        flat["future"] = "preserve"
        migrated_flat = session_from_document(flat)
        self.assertEqual(migrated_flat.custom_review_instructions, "legacy review instruction")
        self.assertEqual(migrated_flat.complete_text_draft, "legacy draft")
        self.assertEqual(migrated_flat.unknown_fields["future"], "preserve")

        migrated_v1 = session_from_document({
            "version": 1, "record_type": "legacy", "data": current, "future_envelope": 9,
        })
        self.assertEqual(migrated_v1.id, session.id)
        self.assertEqual(migrated_v1.envelope_unknown_fields["future_envelope"], 9)

    def test_corrupt_optional_fields_are_tolerated_and_preserved(self) -> None:
        session = create_pasted_session("Recoverable private text", "en", "ja")
        document = session_document(session)
        data = document["session"]
        data["proficiency_level"] = {"bad": "optional type"}
        data["attempts"] = ["bad attempt", {"id": "missing translation"}]
        data["segment_drafts"] = {session.segments[0].id: "valid", "unknown": 3}
        restored = session_from_document(document)
        self.assertIsNone(restored.proficiency_level)
        self.assertEqual(restored.attempts, ())
        self.assertEqual(restored.segment_drafts, {session.segments[0].id: "valid"})
        reserialized = session_document(restored)
        self.assertEqual(len(reserialized["session"]["attempts"]), 2)

    def test_required_corruption_and_newer_schema_fail_safely(self) -> None:
        with self.assertRaises(CorruptPracticeRecord):
            session_from_document({"schema_version": 2, "session": {"id": "only-id"}})
        with self.assertRaises(UnsupportedPracticeSchema):
            session_from_document({"schema_version": CURRENT_SCHEMA_VERSION + 1, "session": {}})

    def test_path_traversal_is_rejected_for_all_record_operations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = PracticeRepository(directory)
            for operation in (repository.load, repository.delete):
                with self.subTest(operation=operation.__name__):
                    with self.assertRaises(InvalidPracticeId):
                        operation("../outside")

    def test_load_and_delete_reject_symbolic_link_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "records"
            root.mkdir()
            outside = Path(directory) / "outside.json"
            outside.write_text("{}")
            link = root / "linked.json"
            try:
                link.symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("symbolic links are unavailable")
            repository = PracticeRepository(root)
            with self.assertRaises(InvalidPracticeId):
                repository.load("linked")
            with self.assertRaises(InvalidPracticeId):
                repository.delete("linked")

    def test_failed_atomic_replace_keeps_previous_record_and_removes_temp(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "practice_sessions"
            repository = PracticeRepository(root)
            session = create_pasted_session("Original", "en", "ja")
            path = repository.save(session)
            original = path.read_bytes()
            changed = session.save_draft("unsaved replacement")

            with patch("dairr_core.practice_repository.os.replace", side_effect=OSError("disk failure")):
                with self.assertRaises(OSError):
                    repository.save(changed)

            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(list(root.glob("*.tmp")), [])

    def test_load_rejects_filename_record_id_mismatch_and_malformed_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = PracticeRepository(root)
            session = create_pasted_session("Text", "en", "ja")
            (root / "different.json").write_text(json.dumps(session_document(session)))
            with self.assertRaises(CorruptPracticeRecord):
                repository.load("different")
            (root / "broken.json").write_text("{not json")
            with self.assertRaises(CorruptPracticeRecord):
                repository.load("broken")


if __name__ == "__main__":
    unittest.main()
