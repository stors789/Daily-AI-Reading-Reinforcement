"""Focused contract tests for normalized standalone/add-on Anki evidence."""

from __future__ import annotations

import sqlite3
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
for path in (
    ROOT / "packages" / "dairr_core" / "src",
    ROOT / "desktop_mock",
    ROOT / "addon" / "daily_ai_reading_reinforcement",
):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from dairr_core.capabilities import (  # noqa: E402
    CapabilityId,
    CapabilityReason,
    CapabilityStatus,
    Provenance,
)
from dairr_core.study_signals import CardState, ReviewGrade  # noqa: E402
from ankiconnect_data_adapter import AnkiConnectDataAdapter  # noqa: E402
from ankiconnect_provider import (  # noqa: E402
    AnkiConnectError,
    AnkiConnectFailure,
)
from anki_data_adapter import AnkiAddonDataAdapter, AnkiAddonUnavailable  # noqa: E402


class _DesktopProvider:
    def __init__(self, *, review_error: AnkiConnectError | None = None) -> None:
        self.review_error = review_error
        self.actions: list[str] = []

    def api_version(self) -> int:
        return 6

    def _today_card_sets(self):
        return [101, 102], {ease: set() for ease in range(1, 5)}, set()

    def _invoke(self, action, params=None):
        self.actions.append(action)
        if action == "cardsInfo":
            return [
                {
                    "cardId": 101,
                    "note": 500,
                    "deckName": "Words",
                    "fields": {"Front": {"value": "alpha"}},
                    "type": 2,
                    "queue": 2,
                    "reps": 99,
                    "lapses": 4,
                },
                {
                    "cardId": 102,
                    "note": 500,
                    "deckName": "Words",
                    "fields": {"Front": {"value": "beta"}},
                    "type": 3,
                    "queue": 1,
                    "reps": 7,
                },
            ]
        if action == "getReviewsOfCards":
            if self.review_error is not None:
                raise self.review_error
            cards = (params or {}).get("cards", [])
            if not cards:
                return {}
            return {
                "101": [
                    {"id": 900, "ease": 1, "type": 1, "factor": 2500},
                    {"id": 1100, "ease": 1, "type": 1, "factor": 2500},
                    {"id": 1200, "ease": 1, "type": 1, "factor": 2500},
                    {"id": 1300, "ease": 3, "type": 1, "factor": 2500},
                    {"id": 1400, "ease": 0, "type": 4, "factor": 0},
                ],
                102: [{"id": 1500, "ease": 2, "type": 1, "factor": 2500}],
            }
        raise AssertionError(action)


