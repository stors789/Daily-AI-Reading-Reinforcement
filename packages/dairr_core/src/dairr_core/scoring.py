"""Configurable, explainable reinforcement-priority heuristic.

This module ranks available study evidence. It does not claim to measure
intrinsic difficulty, and unavailable evidence always contributes zero with a
visible explanation.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Iterable, Mapping

from .capabilities import CapabilityReason, Provenance
from .study_signals import (
    CardState,
    CardStudySignals,
    Observation,
    ReviewGrade,
)


SCORING_PRESET_SCHEMA_VERSION = 1


class SignalName(str, Enum):
    AGAIN_COUNT = "again_count"
    HARD_COUNT = "hard_count"
    GOOD_COUNT = "good_count"
    EASY_COUNT = "easy_count"
    SAME_DAY_ATTEMPTS = "same_day_attempts"
    RECOVERY_AFTER_FAILURE = "recovery_after_failure"
    REPEATED_FAILURE = "repeated_failure"
    RECENT_LAPSES = "recent_lapses"
    HISTORICAL_LAPSES = "historical_lapses"
    LOW_RETRIEVABILITY = "low_retrievability"
    FSRS_DIFFICULTY = "fsrs_difficulty"
    LOW_STABILITY = "low_stability"
    ELAPSED_DAYS = "elapsed_days"
    OVERDUE_DAYS = "overdue_days"
    CARD_STATE = "card_state"
    DUPLICATE_TARGET = "duplicate_target"
    SIBLING_CARD = "sibling_card"
    RECENT_REUSE = "recent_reuse"
    RECENT_INCLUSION_COUNT = "recent_inclusion_count"


class Transform(str, Enum):
    LINEAR = "linear"
    SQRT = "sqrt"
    LOG1P = "log1p"
    SQUARE = "square"


class Normalization(str, Enum):
    NONE = "none"
    CLAMP_0_100 = "clamp_0_100"
    MIN_MAX_0_100 = "min_max_0_100"


class SettingsMode(str, Enum):
    SIMPLE = "simple"
    ADVANCED = "advanced"


class ContributionStatus(str, Enum):
    APPLIED = "applied"
    DISABLED = "disabled"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class DecayConfig:
    enabled: bool = False
    half_life_days: float = 14.0

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise ValueError("decay enabled must be a boolean")
        if (
            isinstance(self.half_life_days, bool)
            or not isinstance(self.half_life_days, (int, float))
            or not math.isfinite(self.half_life_days)
            or self.half_life_days <= 0
        ):
            raise ValueError("decay half_life_days must be positive and finite")

    def to_dict(self) -> dict[str, Any]:
        return {"enabled": self.enabled, "halfLifeDays": self.half_life_days}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "DecayConfig":
        return cls(
            enabled=_boolean(payload.get("enabled", False), "decay.enabled"),
            half_life_days=_number(payload.get("halfLifeDays", 14.0), "decay.halfLifeDays"),
        )


@dataclass(frozen=True, slots=True)
class SignalRule:
    enabled: bool
    weight: float
    transform: Transform = Transform.LINEAR
    normalize_by: float = 1.0
    minimum_contribution: float | None = None
    maximum_contribution: float | None = None
    decay: DecayConfig = field(default_factory=DecayConfig)

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise ValueError("signal enabled must be a boolean")
        if isinstance(self.weight, bool):
            raise ValueError("weight must be a number")
        if not isinstance(self.transform, Transform):
            raise ValueError("transform must be a Transform")
        for name, value in (
            ("weight", self.weight),
            ("normalize_by", self.normalize_by),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
            ):
                raise ValueError(f"{name} must be finite")
        if self.normalize_by <= 0:
            raise ValueError("normalize_by must be positive")
        for name, value in (
            ("minimum_contribution", self.minimum_contribution),
            ("maximum_contribution", self.maximum_contribution),
        ):
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
            ):
                raise ValueError(f"{name} must be finite")
        if (
            self.minimum_contribution is not None
            and self.maximum_contribution is not None
            and self.minimum_contribution > self.maximum_contribution
        ):
            raise ValueError("minimum contribution cannot exceed maximum contribution")

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "weight": self.weight,
            "transform": self.transform.value,
            "normalizeBy": self.normalize_by,
            "minimumContribution": self.minimum_contribution,
            "maximumContribution": self.maximum_contribution,
            "decay": self.decay.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SignalRule":
        decay = payload.get("decay") or {}
        if not isinstance(decay, Mapping):
            raise ValueError("signal decay must be an object")
        return cls(
            enabled=_boolean(payload.get("enabled", True), "signal.enabled"),
            weight=_number(payload.get("weight", 0), "signal.weight"),
            transform=Transform(str(payload.get("transform", "linear"))),
            normalize_by=_number(payload.get("normalizeBy", 1), "signal.normalizeBy"),
            minimum_contribution=_optional_number(
                payload.get("minimumContribution"), "signal.minimumContribution"
            ),
            maximum_contribution=_optional_number(
                payload.get("maximumContribution"), "signal.maximumContribution"
            ),
            decay=DecayConfig.from_dict(decay),
        )


@dataclass(frozen=True, slots=True)
class SelectionDefaults:
    minimum_inclusion_score: float = 0.0
    maximum_selected_cards: int = 20
    required_target_count: int = 5
    preferred_target_count: int = 8
    optional_target_count: int = 7

    def __post_init__(self) -> None:
        if (
            isinstance(self.minimum_inclusion_score, bool)
            or not isinstance(self.minimum_inclusion_score, (int, float))
            or not math.isfinite(self.minimum_inclusion_score)
        ):
            raise ValueError("minimum inclusion score must be finite")
        counts = (
            self.maximum_selected_cards,
            self.required_target_count,
            self.preferred_target_count,
            self.optional_target_count,
        )
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in counts
        ):
            raise ValueError("selection counts must be non-negative integers")
        if self.maximum_selected_cards < 1:
            raise ValueError("maximum_selected_cards must be at least one")
        if sum(counts[1:]) > self.maximum_selected_cards:
            raise ValueError("target category counts cannot exceed maximum selected cards")

    def to_dict(self) -> dict[str, Any]:
        return {
            "minimumInclusionScore": self.minimum_inclusion_score,
            "maximumSelectedCards": self.maximum_selected_cards,
            "requiredTargetCount": self.required_target_count,
            "preferredTargetCount": self.preferred_target_count,
            "optionalTargetCount": self.optional_target_count,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SelectionDefaults":
        return cls(
            minimum_inclusion_score=_number(
                payload.get("minimumInclusionScore", 0), "selection.minimumInclusionScore"
            ),
            maximum_selected_cards=_integer(
                payload.get("maximumSelectedCards", 20), "selection.maximumSelectedCards"
            ),
            required_target_count=_integer(
                payload.get("requiredTargetCount", 5), "selection.requiredTargetCount"
            ),
            preferred_target_count=_integer(
                payload.get("preferredTargetCount", 8), "selection.preferredTargetCount"
            ),
            optional_target_count=_integer(
                payload.get("optionalTargetCount", 7), "selection.optionalTargetCount"
            ),
        )


@dataclass(frozen=True, slots=True)
class ScoringPreset:
    id: str
    name: str
    mode: SettingsMode
    normalization: Normalization
    rules: Mapping[SignalName, SignalRule]
    selection: SelectionDefaults = field(default_factory=SelectionDefaults)
    schema_version: int = SCORING_PRESET_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.name.strip():
            raise ValueError("scoring preset id and name are required")
        if self.schema_version != SCORING_PRESET_SCHEMA_VERSION:
            raise ValueError(f"unsupported scoring preset schema: {self.schema_version}")
        unknown = set(self.rules) - set(SignalName)
        if unknown:
            raise ValueError(f"unknown scoring signals: {unknown}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "id": self.id,
            "name": self.name,
            "mode": self.mode.value,
            "normalization": self.normalization.value,
            "rules": {
                name.value: rule.to_dict()
                for name, rule in sorted(self.rules.items(), key=lambda item: item[0].value)
            },
            "selection": self.selection.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ScoringPreset":
        rules_payload = payload.get("rules")
        if not isinstance(rules_payload, Mapping):
            raise ValueError("scoring preset rules must be an object")
        rules: dict[SignalName, SignalRule] = {}
        for name, rule_payload in rules_payload.items():
            if not isinstance(rule_payload, Mapping):
                raise ValueError(f"invalid rule for {name}")
            rules[SignalName(str(name))] = SignalRule.from_dict(rule_payload)
        selection_payload = payload.get("selection") or {}
        if not isinstance(selection_payload, Mapping):
            raise ValueError("scoring preset selection must be an object")
        return cls(
            schema_version=_integer(
                payload.get("schemaVersion", SCORING_PRESET_SCHEMA_VERSION),
                "schemaVersion",
            ),
            id=str(payload.get("id") or ""),
            name=str(payload.get("name") or ""),
            mode=SettingsMode(str(payload.get("mode", "simple"))),
            normalization=Normalization(str(payload.get("normalization", "none"))),
            rules=rules,
            selection=SelectionDefaults.from_dict(selection_payload),
        )


@dataclass(frozen=True, slots=True)
class SignalMetadata:
    name: SignalName
    label: str
    explanation: str
    simple_control: bool


SIGNAL_METADATA: tuple[SignalMetadata, ...] = (
    SignalMetadata(SignalName.AGAIN_COUNT, "Again answers", "Same-day Again answers.", True),
    SignalMetadata(SignalName.HARD_COUNT, "Hard answers", "Same-day Hard answers.", True),
    SignalMetadata(SignalName.GOOD_COUNT, "Good answers", "Same-day Good answers.", False),
    SignalMetadata(SignalName.EASY_COUNT, "Easy answers", "Same-day Easy answers.", False),
    SignalMetadata(SignalName.SAME_DAY_ATTEMPTS, "Same-day attempts", "Number of attempts in the current Anki day.", True),
    SignalMetadata(SignalName.RECOVERY_AFTER_FAILURE, "Recovery", "An Again followed by a later successful answer.", True),
    SignalMetadata(SignalName.REPEATED_FAILURE, "Repeated failure", "More than one Again in the current Anki day.", True),
    SignalMetadata(SignalName.RECENT_LAPSES, "Recent lapses", "Lapses in the adapter-defined recent window.", False),
    SignalMetadata(SignalName.HISTORICAL_LAPSES, "Historical lapses", "Lifetime lapse count when available.", False),
    SignalMetadata(SignalName.LOW_RETRIEVABILITY, "Low retrievability", "One minus current FSRS retrievability.", False),
    SignalMetadata(SignalName.FSRS_DIFFICULTY, "FSRS difficulty", "Current FSRS difficulty scaled to 0–1.", False),
    SignalMetadata(SignalName.LOW_STABILITY, "Low stability", "Inverse of FSRS stability in days.", False),
    SignalMetadata(SignalName.ELAPSED_DAYS, "Elapsed time", "Days elapsed since the relevant review.", False),
    SignalMetadata(SignalName.OVERDUE_DAYS, "Overdue", "Days overdue.", False),
    SignalMetadata(SignalName.CARD_STATE, "Card state", "New/learning/relearning/review priority mapping.", False),
    SignalMetadata(SignalName.DUPLICATE_TARGET, "Duplicate target", "Other candidates with an equivalent normalized target.", True),
    SignalMetadata(SignalName.SIBLING_CARD, "Sibling card", "Other candidates from the same note.", True),
    SignalMetadata(SignalName.RECENT_REUSE, "Recent reuse", "Recent use in a DAIRR article with optional decay.", True),
    SignalMetadata(SignalName.RECENT_INCLUSION_COUNT, "Reuse count", "Recent article inclusion count.", False),
)


@dataclass(frozen=True, slots=True)
class ScoreContribution:
    signal: SignalName
    status: ContributionStatus
    raw_value: float | None
    transformed_value: float | None
    contribution: float
    reason: CapabilityReason
    provenance: Provenance
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal": self.signal.value,
            "status": self.status.value,
            "rawValue": self.raw_value,
            "transformedValue": self.transformed_value,
            "contribution": self.contribution,
            "reason": self.reason.value,
            "provenance": self.provenance.value,
            "explanation": self.explanation,
        }


@dataclass(frozen=True, slots=True)
class ScoreResult:
    card: CardStudySignals
    raw_total: float
    total: float
    normalization: Normalization
    contributions: tuple[ScoreContribution, ...]

    def contribution(self, signal: SignalName) -> ScoreContribution:
        return next(item for item in self.contributions if item.signal is signal)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cardId": self.card.identity.stable_id,
            "sourceId": self.card.identity.source_id,
            "localCardId": self.card.identity.card_id,
            "noteId": self.card.identity.note_id,
            "term": self.card.term,
            "rawTotal": self.raw_total,
            "total": self.total,
            "normalization": self.normalization.value,
            "contributions": [item.to_dict() for item in self.contributions],
        }


def recommended_preset() -> ScoringPreset:
    """Return a fresh recommended heuristic preset."""

    rules = {
        SignalName.AGAIN_COUNT: SignalRule(True, 18, Transform.LOG1P, maximum_contribution=36),
        SignalName.HARD_COUNT: SignalRule(True, 8, Transform.LOG1P, maximum_contribution=16),
        SignalName.GOOD_COUNT: SignalRule(True, -2, Transform.LOG1P, minimum_contribution=-6),
        SignalName.EASY_COUNT: SignalRule(True, -6, Transform.LOG1P, minimum_contribution=-12),
        SignalName.SAME_DAY_ATTEMPTS: SignalRule(True, 3, Transform.LOG1P, maximum_contribution=9),
        SignalName.RECOVERY_AFTER_FAILURE: SignalRule(True, 6),
        SignalName.REPEATED_FAILURE: SignalRule(True, 10, Transform.LOG1P, maximum_contribution=20),
        SignalName.RECENT_LAPSES: SignalRule(True, 6, Transform.LOG1P, maximum_contribution=18),
        SignalName.HISTORICAL_LAPSES: SignalRule(True, 3, Transform.LOG1P, maximum_contribution=15),
        SignalName.LOW_RETRIEVABILITY: SignalRule(True, 20),
        SignalName.FSRS_DIFFICULTY: SignalRule(True, 10),
        SignalName.LOW_STABILITY: SignalRule(True, 8),
        SignalName.ELAPSED_DAYS: SignalRule(True, 1, Transform.LOG1P, normalize_by=7, maximum_contribution=8),
        SignalName.OVERDUE_DAYS: SignalRule(True, 2, Transform.LOG1P, normalize_by=7, maximum_contribution=12),
        SignalName.CARD_STATE: SignalRule(True, 5),
        SignalName.DUPLICATE_TARGET: SignalRule(True, -8, Transform.LOG1P, minimum_contribution=-16),
        SignalName.SIBLING_CARD: SignalRule(True, -5, Transform.LOG1P, minimum_contribution=-10),
        SignalName.RECENT_REUSE: SignalRule(True, -18, decay=DecayConfig(True, 14), minimum_contribution=-18),
        SignalName.RECENT_INCLUSION_COUNT: SignalRule(True, -4, Transform.LOG1P, minimum_contribution=-12),
    }
    return ScoringPreset(
        id="recommended-v1",
        name="Recommended reinforcement priority",
        mode=SettingsMode.SIMPLE,
        normalization=Normalization.CLAMP_0_100,
        rules=rules,
    )


def reset_to_recommended() -> ScoringPreset:
    return recommended_preset()


def export_preset(preset: ScoringPreset) -> str:
    return json.dumps(preset.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def import_preset(serialized: str) -> ScoringPreset:
    try:
        payload = json.loads(serialized)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("scoring preset is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("scoring preset must be a JSON object")
    return ScoringPreset.from_dict(payload)


def score_cards(
    cards: Iterable[CardStudySignals], preset: ScoringPreset
) -> tuple[ScoreResult, ...]:
    card_list = list(cards)
    identities = [card.identity.stable_id for card in card_list]
    if len(identities) != len(set(identities)):
        raise ValueError("cards must have unique source-scoped identities")
    target_counts: dict[str, int] = {}
    note_counts: dict[tuple[str, str], int] = {}
    for card in card_list:
        target_counts[card.target_key] = target_counts.get(card.target_key, 0) + 1
        if card.identity.note_id:
            note_key = (card.identity.source_id, card.identity.note_id)
            note_counts[note_key] = note_counts.get(note_key, 0) + 1

    raw_results = [
        _score_one(card, preset, target_counts, note_counts) for card in card_list
    ]
    if preset.normalization is Normalization.MIN_MAX_0_100 and raw_results:
        minimum = min(result.raw_total for result in raw_results)
        maximum = max(result.raw_total for result in raw_results)
        span = maximum - minimum
        return tuple(
            replace(
                result,
                total=0.0 if span == 0 else 100 * (result.raw_total - minimum) / span,
            )
            for result in raw_results
        )
    return tuple(raw_results)


def signal_metadata(mode: SettingsMode) -> tuple[SignalMetadata, ...]:
    """Return controls suitable for simple or advanced configuration UI."""

    if mode is SettingsMode.SIMPLE:
        return tuple(item for item in SIGNAL_METADATA if item.simple_control)
    if mode is SettingsMode.ADVANCED:
        return SIGNAL_METADATA
    raise ValueError("unknown settings mode")


def _score_one(
    card: CardStudySignals,
    preset: ScoringPreset,
    target_counts: Mapping[str, int],
    note_counts: Mapping[tuple[str, str], int],
) -> ScoreResult:
    contributions = []
    for metadata in SIGNAL_METADATA:
        rule = preset.rules.get(metadata.name, SignalRule(False, 0))
        if not rule.enabled:
            contributions.append(ScoreContribution(
                metadata.name, ContributionStatus.DISABLED, None, None, 0.0,
                CapabilityReason.NONE, Provenance.USER_CONFIGURED,
                "Disabled by the scoring preset.",
            ))
            continue
        observed = _signal_value(metadata.name, card, target_counts, note_counts)
        if not observed.is_available:
            contributions.append(ScoreContribution(
                metadata.name, ContributionStatus.UNAVAILABLE, None, None, 0.0,
                observed.reason, observed.provenance,
                f"Unavailable: {observed.reason.value}.",
            ))
            continue
        raw = float(observed.value)
        normalized = raw / rule.normalize_by
        transformed = _transform(normalized, rule.transform)
        if rule.decay.enabled:
            decay_factor = 0.5 ** (raw / rule.decay.half_life_days)
            # RECENT_REUSE observes age, not magnitude: a just-used target has
            # full penalty and that penalty decays as the use gets older.
            transformed = (
                decay_factor
                if metadata.name is SignalName.RECENT_REUSE
                else transformed * decay_factor
            )
        contribution = transformed * rule.weight
        if rule.minimum_contribution is not None:
            contribution = max(rule.minimum_contribution, contribution)
        if rule.maximum_contribution is not None:
            contribution = min(rule.maximum_contribution, contribution)
        contributions.append(ScoreContribution(
            metadata.name, ContributionStatus.APPLIED, raw, transformed, contribution,
            CapabilityReason.NONE, observed.provenance,
            f"{raw:g} transformed with {rule.transform.value}, weighted by {rule.weight:g}.",
        ))
    raw_total = sum(item.contribution for item in contributions)
    if preset.normalization is Normalization.CLAMP_0_100:
        total = min(100.0, max(0.0, raw_total))
    else:
        total = raw_total
    return ScoreResult(card, raw_total, total, preset.normalization, tuple(contributions))


def _signal_value(
    signal: SignalName,
    card: CardStudySignals,
    target_counts: Mapping[str, int],
    note_counts: Mapping[tuple[str, str], int],
) -> Observation[float]:
    reviews = card.reviews
    if signal in {
        SignalName.AGAIN_COUNT, SignalName.HARD_COUNT, SignalName.GOOD_COUNT,
        SignalName.EASY_COUNT, SignalName.RECOVERY_AFTER_FAILURE,
        SignalName.REPEATED_FAILURE,
    }:
        if not reviews.is_available:
            return Observation.unavailable(reviews.reason, reviews.provenance)
        events = reviews.value or ()
        grades = [event.grade for event in events]
        if signal is SignalName.RECOVERY_AFTER_FAILURE:
            recovery = any(
                grade is ReviewGrade.AGAIN and any(later > ReviewGrade.AGAIN for later in grades[index + 1:])
                for index, grade in enumerate(grades)
            )
            value = float(recovery)
        elif signal is SignalName.REPEATED_FAILURE:
            value = float(max(0, grades.count(ReviewGrade.AGAIN) - 1))
        else:
            target_grade = {
                SignalName.AGAIN_COUNT: ReviewGrade.AGAIN,
                SignalName.HARD_COUNT: ReviewGrade.HARD,
                SignalName.GOOD_COUNT: ReviewGrade.GOOD,
                SignalName.EASY_COUNT: ReviewGrade.EASY,
            }[signal]
            value = float(grades.count(target_grade))
        return Observation.available(value, reviews.provenance)

    direct = {
        SignalName.SAME_DAY_ATTEMPTS: card.same_day_attempts,
        SignalName.RECENT_LAPSES: card.recent_lapses,
        SignalName.HISTORICAL_LAPSES: card.historical_lapses,
        SignalName.ELAPSED_DAYS: card.scheduling.elapsed_days,
        SignalName.OVERDUE_DAYS: card.scheduling.overdue_days,
        SignalName.RECENT_REUSE: card.days_since_last_article_use,
        SignalName.RECENT_INCLUSION_COUNT: card.recent_article_inclusions,
    }
    if signal in direct:
        observed = direct[signal]
        if not observed.is_available:
            return Observation.unavailable(observed.reason, observed.provenance)
        return Observation.available(float(observed.value), observed.provenance)
    if signal is SignalName.LOW_RETRIEVABILITY:
        return _mapped(card.scheduling.retrievability, lambda value: 1 - float(value))
    if signal is SignalName.FSRS_DIFFICULTY:
        return _mapped(card.scheduling.difficulty, lambda value: float(value) / 10)
    if signal is SignalName.LOW_STABILITY:
        return _mapped(card.scheduling.stability_days, lambda value: 1 / (1 + float(value)))
    if signal is SignalName.CARD_STATE:
        return _mapped(card.scheduling.state, lambda value: {
            CardState.NEW: 0.4,
            CardState.LEARNING: 0.7,
            CardState.RELEARNING: 1.0,
            CardState.REVIEW: 0.2,
            CardState.UNKNOWN: 0.0,
        }[value])
    if signal is SignalName.DUPLICATE_TARGET:
        return Observation.available(float(max(0, target_counts[card.target_key] - 1)), Provenance.SHARED_CORE)
    if signal is SignalName.SIBLING_CARD:
        if not card.identity.note_id:
            return Observation.unavailable(CapabilityReason.MISSING_FIELD, Provenance.SHARED_CORE)
        key = (card.identity.source_id, card.identity.note_id)
        return Observation.available(float(max(0, note_counts.get(key, 1) - 1)), Provenance.SHARED_CORE)
    raise AssertionError(f"unhandled scoring signal: {signal.value}")


def _mapped(observed: Observation[Any], mapper: Any) -> Observation[float]:
    if not observed.is_available:
        return Observation.unavailable(observed.reason, observed.provenance)
    return Observation.available(float(mapper(observed.value)), observed.provenance)


def _transform(value: float, transform: Transform) -> float:
    if value < 0:
        raise ValueError("scoring signal values must be non-negative")
    if transform is Transform.LINEAR:
        return value
    if transform is Transform.SQRT:
        return math.sqrt(value)
    if transform is Transform.LOG1P:
        return math.log1p(value)
    if transform is Transform.SQUARE:
        return value * value
    raise AssertionError(transform)


def _boolean(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean")
    return value


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def _optional_number(value: Any, name: str) -> float | None:
    return None if value is None else _number(value, name)


def _integer(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    return value
