"""Versioned contracts for DAIRR learning sources.

The contract deliberately describes *learning data*, not an individual
service's API.  A desktop, add-on, or mobile host can therefore adapt Anki,
MoMo, an import file, or a future service without exposing provider-specific
identifiers to the shared UI and generation pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Protocol, runtime_checkable
from urllib.parse import quote, unquote


LEARNING_SOURCE_CONTRACT_VERSION = "v1"
_SCOPED_ID_PREFIX = f"dairr:{LEARNING_SOURCE_CONTRACT_VERSION}:"


class SourceCapability(str, Enum):
    """Operations a source can reliably provide to a DAIRR host."""

    READ_TODAY_DECKS = "read_today_decks"
    READ_DECK_CARDS = "read_deck_cards"
    WRITE_ARTICLE_CARD = "write_article_card"
    OFFLINE_CACHE = "offline_cache"


@dataclass(frozen=True, slots=True)
class SourceScopedId:
    """An opaque identifier whose local component belongs to one source."""

    source_id: str
    local_id: str

    def __post_init__(self) -> None:
        if not self.source_id.strip() or not self.local_id:
            raise ValueError("source_id and local_id are required")

    def encode(self) -> str:
        return _SCOPED_ID_PREFIX + quote(self.source_id, safe="") + ":" + quote(self.local_id, safe="")

    @classmethod
    def parse(cls, value: str) -> "SourceScopedId":
        if not isinstance(value, str) or not value.startswith(_SCOPED_ID_PREFIX):
            raise ValueError("not a DAIRR source-scoped id")
        encoded = value[len(_SCOPED_ID_PREFIX):]
        source, separator, local = encoded.partition(":")
        if not separator:
            raise ValueError("malformed DAIRR source-scoped id")
        return cls(unquote(source), unquote(local))


@dataclass(frozen=True, slots=True)
class LearningSourceDescriptor:
    """Stable, safe-to-display metadata for a configured learning source."""

    id: str
    name: str
    capabilities: frozenset[SourceCapability] = field(default_factory=frozenset)
    contract_version: str = LEARNING_SOURCE_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.name.strip():
            raise ValueError("learning source id and name are required")

    def to_bridge_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "contractVersion": self.contract_version,
            "capabilities": sorted(capability.value for capability in self.capabilities),
        }


@dataclass(frozen=True, slots=True)
class StudyCardSnapshot:
    """Normalized card data used by filtering and article generation."""

    id: SourceScopedId
    term: str
    fields: Mapping[str, str] = field(default_factory=dict)
    note_id: str = ""
    is_new: bool = False
    is_failed: bool = False
    review_count: int | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_bridge_dict(self) -> dict[str, Any]:
        payload = {
            "cid": self.id.encode(),
            "nid": self.note_id,
            "term": self.term,
            "fields": dict(self.fields),
            "is_new": self.is_new,
            "is_failed": self.is_failed,
        }
        if self.review_count is not None:
            payload["review_count"] = self.review_count
        payload.update(dict(self.metadata))
        return payload


@dataclass(frozen=True, slots=True)
class StudyDeckSnapshot:
    """A source-scoped deck plus its current, normalized card snapshot."""

    id: SourceScopedId
    name: str
    cards: tuple[StudyCardSnapshot, ...] = ()
    new_count: int = 0
    failed_count: int = 0
    total_count: int = 0
    is_group: bool = False
    selected_fields: tuple[str, ...] = ()

    def to_bridge_row(self) -> dict[str, Any]:
        return {
            "id": self.id.encode(),
            "name": self.name,
            "newCount": self.new_count,
            "failedCount": self.failed_count,
            "totalCount": self.total_count,
            "isGroup": self.is_group,
        }

    def to_bridge_cards(self) -> dict[str, Any]:
        cards = [card.to_bridge_dict() for card in self.cards]
        fields = list(self.selected_fields)
        if not fields:
            fields = _field_names(cards)
        return {
            "deckId": self.id.encode(),
            "name": self.name,
            "cards": cards,
            "fields": fields,
            "selectedFields": list(self.selected_fields) or list(fields),
        }


@runtime_checkable
class LearningSource(Protocol):
    """Platform-neutral source contract implemented by shell adapters."""

    @property
    def descriptor(self) -> LearningSourceDescriptor: ...

    def list_today_decks(self) -> list[StudyDeckSnapshot]: ...

    def get_deck(self, deck_id: SourceScopedId) -> StudyDeckSnapshot: ...


class LearningSourceRegistry:
    """Routes opaque deck ids to the registered source that owns them."""

    def __init__(self, sources: tuple[LearningSource, ...] | list[LearningSource] = ()) -> None:
        self._sources: dict[str, LearningSource] = {}
        for source in sources:
            self.register(source)

    def register(self, source: LearningSource) -> None:
        source_id = source.descriptor.id
        if source_id in self._sources:
            raise ValueError(f"learning source is already registered: {source_id}")
        self._sources[source_id] = source

    def descriptors(self) -> list[LearningSourceDescriptor]:
        return [source.descriptor for source in self._sources.values()]

    def get(self, source_id: str) -> LearningSource:
        try:
            return self._sources[source_id]
        except KeyError as exc:
            raise KeyError(f"unknown learning source: {source_id}") from exc

    def resolve_deck(self, encoded_deck_id: str) -> tuple[LearningSource, SourceScopedId]:
        deck_id = SourceScopedId.parse(encoded_deck_id)
        return self.get(deck_id.source_id), deck_id


def _field_names(cards: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    names: list[str] = []
    for card in cards:
        for name, value in (card.get("fields") or {}).items():
            if name not in seen and value:
                seen.add(name)
                names.append(str(name))
    return names
