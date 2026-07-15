"""Normalized study signals from the public AnkiConnect API.

The adapter deliberately keeps the legacy deck payload separate.  In
particular, ``cardsInfo.reps`` is a lifetime repetition counter and is never
substituted for today's attempt count.  Ordered current-day events are only
published when the standard ``getReviewsOfCards`` action is present *and* the
caller supplies Anki-day bounds obtained from an authoritative source.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

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
    from ankiconnect_provider import (
        ANKICONNECT_VERSION,
        AnkiConnectDeckProvider,
        AnkiConnectError,
        AnkiConnectFailure,
        _as_int,
        _extract_fields,
        _first_meaningful_field,
        _clean_text,
    )
except ImportError:  # pragma: no cover - package-style import
    from .ankiconnect_provider import (
        ANKICONNECT_VERSION,
        AnkiConnectDeckProvider,
        AnkiConnectError,
        AnkiConnectFailure,
        _as_int,
        _extract_fields,
        _first_meaningful_field,
        _clean_text,
    )


SOURCE_ID = "ankiconnect"


@dataclass(frozen=True, slots=True)
class AdapterIssue:
    """Safe diagnostic metadata; it never contains response bodies."""

    reason: CapabilityReason
    action: str
    detail: str


class AnkiConnectDataAdapter:
    """Convert public AnkiConnect actions into shared scoring evidence."""

    def __init__(self, provider: AnkiConnectDeckProvider) -> None:
        self._provider = provider
        self._review_action_supported: bool | None = None
        self._issues: list[AdapterIssue] = []
        self._connection_reason = CapabilityReason.UNKNOWN
        self._connection_probed = False
        self._review_reason = CapabilityReason.MISSING_FIELD

    @property
    def issues(self) -> tuple[AdapterIssue, ...]:
        return tuple(self._issues)

    def capabilities(self, *, authoritative_day_bounds: bool = False) -> CapabilitySet:
        connected = self._connection_probed and self._connection_reason is CapabilityReason.NONE
        connection_status = (
            CapabilityStatus.AVAILABLE
            if connected
            else (
                CapabilityStatus.ANKI_DISCONNECTED
                if self._connection_probed
                else CapabilityStatus.TEMPORARILY_UNAVAILABLE
            )
        )
        review_available = bool(
            connected
            and authoritative_day_bounds
            and self._review_action_supported
            and self._review_reason is CapabilityReason.NONE
        )
        if connected:
            review_status = (
                CapabilityStatus.AVAILABLE
                if review_available
                else CapabilityStatus.DATA_ABSENT
            )
            review_reason = (
                CapabilityReason.NONE if review_available else self._review_reason
            )
            fsrs_status = CapabilityStatus.DATA_ABSENT
            fsrs_reason = CapabilityReason.FSRS_NOT_AVAILABLE
        else:
            review_status = connection_status
            review_reason = self._connection_reason
            fsrs_status = connection_status
            fsrs_reason = self._connection_reason
        return CapabilitySet(
            (
                Capability(
                    CapabilityId.ANKI_CONNECTION,
                    connection_status,
                    CapabilityReason.NONE if connected else self._connection_reason,
                    Provenance.ANKICONNECT_STANDARD,
                    "Standard AnkiConnect API v6 or newer." if connected else "",
                ),
                Capability(
                    CapabilityId.INTERNAL_ANKI_APIS,
                    CapabilityStatus.UNAVAILABLE_IN_MODE,
                    CapabilityReason.HOST_MODE_LIMITATION,
                    Provenance.ANKICONNECT_STANDARD,
                    "Standalone mode never imports Anki internals.",
                ),
                Capability(
                    CapabilityId.REVIEW_HISTORY,
                    review_status,
                    review_reason,
                    Provenance.ANKICONNECT_STANDARD,
                    (
                        "Ordered current-day rows from getReviewsOfCards."
                        if review_available
                        else "Ordered rows require getReviewsOfCards and authoritative Anki-day bounds."
                    ),
                ),
                Capability(
                    CapabilityId.FSRS_VALUES,
                    fsrs_status,
                    fsrs_reason,
                    Provenance.ANKICONNECT_STANDARD,
                    "cardsInfo does not expose normalized FSRS memory-state values.",
                ),
                Capability(
                    CapabilityId.TARGET_CARD_SCORING,
                    connection_status,
                    CapabilityReason.NONE if connected else self._connection_reason,
                    Provenance.ANKICONNECT_STANDARD,
                    "Available signals continue to score when review history or FSRS is absent.",
                ),
                Capability(
                    CapabilityId.CANCELLATION,
                    CapabilityStatus.AVAILABLE,
                    CapabilityReason.NONE,
                    Provenance.ANKICONNECT_STANDARD,
                    "Cancellation is checked before and after each HTTP request.",
                ),
            )
        )

    def probe_capabilities(
        self, *, authoritative_day_bounds: bool = False
    ) -> CapabilitySet:
        """Probe standard actions without fetching or retaining card content."""

        self._issues.clear()
        try:
            self._provider.api_version()
            self._connection_reason = CapabilityReason.NONE
            self._connection_probed = True
            if authoritative_day_bounds:
                self._review_action_supported = None
                self._probe_review_action()
                if self._review_action_supported:
                    self._review_reason = CapabilityReason.NONE
        except AnkiConnectError as exc:
            self._connection_reason = _capability_reason(exc.failure)
            self._connection_probed = True
            self._issues.append(
                AdapterIssue(self._connection_reason, exc.action, "AnkiConnect capability probe failed.")
            )
        return self.capabilities(authoritative_day_bounds=authoritative_day_bounds)

    def collect_today_signals(
        self,
        *,
        day_start_ms: int | None = None,
        day_end_ms: int | None = None,
    ) -> list[CardStudySignals]:
        """Fetch today's cards and normalize only evidence the host can prove."""

        self._issues.clear()
        self._connection_reason = CapabilityReason.NONE
        self._connection_probed = False
        self._review_reason = CapabilityReason.MISSING_FIELD
        bounds_valid = _valid_bounds(day_start_ms, day_end_ms)
        try:
            version = self._provider.api_version()
            if version < ANKICONNECT_VERSION:  # defensive; provider already checks
                raise AnkiConnectError(AnkiConnectFailure.INCOMPATIBLE_VERSION)
            today_ids, _grade_ids, _introduced_ids = self._provider._today_card_sets()
            raw_infos = self._provider._invoke("cardsInfo", {"cards": today_ids}) if today_ids else []
            if not isinstance(raw_infos, list):
                raise AnkiConnectError(
                    AnkiConnectFailure.MALFORMED_RESPONSE, action="cardsInfo"
                )
            self._connection_probed = True
        except AnkiConnectError as exc:
            self._connection_reason = _capability_reason(exc.failure)
            self._connection_probed = True
            self._issues.append(
                AdapterIssue(self._connection_reason, exc.action, "Required AnkiConnect action failed.")
            )
            raise

        info_by_card: dict[int, Mapping[str, Any]] = {}
        for item in raw_infos:
            if not isinstance(item, Mapping):
                self._record_partial("cardsInfo", "Ignored a non-object card row.")
                continue
            card_id = _as_int(item.get("cardId") or item.get("card_id"))
            if card_id is None:
                self._record_partial("cardsInfo", "Ignored a card row without cardId.")
                continue
            info_by_card[card_id] = item
        missing_ids = set(today_ids).difference(info_by_card)
        if missing_ids:
            self._record_partial("cardsInfo", "Some requested cards were unavailable.")

        review_rows: dict[int, tuple[ReviewEvent, ...]] | None = None
        if bounds_valid and today_ids:
            review_rows = self._fetch_bounded_reviews(
                today_ids, int(day_start_ms), int(day_end_ms)
            )
        elif bounds_valid:
            # No candidates still proves an empty current-day review set.
            self._review_action_supported = self._probe_review_action()
            if self._review_action_supported:
                review_rows = {}
                self._review_reason = CapabilityReason.NONE
        else:
            self._review_reason = CapabilityReason.HOST_MODE_LIMITATION

        signals: list[CardStudySignals] = []
        for card_id in today_ids:
            info = info_by_card.get(card_id)
            if info is None:
                continue
            signal = self._signal_from_info(info, review_rows)
            if signal is not None:
                signals.append(signal)
        return signals

    def _probe_review_action(self) -> bool:
        if self._review_action_supported is not None:
            return self._review_action_supported
        try:
            result = self._provider._invoke("getReviewsOfCards", {"cards": []})
            self._review_action_supported = isinstance(result, Mapping)
            if not self._review_action_supported:
                self._review_reason = CapabilityReason.PARTIAL_RESPONSE
        except AnkiConnectError as exc:
            if exc.failure is AnkiConnectFailure.CANCELLED:
                raise
            self._review_action_supported = False
            self._review_reason = _capability_reason(exc.failure)
            self._issues.append(
                AdapterIssue(
                    self._review_reason,
                    "getReviewsOfCards",
                    "Optional standard review-history action is unavailable.",
                )
            )
        return bool(self._review_action_supported)

    def _fetch_bounded_reviews(
        self, card_ids: list[int], start_ms: int, end_ms: int
    ) -> dict[int, tuple[ReviewEvent, ...]] | None:
        if not self._probe_review_action():
            return None
        try:
            payload = self._provider._invoke("getReviewsOfCards", {"cards": card_ids})
        except AnkiConnectError as exc:
            if exc.failure is AnkiConnectFailure.CANCELLED:
                raise
            self._review_reason = _capability_reason(exc.failure)
            self._issues.append(
                AdapterIssue(self._review_reason, "getReviewsOfCards", "Review history was unavailable.")
            )
            return None
        if not isinstance(payload, Mapping):
            self._review_reason = CapabilityReason.PARTIAL_RESPONSE
            self._record_partial("getReviewsOfCards", "Review history was not an object.")
            return None

        result: dict[int, tuple[ReviewEvent, ...]] = {}
        partial = False
        for card_id in card_ids:
            raw_rows = payload.get(str(card_id), payload.get(card_id))
            if not isinstance(raw_rows, list):
                partial = True
                continue
            parsed: list[tuple[int, ReviewGrade]] = []
            for row in raw_rows:
                if not isinstance(row, Mapping):
                    partial = True
                    continue
                row_id = _as_int(row.get("id"))
                ease = _as_int(row.get("ease"))
                review_type = _as_int(row.get("type"))
                factor = _as_int(row.get("factor"))
                if row_id is None or ease is None:
                    partial = True
                    continue
                if not start_ms <= row_id < end_ms:
                    continue
                if not 1 <= ease <= 4:
                    continue
                if review_type is not None and review_type >= 3 and not factor:
                    continue
                parsed.append((row_id, ReviewGrade(ease)))
            parsed.sort(key=lambda row: row[0])
            # Revlog IDs are timestamps and unique collection-wide. Duplicate
            # IDs indicate malformed evidence, so do not fabricate an order.
            if len({row_id for row_id, _grade in parsed}) != len(parsed):
                partial = True
                continue
            result[card_id] = tuple(
                ReviewEvent(grade, sequence, reviewed_at_ms=row_id)
                for sequence, (row_id, grade) in enumerate(parsed)
            )
        if partial:
            self._review_reason = CapabilityReason.PARTIAL_RESPONSE
            self._record_partial("getReviewsOfCards", "Some review rows were incomplete.")
        else:
            self._review_reason = CapabilityReason.NONE
        return result

    def _signal_from_info(
        self,
        info: Mapping[str, Any],
        review_rows: dict[int, tuple[ReviewEvent, ...]] | None,
    ) -> CardStudySignals | None:
        card_id = _as_int(info.get("cardId") or info.get("card_id"))
        if card_id is None:
            return None
        note_id = _as_int(info.get("note") or info.get("noteId") or info.get("nid"))
        fields = _extract_fields(info.get("fields"))
        term = _clean_text(
            _first_meaningful_field(fields) or info.get("question") or f"Card {card_id}"
        )
        if not term:
            term = f"Card {card_id}"
        events = None if review_rows is None else review_rows.get(card_id)
        reviews = (
            Observation.available(events, Provenance.ANKICONNECT_STANDARD)
            if events is not None
            else Observation.unavailable(self._review_reason, Provenance.ANKICONNECT_STANDARD)
        )
        attempts = (
            Observation.available(len(events), Provenance.ANKICONNECT_STANDARD)
            if events is not None
            else Observation.unavailable(self._review_reason, Provenance.ANKICONNECT_STANDARD)
        )
        recent_lapses = (
            Observation.available(
                sum(event.grade is ReviewGrade.AGAIN for event in events),
                Provenance.ANKICONNECT_STANDARD,
            )
            if events is not None
            else Observation.unavailable(self._review_reason, Provenance.ANKICONNECT_STANDARD)
        )
        lapses = _non_negative_int(info.get("lapses"))
        historical_lapses = (
            Observation.available(lapses, Provenance.ANKICONNECT_STANDARD)
            if lapses is not None
            else Observation.unavailable(
                CapabilityReason.MISSING_FIELD, Provenance.ANKICONNECT_STANDARD
            )
        )
        state = _card_state(info.get("type"), info.get("queue"))
        state_observation = (
            Observation.available(state, Provenance.ANKICONNECT_STANDARD)
            if state is not CardState.UNKNOWN
            else Observation.unavailable(
                CapabilityReason.MISSING_FIELD, Provenance.ANKICONNECT_STANDARD
            )
        )
        unavailable = lambda: Observation.unavailable(
            CapabilityReason.MISSING_FIELD, Provenance.ANKICONNECT_STANDARD
        )
        fsrs_unavailable = lambda: Observation.unavailable(
            CapabilityReason.FSRS_NOT_AVAILABLE, Provenance.ANKICONNECT_STANDARD
        )
        reps = _non_negative_int(info.get("reps"))
        return CardStudySignals(
            identity=CardIdentity(SOURCE_ID, str(card_id), str(note_id or "")),
            term=term,
            normalized_target=term,
            reviews=reviews,
            same_day_attempts=attempts,
            recent_lapses=recent_lapses,
            historical_lapses=historical_lapses,
            scheduling=SchedulingSignals(
                retrievability=fsrs_unavailable(),
                difficulty=fsrs_unavailable(),
                stability_days=fsrs_unavailable(),
                elapsed_days=unavailable(),
                overdue_days=unavailable(),
                state=state_observation,
            ),
            metadata={
                "deckName": str(info.get("deckName") or ""),
                "fields": dict(fields),
                "lifetimeReps": reps,
            },
        )

    def _record_partial(self, action: str, detail: str) -> None:
        self._issues.append(AdapterIssue(CapabilityReason.PARTIAL_RESPONSE, action, detail))


