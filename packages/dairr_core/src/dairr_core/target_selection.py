"""Manual and score-driven target classification for article generation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping, Sequence

from .scoring import ScoreResult, SelectionDefaults


class TargetCategory(str, Enum):
    REQUIRED = "required"
    PREFERRED = "preferred"
    OPTIONAL = "optional"
    EXCLUDED = "excluded"


@dataclass(frozen=True, slots=True)
class ManualOverride:
    card_id: str
    category: TargetCategory

    def __post_init__(self) -> None:
        if not self.card_id.strip():
            raise ValueError("manual override card_id is required")

    def to_dict(self) -> dict[str, str]:
        return {"cardId": self.card_id, "category": self.category.value}

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "ManualOverride":
        return cls(
            card_id=str(payload.get("cardId") or ""),
            category=TargetCategory(str(payload.get("category") or "")),
        )


@dataclass(frozen=True, slots=True)
class TargetAssignment:
    score: ScoreResult
    category: TargetCategory
    manually_set: bool
    explanation: str

    @property
    def card_id(self) -> str:
        return self.score.card.identity.stable_id

    @property
    def selected(self) -> bool:
        return self.category is not TargetCategory.EXCLUDED

    def to_dict(self) -> dict[str, object]:
        return {
            "cardId": self.card_id,
            "category": self.category.value,
            "selected": self.selected,
            "manuallySet": self.manually_set,
            "explanation": self.explanation,
            "score": self.score.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class TargetSelection:
    assignments: tuple[TargetAssignment, ...]
    limit_exceeded_by_manual: bool = False

    @property
    def selected(self) -> tuple[TargetAssignment, ...]:
        return tuple(item for item in self.assignments if item.selected)

    def by_category(self, category: TargetCategory) -> tuple[TargetAssignment, ...]:
        return tuple(item for item in self.assignments if item.category is category)

    def to_dict(self) -> dict[str, object]:
        return {
            "assignments": [item.to_dict() for item in self.assignments],
            "limitExceededByManual": self.limit_exceeded_by_manual,
        }


def select_targets(
    scores: Iterable[ScoreResult],
    policy: SelectionDefaults,
    overrides: Iterable[ManualOverride] = (),
    explicit_order: Sequence[str] = (),
) -> TargetSelection:
    """Classify every candidate and preserve explicit user decisions.

    Manual inclusion bypasses the threshold and is never silently dropped by
    the automatic maximum. If manual inclusions exceed that maximum, the
    result reports ``limit_exceeded_by_manual`` for the UI to explain.
    """

    score_list = list(scores)
    by_id: dict[str, ScoreResult] = {}
    for score in score_list:
        stable_id = score.card.identity.stable_id
        if stable_id in by_id:
            raise ValueError(f"duplicate scored card id: {stable_id}")
        by_id[stable_id] = score

    override_map: dict[str, TargetCategory] = {}
    for override in overrides:
        if override.card_id not in by_id:
            raise ValueError(f"manual override references unknown card: {override.card_id}")
        if override.card_id in override_map:
            raise ValueError(f"duplicate manual override: {override.card_id}")
        override_map[override.card_id] = override.category

    if len(explicit_order) != len(set(explicit_order)):
        raise ValueError("explicit target order contains duplicates")
    unknown_order = set(explicit_order) - set(by_id)
    if unknown_order:
        raise ValueError(f"explicit target order references unknown cards: {sorted(unknown_order)}")
    order_index = {card_id: index for index, card_id in enumerate(explicit_order)}
    ranked = sorted(
        score_list,
        key=lambda result: (
            order_index.get(result.card.identity.stable_id, len(order_index)),
            -result.total,
            result.card.identity.stable_id,
        ),
    )

    assignments: dict[str, TargetAssignment] = {}
    selected_counts = {
        TargetCategory.REQUIRED: 0,
        TargetCategory.PREFERRED: 0,
        TargetCategory.OPTIONAL: 0,
    }
    for score in ranked:
        stable_id = score.card.identity.stable_id
        category = override_map.get(stable_id)
        if category is None:
            continue
        selected = category is not TargetCategory.EXCLUDED
        if selected:
            selected_counts[category] += 1
        assignments[stable_id] = TargetAssignment(
            score,
            category,
            True,
            "Manually included." if selected else "Manually excluded.",
        )

    manual_selected = sum(selected_counts.values())
    remaining_limit = max(0, policy.maximum_selected_cards - manual_selected)
    quota = {
        TargetCategory.REQUIRED: policy.required_target_count,
        TargetCategory.PREFERRED: policy.preferred_target_count,
        TargetCategory.OPTIONAL: policy.optional_target_count,
    }
    automatic_categories: list[TargetCategory] = []
    for category in (
        TargetCategory.REQUIRED,
        TargetCategory.PREFERRED,
        TargetCategory.OPTIONAL,
    ):
        automatic_categories.extend(
            [category] * max(0, quota[category] - selected_counts[category])
        )

    for score in ranked:
        stable_id = score.card.identity.stable_id
        if stable_id in assignments:
            continue
        if score.total < policy.minimum_inclusion_score:
            assignments[stable_id] = TargetAssignment(
                score, TargetCategory.EXCLUDED, False,
                "Below the minimum inclusion score.",
            )
            continue
        if remaining_limit and automatic_categories:
            category = automatic_categories.pop(0)
            remaining_limit -= 1
            assignments[stable_id] = TargetAssignment(
                score, category, False,
                f"Automatically ranked as {category.value}.",
            )
        else:
            assignments[stable_id] = TargetAssignment(
                score, TargetCategory.EXCLUDED, False,
                "Outside the configured target count or selection limit.",
            )

    ordered_assignments = tuple(
        assignments[score.card.identity.stable_id] for score in ranked
    )
    return TargetSelection(
        ordered_assignments,
        limit_exceeded_by_manual=manual_selected > policy.maximum_selected_cards,
    )
