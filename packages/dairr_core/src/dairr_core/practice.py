"""Platform-neutral translation-practice domain models."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import PurePosixPath
from typing import Any, Iterable, Mapping
from uuid import uuid4

from .segmentation import SegmentationLimits, paragraph_texts


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def new_id() -> str:
    return uuid4().hex


def validate_relative_reference(value: str) -> str:
    normalized = value.replace("\\", "/").strip()
    path = PurePosixPath(normalized)
    if (
        not normalized
        or path.is_absolute()
        or (path.parts and ":" in path.parts[0])
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError("article reference must be a safe relative path")
    return path.as_posix()


class PracticeKind(str, Enum):
    PASTED_TEXT = "pasted_text"
    ARTICLE = "article"


class TranslationDirection(str, Enum):
    SOURCE_TO_TARGET = "source_to_target"
    BACK_TRANSLATION = "back_translation"


class PracticeScope(str, Enum):
    SEGMENT = "segment"
    COMPLETE_TEXT = "complete_text"


class PracticeStatus(str, Enum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ARCHIVED = "archived"


@dataclass(slots=True)
class ArticleReference:
    relative_path: str
    title: str = ""
    source_snapshot: str = ""
    reference_snapshot: str | None = None
    unknown_fields: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.relative_path = validate_relative_reference(self.relative_path)


@dataclass(slots=True)
class PracticeSegment:
    id: str
    position: int
    source_text: str
    reference_text: str | None = None
    unknown_fields: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.id = self.id.strip()
        self.source_text = self.source_text.strip()
        if not self.id or not self.source_text or self.position < 0:
            raise ValueError("segment id, source text, and non-negative position are required")


@dataclass(slots=True)
class ReviewFeedback:
    id: str
    created_at: str
    categories: dict[str, str] = field(default_factory=dict)
    summary: str = ""
    suggested_translation: str | None = None
    score: float | None = None
    prompt_snapshot: dict[str, Any] | None = None
    model_settings: dict[str, Any] | None = None
    unknown_fields: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PracticeAttempt:
    id: str
    scope: PracticeScope
    translation: str
    created_at: str
    segment_ids: tuple[str, ...] = ()
    revision_of: str | None = None
    review: ReviewFeedback | None = None
    unknown_fields: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.translation.strip():
            raise ValueError("attempt id and translation are required")
        if self.scope is PracticeScope.SEGMENT and len(self.segment_ids) != 1:
            raise ValueError("a segment attempt must identify exactly one segment")


@dataclass(slots=True)
class PracticeSession:
    id: str
    kind: PracticeKind
    direction: TranslationDirection
    source_language: str
    target_language: str
    source_text: str
    segments: tuple[PracticeSegment, ...]
    created_at: str
    updated_at: str
    status: PracticeStatus = PracticeStatus.DRAFT
    proficiency_level: str | None = None
    custom_review_instructions: str = ""
    article_reference: ArticleReference | None = None
    attempts: tuple[PracticeAttempt, ...] = ()
    segment_drafts: dict[str, str] = field(default_factory=dict)
    complete_text_draft: str = ""
    last_autosaved_at: str | None = None
    unknown_fields: dict[str, Any] = field(default_factory=dict)
    envelope_unknown_fields: dict[str, Any] = field(default_factory=dict, repr=False)

    def validate(self) -> None:
        if not self.id.strip() or not self.source_text.strip():
            raise ValueError("session id and source text are required")
        if not self.source_language.strip() or not self.target_language.strip():
            raise ValueError("source and target languages are required")
        ids = [segment.id for segment in self.segments]
        if len(ids) != len(set(ids)) or [segment.position for segment in self.segments] != list(range(len(ids))):
            raise ValueError("segments require unique ids and contiguous positions")
        if self.kind is PracticeKind.ARTICLE and self.article_reference is None:
            raise ValueError("article practice requires an article reference")
        if self.kind is PracticeKind.PASTED_TEXT and self.article_reference is not None:
            raise ValueError("pasted-text practice cannot have an article reference")
        known_attempts: set[str] = set()
        segment_ids = set(ids)
        for attempt in self.attempts:
            if attempt.id in known_attempts:
                raise ValueError("attempt ids must be unique")
            if not set(attempt.segment_ids).issubset(segment_ids):
                raise ValueError("attempt references an unknown segment")
            if attempt.revision_of and attempt.revision_of not in known_attempts:
                raise ValueError("revision_of must reference an earlier attempt")
            known_attempts.add(attempt.id)

    def with_segments(self, segments: Iterable[PracticeSegment]) -> "PracticeSession":
        values = tuple(segments)
        retained_ids = {segment.id for segment in values}
        updated = replace(
            self,
            segments=values,
            source_text="\n\n".join(segment.source_text for segment in values),
            segment_drafts={
                key: value for key, value in self.segment_drafts.items() if key in retained_ids
            },
            updated_at=utc_now(),
        )
        updated.validate()
        return updated

    def save_draft(self, translation: str, segment_id: str | None = None) -> "PracticeSession":
        now = utc_now()
        if segment_id is None:
            return replace(self, complete_text_draft=translation, updated_at=now, last_autosaved_at=now)
        if segment_id not in {segment.id for segment in self.segments}:
            raise KeyError(segment_id)
        drafts = dict(self.segment_drafts)
        drafts[segment_id] = translation
        return replace(self, segment_drafts=drafts, updated_at=now, last_autosaved_at=now)

    def set_status(self, status: PracticeStatus) -> "PracticeSession":
        return replace(self, status=status, updated_at=utc_now())

    def submit(
        self,
        translation: str,
        *,
        segment_id: str | None = None,
        revision_of: str | None = None,
    ) -> tuple["PracticeSession", PracticeAttempt]:
        scope = PracticeScope.SEGMENT if segment_id else PracticeScope.COMPLETE_TEXT
        segment_ids = (segment_id,) if segment_id else tuple(segment.id for segment in self.segments)
        if segment_id and segment_id not in {segment.id for segment in self.segments}:
            raise KeyError(segment_id)
        if revision_of and revision_of not in {attempt.id for attempt in self.attempts}:
            raise KeyError(revision_of)
        attempt = PracticeAttempt(new_id(), scope, translation, utc_now(), segment_ids, revision_of)
        updated = replace(
            self,
            attempts=(*self.attempts, attempt),
            status=PracticeStatus.IN_PROGRESS,
            updated_at=attempt.created_at,
        )
        updated.validate()
        return updated, attempt

    def attach_review(self, attempt_id: str, review: ReviewFeedback) -> "PracticeSession":
        found = False
        attempts = []
        for attempt in self.attempts:
            if attempt.id == attempt_id:
                attempts.append(replace(attempt, review=review))
                found = True
            else:
                attempts.append(attempt)
        if not found:
            raise KeyError(attempt_id)
        return replace(self, attempts=tuple(attempts), updated_at=utc_now())


def _segments(source_text: str, references: Iterable[str | None] | None, limits: SegmentationLimits) -> tuple[PracticeSegment, ...]:
    texts = paragraph_texts(source_text, limits)
    reference_values = tuple(references or ())
    if reference_values and len(reference_values) != len(texts):
        raise ValueError("reference paragraphs must align with source paragraphs")
    return tuple(
        PracticeSegment(new_id(), index, text, reference_values[index] if reference_values else None)
        for index, text in enumerate(texts)
    )


def create_pasted_session(
    source_text: str,
    source_language: str,
    target_language: str,
    *,
    direction: TranslationDirection = TranslationDirection.SOURCE_TO_TARGET,
    proficiency_level: str | None = None,
    custom_review_instructions: str = "",
    limits: SegmentationLimits | None = None,
) -> PracticeSession:
    limits = limits or SegmentationLimits()
    now = utc_now()
    session = PracticeSession(
        id=new_id(), kind=PracticeKind.PASTED_TEXT, direction=direction,
        source_language=source_language, target_language=target_language,
        source_text=source_text, segments=_segments(source_text, None, limits),
        created_at=now, updated_at=now, proficiency_level=proficiency_level,
        custom_review_instructions=custom_review_instructions,
    )
    session.validate()
    return session


def create_article_session(
    source_text: str,
    source_language: str,
    target_language: str,
    article_reference: ArticleReference,
    *,
    reference_paragraphs: Iterable[str | None] | None = None,
    direction: TranslationDirection = TranslationDirection.BACK_TRANSLATION,
    proficiency_level: str | None = None,
    custom_review_instructions: str = "",
    limits: SegmentationLimits | None = None,
) -> PracticeSession:
    limits = limits or SegmentationLimits()
    now = utc_now()
    session = PracticeSession(
        id=new_id(), kind=PracticeKind.ARTICLE, direction=direction,
        source_language=source_language, target_language=target_language,
        source_text=source_text, segments=_segments(source_text, reference_paragraphs, limits),
        created_at=now, updated_at=now, proficiency_level=proficiency_level,
        custom_review_instructions=custom_review_instructions,
        article_reference=article_reference,
    )
    session.validate()
    return session


def new_review(
    categories: Mapping[str, str], *, summary: str = "", suggested_translation: str | None = None,
    score: float | None = None, prompt_snapshot: dict[str, Any] | None = None,
    model_settings: dict[str, Any] | None = None,
) -> ReviewFeedback:
    return ReviewFeedback(new_id(), utc_now(), dict(categories), summary, suggested_translation, score, prompt_snapshot, model_settings)