def _valid_bounds(start_ms: int | None, end_ms: int | None) -> bool:
    return (
        isinstance(start_ms, int)
        and not isinstance(start_ms, bool)
        and isinstance(end_ms, int)
        and not isinstance(end_ms, bool)
        and 0 <= start_ms < end_ms
    )


def _non_negative_int(value: Any) -> int | None:
    parsed = _as_int(value)
    return parsed if parsed is not None and parsed >= 0 else None


def _card_state(card_type: Any, queue: Any) -> CardState:
    type_value = _as_int(card_type)
    queue_value = _as_int(queue)
    if type_value == 3:
        return CardState.RELEARNING
    if type_value == 0 or queue_value == 0:
        return CardState.NEW
    if type_value == 1 or queue_value in (1, 3):
        return CardState.LEARNING
    if type_value == 2 or queue_value == 2:
        return CardState.REVIEW
    return CardState.UNKNOWN


def _capability_reason(failure: AnkiConnectFailure) -> CapabilityReason:
    return {
        AnkiConnectFailure.CONNECTION_FAILED: CapabilityReason.CONNECTION_FAILED,
        AnkiConnectFailure.TIMEOUT: CapabilityReason.TIMEOUT,
        AnkiConnectFailure.MALFORMED_RESPONSE: CapabilityReason.PARTIAL_RESPONSE,
        AnkiConnectFailure.UNSUPPORTED_ACTION: CapabilityReason.UNSUPPORTED_ACTION,
        AnkiConnectFailure.INCOMPATIBLE_VERSION: CapabilityReason.UNSUPPORTED_ACTION,
        AnkiConnectFailure.PARTIAL_RESPONSE: CapabilityReason.PARTIAL_RESPONSE,
        AnkiConnectFailure.CANCELLED: CapabilityReason.OPERATION_CANCELLED,
    }[failure]
