from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


CORE_SRC = Path(__file__).resolve().parent.parent / "packages" / "dairr_core" / "src"
if str(CORE_SRC) not in sys.path:
    sys.path.insert(0, str(CORE_SRC))

from dairr_core.operations import ModelRequestSettings, ModelResponse, OperationContext, OperationError
from dairr_core.practice import ArticleReference
from dairr_core.practice_repository import PracticeRepository
from dairr_core.practice_service import PracticeService
from dairr_core.prompt_templates import PromptTask, default_prompt_registry
from dairr_core.provider_capabilities import known_provider_capabilities


class FakeTransport:
    def __init__(self, response: str):
        self.response = response
        self.requests = []

    def complete(self, request, *, cancellation):
        cancellation.raise_if_cancelled()
        self.requests.append(request)
        return ModelResponse(self.response)


class FailingTransport:
    def complete(self, request, *, cancellation):
        raise RuntimeError("private provider response and secret token")


class PracticeServiceTests(unittest.TestCase):
    def test_pasted_practice_is_usable_entirely_without_storage_or_anki(self) -> None:
        service = PracticeService()
        session = service.create_pasted("First paragraph.\n\nSecond paragraph.", "English", "Japanese")
        self.assertEqual(len(session.segments), 2)
        edited = service.update_segment(session, session.segments[0].id, "Edited first paragraph.")
        split = service.split_segment(edited, edited.segments[1].id, 6)
        self.assertEqual(len(split.segments), 3)
        merged = service.merge_segments(split, split.segments[1].id, split.segments[2].id)
        reordered = service.reorder_segments(merged, reversed([item.id for item in merged.segments]))
        self.assertEqual([item.position for item in reordered.segments], [0, 1])
        draft = service.save_draft(reordered, "下書き", persist=False)
        self.assertEqual(draft.complete_text_draft, "下書き")

    def test_saved_pasted_session_round_trips_through_existing_repository(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = PracticeService(PracticeRepository(directory))
            session = service.create_pasted("private source", "English", "French", save=True)
            draft = service.save_draft(session, "brouillon")
            loaded = service.load_session(session.id)
            self.assertEqual(loaded.complete_text_draft, "brouillon")
            self.assertEqual(draft.id, loaded.id)

    def test_article_segment_review_uses_reference_as_comparison(self) -> None:
        service = PracticeService()
        session = service.create_from_article(
            "Hello world.",
            "English",
            "Japanese",
            ArticleReference("2026/article.md", reference_snapshot="こんにちは世界。"),
            reference_paragraphs=["こんにちは世界。"],
        )
        prepared = service.prepare_review(
            session,
            "世界、こんにちは。",
            segment_id=session.segments[0].id,
            registry=default_prompt_registry(),
            provider_capabilities=known_provider_capabilities("openrouter"),
            request_settings=ModelRequestSettings("model"),
            context=OperationContext(),
        )
        self.assertIs(prepared.prompt.task, PromptTask.BACK_TRANSLATION_REVIEW)
        self.assertEqual(prepared.provider_request.body["messages"], list(prepared.prompt.messages))
        self.assertIn("こんにちは世界。", prepared.prompt.user)

    def test_prepare_submit_and_revision_preserve_attempt_chain(self) -> None:
        service = PracticeService()
        session = service.create_pasted("Hello.", "English", "Spanish")
        first = service.prepare_review(
            session,
            "Hola.",
            registry=default_prompt_registry(),
            provider_capabilities=known_provider_capabilities("custom"),
            request_settings=ModelRequestSettings("model"),
            context=OperationContext(),
        )
        second = service.prepare_review(
            first.session,
            "Hola a todos.",
            revision_of=first.attempt.id,
            registry=default_prompt_registry(),
            provider_capabilities=known_provider_capabilities("custom"),
            request_settings=ModelRequestSettings("model"),
            context=OperationContext(),
        )
        self.assertEqual(second.attempt.revision_of, first.attempt.id)
        self.assertEqual(len(second.session.attempts), 2)
        with self.assertRaises(OperationError) as locked:
            service.update_segment(second.session, second.session.segments[0].id, "Changed source")
        self.assertEqual(locked.exception.code, "segmentation_locked")

    def test_end_to_end_offline_pasted_review_persists_feedback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = PracticeRepository(directory)
            service = PracticeService(repository)
            session = service.create_pasted(
                "I made a decision.",
                "English",
                "Japanese",
                custom_review_instructions="Be concise.",
                save=True,
            )
            transport = FakeTransport(
                '{"meaning":"Accurate","naturalness":["Natural"],'
                '"suggested_revision":"決断しました。","overall":"Good"}'
            )
            completed = service.review(
                session,
                "決断しました。",
                registry=default_prompt_registry(),
                provider_capabilities=known_provider_capabilities("custom"),
                request_settings=ModelRequestSettings("offline-fake"),
                transport=transport,
                context=OperationContext(),
                persist=True,
            )
            loaded = repository.load(session.id)
            self.assertEqual(len(transport.requests), 1)
            self.assertEqual(loaded.attempts[0].review.summary, "Good")
            self.assertEqual(loaded.attempts[0].review.categories["meaning"], "Accurate")
            self.assertNotIn("I made a decision", repr(loaded.attempts[0].review.prompt_snapshot))
            self.assertEqual(completed.result.suggested_revision, "決断しました。")

    def test_stale_operation_response_is_rejected(self) -> None:
        service = PracticeService()
        session = service.create_pasted("Hello.", "English", "Spanish")
        context = OperationContext()
        prepared = service.prepare_review(
            session,
            "Hola.",
            registry=default_prompt_registry(),
            provider_capabilities=known_provider_capabilities("custom"),
            request_settings=ModelRequestSettings("model"),
            context=context,
        )
        with self.assertRaisesRegex(Exception, "no longer matches"):
            service.complete_review(
                prepared,
                ModelResponse('{"overall":"Good"}'),
                context=OperationContext(),
            )

    def test_failed_provider_call_preserves_submitted_attempt_without_leaking_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = PracticeRepository(directory)
            service = PracticeService(repository)
            session = service.create_pasted("private diary", "English", "French", save=True)
            with self.assertRaises(OperationError) as raised:
                service.review(
                    session,
                    "journal prive",
                    registry=default_prompt_registry(),
                    provider_capabilities=known_provider_capabilities("custom"),
                    request_settings=ModelRequestSettings("model"),
                    transport=FailingTransport(),
                    context=OperationContext(),
                    persist=True,
                )
            loaded = repository.load(session.id)
            self.assertEqual(len(loaded.attempts), 1)
            self.assertIsNone(loaded.attempts[0].review)
            self.assertNotIn("private", str(raised.exception))
            self.assertNotIn("secret", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
