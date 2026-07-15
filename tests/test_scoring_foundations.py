from __future__ import annotations

import dataclasses
import sys
import unittest
from pathlib import Path


CORE_SRC = Path(__file__).resolve().parent.parent / "packages" / "dairr_core" / "src"
if str(CORE_SRC) not in sys.path:
    sys.path.insert(0, str(CORE_SRC))

from dairr_core.capabilities import CapabilityReason, Provenance
from dairr_core.scoring import (
    ContributionStatus,
    DecayConfig,
    Normalization,
    ScoringPreset,
    SelectionDefaults,
    SettingsMode,
    SignalName,
    SignalRule,
    Transform,
    export_preset,
    import_preset,
    recommended_preset,
    score_cards,
    signal_metadata,
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


P = Provenance.ANKI_INTERNAL


def card(
    card_id: str = "1",
    note_id: str = "10",
    target: str = "term",
    reviews: tuple[ReviewEvent, ...] | None = None,
    **kwargs,
) -> CardStudySignals:
    review_observation = (
        Observation.available(reviews, P)
        if reviews is not None
        else Observation.unavailable(CapabilityReason.UNSUPPORTED_ACTION, Provenance.ANKICONNECT_STANDARD)
    )
    return CardStudySignals(
        CardIdentity("anki", card_id, note_id),
        target,
        normalized_target=target,
        reviews=review_observation,
        **kwargs,
    )


def one_rule(signal: SignalName, rule: SignalRule, normalization=Normalization.NONE) -> ScoringPreset:
    return ScoringPreset("test", "Test", SettingsMode.ADVANCED, normalization, {signal: rule})


class ScoringFoundationTests(unittest.TestCase):
    def test_again_recovery_and_repeated_failure_use_ordered_events(self) -> None:
        subject = card(reviews=(
            ReviewEvent(ReviewGrade.AGAIN, 0),
            ReviewEvent(ReviewGrade.AGAIN, 1),
            ReviewEvent(ReviewGrade.GOOD, 2),
        ))
        preset = ScoringPreset(
            "test", "Test", SettingsMode.ADVANCED, Normalization.NONE,
            {
                SignalName.AGAIN_COUNT: SignalRule(True, 1),
                SignalName.RECOVERY_AFTER_FAILURE: SignalRule(True, 10),
                SignalName.REPEATED_FAILURE: SignalRule(True, 5),
            },
        )
        result = score_cards([subject], preset)[0]
        self.assertEqual(result.contribution(SignalName.AGAIN_COUNT).raw_value, 2)
        self.assertEqual(result.contribution(SignalName.RECOVERY_AFTER_FAILURE).raw_value, 1)
        self.assertEqual(result.contribution(SignalName.REPEATED_FAILURE).raw_value, 1)
        self.assertEqual(result.raw_total, 17)

    def test_missing_ordered_reviews_are_explained_and_contribute_zero(self) -> None:
        result = score_cards(
            [card()], one_rule(SignalName.RECOVERY_AFTER_FAILURE, SignalRule(True, 10))
        )[0]
        contribution = result.contribution(SignalName.RECOVERY_AFTER_FAILURE)
        self.assertEqual(contribution.status, ContributionStatus.UNAVAILABLE)
        self.assertEqual(contribution.reason, CapabilityReason.UNSUPPORTED_ACTION)
        self.assertEqual(contribution.provenance, Provenance.ANKICONNECT_STANDARD)
        self.assertEqual(contribution.contribution, 0)

    def test_disabled_signal_is_distinct_from_unavailable(self) -> None:
        result = score_cards(
            [card()], one_rule(SignalName.AGAIN_COUNT, SignalRule(False, 999))
        )[0]
        self.assertEqual(result.contribution(SignalName.AGAIN_COUNT).status, ContributionStatus.DISABLED)
        self.assertEqual(result.raw_total, 0)

    def test_weights_transforms_normalization_and_contribution_caps(self) -> None:
        subject = card(
            same_day_attempts=Observation.available(8, P),
        )
        rule = SignalRule(
            True, 10, Transform.SQRT, normalize_by=2,
            minimum_contribution=-5, maximum_contribution=15,
        )
        result = score_cards([subject], one_rule(SignalName.SAME_DAY_ATTEMPTS, rule))[0]
        self.assertEqual(result.contribution(SignalName.SAME_DAY_ATTEMPTS).transformed_value, 2)
        self.assertEqual(result.raw_total, 15)

    def test_fsrs_present_and_absent_are_both_supported(self) -> None:
        available = card(
            "1", "1",
            scheduling=SchedulingSignals(
                retrievability=Observation.available(0.2, P),
                difficulty=Observation.available(8.0, P),
                stability_days=Observation.available(1.0, P),
            ),
        )
        unavailable = card("2", "2")
        preset = ScoringPreset(
            "fsrs", "FSRS", SettingsMode.ADVANCED, Normalization.NONE,
            {
                SignalName.LOW_RETRIEVABILITY: SignalRule(True, 10),
                SignalName.FSRS_DIFFICULTY: SignalRule(True, 10),
                SignalName.LOW_STABILITY: SignalRule(True, 10),
            },
        )
        with_fsrs, without_fsrs = score_cards([available, unavailable], preset)
        self.assertAlmostEqual(with_fsrs.raw_total, 21)
        self.assertEqual(without_fsrs.raw_total, 0)
        self.assertTrue(all(
            item.status is ContributionStatus.UNAVAILABLE
            for item in without_fsrs.contributions
            if item.signal in preset.rules
        ))

    def test_duplicate_and_sibling_penalties_use_separate_identities(self) -> None:
        cards = [
            card("1", "10", "Same"),
            card("2", "10", "same"),
            card("3", "30", "same"),
        ]
        preset = ScoringPreset(
            "dedupe", "Dedupe", SettingsMode.ADVANCED, Normalization.NONE,
            {
                SignalName.DUPLICATE_TARGET: SignalRule(True, -3),
                SignalName.SIBLING_CARD: SignalRule(True, -5),
            },
        )
        results = score_cards(cards, preset)
        self.assertEqual(results[0].contribution(SignalName.DUPLICATE_TARGET).raw_value, 2)
        self.assertEqual(results[0].contribution(SignalName.SIBLING_CARD).raw_value, 1)
        self.assertEqual(results[0].raw_total, -11)
        self.assertEqual(results[2].contribution(SignalName.SIBLING_CARD).raw_value, 0)

    def test_recent_reuse_penalty_decays_with_age(self) -> None:
        recent = card("1", "1", days_since_last_article_use=Observation.available(0.0, Provenance.LOCAL_HISTORY))
        old = card("2", "2", days_since_last_article_use=Observation.available(14.0, Provenance.LOCAL_HISTORY))
        preset = one_rule(
            SignalName.RECENT_REUSE,
            SignalRule(True, -20, decay=DecayConfig(True, 14)),
        )
        recent_result, old_result = score_cards([recent, old], preset)
        self.assertEqual(recent_result.raw_total, -20)
        self.assertAlmostEqual(old_result.raw_total, -10)

    def test_card_state_and_clamped_normalization(self) -> None:
        subject = card(
            scheduling=SchedulingSignals(
                state=Observation.available(CardState.RELEARNING, P)
            )
        )
        result = score_cards(
            [subject],
            one_rule(SignalName.CARD_STATE, SignalRule(True, 150), Normalization.CLAMP_0_100),
        )[0]
        self.assertEqual(result.raw_total, 150)
        self.assertEqual(result.total, 100)

    def test_min_max_normalizes_across_candidates_without_fake_signal_values(self) -> None:
        low = card("1", "1", same_day_attempts=Observation.available(1, P))
        high = card("2", "2", same_day_attempts=Observation.available(3, P))
        preset = one_rule(
            SignalName.SAME_DAY_ATTEMPTS,
            SignalRule(True, 1),
            Normalization.MIN_MAX_0_100,
        )
        results = score_cards([low, high], preset)
        self.assertEqual([result.total for result in results], [0, 100])
        equal = score_cards([low, dataclasses.replace(low, identity=CardIdentity("anki", "3", "3"))], preset)
        self.assertEqual([result.total for result in equal], [0, 0])

    def test_recommended_preset_round_trips_and_rejects_unsafe_values(self) -> None:
        preset = recommended_preset()
        restored = import_preset(export_preset(preset))
        self.assertEqual(restored.to_dict(), preset.to_dict())
        self.assertEqual(restored.selection.maximum_selected_cards, 20)
        self.assertTrue(restored.rules[SignalName.AGAIN_COUNT].enabled)
        with self.assertRaises(ValueError):
            import_preset('{"schemaVersion":1,"id":"x","name":"x","rules":{"unknown":{}}}')
        with self.assertRaises(ValueError):
            SignalRule(True, float("nan"))

    def test_simple_metadata_is_a_documented_subset_of_advanced(self) -> None:
        simple = signal_metadata(SettingsMode.SIMPLE)
        advanced = signal_metadata(SettingsMode.ADVANCED)
        self.assertLess(len(simple), len(advanced))
        self.assertTrue(set(simple).issubset(set(advanced)))
        self.assertIn(SignalName.AGAIN_COUNT, {item.name for item in simple})

    def test_score_serialization_exposes_breakdown_without_adapter_objects(self) -> None:
        subject = card(same_day_attempts=Observation.available(2, P))
        result = score_cards(
            [subject], one_rule(SignalName.SAME_DAY_ATTEMPTS, SignalRule(True, 2))
        )[0].to_dict()
        self.assertEqual(result["cardId"], "anki:1")
        attempts = next(
            item for item in result["contributions"]
            if item["signal"] == "same_day_attempts"
        )
        self.assertEqual(attempts["status"], "applied")

    def test_duplicate_source_scoped_cards_are_rejected_before_context_counts(self) -> None:
        subject = card()
        with self.assertRaises(ValueError):
            score_cards([subject, subject], recommended_preset())

    def test_selection_default_validation(self) -> None:
        with self.assertRaises(ValueError):
            SelectionDefaults(maximum_selected_cards=2, required_target_count=2, preferred_target_count=1)
        with self.assertRaises(ValueError):
            SelectionDefaults(maximum_selected_cards=True)


if __name__ == "__main__":
    unittest.main()
