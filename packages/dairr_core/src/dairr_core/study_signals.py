"""Normalized study evidence consumed by the shared scoring engine.

Hosts must only mark observations available when the value is supported by
their data source. Missing AnkiConnect/FSRS data is never converted to zero.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any, Generic, Mapping, TypeVar
from urllib.parse import quote

from .capabilities import CapabilityReason, Provenance


T = TypeVar("T")


class ObservationStatus(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class Observation(Generic[T]):
    status: ObservationStatus
    value: T | None = None
    reason: CapabilityReason = CapabilityReason.NONE
    provenance: Provenance = Provenance.UNKNOWN

    def __post_init__(self) -> None:
        if self.status is ObservationStatus.AVAILABLE:
            if self.value is None:
                raise ValueError("available observation requires a value")
            if self.reason is not CapabilityReason.NONE:
                raise ValueError("available observation cannot have an unavailable reason")
        else:
            if self.value is not None:
                raise ValueError("unavailable observation cannot carry a value")
            if self.reason is CapabilityReason.NONE:
                raise ValueError("unavailable observation requires a reason")

    @classmethod
    def available(cls, value: T, provenance: Provenance) -> "Observation[T]":
        return cls(ObservationStatus.AVAILABLE, value, CapabilityReason.NONE, provenance)

    @classmethod
    def unavailable(
        cls, reason: CapabilityReason, provenance: Provenance = Provenance.UNKNOWN
    ) -> "Observation[T]":
        return cls(ObservationStatus.UNAVAILABLE, None, reason, provenance)

    @property
    def is_available(self) -> bool:
        return self.status is ObservationStatus.AVAILABLE


class ReviewGrade(IntEnum):
    AGAIN = 1
    HARD = 2
    GOOD = 3
    EASY = 4


class CardState(str, Enum):
    NEW = "new"
    LEARNING = "learning"
    RELEARNING = "relearning"
    REVIEW = "review"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class CardIdentity:
    source_id: str
    card_id: str
    note_id: str

    def __post_init__(self) -> None:
        if not self.source_id.strip() or not self.card_id.strip():
            raise ValueError("source_id and card_id are required")

    @property
    def stable_id(self) -> str:
        return f"{quote(self.source_id, safe='')}:{quote(self.card_id, safe='')}"


@dataclass(frozen=True, slots=True)
class ReviewEvent:
    grade: ReviewGrade
    sequence: int
    reviewed_at_ms: int | None = None

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise ValueError("review sequence must be non-negative")
        if self.reviewed_at_ms is not None and self.reviewed_at_ms < 0:
            raise ValueError("review timestamp must be non-negative")


def _missing() -> Observation[Any]:
    return Observation.unavailable(CapabilityReason.MISSING_FIELD)


@dataclass(frozen=True, slots=True)
class SchedulingSignals:
    retrievability: Observation[float] = field(default_factory=_missing)
    difficulty: Observation[float] = field(default_factory=_missing)
    stability_days: Observation[float] = field(default_factory=_missing)
    elapsed_days: Observation[float] = field(default_factory=_missing)
    overdue_days: Observation[float] = field(default_factory=_missing)
    state: Observation[CardState] = field(default_factory=_missing)

    def __post_init__(self) -> None:
        _validate_range(self.retrievability, "retrievability", 0.0, 1.0)
        _validate_range(self.difficulty, "difficulty", 0.0, 10.0)
        for name in ("stability_days", "elapsed_days", "overdue_days"):
            value = getattr(self, name)
            if value.is_available and float(value.value) < 0:
                raise ValueError(f"{name} must be non-negative")


@dataclass(frozen=True, slots=True)
class CardStudySignals:
    identity: CardIdentity
    term: str
    normalized_target: str = ""
    reviews: Observation[tuple[ReviewEvent, ...]] = field(default_factory=_missing)
    same_day_attempts: Observation[int] = field(default_factory=_missing)
    recent_lapses: Observation[int] = field(default_factory=_missing)
    historical_lapses: Observation[int] = field(default_factory=_missing)
    scheduling: SchedulingSignals = field(default_factory=SchedulingSignals)
    days_since_last_article_use: Observation[float] = field(default_factory=_missing)
    recent_article_inclusions: Observation[int] = field(default_factory=_missing)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.term.strip():
            raise ValueError("term is required")
        for name in (
            "same_day_attempts",
            "recent_lapses",
            "historical_lapses",
            "recent_article_inclusions",
        ):
            observed = getattr(self, name)
            if observed.is_available and int(observed.value) < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.days_since_last_article_use.is_available:
            if float(self.days_since_last_article_use.value) < 0:
                raise ValueError("days_since_last_article_use must be non-negative")
        if self.reviews.is_available:
            events = self.reviews.value or ()
            sequences = [event.sequence for event in events]
            if sequences != sorted(sequences) or len(sequences) != len(set(sequences)):
                raise ValueError("review events must be uniquely ordered by sequence")

    @property
    def target_key(self) -> str:
        normalized = " ".join(self.normalized_target.casefold().split())
        return normalized or " ".join(self.term.casefold().split())


def _validate_range(
    observed: Observation[float], name: str, minimum: float, maximum: float
) -> None:
    if not observed.is_available:
        return
    value = float(observed.value)
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