class DesktopNormalizedAdapterTests(unittest.TestCase):
    def test_capabilities_are_unknown_until_explicit_probe(self) -> None:
        adapter = AnkiConnectDataAdapter(_DesktopProvider())  # type: ignore[arg-type]
        self.assertEqual(
            adapter.capabilities().get(CapabilityId.ANKI_CONNECTION).status,
            CapabilityStatus.TEMPORARILY_UNAVAILABLE,
        )

        capabilities = adapter.probe_capabilities(authoritative_day_bounds=True)

        self.assertTrue(capabilities.is_available(CapabilityId.ANKI_CONNECTION))
        self.assertTrue(capabilities.is_available(CapabilityId.REVIEW_HISTORY))

        class Disconnected(_DesktopProvider):
            def api_version(self):
                raise AnkiConnectError(
                    AnkiConnectFailure.CONNECTION_FAILED, action="version"
                )

        unavailable = AnkiConnectDataAdapter(Disconnected()).probe_capabilities()
        self.assertEqual(
            unavailable.get(CapabilityId.ANKI_CONNECTION).status,
            CapabilityStatus.ANKI_DISCONNECTED,
        )
        self.assertEqual(
            unavailable.get(CapabilityId.FSRS_VALUES).reason,
            CapabilityReason.CONNECTION_FAILED,
        )

    def test_without_authoritative_day_bounds_does_not_invent_attempts_or_order(self) -> None:
        provider = _DesktopProvider()
        adapter = AnkiConnectDataAdapter(provider)  # type: ignore[arg-type]

        first, sibling = adapter.collect_today_signals()

        self.assertFalse(first.reviews.is_available)
        self.assertEqual(first.reviews.reason, CapabilityReason.HOST_MODE_LIMITATION)
        self.assertFalse(first.same_day_attempts.is_available)
        self.assertEqual(first.metadata["lifetimeReps"], 99)
        self.assertEqual(first.historical_lapses.value, 4)
        self.assertFalse(first.scheduling.difficulty.is_available)
        self.assertEqual(first.scheduling.difficulty.reason, CapabilityReason.FSRS_NOT_AVAILABLE)
        self.assertEqual(first.scheduling.state.value, CardState.REVIEW)
        self.assertEqual(sibling.scheduling.state.value, CardState.RELEARNING)
        self.assertEqual(first.identity.note_id, sibling.identity.note_id)
        self.assertNotEqual(first.identity.stable_id, sibling.identity.stable_id)
        self.assertNotIn("getReviewsOfCards", provider.actions)

    def test_probed_standard_review_action_preserves_order_and_multiplicity(self) -> None:
        provider = _DesktopProvider()
        adapter = AnkiConnectDataAdapter(provider)  # type: ignore[arg-type]

        first, second = adapter.collect_today_signals(day_start_ms=1000, day_end_ms=2000)

        self.assertEqual(
            [event.grade for event in first.reviews.value],
            [ReviewGrade.AGAIN, ReviewGrade.AGAIN, ReviewGrade.GOOD],
        )
        self.assertEqual([event.reviewed_at_ms for event in first.reviews.value], [1100, 1200, 1300])
        self.assertEqual(first.same_day_attempts.value, 3)
        self.assertEqual(first.recent_lapses.value, 2)
        self.assertEqual(second.same_day_attempts.value, 1)
        capability = adapter.capabilities(authoritative_day_bounds=True).get(
            CapabilityId.REVIEW_HISTORY
        )
        self.assertTrue(capability.available)
        self.assertEqual(capability.provenance, Provenance.ANKICONNECT_STANDARD)

    def test_optional_review_action_failure_degrades_without_losing_cards(self) -> None:
        provider = _DesktopProvider(
            review_error=AnkiConnectError(
                AnkiConnectFailure.UNSUPPORTED_ACTION,
                action="getReviewsOfCards",
            )
        )
        adapter = AnkiConnectDataAdapter(provider)  # type: ignore[arg-type]

        cards = adapter.collect_today_signals(day_start_ms=1000, day_end_ms=2000)

        self.assertEqual(len(cards), 2)
        self.assertTrue(all(not card.reviews.is_available for card in cards))
        self.assertTrue(all(
            card.reviews.reason is CapabilityReason.UNSUPPORTED_ACTION for card in cards
        ))
        capability = adapter.capabilities(authoritative_day_bounds=True).get(
            CapabilityId.REVIEW_HISTORY
        )
        self.assertEqual(capability.status, CapabilityStatus.DATA_ABSENT)
        self.assertEqual(capability.reason, CapabilityReason.UNSUPPORTED_ACTION)


