"""Application service for article and pasted-text translation practice."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol

from .operations import (
    CompletionTransport,
    ModelRequestSettings,
    ModelResponse,
    OperationContext,
    OperationError,
    run_completion,
)
from .practice import (
    ArticleReference,
    PracticeAttempt,
    PracticeSegment,
    PracticeSession,
    TranslationDirection,
    create_article_session,
    create_pasted_session,
    new_review,
)
from .prompt_templates import PromptRegistry, RenderedPrompt
from .provider_capabilities import ProviderCapabilities
from .provider_requests import BuiltProviderRequest
from .segmentation import (
    SegmentationLimits,
    merge_segments,
    reorder_segments,
    split_segment,
    update_segment,
)
from .translation_review import (
    TranslationReviewRequest,
    TranslationReviewResult,
    parse_translation_review,
    render_translation_review_prompt,
)


class SessionRepository(Protocol):
    def save(self, session: PracticeSession): ...
    def load(self, session_id: str) -> PracticeSession: ...


@dataclass(frozen=True, slots=True)
class PreparedReview:
    session: PracticeSession
    attempt: PracticeAttempt
    prompt: RenderedPrompt
    provider_request: BuiltProviderRequest
    operation_id: str


@dataclass(frozen=True, slots=True)
class CompletedReview:
    session: PracticeSession
    attempt_id: str
    result: TranslationReviewResult


class PracticeService:
    """Coordinates immutable domain changes and optional atomic persistence.

    The service performs no Anki access and no UI scheduling.  A host may omit
    the repository for an entirely in-memory session, which is why pasted-text
    practice remains functional when Anki and AnkiConnect are unavailable.
    """

    def __init__(
        self,
        repository: SessionRepository | None = None,
        *,
        segmentation_limits: SegmentationLimits | None = None,
    ) -> None:
        self.repository = repository
        self.segmentation_limits = segmentation_limits or SegmentationLimits()

    def create_pasted(
        self,
        source_text: str,
        source_language: str,
        target_language: str,
        *,
        direction: TranslationDirection = TranslationDirection.SOURCE_TO_TARGET,
        proficiency_level: str | None = None,
        custom_review_instructions: str = "",
        save: bool = False,
    ) -> PracticeSession:
        session = create_pasted_session(
            source_text,
            source_language,
            target_language,
            direction=direction,
            proficiency_level=proficiency_level,
            custom_review_instructions=custom_review_instructions,
            limits=self.segmentation_limits,
        )
        return self.save_session(session) if save else session

    def create_from_article(
        self,
        source_text: str,
        source_language: str,
        target_language: str,
        article_reference: ArticleReference,
        *,
        reference_paragraphs: Iterable[str | None] | None = None,
        direction: TranslationDirection = TranslationDirection.BACK_TRANSLATION,
        proficiency_level: str | None = None,
        custom_review_instructions: str = "",
        save: bool = False,
    ) -> PracticeSession:
        session = create_article_session(
            source_text,
            source_language,
            target_language,
            article_reference,
            reference_paragraphs=reference_paragraphs,
            direction=direction,
            proficiency_level=proficiency_level,
            custom_review_instructions=custom_review_instructions,
            limits=self.segmentation_limits,
        )
        return self.save_session(session) if save else session

    def save_session(self, session: PracticeSession) -> PracticeSession:
        session.validate()
        if self.repository is None:
            raise OperationError(
                "practice_storage_unavailable",
                "Practice storage is unavailable, but the current session can remain open.",
            )
        try:
            self.repository.save(session)
        except OperationError:
            raise
        except Exception as exc:
            raise OperationError(
                "practice_save_failed",
                "The practice session could not be saved. Keep this workspace open and try again.",
                retryable=True,
            ) from exc
        return session

    def load_session(self, session_id: str) -> PracticeSession:
        if self.repository is None:
            raise OperationError("practice_storage_unavailable", "Practice storage is unavailable.")
        try:
            return self.repository.load(session_id)
        except FileNotFoundError as exc:
            raise OperationError("practice_not_found", "The saved practice session was not found.") from exc
        except OperationError:
            raise
        except Exception as exc:
            raise OperationError(
                "practice_load_failed",
                "The saved practice session could not be opened.",
            ) from exc

    def save_draft(
        self,
        session: PracticeSession,
        translation: str,
        *,
        segment_id: str | None = None,
        persist: bool = True,
    ) -> PracticeSession:
        try:
            updated = session.save_draft(translation, segment_id)
        except KeyError as exc:
            raise OperationError("unknown_segment", "The selected practice segment no longer exists.") from exc
        if persist:
            self.save_session(updated)
        return updated

    def update_segment(self, session: PracticeSession, segment_id: str, text: str) -> PracticeSession:
        self._ensure_segmentation_editable(session)
        return session.with_segments(
            update_segment(session.segments, segment_id, text, self.segmentation_limits)
        )

    def split_segment(self, session: PracticeSession, segment_id: str, offset: int) -> PracticeSession:
        self._ensure_segmentation_editable(session)
        return session.with_segments(
            split_segment(session.segments, segment_id, offset, limits=self.segmentation_limits)
        )

    def merge_segments(
        self,
        session: PracticeSession,
        first_id: str,
        second_id: str,
    ) -> PracticeSession:
        self._ensure_segmentation_editable(session)
        return session.with_segments(
            merge_segments(
                session.segments,
                first_id,
                second_id,
                limits=self.segmentation_limits,
            )
        )

    def reorder_segments(
        self,
        session: PracticeSession,
        ordered_ids: Iterable[str],
    ) -> PracticeSession:
        self._ensure_segmentation_editable(session)
        return session.with_segments(reorder_segments(session.segments, ordered_ids))

    def prepare_review(
        self,
        session: PracticeSession,
        translation: str,
        *,
        registry: PromptRegistry,
        provider_capabilities: ProviderCapabilities,
        request_settings: ModelRequestSettings,
        context: OperationContext,
        segment_id: str | None = None,
        revision_of: str | None = None,
        provider_id: str = "",
        profile_id: str = "",
        persist_attempt: bool = False,
    ) -> PreparedReview:
        context.cancellation.raise_if_cancelled()
        if not translation.strip():
            raise OperationError("empty_translation", "Enter a translation before requesting review.")
        if revision_of and revision_of not in {item.id for item in session.attempts}:
            raise OperationError("unknown_revision", "The selected earlier attempt no longer exists.")
        review_request = self._review_request(session, translation, segment_id)
        prompt = render_translation_review_prompt(
            registry,
            review_request,
            provider_id=provider_id,
            profile_id=profile_id,
        )
        provider_request = request_settings.build(provider_capabilities, prompt)
        updated, attempt = session.submit(
            translation,
            segment_id=segment_id,
            revision_of=revision_of,
        )
        if persist_attempt:
            self.save_session(updated)
        context.cancellation.raise_if_cancelled()
        return PreparedReview(updated, attempt, prompt, provider_request, context.operation_id)

    def complete_review(
        self,
        prepared: PreparedReview,
        response: ModelResponse,
        *,
        context: OperationContext,
        persist: bool = False,
    ) -> CompletedReview:
        if prepared.operation_id != context.operation_id:
            raise OperationError("operation_mismatch", "The review response no longer matches this request.")
        context.cancellation.raise_if_cancelled()
        segment = self._attempt_segment(prepared.session, prepared.attempt)
        parsed = parse_translation_review(
            response.content,
            mode=prepared.prompt.response_mode,
            reference_was_provided=bool(segment.reference_text if segment else self._complete_reference(prepared.session)),
            finish_reason=response.finish_reason,
        )
        categories = {
            key: "\n".join(values)
            for key, values in parsed.categories.items()
            if values
        }
        if parsed.plain_text:
            categories["feedback"] = parsed.plain_text
        review = new_review(
            categories,
            summary=parsed.overall,
            suggested_translation=parsed.suggested_revision or None,
            # Persist only contract metadata by default. Exact private messages
            # remain available in PreparedReview for explicit UI preview.
            prompt_snapshot={
                "task": prepared.prompt.task.value,
                "templateVersion": prepared.prompt.template_version,
                "responseMode": prepared.prompt.response_mode.value,
            },
            model_settings=prepared.provider_request.effective_settings.to_safe_dict(),
        )
        updated = prepared.session.attach_review(prepared.attempt.id, review)
        if persist:
            self.save_session(updated)
        context.cancellation.raise_if_cancelled()
        return CompletedReview(updated, prepared.attempt.id, parsed)

    def review(
        self,
        session: PracticeSession,
        translation: str,
        *,
        registry: PromptRegistry,
        provider_capabilities: ProviderCapabilities,
        request_settings: ModelRequestSettings,
        transport: CompletionTransport,
        context: OperationContext,
        segment_id: str | None = None,
        revision_of: str | None = None,
        provider_id: str = "",
        profile_id: str = "",
        persist: bool = False,
    ) -> CompletedReview:
        prepared = self.prepare_review(
            session,
            translation,
            registry=registry,
            provider_capabilities=provider_capabilities,
            request_settings=request_settings,
            context=context,
            segment_id=segment_id,
            revision_of=revision_of,
            provider_id=provider_id,
            profile_id=profile_id,
            persist_attempt=persist,
        )
        response = run_completion(transport, prepared.provider_request, context)
        return self.complete_review(prepared, response, context=context, persist=persist)

    def _review_request(
        self,
        session: PracticeSession,
        translation: str,
        segment_id: str | None,
    ) -> TranslationReviewRequest:
        if segment_id is None:
            source = session.source_text
            reference = self._complete_reference(session)
        else:
            segment = next((item for item in session.segments if item.id == segment_id), None)
            if segment is None:
                raise OperationError("unknown_segment", "The selected practice segment no longer exists.")
            source = segment.source_text
            reference = segment.reference_text
        return TranslationReviewRequest(
            source,
            translation,
            session.source_language,
            session.target_language,
            reference_translation=reference,
            proficiency_level=session.proficiency_level or "",
            custom_instructions=session.custom_review_instructions,
        )

    @staticmethod
    def _complete_reference(session: PracticeSession) -> str | None:
        references = [item.reference_text or "" for item in session.segments]
        return "\n\n".join(references) if any(value.strip() for value in references) else None

    @staticmethod
    def _attempt_segment(
        session: PracticeSession,
        attempt: PracticeAttempt,
    ) -> PracticeSegment | None:
        if len(attempt.segment_ids) != 1:
            return None
        return next((item for item in session.segments if item.id == attempt.segment_ids[0]), None)

    @staticmethod
    def _ensure_segmentation_editable(session: PracticeSession) -> None:
        if session.attempts:
            raise OperationError(
                "segmentation_locked",
                "Source segmentation cannot be changed after review attempts exist. "
                "Start a new session to edit the source.",
            )
