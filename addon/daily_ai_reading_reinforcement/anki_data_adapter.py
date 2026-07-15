"""Lifecycle-safe normalized study adapter for the DAIRR Anki add-on.

Only supported collection/card/note/database APIs are used.  The adapter keeps
no collection, scheduler, card, note, or Qt object after a call returns; a
fresh collection is obtained from the injected getter for every operation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable, Mapping

try:
    from .dairr_core.capabilities import (
        Capability,
        CapabilityId,
        CapabilityReason,
        CapabilitySet,
        CapabilityStatus,
        Provenance,
    )
    from .dairr_core.study_signals import (
        CardIdentity,
        CardState,
        CardStudySignals,
        Observation,
        ReviewEvent,
        ReviewGrade,
        SchedulingSignals,
    )
    from .anki_review_history import fetch_today_review_event_rows
except ImportError:  # source-tree tests and host-managed shared-core install
    from dairr_core.capabilities import (
        Capability,
        CapabilityId,
        CapabilityReason,
        CapabilitySet,
        CapabilityStatus,
        Provenance,
    )
    from dairr_core.study_signals import (
        CardIdentity,
        CardState,
        CardStudySignals,
        Observation,
        ReviewEvent,
        ReviewGrade,
        SchedulingSignals,
    )
    try:
        from anki_review_history import fetch_today_review_event_rows
    except ImportError:
        from .anki_review_history import fetch_today_review_event_rows


SOURCE_ID = "anki-addon"


class AnkiAddonUnavailable(RuntimeError):
    """Safe lifecycle failure for a closed profile or cancelled operation."""

    def __init__(self, reason: CapabilityReason) -> None:
        self.reason = reason
        message = {
            CapabilityReason.PROFILE_CLOSED: (
                "The Anki collection is not available. Open a profile and try again."
            ),
            CapabilityReason.OPERATION_CANCELLED: "The Anki study-data operation was cancelled.",
        }.get(reason, "Anki study data is temporarily unavailable.")
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class _FsrsValues:
    retrievability: float | None = None
    difficulty: float | None = None
    stability_days: float | None = None


class AnkiAddonDataAdapter:
    """Adapt supported Anki collection evidence to ``CardStudySignals``."""

    def __init__(
        self,
        collection_getter: Callable[[], Any | None],
        *,
        cancelled: Callable[[], bool] | None = None,
        fsrs_extractor: Callable[[Any, Any], Mapping[str, Any] | None] | None = None,
    ) -> None:
        self._collection_getter = collection_getter
        self._cancelled = cancelled or (lambda: False)
        self._fsrs_extractor = fsrs_extractor or _supported_fsrs_values
        self._profile_available = True
        self._fsrs_available = False

    def capabilities(self) -> CapabilitySet:
        # Probe lifecycle state without retaining the returned host object.
        try:
            self._profile_available = self._collection_getter() is not None
        except Exception:
            self._profile_available = False
        connection_status = (
            CapabilityStatus.AVAILABLE
            if self._profile_available
            else CapabilityStatus.TEMPORARILY_UNAVAILABLE
        )
        connection_reason = (
            CapabilityReason.NONE
            if self._profile_available
            else CapabilityReason.PROFILE_CLOSED
        )
        return CapabilitySet(
            (
                Capability(
                    CapabilityId.ANKI_CONNECTION,
                    connection_status,
                    connection_reason,
                    Provenance.ANKI_INTERNAL,
                    "The active profile collection is obtained per operation.",
                ),
                Capability(
                    CapabilityId.INTERNAL_ANKI_APIS,
                    connection_status,
                    connection_reason,
                    Provenance.ANKI_INTERNAL,
                    "Supported collection, card, note, scheduler, and database APIs.",
                ),
                Capability(
                    CapabilityId.REVIEW_HISTORY,
                    connection_status,
                    connection_reason,
                    Provenance.ANKI_INTERNAL,
                    "Ordered current-day revlog answers with timestamps and multiplicity.",
                ),
                Capability(
                    CapabilityId.FSRS_VALUES,
                    (
                        CapabilityStatus.TEMPORARILY_UNAVAILABLE
                        if not self._profile_available
                        else (
                            CapabilityStatus.AVAILABLE
                            if self._fsrs_available
                            else CapabilityStatus.DATA_ABSENT
                        )
                    ),
                    (
                        CapabilityReason.PROFILE_CLOSED
                        if not self._profile_available
                        else (
                            CapabilityReason.NONE
                            if self._fsrs_available
                            else CapabilityReason.FSRS_NOT_AVAILABLE
                        )
                    ),
                    Provenance.ANKI_INTERNAL,
                    "FSRS fields are emitted only when the active Anki API exposes valid values.",
                ),
                Capability(
                    CapabilityId.TARGET_CARD_SCORING,
                    connection_status,
                    connection_reason,
                    Provenance.ANKI_INTERNAL,
                    "Scoring remains usable when optional FSRS fields are absent.",
                ),
                Capability(
                    CapabilityId.CANCELLATION,
                    CapabilityStatus.AVAILABLE,
                    CapabilityReason.NONE,
                    Provenance.ANKI_INTERNAL,
                    "Cancellation is checked between collection operations.",
                ),
            )
        )

    def collect_today_signals(
        self, start_ms: int, end_ms: int
    ) -> list[CardStudySignals]:
        if not _valid_bounds(start_ms, end_ms):
            raise ValueError("valid Anki-day bounds are required")
        self._check_cancelled()
        collection = self._collection_getter()
        if collection is None:
            self._profile_available = False
            raise AnkiAddonUnavailable(CapabilityReason.PROFILE_CLOSED)
        self._profile_available = True
        self._fsrs_available = False

        # Keep every host object local. Only immutable scalar/string mappings
        # are copied into the returned domain values.
        rows = fetch_today_review_event_rows(collection.db, start_ms, end_ms)
        self._check_cancelled()
        grouped: dict[int, dict[str, Any]] = {}
        for deck_id, card_id, reviewed_at_ms, ease in rows:
            parsed_card_id = _as_int(card_id)
            parsed_time = _as_int(reviewed_at_ms)
            parsed_ease = _as_int(ease)
            if (
                parsed_card_id is None
                or parsed_time is None
                or parsed_ease not in (1, 2, 3, 4)
            ):
                continue
            item = grouped.setdefault(
                parsed_card_id,
                {"deck_id": _as_int(deck_id), "events": []},
            )
            item["events"].append((parsed_time, ReviewGrade(parsed_ease)))

        signals: list[CardStudySignals] = []
        for card_id, row in grouped.items():
            self._check_cancelled()
            self._ensure_collection_active(collection)
            try:
                card = collection.get_card(card_id)
            except Exception:
                self._ensure_collection_active(collection)
                raise
            if card is None:
                continue
            try:
                note = card.note()
            except Exception:
                self._ensure_collection_active(collection)
                raise
            note_id = _as_int(getattr(note, "id", None))
            fields = _note_fields(note)
            term = _first_value(fields) or f"Card {card_id}"
            ordered = sorted(row["events"], key=lambda value: value[0])
            if len({timestamp for timestamp, _grade in ordered}) != len(ordered):
                # Duplicate revlog IDs should be impossible. If a test double
                # or corrupt collection presents them, omit ambiguous events.
                continue
            events = tuple(
                ReviewEvent(grade, sequence, timestamp)
                for sequence, (timestamp, grade) in enumerate(ordered)
            )
            try:
                raw_fsrs = self._fsrs_extractor(collection, card)
            except Exception:
                # FSRS is optional evidence. Version-specific API absence must
                # never make the otherwise valid card unusable.
                raw_fsrs = None
            fsrs = _coerce_fsrs(raw_fsrs)
            if any(
                value is not None
                for value in (fsrs.retrievability, fsrs.difficulty, fsrs.stability_days)
            ):
                self._fsrs_available = True
            scheduling = SchedulingSignals(
                retrievability=_fsrs_observation(fsrs.retrievability),
                difficulty=_fsrs_observation(fsrs.difficulty),
                stability_days=_fsrs_observation(fsrs.stability_days),
                elapsed_days=_unavailable(CapabilityReason.MISSING_FIELD),
                overdue_days=_overdue_observation(collection, card),
                state=_state_observation(card),
            )
            lapses = _non_negative_int(getattr(card, "lapses", None))
            signals.append(
                CardStudySignals(
                    identity=CardIdentity(SOURCE_ID, str(card_id), str(note_id or "")),
                    term=term,
                    normalized_target=term,
                    reviews=Observation.available(events, Provenance.ANKI_INTERNAL),
                    same_day_attempts=Observation.available(
                        len(events), Provenance.ANKI_INTERNAL
                    ),
                    recent_lapses=Observation.available(
                        sum(event.grade is ReviewGrade.AGAIN for event in events),
                        Provenance.ANKI_INTERNAL,
                    ),
                    historical_lapses=(
                        Observation.available(lapses, Provenance.ANKI_INTERNAL)
                        if lapses is not None
                        else _unavailable(CapabilityReason.MISSING_FIELD)
                    ),
                    scheduling=scheduling,
                    metadata={
                        "deckId": str(row.get("deck_id") or ""),
                        "fields": fields,
                        "lifetimeReps": _non_negative_int(getattr(card, "reps", None)),
                    },
                )
            )
            # Drop references eagerly within long collections. No host object
            # is captured in returned values or adapter state.
            del note, card
        return signals

    def _check_cancelled(self) -> None:
        if self._cancelled():
            raise AnkiAddonUnavailable(CapabilityReason.OPERATION_CANCELLED)

    def _ensure_collection_active(self, expected: Any) -> None:
        try:
            active = self._collection_getter()
        except Exception as exc:
            self._profile_available = False
            raise AnkiAddonUnavailable(CapabilityReason.PROFILE_CLOSED) from exc
        if active is not expected:
            self._profile_available = False
            raise AnkiAddonUnavailable(CapabilityReason.PROFILE_CLOSED)


def _supported_fsrs_values(collection: Any, card: Any) -> Mapping[str, Any] | None:
    """Read public memory-state attributes when available, otherwise omit."""

    state = getattr(card, "memory_state", None)
    if callable(state):
        state = state()
    if state is None:
        compute = getattr(collection, "compute_memory_state", None)
        if callable(compute):
            state = compute(card)
    if state is None:
        return None
    return {
        "retrievability": getattr(state, "retrievability", None),
        "difficulty": getattr(state, "difficulty", None),
        "stability_days": getattr(state, "stability", None),
    }


def _coerce_fsrs(raw: Mapping[str, Any] | None) -> _FsrsValues:
    if not isinstance(raw, Mapping):
        return _FsrsValues()
    retrievability = _bounded_float(raw.get("retrievability"), 0.0, 1.0)
    difficulty = _bounded_float(raw.get("difficulty"), 0.0, 10.0)
    stability = _bounded_float(raw.get("stability_days", raw.get("stability")), 0.0, None)
    return _FsrsValues(retrievability, difficulty, stability)


def _fsrs_observation(value: float | None) -> Observation[float]:
    if value is None:
        return Observation.unavailable(
            CapabilityReason.FSRS_NOT_AVAILABLE, Provenance.ANKI_INTERNAL
        )
    return Observation.available(value, Provenance.ANKI_INTERNAL)


def _unavailable(reason: CapabilityReason) -> Observation[Any]:
    return Observation.unavailable(reason, Provenance.ANKI_INTERNAL)


def _overdue_observation(collection: Any, card: Any) -> Observation[float]:
    card_type = _as_int(getattr(card, "type", None))
    queue = _as_int(getattr(card, "queue", None))
    due = _as_int(getattr(card, "due", None))
    today = _as_int(getattr(getattr(collection, "sched", None), "today", None))
    if card_type != 2 or queue != 2 or due is None or today is None:
        return _unavailable(CapabilityReason.MISSING_FIELD)
    return Observation.available(float(max(0, today - due)), Provenance.ANKI_INTERNAL)


def _state_observation(card: Any) -> Observation[CardState]:
    card_type = _as_int(getattr(card, "type", None))
    queue = _as_int(getattr(card, "queue", None))
    if card_type == 3:
        state = CardState.RELEARNING
    elif card_type == 0 or queue == 0:
        state = CardState.NEW
    elif card_type == 1 or queue in (1, 3):
        state = CardState.LEARNING
    elif card_type == 2 or queue == 2:
        state = CardState.REVIEW
    else:
        return _unavailable(CapabilityReason.MISSING_FIELD)
    return Observation.available(state, Provenance.ANKI_INTERNAL)


def _note_fields(note: Any) -> dict[str, str]:
    items = getattr(note, "items", None)
    if callable(items):
        try:
            return {str(key): _clean(value) for key, value in items()}
        except (TypeError, ValueError):
            return {}
    keys = getattr(note, "keys", None)
    if callable(keys):
        result: dict[str, str] = {}
        for key in keys():
            try:
                result[str(key)] = _clean(note[key])
            except (KeyError, TypeError):
                continue
        return result
    return {}


def _first_value(fields: Mapping[str, str]) -> str:
    return next((value for value in fields.values() if value), "")


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _non_negative_int(value: Any) -> int | None:
    parsed = _as_int(value)
    return parsed if parsed is not None and parsed >= 0 else None


def _bounded_float(
    value: Any, minimum: float, maximum: float | None
) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    if parsed < minimum or (maximum is not None and parsed > maximum):
        return None
    return parsed


def _valid_bounds(start_ms: int, end_ms: int) -> bool:
    return (
        isinstance(start_ms, int)
        and not isinstance(start_ms, bool)
        and isinstance(end_ms, int)
        and not isinstance(end_ms, bool)
        and 0 <= start_ms < end_ms
    )