class _Db:
    def __init__(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.connection.executescript(
            """
            create table cards (id integer primary key, did integer, odid integer);
            create table revlog (
                id integer primary key,
                cid integer,
                ease integer,
                factor integer,
                type integer
            );
            """
        )

    def all(self, sql, *args):
        return self.connection.execute(sql, args).fetchall()


class _Note:
    def __init__(self, note_id: int, term: str) -> None:
        self.id = note_id
        self._term = term

    def items(self):
        return [("Front", self._term), ("Back", "meaning")]


class _Card:
    def __init__(self, card_id: int, note_id: int, term: str) -> None:
        self.id = card_id
        self._note = _Note(note_id, term)
        self.type = 2
        self.queue = 2
        self.due = 8
        self.reps = 20 + card_id
        self.lapses = 3

    def note(self):
        return self._note


class _Sched:
    today = 10


class _Collection:
    def __init__(self) -> None:
        self.db = _Db()
        self.sched = _Sched()
        self.cards = {
            1: _Card(1, 77, "alpha"),
            2: _Card(2, 77, "beta"),
        }
        self.db.connection.executemany("insert into cards values (?, ?, ?)", [(1, 10, 0), (2, 10, 0)])
        self.db.connection.executemany(
            "insert into revlog values (?, ?, ?, ?, ?)",
            [
                (1100, 1, 1, 2500, 1),
                (1200, 2, 2, 2500, 1),
                (1300, 1, 1, 2500, 1),
                (1400, 1, 3, 2500, 1),
                (1500, 2, 0, 0, 4),
            ],
        )

    def get_card(self, card_id):
        return self.cards.get(card_id)


class AddonNormalizedAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.collection = _Collection()

    def tearDown(self) -> None:
        self.collection.db.connection.close()

    def test_addon_preserves_order_repeats_card_identity_and_supported_fields(self) -> None:
        adapter = AnkiAddonDataAdapter(
            lambda: self.collection,
            fsrs_extractor=lambda _collection, card: (
                {"retrievability": 0.4, "difficulty": 8, "stability_days": 3}
                if card.id == 1
                else None
            ),
        )

        first, sibling = adapter.collect_today_signals(1000, 2000)

        self.assertEqual([event.grade for event in first.reviews.value], [1, 1, 3])
        self.assertEqual([event.reviewed_at_ms for event in first.reviews.value], [1100, 1300, 1400])
        self.assertEqual(first.same_day_attempts.value, 3)
        self.assertEqual(first.recent_lapses.value, 2)
        self.assertEqual(first.historical_lapses.value, 3)
        self.assertEqual(first.scheduling.overdue_days.value, 2.0)
        self.assertEqual(first.scheduling.difficulty.value, 8.0)
        self.assertFalse(sibling.scheduling.difficulty.is_available)
        self.assertEqual(first.identity.note_id, sibling.identity.note_id)
        self.assertNotEqual(first.identity.stable_id, sibling.identity.stable_id)
        self.assertEqual(first.metadata["lifetimeReps"], 21)
        self.assertTrue(adapter.capabilities().is_available(CapabilityId.FSRS_VALUES))

    def test_profile_closure_and_cancellation_are_safe(self) -> None:
        closed = AnkiAddonDataAdapter(lambda: None)
        with self.assertRaises(AnkiAddonUnavailable) as closed_error:
            closed.collect_today_signals(1000, 2000)
        self.assertEqual(closed_error.exception.reason, CapabilityReason.PROFILE_CLOSED)
        self.assertEqual(
            closed.capabilities().get(CapabilityId.ANKI_CONNECTION).status,
            CapabilityStatus.TEMPORARILY_UNAVAILABLE,
        )

        cancelled = AnkiAddonDataAdapter(lambda: self.collection, cancelled=lambda: True)
        with self.assertRaises(AnkiAddonUnavailable) as cancel_error:
            cancelled.collect_today_signals(1000, 2000)
        self.assertEqual(cancel_error.exception.reason, CapabilityReason.OPERATION_CANCELLED)

        calls = iter((self.collection, None))
        unloaded = AnkiAddonDataAdapter(lambda: next(calls, None))
        with self.assertRaises(AnkiAddonUnavailable) as unload_error:
            unloaded.collect_today_signals(1000, 2000)
        self.assertEqual(unload_error.exception.reason, CapabilityReason.PROFILE_CLOSED)

    def test_fsrs_extractor_failure_only_disables_optional_evidence(self) -> None:
        def unavailable_fsrs(_collection, _card):
            raise AttributeError("API not available")

        adapter = AnkiAddonDataAdapter(
            lambda: self.collection,
            fsrs_extractor=unavailable_fsrs,
        )

        cards = adapter.collect_today_signals(1000, 2000)

        self.assertEqual(len(cards), 2)
        self.assertTrue(all(not card.scheduling.difficulty.is_available for card in cards))
        self.assertEqual(
            adapter.capabilities().get(CapabilityId.FSRS_VALUES).reason,
            CapabilityReason.FSRS_NOT_AVAILABLE,
        )

        non_finite = AnkiAddonDataAdapter(
            lambda: self.collection,
            fsrs_extractor=lambda _collection, _card: {"difficulty": float("nan")},
        )
        self.assertTrue(all(
            not card.scheduling.difficulty.is_available
            for card in non_finite.collect_today_signals(1000, 2000)
        ))


if __name__ == "__main__":
    unittest.main()
