"""Desktop adapters from legacy deck providers to ``dairr_core`` contracts."""

from __future__ import annotations

from typing import Any

from dairr_core_runtime import enable_dairr_core_imports

enable_dairr_core_imports()

from dairr_core.learning_sources import (
    LearningSourceDescriptor,
    SourceCapability,
    SourceScopedId,
    StudyCardSnapshot,
    StudyDeckSnapshot,
)


class LegacyDeckProviderSource:
    """Normalizes the current desktop providers without changing their API.

    This is intentionally a thin edge adapter.  AnkiConnect, MoMo, and the
    local demo provider can continue to own their transport details while all
    callers above this layer work with source-scoped IDs and typed snapshots.
    """

    def __init__(
        self,
        descriptor: LearningSourceDescriptor,
        provider: Any,
    ) -> None:
        self._descriptor = descriptor
        self._provider = provider

    @property
    def descriptor(self) -> LearningSourceDescriptor:
        return self._descriptor

    @property
    def provider(self) -> Any:
        """Underlying edge provider for shell-only operations such as saving."""
        return self._provider

    def list_today_decks(self) -> list[StudyDeckSnapshot]:
        rows = self._provider.get_today_decks()
        if not isinstance(rows, list):
            return []
        return [self._deck_from_row(row) for row in rows if isinstance(row, dict)]

    def get_deck(self, deck_id: SourceScopedId) -> StudyDeckSnapshot:
        if deck_id.source_id != self.descriptor.id:
            raise ValueError("deck id belongs to a different learning source")
        payload = self._provider.get_deck_cards(deck_id.local_id)
        if not isinstance(payload, dict):
            payload = {}
        return self._deck_from_payload(deck_id, payload)

    def _deck_from_row(self, row: dict[str, Any]) -> StudyDeckSnapshot:
        local_id = str(row.get("id") or "")
        return StudyDeckSnapshot(
            id=SourceScopedId(self.descriptor.id, local_id),
            name=str(row.get("name") or ""),
            new_count=_nonnegative_int(row.get("newCount")),
            failed_count=_nonnegative_int(row.get("failedCount")),
            total_count=_nonnegative_int(row.get("totalCount")),
            is_group=bool(row.get("isGroup")),
        )

    def _deck_from_payload(
        self,
        deck_id: SourceScopedId,
        payload: dict[str, Any],
    ) -> StudyDeckSnapshot:
        raw_cards = payload.get("cards")
        if not isinstance(raw_cards, list):
            raw_cards = []
        cards = tuple(
            self._card_from_payload(deck_id.source_id, card)
            for card in raw_cards
            if isinstance(card, dict)
        )
        selected_fields = payload.get("selectedFields") or payload.get("fields") or []
        return StudyDeckSnapshot(
            id=deck_id,
            name=str(payload.get("name") or ""),
            cards=cards,
            total_count=len(cards),
            new_count=sum(1 for card in cards if card.is_new),
            failed_count=sum(1 for card in cards if card.is_failed),
            selected_fields=tuple(str(field) for field in selected_fields if str(field)),
        )

    def _card_from_payload(self, source_id: str, card: dict[str, Any]) -> StudyCardSnapshot:
        local_id = str(card.get("cid") or "")
        fields = card.get("fields") if isinstance(card.get("fields"), dict) else {}
        metadata = {
            str(key): value
            for key, value in card.items()
            if key not in {"cid", "nid", "term", "fields", "is_new", "is_failed", "review_count"}
        }
        return StudyCardSnapshot(
            id=SourceScopedId(source_id, local_id),
            note_id=str(card.get("nid") or ""),
            term=str(card.get("term") or ""),
            fields={str(key): str(value) for key, value in fields.items()},
            is_new=bool(card.get("is_new")),
            is_failed=bool(card.get("is_failed")),
            review_count=_optional_int(card.get("review_count")),
            metadata=metadata,
        )


def source_descriptor(
    source_id: str,
    name: str,
    *,
    supports_article_card_write: bool = False,
) -> LearningSourceDescriptor:
    capabilities = {
        SourceCapability.READ_TODAY_DECKS,
        SourceCapability.READ_DECK_CARDS,
    }
    if supports_article_card_write:
        capabilities.add(SourceCapability.WRITE_ARTICLE_CARD)
    return LearningSourceDescriptor(source_id, name, frozenset(capabilities))


def _nonnegative_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
