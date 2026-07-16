"""Versioned sibling JSON repository for translation-practice sessions.

Article history remains authoritative and untouched.  Practice records keep a
safe relative article reference plus snapshots, and are written atomically
with restrictive permissions.  This module contains no logging of record data.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Iterable, Mapping

from .practice import (
    ArticleReference,
    PracticeAttempt,
    PracticeKind,
    PracticeScope,
    PracticeSegment,
    PracticeSession,
    PracticeStatus,
    ReviewFeedback,
    TranslationDirection,
    utc_now,
)


CURRENT_SCHEMA_VERSION = 2
RECORD_TYPE = "dairr_practice_session"
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class PracticeRepositoryError(RuntimeError):
    pass


class InvalidPracticeId(PracticeRepositoryError):
    pass


class UnsupportedPracticeSchema(PracticeRepositoryError):
    pass


class CorruptPracticeRecord(PracticeRepositoryError):
    pass


def _safe_id(value: str) -> str:
    if value in {".", ".."} or not SAFE_ID.fullmatch(value):
        raise InvalidPracticeId("practice session id contains unsafe path characters")
    return value


def _string(value: Any, default: str = "") -> str:
    return value if isinstance(value, str) else default


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _enum(enum_type: type, value: Any, default: Any) -> Any:
    try:
        return enum_type(value)
    except (TypeError, ValueError):
        return default


def _unknown(data: Mapping[str, Any], known: Iterable[str]) -> dict[str, Any]:
    known_set = set(known)
    return {key: value for key, value in data.items() if key not in known_set}


def _review_from_json(value: Any) -> ReviewFeedback | None:
    if not isinstance(value, Mapping):
        return None
    data = dict(value)
    review_id = _string(data.get("id"))
    created_at = _string(data.get("created_at"))
    if not review_id or not created_at:
        return None
    categories = {
        str(key): str(item) for key, item in _mapping(data.get("categories")).items()
        if isinstance(key, str) and isinstance(item, str)
    }
    score = data.get("score")
    if not isinstance(score, (int, float)) or isinstance(score, bool):
        score = None
    known = {
        "id", "created_at", "categories", "summary", "suggested_translation",
        "score", "prompt_snapshot", "model_settings",
    }
    return ReviewFeedback(
        review_id, created_at, categories, _string(data.get("summary")),
        _optional_string(data.get("suggested_translation")), score,
        _mapping(data.get("prompt_snapshot")) or None,
        _mapping(data.get("model_settings")) or None,
        _unknown(data, known),
    )


def _attempt_from_json(value: Any) -> PracticeAttempt | None:
    if not isinstance(value, Mapping):
        return None
    data = dict(value)
    attempt_id = _string(data.get("id"))
    translation = _string(data.get("translation"))
    created_at = _string(data.get("created_at"))
    if not attempt_id or not translation.strip() or not created_at:
        return None
    ids = data.get("segment_ids")
    segment_ids = tuple(item for item in ids if isinstance(item, str)) if isinstance(ids, list) else ()
    scope = _enum(PracticeScope, data.get("scope"), PracticeScope.COMPLETE_TEXT)
    known = {
        "id", "scope", "translation", "created_at", "segment_ids", "revision_of", "review",
    }
    unknown = _unknown(data, known)
    if data.get("review") is not None and _review_from_json(data.get("review")) is None:
        unknown["_unparsed_review"] = data.get("review")
    try:
        return PracticeAttempt(
            attempt_id, scope, translation, created_at, segment_ids,
            _optional_string(data.get("revision_of")), _review_from_json(data.get("review")), unknown,
        )
    except ValueError:
        return None


def _segment_from_json(value: Any, fallback_position: int) -> PracticeSegment | None:
    if not isinstance(value, Mapping):
        return None
    data = dict(value)
    segment_id = _string(data.get("id"))
    source_text = _string(data.get("source_text"))
    position = data.get("position", fallback_position)
    if not isinstance(position, int) or isinstance(position, bool):
        position = fallback_position
    if not segment_id or not source_text.strip():
        return None
    known = {"id", "position", "source_text", "reference_text"}
    try:
        return PracticeSegment(
            segment_id, position, source_text, _optional_string(data.get("reference_text")),
            _unknown(data, known),
        )
    except ValueError:
        return None


def _article_reference_from_json(value: Any) -> ArticleReference | None:
    if not isinstance(value, Mapping):
        return None
    data = dict(value)
    known = {"relative_path", "title", "source_snapshot", "reference_snapshot"}
    try:
        return ArticleReference(
            _string(data.get("relative_path")), _string(data.get("title")),
            _string(data.get("source_snapshot")), _optional_string(data.get("reference_snapshot")),
            _unknown(data, known),
        )
    except ValueError:
        return None


def _session_from_json(data: Mapping[str, Any], envelope_unknown: dict[str, Any]) -> PracticeSession:
    raw = dict(data)
    required = ("id", "source_text", "source_language", "target_language")
    if any(not _string(raw.get(key)).strip() for key in required):
        raise CorruptPracticeRecord("practice record is missing required text fields")
    raw_segments = raw.get("segments")
    if not isinstance(raw_segments, list):
        raise CorruptPracticeRecord("practice record has no segment list")
    parsed_segments = [
        segment for index, value in enumerate(raw_segments)
        if (segment := _segment_from_json(value, index)) is not None
    ]
    if not parsed_segments and _string(raw.get("source_text")).strip():
        raise CorruptPracticeRecord("practice record has no usable segments")
    # Positions are derived from array order so a partially corrupt optional
    # position cannot make the entire otherwise recoverable record unreadable.
    segments = tuple(
        PracticeSegment(item.id, index, item.source_text, item.reference_text, item.unknown_fields)
        for index, item in enumerate(parsed_segments)
    )
    raw_attempts = raw.get("attempts")
    parsed_attempts: list[tuple[Any, PracticeAttempt]] = []
    rejected_attempts: list[Any] = []
    if isinstance(raw_attempts, list):
        for value in raw_attempts:
            attempt = _attempt_from_json(value)
            if attempt is None:
                rejected_attempts.append(value)
            else:
                parsed_attempts.append((value, attempt))
    attempts_list: list[PracticeAttempt] = []
    known_attempt_ids: set[str] = set()
    known_segment_ids = {segment.id for segment in segments}
    for raw_attempt, attempt in parsed_attempts:
        if (
            attempt.id in known_attempt_ids
            or not set(attempt.segment_ids).issubset(known_segment_ids)
            or (attempt.revision_of and attempt.revision_of not in known_attempt_ids)
        ):
            # Parsing is not the only rejection stage. Preserve attempts that
            # are individually well-formed but semantically invalid in this
            # session (duplicate IDs, missing segments, or broken revision
            # chains) so a migration round trip is non-destructive.
            rejected_attempts.append(raw_attempt)
            continue
        attempts_list.append(attempt)
        known_attempt_ids.add(attempt.id)
    attempts = tuple(attempts_list)
    article_reference = _article_reference_from_json(raw.get("article_reference"))
    kind = _enum(PracticeKind, raw.get("kind"), PracticeKind.PASTED_TEXT)
    if kind is PracticeKind.ARTICLE and article_reference is None:
        # A corrupt optional article reference should not destroy private
        # practice text; recover it as a standalone pasted-text session.
        kind = PracticeKind.PASTED_TEXT
    if kind is PracticeKind.PASTED_TEXT:
        article_reference = None
    known = {
        "id", "kind", "direction", "source_language", "target_language", "source_text",
        "segments", "created_at", "updated_at", "status", "proficiency_level",
        "custom_review_instructions", "article_reference", "attempts", "segment_drafts",
        "complete_text_draft", "last_autosaved_at",
    }
    unknown = _unknown(raw, known)
    if rejected_attempts:
        unknown["_unparsed_attempts"] = rejected_attempts
    now = utc_now()
    session = PracticeSession(
        id=_safe_id(_string(raw.get("id"))), kind=kind,
        direction=_enum(TranslationDirection, raw.get("direction"), TranslationDirection.SOURCE_TO_TARGET),
        source_language=_string(raw.get("source_language")),
        target_language=_string(raw.get("target_language")),
        source_text=_string(raw.get("source_text")), segments=segments,
        created_at=_string(raw.get("created_at"), now), updated_at=_string(raw.get("updated_at"), now),
        status=_enum(PracticeStatus, raw.get("status"), PracticeStatus.DRAFT),
        proficiency_level=_optional_string(raw.get("proficiency_level")),
        custom_review_instructions=_string(raw.get("custom_review_instructions")),
        article_reference=article_reference, attempts=attempts,
        segment_drafts={
            key: value for key, value in _mapping(raw.get("segment_drafts")).items()
            if isinstance(key, str) and isinstance(value, str) and key in {segment.id for segment in segments}
        },
        complete_text_draft=_string(raw.get("complete_text_draft")),
        last_autosaved_at=_optional_string(raw.get("last_autosaved_at")),
        unknown_fields=unknown, envelope_unknown_fields=envelope_unknown,
    )
    session.validate()
    return session


def _migrate_document(document: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    root = dict(document)
    version = root.get("schema_version", root.get("version", 0))
    if not isinstance(version, int) or isinstance(version, bool):
        version = 0
    if version > CURRENT_SCHEMA_VERSION:
        raise UnsupportedPracticeSchema(f"practice schema {version} is newer than supported schema {CURRENT_SCHEMA_VERSION}")
    if version == 0:
        # Early development records were the session itself, without an envelope.
        session_data = root
        envelope_unknown: dict[str, Any] = {}
    else:
        session_data = root.get("session", root.get("data"))
        if not isinstance(session_data, Mapping):
            raise CorruptPracticeRecord("practice envelope has no session object")
        envelope_unknown = _unknown(root, {"schema_version", "version", "record_type", "session", "data"})
    migrated = dict(session_data)
    if "custom_review_instructions" not in migrated and isinstance(migrated.get("instructions"), str):
        migrated["custom_review_instructions"] = migrated.pop("instructions")
    if "complete_text_draft" not in migrated and isinstance(migrated.get("draft"), str):
        migrated["complete_text_draft"] = migrated.pop("draft")
    return migrated, envelope_unknown


def session_from_document(document: Any) -> PracticeSession:
    if not isinstance(document, Mapping):
        raise CorruptPracticeRecord("practice record root must be an object")
    session_data, envelope_unknown = _migrate_document(document)
    return _session_from_json(session_data, envelope_unknown)


def _merge(known: dict[str, Any], unknown: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(unknown)
    result.update(known)
    return result


def _review_json(review: ReviewFeedback) -> dict[str, Any]:
    return _merge({
        "id": review.id, "created_at": review.created_at, "categories": review.categories,
        "summary": review.summary, "suggested_translation": review.suggested_translation,
        "score": review.score, "prompt_snapshot": review.prompt_snapshot,
        "model_settings": review.model_settings,
    }, review.unknown_fields)


def _attempt_json(attempt: PracticeAttempt) -> dict[str, Any]:
    unknown = dict(attempt.unknown_fields)
    unknown.pop("_unparsed_review", None)
    return _merge({
        "id": attempt.id, "scope": attempt.scope.value, "translation": attempt.translation,
        "created_at": attempt.created_at, "segment_ids": list(attempt.segment_ids),
        "revision_of": attempt.revision_of,
        "review": _review_json(attempt.review) if attempt.review else attempt.unknown_fields.get("_unparsed_review"),
    }, unknown)


def session_document(session: PracticeSession) -> dict[str, Any]:
    session.validate()
    article = None
    if session.article_reference:
        article = _merge({
            "relative_path": session.article_reference.relative_path,
            "title": session.article_reference.title,
            "source_snapshot": session.article_reference.source_snapshot,
            "reference_snapshot": session.article_reference.reference_snapshot,
        }, session.article_reference.unknown_fields)
    unknown = dict(session.unknown_fields)
    rejected_attempts = unknown.pop("_unparsed_attempts", [])
    session_data = _merge({
        "id": session.id, "kind": session.kind.value, "direction": session.direction.value,
        "source_language": session.source_language, "target_language": session.target_language,
        "source_text": session.source_text,
        "segments": [
            _merge({"id": item.id, "position": item.position, "source_text": item.source_text,
                    "reference_text": item.reference_text}, item.unknown_fields)
            for item in session.segments
        ],
        "created_at": session.created_at, "updated_at": session.updated_at,
        "status": session.status.value, "proficiency_level": session.proficiency_level,
        "custom_review_instructions": session.custom_review_instructions,
        "article_reference": article,
        "attempts": [*(_attempt_json(item) for item in session.attempts), *rejected_attempts],
        "segment_drafts": session.segment_drafts,
        "complete_text_draft": session.complete_text_draft,
        "last_autosaved_at": session.last_autosaved_at,
    }, unknown)
    return _merge({
        "schema_version": CURRENT_SCHEMA_VERSION,
        "record_type": RECORD_TYPE,
        "session": session_data,
    }, session.envelope_unknown_fields)


class PracticeRepository:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    def _path(self, session_id: str) -> Path:
        return self.root / f"{_safe_id(session_id)}.json"

    def save(self, session: PracticeSession) -> Path:
        path = self._path(session.id)
        self.root.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(session_document(session), ensure_ascii=False, indent=2) + "\n"
        temporary: Path | None = None
        try:
            descriptor, name = tempfile.mkstemp(prefix=f".{session.id}.", suffix=".tmp", dir=self.root)
            temporary = Path(name)
            try:
                try:
                    os.fchmod(descriptor, 0o600)
                except (AttributeError, OSError):
                    # mkstemp is already private on POSIX. Windows security is
                    # governed by the containing application-data ACL.
                    pass
                with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                    descriptor = -1
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
            finally:
                if descriptor >= 0:
                    os.close(descriptor)
            os.replace(temporary, path)
            temporary = None
            try:
                directory_fd = os.open(self.root, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            except OSError:
                pass
            return path
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def autosave(self, session: PracticeSession) -> Path:
        if session.last_autosaved_at is None:
            session.last_autosaved_at = utc_now()
            session.updated_at = session.last_autosaved_at
        return self.save(session)

    def load(self, session_id: str) -> PracticeSession:
        path = self._path(session_id)
        if path.is_symlink():
            raise InvalidPracticeId("practice session path cannot be a symbolic link")
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise CorruptPracticeRecord("practice record could not be decoded") from exc
        session = session_from_document(document)
        if session.id != session_id:
            raise CorruptPracticeRecord("practice record id does not match its filename")
        return session

    def list_ids(self) -> list[str]:
        if not self.root.exists():
            return []
        return sorted(
            path.stem for path in self.root.glob("*.json")
            if SAFE_ID.fullmatch(path.stem) and path.stem not in {".", ".."}
        )

    def delete(self, session_id: str) -> bool:
        path = self._path(session_id)
        if path.is_symlink():
            raise InvalidPracticeId("practice session path cannot be a symbolic link")
        try:
            path.unlink()
            return True
        except FileNotFoundError:
            return False
